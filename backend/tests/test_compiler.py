import json
from pathlib import Path

import yaml

from app.compiler import compile_pipeline, safe_task_names
from app.models.pipeline import Pipeline


EXAMPLE = Path(__file__).parents[2] / "examples" / "model-comparison-pipeline.json"


def pipeline() -> Pipeline:
    return Pipeline.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))


def test_compiles_to_structured_workflow() -> None:
    workflow = compile_pipeline(pipeline(), run_id="goldenrun001")
    assert workflow["apiVersion"] == "argoproj.io/v1alpha1"
    assert workflow["metadata"]["generateName"] == "model-comparison-demo-"
    assert workflow["metadata"]["namespace"] == "pipeline-demo"
    assert workflow["spec"]["serviceAccountName"] == "pipeline-demo-workflow"
    assert workflow["spec"]["activeDeadlineSeconds"] == 300
    assert workflow["metadata"]["labels"] == {
        "demo.pipeline.io/project": "pipeline-demo", "demo.pipeline.io/pipeline": "model-comparison-demo", "demo.pipeline.io/run-id": "goldenrun001"
    }


def test_compiler_matches_golden_workflow() -> None:
    workflow = compile_pipeline(pipeline(), run_id="goldenrun001")
    golden = yaml.safe_load((EXAMPLE.parent / "expected-workflow.yaml").read_text(encoding="utf-8"))
    assert workflow == golden


def test_parallel_dependencies_and_parameter_references() -> None:
    workflow = compile_pipeline(pipeline(), run_id="test")
    tasks = {item["name"]: item for item in workflow["spec"]["templates"][0]["dag"]["tasks"]}
    assert tasks["train-a"]["dependencies"] == ["preprocess"]
    assert tasks["train-b"]["dependencies"] == ["preprocess"]
    assert tasks["compare"]["dependencies"] == ["train-a", "train-b"]
    assert tasks["report"]["dependencies"] == ["compare"]
    compare_args = {item["name"]: item["value"] for item in tasks["compare"]["arguments"]["parameters"]}
    assert compare_args == {
        "node-id": "compare",
        "model-a": "{{tasks.train-a.outputs.parameters.model}}",
        "model-b": "{{tasks.train-b.outputs.parameters.model}}",
    }


def test_retry_strategy_and_fixed_template_whitelist() -> None:
    workflow = compile_pipeline(pipeline(), run_id="test")
    wrappers = {item["name"]: item for item in workflow["spec"]["templates"][1:]}
    assert wrappers["node-train-a"]["retryStrategy"] == {"limit": "2", "retryPolicy": "Always"}
    ref = wrappers["node-train-a"]["steps"][0][0]["templateRef"]
    assert ref == {"name": "pipeline-demo-nodes", "template": "mock-training"}
    serialized = json.dumps(workflow)
    assert "image" not in serialized and "serviceAccountName" in serialized


def test_safe_task_name_conversion_and_collision() -> None:
    result = safe_task_names(["Train_A", "train-a", "123 bad/id", "x" * 90])
    assert result["Train_A"] == "train-a"
    assert result["train-a"].startswith("train-a-")
    assert result["123 bad/id"].startswith("n-")
    assert all(len(value) <= 54 for value in result.values())
    assert len(set(result.values())) == 4

