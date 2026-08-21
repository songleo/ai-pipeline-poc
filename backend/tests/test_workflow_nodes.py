import json

from app import workflow_nodes


def read_output(name: str) -> dict:
    return json.loads((workflow_nodes.OUTPUT_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_data_quality_gate_exposes_approved_and_rejected_decisions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_nodes, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(workflow_nodes, "ensure_node_running", lambda *_: None)
    dataset = {"kind": "DatasetRef", "id": "dataset-1"}
    approved_profile = {"sampleCount": 12000, "missingRate": 0.01}
    workflow_nodes.data_quality_gate("gate", "wf", [json.dumps(dataset), json.dumps(approved_profile), "5000", "0.05"])
    assert (tmp_path / "decision.json").read_text() == "APPROVED"
    assert read_output("approvedDecision")["outcome"] == "APPROVED"

    rejected_profile = {"sampleCount": 4000, "missingRate": 0.08}
    workflow_nodes.data_quality_gate("gate", "wf", [json.dumps(dataset), json.dumps(rejected_profile), "5000", "0.05"])
    assert (tmp_path / "decision.json").read_text() == "REJECTED"
    assert read_output("rejectedDecision")["checks"] == {"sampleCount": False, "missingRate": False}


def test_leaderboard_and_model_admission_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_nodes, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(workflow_nodes, "ensure_node_running", lambda *_: None)
    first = {"id": "eval-a", "model": {"id": "model-a", "algorithm": "bert-base-chinese"}, "metrics": {"accuracy": 0.88, "f1": 0.82, "latencyMs": 28}}
    second = {"id": "eval-b", "model": {"id": "model-b", "algorithm": "roberta-wwm-ext"}, "metrics": {"accuracy": 0.915, "f1": 0.8625, "latencyMs": 42}}
    workflow_nodes.compare_evaluations("compare", "wf", [json.dumps(first), json.dumps(second)])
    candidate = read_output("candidate")
    assert candidate["model"]["id"] == "model-b"
    assert [item["rank"] for item in read_output("leaderboard")["entries"]] == [1, 2]

    workflow_nodes.model_admission_gate("admission", "wf", [json.dumps(candidate), "0.90", "0.84", "50"])
    assert (tmp_path / "decision.json").read_text() == "APPROVED"
    workflow_nodes.model_admission_gate("admission", "wf", [json.dumps(candidate), "0.99", "0.84", "50"])
    assert (tmp_path / "decision.json").read_text() == "REJECTED"


def test_deployment_handoff_exposes_future_platform_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_nodes, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(workflow_nodes, "ensure_node_running", lambda *_: None)
    registered = {"kind": "RegisteredModelRef", "id": "registered-model-1"}
    inference = {"kind": "InferenceTestRef", "id": "inference-test-1", "passed": True}
    workflow_nodes.deployment_handoff("deploy", "wf", [json.dumps(registered), json.dumps(inference), "staging", "cpu-small", "2"])
    request = read_output("deploymentRequest")
    assert request["modelVersionId"] == "registered-model-1"
    assert request["inferenceTestId"] == "inference-test-1"
    assert request["status"] == "READY_FOR_PLATFORM"
    assert request["adapterContract"] == "InferenceDeploymentAdapter/v1"
    assert request["executionMode"] == "SIMULATED_HANDOFF"


def test_comment_inference_smoke_is_structured_and_simulated(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(workflow_nodes, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(workflow_nodes, "controlled_sleep", lambda *_: None)
    registered = {"kind": "RegisteredModelRef", "id": "comment-model-v1"}
    workflow_nodes.inference_smoke_test(
        "smoke", "wf", [json.dumps(registered), "客服一直不处理我的退款申请", "投诉", "2"],
    )
    result = read_output("inferenceTest")
    assert result["output"] == "投诉"
    assert result["confidence"] == 0.96
    assert result["passed"] is True
    assert result["executionMode"] == "SIMULATED"
