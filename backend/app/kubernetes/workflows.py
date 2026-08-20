import json
import os
from datetime import datetime
from typing import Any

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


GROUP, VERSION, PLURAL = "argoproj.io", "v1alpha1", "workflows"
TERMINAL = {"SUCCEEDED", "FAILED", "ERROR", "CANCELLED"}


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


def _pod_name_matches(pod_name: str, argo_node_id: str | None) -> bool:
    if not argo_node_id:
        return False
    if pod_name == argo_node_id:
        return True
    return pod_name.endswith(f"-{argo_node_id.rsplit('-', 1)[-1]}")


def workflow_detail(workflow: dict[str, Any]) -> dict[str, Any]:
    metadata, spec, status = workflow.get("metadata", {}), workflow.get("spec", {}), workflow.get("status", {})
    mapping = json.loads(metadata.get("annotations", {}).get("demo.ssli.io/node-map", "{}"))
    statuses: dict[str, dict[str, Any]] = status.get("nodes", {}) or {}
    result_nodes = []
    for node_id, task_name in mapping.items():
        matches = [(key, value) for key, value in statuses.items() if value.get("displayName") == task_name]
        primary_key, primary = matches[-1] if matches else (None, {})
        pod_matches = [(key, value) for key, value in statuses.items() if value.get("type") == "Pod" and (
            task_name in value.get("name", "") or value.get("boundaryID") == primary_key
        )]
        pod_name = (pod_matches[-1][1].get("id") or pod_matches[-1][0]) if pod_matches else None
        result_nodes.append({
            "nodeId": node_id, "taskName": task_name,
            "status": map_phase(primary.get("phase"), primary.get("message", ""), spec.get("shutdown")),
            "startedAt": primary.get("startedAt"), "finishedAt": primary.get("finishedAt"),
            "duration": _duration(primary.get("startedAt"), primary.get("finishedAt")),
            "message": primary.get("message"), "retryCount": max(0, len(pod_matches) - 1),
            "podName": pod_name, "outputs": _outputs(primary),
        })
    return {
        "workflowName": metadata.get("name"),
        "pipelineName": metadata.get("labels", {}).get("demo.ssli.io/pipeline"),
        "status": map_phase(status.get("phase"), status.get("message", ""), spec.get("shutdown")),
        "startedAt": status.get("startedAt"), "finishedAt": status.get("finishedAt"),
        "message": status.get("message"), "nodes": result_nodes,
    }


class KubernetesWorkflowClient:
    def __init__(self, namespace: str | None = None) -> None:
        self.namespace = namespace or os.getenv("PIPELINE_NAMESPACE", "pipeline-demo")
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config(context=os.getenv("KUBERNETES_CONTEXT", "kind-ssli-demo"))
        self.custom = client.CustomObjectsApi()
        self.core = client.CoreV1Api()

    def create(self, workflow: dict[str, Any]) -> dict[str, Any]:
        return self.custom.create_namespaced_custom_object(GROUP, VERSION, self.namespace, PLURAL, workflow)

    def get(self, name: str) -> dict[str, Any]:
        return self.custom.get_namespaced_custom_object(GROUP, VERSION, self.namespace, PLURAL, name)

    def list(self) -> list[dict[str, Any]]:
        response = self.custom.list_namespaced_custom_object(GROUP, VERSION, self.namespace, PLURAL, label_selector="demo.ssli.io/project=ssli-demo")
        return response.get("items", [])

    def stop(self, name: str) -> dict[str, Any]:
        workflow = self.get(name)
        detail = workflow_detail(workflow)
        if detail["status"] in TERMINAL:
            return {"workflowName": name, "status": detail["status"], "message": "Workflow is already terminal."}
        patched = self.custom.patch_namespaced_custom_object(GROUP, VERSION, self.namespace, PLURAL, name, {"spec": {"shutdown": "Terminate"}})
        return {"workflowName": name, "status": map_phase(patched.get("status", {}).get("phase"), shutdown="Terminate"), "message": "Termination requested."}

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


__all__ = ["ApiException", "KubernetesWorkflowClient", "map_phase", "workflow_detail"]
