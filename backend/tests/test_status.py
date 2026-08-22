import json

from app.kubernetes.workflows import _pod_name_matches, map_phase, workflow_detail


def test_status_mapping() -> None:
    assert map_phase(None) == "PENDING"
    assert map_phase("Running") == "RUNNING"
    assert map_phase("Succeeded") == "SUCCEEDED"
    assert map_phase("Failed") == "FAILED"
    assert map_phase("Error") == "ERROR"
    assert map_phase("Skipped") == "SKIPPED"
    assert map_phase("Running", shutdown="Terminate") == "CANCELLED"


def test_argo_v2_pod_name_matches_node_id_suffix() -> None:
    assert _pod_name_matches(
        "training-qualification-demo-abc-train-model-1327291279",
        "training-qualification-demo-abc-1327291279",
    )
    assert not _pod_name_matches(
        "training-qualification-demo-abc-train-model-52739434",
        "training-qualification-demo-abc-1327291279",
    )


def test_node_status_output_and_retry_mapping() -> None:
    definition = {"apiVersion": "demo.pipeline.io/v1alpha1", "kind": "Pipeline", "metadata": {"name": "demo", "experimentName": "Demo", "scenario": "test", "tags": [], "version": 3}, "spec": {"nodes": [], "edges": [], "runPolicy": {"timeoutSeconds": 60}}, "uiLayout": {"nodes": {}}}
    workflow = {
        "metadata": {"name": "demo-abc", "labels": {"demo.pipeline.io/pipeline": "demo"}, "annotations": {"demo.pipeline.io/node-map": json.dumps({"train-a": "train-a"}), "demo.pipeline.io/definition-digest": "abc123def456", "demo.pipeline.io/pipeline-version": "3", "demo.pipeline.io/definition-snapshot": json.dumps(definition)}},
        "spec": {},
        "status": {"phase": "Succeeded", "nodes": {
            "wrapper": {"displayName": "train-a", "phase": "Succeeded", "startedAt": "2026-01-01T00:00:00Z", "finishedAt": "2026-01-01T00:00:03Z", "outputs": {"parameters": [{"name": "model", "value": "{\"accuracy\":0.86}"}]}},
            "pod-1": {"id": "pod-1", "type": "Pod", "name": "demo.train-a.execute(0)", "phase": "Failed"},
            "pod-2": {"id": "pod-2", "type": "Pod", "name": "demo.train-a.execute(1)", "phase": "Succeeded"},
        }},
    }
    detail = workflow_detail(workflow); node = detail["nodes"][0]
    assert detail["status"] == "SUCCEEDED"
    assert detail["definitionDigest"] == "abc123def456"
    assert detail["definitionVersion"] == 3
    assert detail["pipelineDefinition"] == definition
    assert node["duration"] == 3
    assert node["retryCount"] == 1
    assert node["podName"] == "pod-2"
    assert node["outputs"]["model"]["accuracy"] == 0.86
    assert node["canStop"] is False
    assert node["canRerun"] is True


def test_invalid_snapshot_metadata_is_backward_compatible() -> None:
    workflow = {"metadata": {"name": "old", "labels": {}, "annotations": {"demo.pipeline.io/node-map": "{}", "demo.pipeline.io/pipeline-version": "broken", "demo.pipeline.io/definition-snapshot": "not-json"}}, "spec": {}, "status": {}}
    detail = workflow_detail(workflow)
    assert detail["definitionVersion"] is None
    assert detail["pipelineDefinition"] is None


def test_requested_stop_maps_failed_node_to_cancelled() -> None:
    workflow = {
        "metadata": {
            "name": "demo-stop",
            "labels": {"demo.pipeline.io/pipeline": "demo"},
            "annotations": {
                "demo.pipeline.io/node-map": json.dumps({"train-a": "train-a"}),
                "demo.pipeline.io/node-controls": json.dumps({"train-a": "STOP_REQUESTED"}),
            },
        },
        "spec": {},
        "status": {"phase": "Failed", "nodes": {"wrapper": {"displayName": "train-a", "phase": "Failed"}}},
    }
    node = workflow_detail(workflow)["nodes"][0]
    assert node["status"] == "CANCELLED"
    assert node["controlState"] == "STOP_REQUESTED"
    assert node["canRerun"] is True


def test_stop_request_that_loses_completion_race_is_not_shown_as_active() -> None:
    workflow = {
        "metadata": {
            "name": "demo-finished",
            "labels": {"demo.pipeline.io/pipeline": "demo"},
            "annotations": {
                "demo.pipeline.io/node-map": json.dumps({"train-a": "train-a"}),
                "demo.pipeline.io/node-controls": json.dumps({"train-a": "STOP_REQUESTED"}),
            },
        },
        "spec": {},
        "status": {"phase": "Succeeded", "nodes": {"wrapper": {"displayName": "train-a", "phase": "Succeeded"}}},
    }
    node = workflow_detail(workflow)["nodes"][0]
    assert node["status"] == "SUCCEEDED"
    assert node["controlState"] is None
