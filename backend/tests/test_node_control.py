import json

from app.kubernetes.workflows import CONTROL_ANNOTATION, KubernetesWorkflowClient


def workflow(phase: str = "Running", node_phase: str = "Running") -> dict:
    return {
        "metadata": {
            "name": "demo-abc",
            "labels": {"demo.pipeline.io/pipeline": "demo"},
            "annotations": {"demo.pipeline.io/node-map": json.dumps({"train-a": "train-a"})},
        },
        "spec": {},
        "status": {"phase": phase, "nodes": {"wrapper": {"displayName": "train-a", "phase": node_phase}}},
    }


class FakeCustom:
    def __init__(self) -> None:
        self.patches: list[dict] = []

    def patch_namespaced_custom_object(self, *args, **kwargs):
        self.patches.append(args[-1])
        return args[-1]


class FakeResponse:
    ok = True
    status_code = 200
    text = ""


class FakeHttp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, int]] = []

    def put(self, url: str, json: dict, timeout: int) -> FakeResponse:
        self.calls.append((url, json, timeout))
        return FakeResponse()


def client_for(value: dict) -> KubernetesWorkflowClient:
    instance = KubernetesWorkflowClient.__new__(KubernetesWorkflowClient)
    instance.namespace = "pipeline-demo"
    instance.argo_url = "http://argo.test"
    instance.custom = FakeCustom()
    instance.http = FakeHttp()
    instance.get = lambda name: value
    return instance


def test_stop_node_records_only_server_validated_node_id() -> None:
    client = client_for(workflow())
    result = client.stop_node("demo-abc", "train-a")
    annotation = client.custom.patches[0]["metadata"]["annotations"][CONTROL_ANNOTATION]
    assert json.loads(annotation) == {"train-a": "STOP_REQUESTED"}
    assert result["controlState"] == "STOP_REQUESTED"


def test_rerun_uses_compiler_task_name_and_clears_stop_request() -> None:
    value = workflow("Failed", "Failed")
    value["metadata"]["annotations"][CONTROL_ANNOTATION] = json.dumps({"train-a": "STOP_REQUESTED"})
    client = client_for(value)
    result = client.rerun_node("demo-abc", "train-a")
    url, body, timeout = client.http.calls[0]
    assert url == "http://argo.test/api/v1/workflows/pipeline-demo/demo-abc/retry"
    assert body == {
        "name": "demo-abc", "namespace": "pipeline-demo",
        "nodeFieldSelector": "displayName=train-a", "restartSuccessful": True,
    }
    assert timeout == 10
    assert json.loads(client.custom.patches[0]["metadata"]["annotations"][CONTROL_ANNOTATION]) == {}
    assert result["status"] == "PENDING"
