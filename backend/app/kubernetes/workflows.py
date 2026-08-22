import json
import os
from datetime import datetime
from typing import Any

import requests
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


GROUP, VERSION, PLURAL = "argoproj.io", "v1alpha1", "workflows"
TERMINAL = {"SUCCEEDED", "FAILED", "ERROR", "CANCELLED"}
CONTROL_ANNOTATION = "demo.pipeline.io/node-controls"
CONTROL_STOP = "STOP_REQUESTED"


class NodeControlError(RuntimeError):
    pass


def _node_controls(workflow: dict[str, Any]) -> dict[str, str]:
    raw = workflow.get("metadata", {}).get("annotations", {}).get(CONTROL_ANNOTATION, "{}")
    try:
        controls = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return controls if isinstance(controls, dict) else {}


def map_phase(phase: str | None, message: str = "", shutdown: str | None = None) -> str:
    if shutdown in {"Terminate", "Stop"} or "terminated" in message.lower() or "stopped" in message.lower():
        return "CANCELLED"
    return {
        None: "PENDING", "": "PENDING", "Pending": "PENDING", "Running": "RUNNING",
        "Succeeded": "SUCCEEDED", "Failed": "FAILED", "Error": "ERROR",
        "Skipped": "SKIPPED", "Omitted": "SKIPPED",
    }.get(phase, "ERROR")


def _duration(started: str | None, finished: str | None) -> float | None:
    if not started or not finished:
        return None
    try:
        return (datetime.fromisoformat(finished.replace("Z", "+00:00")) - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()
    except ValueError:
        return None


def _outputs(node: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for parameter in node.get("outputs", {}).get("parameters", []) or []:
        value = parameter.get("value")
        try:
            result[parameter["name"]] = json.loads(value) if isinstance(value, str) else value
        except json.JSONDecodeError:
            result[parameter["name"]] = value
    return result


def _json_annotation(annotations: dict[str, str], key: str, fallback: Any) -> Any:
    try:
        return json.loads(annotations.get(key, ""))
    except (TypeError, json.JSONDecodeError):
        return fallback


def _positive_int_annotation(annotations: dict[str, str], key: str) -> int | None:
    try:
        value = int(annotations.get(key, "0"))
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _pod_name_matches(pod_name: str, argo_node_id: str | None) -> bool:
    if not argo_node_id:
        return False
    if pod_name == argo_node_id:
        return True
    return pod_name.endswith(f"-{argo_node_id.rsplit('-', 1)[-1]}")


def workflow_detail(workflow: dict[str, Any]) -> dict[str, Any]:
    metadata, spec, status = workflow.get("metadata", {}), workflow.get("spec", {}), workflow.get("status", {})
    annotations = metadata.get("annotations", {})
    mapping = _json_annotation(annotations, "demo.pipeline.io/node-map", {})
    controls = _node_controls(workflow)
    workflow_status = map_phase(status.get("phase"), status.get("message", ""), spec.get("shutdown"))
    statuses: dict[str, dict[str, Any]] = status.get("nodes", {}) or {}
    result_nodes = []
    for node_id, task_name in mapping.items():
        matches = [(key, value) for key, value in statuses.items() if value.get("displayName") == task_name]
        primary_key, primary = matches[-1] if matches else (None, {})
        pod_matches = [(key, value) for key, value in statuses.items() if value.get("type") == "Pod" and (
            task_name in value.get("name", "") or value.get("boundaryID") == primary_key
        )]
        pod_name = (pod_matches[-1][1].get("id") or pod_matches[-1][0]) if pod_matches else None
        node_status = map_phase(primary.get("phase"), primary.get("message", ""), spec.get("shutdown"))
        control_state = controls.get(node_id)
        if control_state == CONTROL_STOP and node_status in {"FAILED", "ERROR"}:
            node_status = "CANCELLED"
        elif node_status not in {"PENDING", "RUNNING"}:
            control_state = None
        result_nodes.append({
            "nodeId": node_id, "taskName": task_name,
            "status": node_status,
            "startedAt": primary.get("startedAt"), "finishedAt": primary.get("finishedAt"),
            "duration": _duration(primary.get("startedAt"), primary.get("finishedAt")),
            "message": primary.get("message"), "retryCount": max(0, len(pod_matches) - 1),
            "podName": pod_name, "outputs": _outputs(primary), "controlState": control_state,
            "canStop": node_status in {"PENDING", "RUNNING"} and control_state != CONTROL_STOP,
            "canRerun": workflow_status in TERMINAL and node_status in {"SUCCEEDED", "FAILED", "ERROR", "CANCELLED"},
        })
    return {
        "workflowName": metadata.get("name"),
        "pipelineName": metadata.get("labels", {}).get("demo.pipeline.io/pipeline"),
        "experimentName": annotations.get("demo.pipeline.io/experiment"),
        "scenario": annotations.get("demo.pipeline.io/scenario"),
        "tags": _json_annotation(annotations, "demo.pipeline.io/tags", []),
        "definitionVersion": _positive_int_annotation(annotations, "demo.pipeline.io/pipeline-version"),
        "definitionDigest": annotations.get("demo.pipeline.io/definition-digest"),
        "pipelineDefinition": _json_annotation(annotations, "demo.pipeline.io/definition-snapshot", None),
        "status": workflow_status,
        "startedAt": status.get("startedAt"), "finishedAt": status.get("finishedAt"),
        "message": status.get("message"), "nodes": result_nodes,
    }


class KubernetesWorkflowClient:
    def __init__(self, namespace: str | None = None, argo_url: str | None = None) -> None:
        self.namespace = namespace or os.getenv("PIPELINE_NAMESPACE", "pipeline-demo")
        self.argo_url = (argo_url or os.getenv("ARGO_SERVER_URL", "http://argo-workflows-server.argo.svc:2746")).rstrip("/")
        self.http = requests.Session()
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config(context=os.getenv("KUBERNETES_CONTEXT", "kind-pipeline-demo"))
        self.custom = client.CustomObjectsApi()
        self.core = client.CoreV1Api()

    def create(self, workflow: dict[str, Any]) -> dict[str, Any]:
        return self.custom.create_namespaced_custom_object(GROUP, VERSION, self.namespace, PLURAL, workflow)

    def get(self, name: str) -> dict[str, Any]:
        return self.custom.get_namespaced_custom_object(GROUP, VERSION, self.namespace, PLURAL, name)

    def list(self) -> list[dict[str, Any]]:
        response = self.custom.list_namespaced_custom_object(GROUP, VERSION, self.namespace, PLURAL, label_selector="demo.pipeline.io/project=pipeline-demo")
        return response.get("items", [])

    def stop(self, name: str) -> dict[str, Any]:
        workflow = self.get(name)
        detail = workflow_detail(workflow)
        if detail["status"] in TERMINAL:
            return {"workflowName": name, "status": detail["status"], "message": "Workflow is already terminal."}
        patched = self.custom.patch_namespaced_custom_object(GROUP, VERSION, self.namespace, PLURAL, name, {"spec": {"shutdown": "Terminate"}})
        return {"workflowName": name, "status": map_phase(patched.get("status", {}).get("phase"), shutdown="Terminate"), "message": "Termination requested."}

    def node_control(self, name: str, node_id: str) -> dict[str, str | None]:
        workflow = self.get(name)
        mapping = json.loads(workflow.get("metadata", {}).get("annotations", {}).get("demo.pipeline.io/node-map", "{}"))
        if node_id not in mapping:
            raise KeyError(node_id)
        return {"nodeId": node_id, "controlState": _node_controls(workflow).get(node_id)}

    def stop_node(self, name: str, node_id: str) -> dict[str, str | None]:
        workflow = self.get(name)
        detail = workflow_detail(workflow)
        node = next((item for item in detail["nodes"] if item["nodeId"] == node_id), None)
        if not node:
            raise KeyError(node_id)
        if node["status"] not in {"PENDING", "RUNNING"}:
            raise NodeControlError(f"Node {node_id} is already {node['status']}.")
        controls = _node_controls(workflow)
        controls[node_id] = CONTROL_STOP
        self.custom.patch_namespaced_custom_object(
            GROUP, VERSION, self.namespace, PLURAL, name,
            {"metadata": {"annotations": {CONTROL_ANNOTATION: json.dumps(controls, separators=(",", ":"))}}},
        )
        return {"workflowName": name, "nodeId": node_id, "status": node["status"], "controlState": CONTROL_STOP, "message": "Node stop requested."}

    def rerun_node(self, name: str, node_id: str) -> dict[str, str]:
        workflow = self.get(name)
        detail = workflow_detail(workflow)
        node = next((item for item in detail["nodes"] if item["nodeId"] == node_id), None)
        if not node:
            raise KeyError(node_id)
        if detail["status"] not in TERMINAL:
            raise NodeControlError("Wait for the current workflow to reach a terminal state before rerunning a node.")
        if node["status"] not in {"SUCCEEDED", "FAILED", "ERROR", "CANCELLED"}:
            raise NodeControlError(f"Node {node_id} cannot be rerun from {node['status']}.")
        controls = _node_controls(workflow)
        original_control = controls.pop(node_id, None)
        self.custom.patch_namespaced_custom_object(
            GROUP, VERSION, self.namespace, PLURAL, name,
            {"metadata": {"annotations": {CONTROL_ANNOTATION: json.dumps(controls, separators=(",", ":"))}}},
        )
        task_name = node["taskName"]
        try:
            response = self.http.put(
                f"{self.argo_url}/api/v1/workflows/{self.namespace}/{name}/retry",
                json={
                    "name": name,
                    "namespace": self.namespace,
                    "nodeFieldSelector": f"displayName={task_name}",
                    "restartSuccessful": True,
                },
                timeout=10,
            )
        except requests.RequestException as exc:
            if original_control:
                controls[node_id] = original_control
            self.custom.patch_namespaced_custom_object(
                GROUP, VERSION, self.namespace, PLURAL, name,
                {"metadata": {"annotations": {CONTROL_ANNOTATION: json.dumps(controls, separators=(",", ":"))}}},
            )
            raise NodeControlError("Argo retry service is unavailable.") from exc
        if not response.ok:
            if original_control:
                controls[node_id] = original_control
            self.custom.patch_namespaced_custom_object(
                GROUP, VERSION, self.namespace, PLURAL, name,
                {"metadata": {"annotations": {CONTROL_ANNOTATION: json.dumps(controls, separators=(",", ":"))}}},
            )
            raise NodeControlError(f"Argo retry rejected the request ({response.status_code}): {response.text[:300]}")
        return {"workflowName": name, "nodeId": node_id, "status": "PENDING", "message": "Node and its downstream nodes are scheduled to rerun."}

    def logs(self, workflow: dict[str, Any], node_id: str) -> str:
        detail = workflow_detail(workflow)
        node = next((item for item in detail["nodes"] if item["nodeId"] == node_id), None)
        if not node:
            raise KeyError(node_id)
        pods = self.core.list_namespaced_pod(self.namespace, label_selector=f"workflows.argoproj.io/workflow={detail['workflowName']}").items
        pod = next((item for item in pods if _pod_name_matches(item.metadata.name, node.get("podName"))), None)
        if not pod:
            raise KeyError(f"Pod for node {node_id} not found")
        return self.core.read_namespaced_pod_log(pod.metadata.name, self.namespace, container="main")


__all__ = ["ApiException", "KubernetesWorkflowClient", "NodeControlError", "map_phase", "workflow_detail"]

