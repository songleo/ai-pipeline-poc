import copy
import json
from pathlib import Path

import pytest

from app.compiler import validate_pipeline
from app.models.pipeline import Pipeline


EXAMPLE = Path(__file__).parents[2] / "examples" / "training-qualification-pipeline.json"
BEGINNER_EXAMPLE = Path(__file__).parents[2] / "examples" / "beginner-training-pipeline.json"


def data() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def codes(value: dict) -> set[str]:
    result = validate_pipeline(Pipeline.model_validate(value))
    return {item.code for item in result.errors}


def test_valid_dag() -> None:
    result = validate_pipeline(Pipeline.model_validate(data()))
    assert result.valid
    assert result.errors == []


def test_beginner_example_is_a_valid_four_node_dag() -> None:
    value = json.loads(BEGINNER_EXAMPLE.read_text(encoding="utf-8"))
    result = validate_pipeline(Pipeline.model_validate(value))
    assert result.valid
    assert len(value["spec"]["nodes"]) == 4
    assert len(value["spec"]["edges"]) == 4


def test_cycle_detection() -> None:
    value = data()
    value["spec"]["edges"].append({"source": "register", "sourcePort": "registeredModel", "target": "preprocess", "targetPort": "dataset"})
    assert "DAG_CYCLE" in codes(value)


def test_duplicate_node_id() -> None:
    value = data(); value["spec"]["nodes"].append(copy.deepcopy(value["spec"]["nodes"][0]))
    assert "DUPLICATE_NODE_ID" in codes(value)


def test_unknown_node_type() -> None:
    value = data(); value["spec"]["nodes"][0]["type"] = "arbitrary-shell"
    assert "UNKNOWN_NODE_TYPE" in codes(value)


def test_missing_required_parameter() -> None:
    value = data(); del value["spec"]["nodes"][0]["parameters"]["sampleCount"]
    assert "MISSING_PARAMETER" in codes(value)


@pytest.mark.parametrize("bad_value", ["many", True, 1.5])
def test_parameter_type_error(bad_value: object) -> None:
    value = data(); value["spec"]["nodes"][0]["parameters"]["sampleCount"] = bad_value
    assert "INVALID_PARAMETER" in codes(value)


def test_port_does_not_exist() -> None:
    value = data(); value["spec"]["edges"][0]["sourcePort"] = "missing"
    assert "UNKNOWN_SOURCE_PORT" in codes(value)


def test_port_type_mismatch() -> None:
    value = data(); value["spec"]["edges"][10]["source"] = "dataset"; value["spec"]["edges"][10]["sourcePort"] = "dataset"
    assert "PORT_TYPE_MISMATCH" in codes(value)


def test_required_input_not_connected() -> None:
    value = data(); value["spec"]["edges"] = [e for e in value["spec"]["edges"] if not (e["target"] == "leaderboard" and e["targetPort"] == "evaluationB")]
    assert "MISSING_REQUIRED_INPUT" in codes(value)


def test_duplicate_connection_and_single_input_limit() -> None:
    value = data(); value["spec"]["edges"].append(copy.deepcopy(value["spec"]["edges"][0]))
    assert {"DUPLICATE_EDGE", "MULTIPLE_INPUT_CONNECTIONS"} <= codes(value)
