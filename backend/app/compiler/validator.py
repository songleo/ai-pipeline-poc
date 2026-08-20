import re
from collections import Counter, defaultdict, deque
from typing import Any

from app.models.pipeline import Pipeline, ValidationIssue, ValidationResult
from app.registry import NODE_TYPES


NAME_RE = re.compile(r"^[a-z]([-a-z0-9]*[a-z0-9])?$")


def issue(code: str, message: str, node_id: str | None = None, field: str | None = None) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, nodeId=node_id, field=field)


def _check_value(value: Any, schema: dict[str, Any]) -> str | None:
    expected = schema.get("type")
    ok = {
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
    }.get(expected, True)
    if not ok:
        return f"expected {expected}"
    if "enum" in schema and value not in schema["enum"]:
        return f"must be one of {schema['enum']}"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            return f"must be >= {schema['minimum']}"
        if "maximum" in schema and value > schema["maximum"]:
            return f"must be <= {schema['maximum']}"
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            return f"length must be >= {schema['minLength']}"
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            return f"length must be <= {schema['maxLength']}"
    return None


def validate_pipeline(pipeline: Pipeline) -> ValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    if not NAME_RE.fullmatch(pipeline.metadata.name) or len(pipeline.metadata.name) > 50:
        errors.append(issue("INVALID_NAME", "Pipeline name must be a lowercase DNS-style name up to 50 characters.", field="metadata.name"))

    counts = Counter(node.id for node in pipeline.spec.nodes)
    for node_id, count in counts.items():
        if count > 1:
            errors.append(issue("DUPLICATE_NODE_ID", f"Node ID '{node_id}' appears {count} times.", node_id, "id"))
    nodes = {node.id: node for node in pipeline.spec.nodes}

    for node in pipeline.spec.nodes:
        definition = NODE_TYPES.get(node.type)
        if not definition:
            errors.append(issue("UNKNOWN_NODE_TYPE", f"Unknown node type '{node.type}'.", node.id, "type"))
            continue
        if node.version != definition["version"]:
            errors.append(issue("UNKNOWN_NODE_VERSION", f"Unsupported version '{node.version}' for '{node.type}'.", node.id, "version"))
        schema = definition["parametersSchema"]
        for required in schema.get("required", []):
            if required not in node.parameters:
                errors.append(issue("MISSING_PARAMETER", f"Required parameter '{required}' is missing.", node.id, f"parameters.{required}"))
        properties = schema.get("properties", {})
        for name, value in node.parameters.items():
            if name not in properties:
                errors.append(issue("UNKNOWN_PARAMETER", f"Parameter '{name}' is not allowed.", node.id, f"parameters.{name}"))
                continue
            message = _check_value(value, properties[name])
            if message:
                errors.append(issue("INVALID_PARAMETER", f"Parameter '{name}' {message}.", node.id, f"parameters.{name}"))

    edge_keys: set[tuple[str, str, str, str]] = set()
    incoming: dict[tuple[str, str], int] = Counter()
    participating: set[str] = set()
    adjacency: dict[str, set[str]] = defaultdict(set)
    indegree = {node_id: 0 for node_id in nodes}
    for index, edge in enumerate(pipeline.spec.edges):
        field = f"spec.edges[{index}]"
        key = (edge.source, edge.sourcePort, edge.target, edge.targetPort)
        if key in edge_keys:
            errors.append(issue("DUPLICATE_EDGE", "Duplicate connection.", edge.target, field))
        edge_keys.add(key)
        if edge.source == edge.target:
            errors.append(issue("SELF_CONNECTION", "A node cannot connect to itself.", edge.source, field))
        source_node, target_node = nodes.get(edge.source), nodes.get(edge.target)
        if not source_node:
            errors.append(issue("UNKNOWN_EDGE_NODE", f"Source node '{edge.source}' does not exist.", field=field))
        if not target_node:
            errors.append(issue("UNKNOWN_EDGE_NODE", f"Target node '{edge.target}' does not exist.", field=field))
        if not source_node or not target_node:
            continue
        participating.update((edge.source, edge.target))
        source_def, target_def = NODE_TYPES.get(source_node.type), NODE_TYPES.get(target_node.type)
        if not source_def or not target_def:
            continue
        source_ports = {p["name"]: p for p in source_def["outputPorts"]}
        target_ports = {p["name"]: p for p in target_def["inputPorts"]}
        if edge.sourcePort not in source_ports:
            errors.append(issue("UNKNOWN_SOURCE_PORT", f"Output port '{edge.sourcePort}' does not exist.", edge.source, f"{field}.sourcePort"))
        if edge.targetPort not in target_ports:
            errors.append(issue("UNKNOWN_TARGET_PORT", f"Input port '{edge.targetPort}' does not exist.", edge.target, f"{field}.targetPort"))
        if edge.sourcePort in source_ports and edge.targetPort in target_ports and source_ports[edge.sourcePort]["type"] != target_ports[edge.targetPort]["type"]:
            errors.append(issue("PORT_TYPE_MISMATCH", f"Cannot connect {source_ports[edge.sourcePort]['type']} to {target_ports[edge.targetPort]['type']}.", edge.target, field))
        incoming[(edge.target, edge.targetPort)] += 1
        if edge.target not in adjacency[edge.source]:
            adjacency[edge.source].add(edge.target)
            indegree[edge.target] += 1

    for node in pipeline.spec.nodes:
        definition = NODE_TYPES.get(node.type)
        if not definition:
            continue
        for port_def in definition["inputPorts"]:
            count = incoming[(node.id, port_def["name"])]
            if port_def.get("required", True) and count == 0:
                errors.append(issue("MISSING_REQUIRED_INPUT", f"Required input '{port_def['name']}' has no upstream connection.", node.id, f"inputs.{port_def['name']}"))
            if not port_def.get("multiple", False) and count > 1:
                errors.append(issue("MULTIPLE_INPUT_CONNECTIONS", f"Input '{port_def['name']}' accepts only one connection.", node.id, f"inputs.{port_def['name']}"))

    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft(); visited += 1
        for target in adjacency[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(nodes):
        errors.append(issue("DAG_CYCLE", "Pipeline contains a cycle.", field="spec.edges"))

    if len(nodes) > 1:
        for node_id in nodes.keys() - participating:
            warnings.append(issue("ISOLATED_NODE", "Node is not connected and will execute independently.", node_id, "id"))
    return ValidationResult(valid=not errors, errors=errors, warnings=warnings)
