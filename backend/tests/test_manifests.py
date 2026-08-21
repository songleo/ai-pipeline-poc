from pathlib import Path

import yaml

from app.registry import NODE_TYPES


ROOT = Path(__file__).parents[2]


def test_all_project_manifests_are_valid_yaml_documents() -> None:
    files = list((ROOT / "deploy").rglob("*.yaml"))
    assert files
    for path in files:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        assert all(document["apiVersion"] and document["kind"] for document in documents), path


def test_workflow_template_is_fixed_whitelist() -> None:
    path = ROOT / "deploy" / "argo" / "workflow-templates" / "pipeline-demo-nodes.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert document["metadata"]["name"] == "pipeline-demo-nodes"
    assert {item["name"] for item in document["spec"]["templates"]} == {
        "dataset-version", "data-profile", "data-quality-gate", "feature-preprocess", "train-model",
        "evaluate-model", "compare-evaluations", "model-admission-gate", "register-model-version",
        "qualification-report", "inference-smoke-test", "deployment-handoff",
    }
    for template in document["spec"]["templates"]:
        assert template["container"]["image"] == "pipeline-demo-backend:0.1.0"
        assert template["container"]["command"] == ["python", "-m", "app.workflow_nodes"]


def test_registry_exposes_professional_parameter_presentation() -> None:
    fields = NODE_TYPES["train-model"]["uiSchema"]["fields"]
    assert fields["algorithm"]["label"] == "算法 / 基础模型"
    assert fields["resourceProfile"]["group"] == "资源配置"
    assert fields["baseAccuracy"]["simulation"] is True
    assert "正式接入后" in fields["baseAccuracy"]["help"]
