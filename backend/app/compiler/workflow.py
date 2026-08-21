import hashlib
import json
import re
import uuid
from collections import defaultdict
from typing import Any

from app.compiler.validator import validate_pipeline
from app.models.pipeline import Pipeline
from app.registry import NODE_TYPES


def _safe_name(value: str) -> str:
    name = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    if not name or not name[0].isalpha():
        name = f"n-{name}"
    if len(name) > 45:
        digest = hashlib.sha1(value.encode()).hexdigest()[:8]
        name = f"{name[:36].rstrip('-')}-{digest}"
    return name


def safe_task_names(node_ids: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    used: set[str] = set()
    for node_id in node_ids:
        candidate = _safe_name(node_id)
        if candidate in used:
            digest = hashlib.sha1(node_id.encode()).hexdigest()[:8]
            candidate = f"{candidate[:45].rstrip('-')}-{digest}"
        while candidate in used:
            candidate = f"{candidate[:52]}-{len(used)}"
        used.add(candidate); result[node_id] = candidate
    return result


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def compile_pipeline(pipeline: Pipeline, run_id: str | None = None) -> dict[str, Any]:
    validation = validate_pipeline(pipeline)
    if not validation.valid:
        raise ValueError(validation.model_dump(mode="json"))
    run_id = run_id or uuid.uuid4().hex[:12]
    mapping = safe_task_names([node.id for node in pipeline.spec.nodes])
    nodes_by_id = {node.id: node for node in pipeline.spec.nodes}
    incoming: dict[str, list[Any]] = defaultdict(list)
    parents: dict[str, set[str]] = defaultdict(set)
    for edge in pipeline.spec.edges:
        incoming[edge.target].append(edge)
        parents[edge.target].add(edge.source)

    inherited_conditions: dict[str, frozenset[str]] = {}

    def branch_conditions(node_id: str) -> frozenset[str]:
        if node_id in inherited_conditions:
            return inherited_conditions[node_id]
        expressions: set[str] = set()
        for edge in incoming[node_id]:
            source_definition = NODE_TYPES[nodes_by_id[edge.source].type]
            condition = source_definition.get("branchConditions", {}).get(edge.sourcePort)
            if condition:
                expressions.add(
                    f"{{{{tasks.{mapping[edge.source]}.outputs.parameters.{condition['output']}}}}} == {condition['value']}"
                )
            else:
                expressions.update(branch_conditions(edge.source))
        if len(expressions) > 1:
            raise ValueError(f"Node '{node_id}' has incompatible branch conditions.")
        inherited_conditions[node_id] = frozenset(expressions)
        return inherited_conditions[node_id]

    dag_tasks: list[dict[str, Any]] = []
    wrappers: list[dict[str, Any]] = []
    for node in pipeline.spec.nodes:
        definition = NODE_TYPES[node.type]
        task_name = mapping[node.id]
        retry_limit = int(node.parameters.get("retryLimit", definition["defaultRetryLimit"]))
        argument_values: dict[str, str] = {
            "node-id": node.id,
            "workflow-name": "{{workflow.name}}",
            "retry-limit": str(retry_limit),
        }
        for param_name, template_param in definition.get("parameterMapping", {}).items():
            argument_values[template_param] = _value(node.parameters[param_name])
        for edge in incoming[node.id]:
            template_input = definition["inputMapping"][edge.targetPort]
            argument_values[template_input] = f"{{{{tasks.{mapping[edge.source]}.outputs.parameters.{edge.sourcePort}}}}}"
        inputs = [{"name": name} for name in argument_values]
        task: dict[str, Any] = {
            "name": task_name,
            "template": f"node-{task_name}",
            "arguments": {"parameters": [{"name": name, "value": value} for name, value in argument_values.items()]},
        }
        if parents[node.id]:
            task["dependencies"] = sorted(mapping[parent] for parent in parents[node.id])
        branch_expressions = branch_conditions(node.id)
        if branch_expressions:
            task["when"] = next(iter(branch_expressions))
        dag_tasks.append(task)

        execute = {
            "name": "execute",
            "templateRef": {"name": definition["workflowTemplateName"], "template": definition["templateName"]},
            "arguments": {"parameters": [{"name": item["name"], "value": f"{{{{inputs.parameters.{item['name']}}}}}"} for item in inputs]},
        }
        wrapper: dict[str, Any] = {
            "name": f"node-{task_name}",
            "inputs": {"parameters": inputs},
            "outputs": {"parameters": [
                {"name": port["name"], "valueFrom": {"parameter": f"{{{{steps.execute.outputs.parameters.{port['name']}}}}}"}}
                for port in [*definition["outputPorts"], *({"name": name} for name in definition.get("internalOutputs", []))]
            ]},
            "steps": [[execute]],
        }
        wrappers.append(wrapper)

    labels = {
        "demo.pipeline.io/project": "pipeline-demo",
        "demo.pipeline.io/pipeline": pipeline.metadata.name[:63],
        "demo.pipeline.io/run-id": run_id,
    }
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Workflow",
        "metadata": {
            "generateName": f"{pipeline.metadata.name[:45].rstrip('-')}-",
            "namespace": "pipeline-demo",
            "labels": labels,
            "annotations": {
                "demo.pipeline.io/node-map": json.dumps(mapping, separators=(",", ":")),
                "demo.pipeline.io/dsl-version": pipeline.apiVersion,
                "demo.pipeline.io/experiment": pipeline.metadata.experimentName,
                "demo.pipeline.io/scenario": pipeline.metadata.scenario,
                "demo.pipeline.io/tags": json.dumps(pipeline.metadata.tags, separators=(",", ":")),
            },
        },
        "spec": {
            "entrypoint": "pipeline",
            "serviceAccountName": "pipeline-demo-workflow",
            "activeDeadlineSeconds": pipeline.spec.runPolicy.timeoutSeconds,
            "arguments": {"parameters": []},
            "templates": [{"name": "pipeline", "dag": {"tasks": dag_tasks}}, *wrappers],
        },
    }

