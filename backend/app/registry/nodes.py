from copy import deepcopy
from typing import Any


def port(name: str, data_type: str, required: bool = True) -> dict[str, Any]:
    return {"name": name, "type": data_type, "required": required, "multiple": False}


NODE_TYPES: dict[str, dict[str, Any]] = {
    "data-generator": {
        "type": "data-generator", "version": "1.0.0", "displayName": "生成数据",
        "description": "生成小型模拟数据集引用。", "category": "数据",
        "parametersSchema": {"type": "object", "required": ["sampleCount", "featureCount", "durationSeconds"], "properties": {
            "sampleCount": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 1000},
            "featureCount": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 10},
            "durationSeconds": {"type": "integer", "minimum": 0, "maximum": 120, "default": 2}}},
        "uiSchema": {"order": ["sampleCount", "featureCount", "durationSeconds"]},
        "inputPorts": [], "outputPorts": [port("dataset", "DatasetRef")],
        "workflowTemplateName": "pipeline-demo-nodes", "templateName": "generate-data",
        "defaultRetryLimit": 0, "defaultTimeoutSeconds": 120,
        "parameterMapping": {"sampleCount": "sample-count", "featureCount": "feature-count", "durationSeconds": "duration-seconds"}},
    "preprocess": {
        "type": "preprocess", "version": "1.0.0", "displayName": "数据预处理",
        "description": "模拟数据清洗。", "category": "数据",
        "parametersSchema": {"type": "object", "required": ["cleanRatio", "durationSeconds"], "properties": {
            "cleanRatio": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.95},
            "durationSeconds": {"type": "integer", "minimum": 0, "maximum": 120, "default": 2}}},
        "uiSchema": {"order": ["cleanRatio", "durationSeconds"]},
        "inputPorts": [port("dataset", "DatasetRef")], "outputPorts": [port("processedDataset", "DatasetRef")],
        "workflowTemplateName": "pipeline-demo-nodes", "templateName": "preprocess-data",
        "defaultRetryLimit": 0, "defaultTimeoutSeconds": 120,
        "parameterMapping": {"cleanRatio": "clean-ratio", "durationSeconds": "duration-seconds"},
        "inputMapping": {"dataset": "dataset"}},
    "mock-training": {
        "type": "mock-training", "version": "1.0.0", "displayName": "模拟训练",
        "description": "输出模型指标；可固定失败以演示重试。", "category": "训练",
        "parametersSchema": {"type": "object", "required": ["algorithm", "durationSeconds", "accuracy", "retryLimit", "failMode"], "properties": {
            "algorithm": {"type": "string", "minLength": 1, "maxLength": 40, "default": "qwen-demo"},
            "durationSeconds": {"type": "integer", "minimum": 1, "maximum": 120, "default": 8},
            "accuracy": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.86},
            "retryLimit": {"type": "integer", "minimum": 0, "maximum": 5, "default": 2},
            "failMode": {"type": "string", "enum": ["never", "always"], "default": "never"}}},
        "uiSchema": {"order": ["algorithm", "durationSeconds", "accuracy", "retryLimit", "failMode"]},
        "inputPorts": [port("dataset", "DatasetRef")], "outputPorts": [port("model", "ModelMetricRef")],
        "workflowTemplateName": "pipeline-demo-nodes", "templateName": "mock-training",
        "defaultRetryLimit": 2, "defaultTimeoutSeconds": 180,
        "parameterMapping": {"algorithm": "algorithm", "durationSeconds": "duration-seconds", "accuracy": "accuracy", "failMode": "fail-mode"},
        "inputMapping": {"dataset": "dataset"}},
    "compare-models": {
        "type": "compare-models", "version": "1.0.0", "displayName": "模型对比",
        "description": "选择 accuracy 更高的模型。", "category": "评测",
        "parametersSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "uiSchema": {"order": []},
        "inputPorts": [port("modelA", "ModelMetricRef"), port("modelB", "ModelMetricRef")],
        "outputPorts": [port("bestModel", "ModelMetricRef")],
        "workflowTemplateName": "pipeline-demo-nodes", "templateName": "compare-models",
        "defaultRetryLimit": 0, "defaultTimeoutSeconds": 60,
        "parameterMapping": {}, "inputMapping": {"modelA": "model-a", "modelB": "model-b"}},
    "generate-report": {
        "type": "generate-report", "version": "1.0.0", "displayName": "生成报告",
        "description": "根据最佳模型生成小型 JSON 报告。", "category": "输出",
        "parametersSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "uiSchema": {"order": []},
        "inputPorts": [port("model", "ModelMetricRef")], "outputPorts": [port("report", "ReportRef")],
        "workflowTemplateName": "pipeline-demo-nodes", "templateName": "generate-report",
        "defaultRetryLimit": 0, "defaultTimeoutSeconds": 60,
        "parameterMapping": {}, "inputMapping": {"model": "model"}},
}


def list_node_types() -> list[dict[str, Any]]:
    return [deepcopy(item) for item in NODE_TYPES.values()]


def get_node_type(node_type: str) -> dict[str, Any] | None:
    item = NODE_TYPES.get(node_type)
    return deepcopy(item) if item else None
