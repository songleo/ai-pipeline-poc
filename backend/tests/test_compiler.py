import json
from pathlib import Path

from app.compiler import compile_pipeline, safe_task_names
from app.models.pipeline import Pipeline


EXAMPLE = Path(__file__).parents[2] / "examples" / "training-qualification-pipeline.json"


def pipeline() -> Pipeline:
    return Pipeline.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))


def tasks(workflow: dict) -> dict[str, dict]:
    return {item["name"]: item for item in workflow["spec"]["templates"][0]["dag"]["tasks"]}


def test_compiles_professional_workflow_metadata() -> None:
    workflow = compile_pipeline(pipeline(), run_id="goldenrun001")
    assert workflow["metadata"]["generateName"] == "training-qualification-demo-"
    assert workflow["metadata"]["namespace"] == "pipeline-demo"
    assert workflow["spec"]["serviceAccountName"] == "pipeline-demo-workflow"
    assert workflow["spec"]["activeDeadlineSeconds"] == 420
    assert workflow["metadata"]["annotations"]["demo.pipeline.io/experiment"] == "客户流失模型资格评审"
    assert json.loads(workflow["metadata"]["annotations"]["demo.pipeline.io/tags"]) == ["p0", "classification", "qualification"]


def test_parallel_training_evaluation_and_fan_in() -> None:
    compiled = tasks(compile_pipeline(pipeline(), run_id="test"))
    assert compiled["train-baseline"]["dependencies"] == ["preprocess"]
    assert compiled["train-candidate"]["dependencies"] == ["preprocess"]
    assert compiled["leaderboard"]["dependencies"] == ["eval-baseline", "eval-candidate"]
    args = {item["name"]: item["value"] for item in compiled["leaderboard"]["arguments"]["parameters"]}
    assert args["evaluation-a"] == "{{tasks.eval-baseline.outputs.parameters.evaluation}}"
    assert args["evaluation-b"] == "{{tasks.eval-candidate.outputs.parameters.evaluation}}"


def test_gate_edges_compile_to_real_argo_conditions() -> None:
    compiled = tasks(compile_pipeline(pipeline(), run_id="test"))
    assert compiled["preprocess"]["when"] == "{{tasks.data-gate.outputs.parameters.decision}} == APPROVED"
    assert compiled["register"]["when"] == "{{tasks.admission.outputs.parameters.decision}} == APPROVED"
    assert compiled["approved-report"]["when"] == "{{tasks.admission.outputs.parameters.decision}} == APPROVED"
    assert compiled["rejected-report"]["when"] == "{{tasks.admission.outputs.parameters.decision}} == REJECTED"


def test_retry_limit_and_template_whitelist() -> None:
    workflow = compile_pipeline(pipeline(), run_id="test")
    compiled = tasks(workflow)
    args = {item["name"]: item["value"] for item in compiled["train-baseline"]["arguments"]["parameters"]}
    assert args["retry-limit"] == "2"
    wrappers = {item["name"]: item for item in workflow["spec"]["templates"][1:]}
    ref = wrappers["node-train-baseline"]["steps"][0][0]["templateRef"]
    assert ref == {"name": "pipeline-demo-nodes", "template": "train-model"}
    serialized = json.dumps(workflow)
    assert "image" not in serialized and "serviceAccountName" in serialized


def test_safe_task_name_conversion_and_collision() -> None:
    result = safe_task_names(["Train_A", "train-a", "123 bad/id", "x" * 90])
    assert result["Train_A"] == "train-a"
    assert result["train-a"].startswith("train-a-")
    assert result["123 bad/id"].startswith("n-")
    assert all(len(value) <= 54 for value in result.values())
    assert len(set(result.values())) == 4
