from copy import deepcopy
from typing import Any


PARAMETER_UI: dict[str, dict[str, Any]] = {
    "datasetName": {"label": "数据集名称", "group": "基础信息"},
    "version": {"label": "数据版本", "group": "基础信息", "help": "选择不可变的数据集版本。"},
    "sampleCount": {"label": "模拟样本数", "group": "PoC 模拟参数", "unit": "条", "simulation": True},
    "missingRate": {"label": "模拟缺失率", "group": "PoC 模拟参数", "simulation": True},
    "classBalance": {"label": "模拟类别占比", "group": "PoC 模拟参数", "simulation": True},
    "durationSeconds": {"label": "模拟执行时长", "group": "PoC 模拟参数", "unit": "秒", "simulation": True},
    "strategy": {"label": "处理策略", "group": "处理配置"},
    "minSamples": {"label": "最小样本数", "group": "门禁规则", "unit": "条"},
    "maxMissingRate": {"label": "最大缺失率", "group": "门禁规则"},
    "algorithm": {"label": "算法 / 基础模型", "group": "训练配置"},
    "epochs": {"label": "训练轮次", "group": "训练配置", "unit": "轮"},
    "learningRate": {"label": "学习率", "group": "训练配置"},
    "resourceProfile": {"label": "资源规格", "group": "资源配置"},
    "baseAccuracy": {"label": "模拟 Accuracy", "group": "PoC 模拟结果", "simulation": True, "help": "仅用于生成模拟评测输出，正式接入后不可人工设置。"},
    "baseF1": {"label": "模拟 F1", "group": "PoC 模拟结果", "simulation": True, "help": "仅用于生成模拟评测输出，正式接入后不可人工设置。"},
    "latencyMs": {"label": "模拟推理延迟", "group": "PoC 模拟结果", "unit": "毫秒", "simulation": True},
    "retryLimit": {"label": "失败重试次数", "group": "运行策略", "unit": "次"},
    "failMode": {"label": "模拟失败模式", "group": "PoC 模拟参数", "simulation": True},
    "accuracyAdjustment": {"label": "模拟精度修正", "group": "PoC 模拟结果", "simulation": True},
    "minAccuracy": {"label": "最低 Accuracy", "group": "门禁规则"},
    "minF1": {"label": "最低 F1", "group": "门禁规则"},
    "maxLatencyMs": {"label": "最大推理延迟", "group": "门禁规则", "unit": "毫秒"},
    "versionAlias": {"label": "模型版本别名", "group": "登记配置"},
    "inputSample": {"label": "冒烟输入样本", "group": "冒烟配置"},
    "expectedOutput": {"label": "预期输出", "group": "冒烟配置"},
    "environment": {"label": "目标环境", "group": "部署交接"},
    "replicas": {"label": "实例数", "group": "部署交接", "unit": "个"},
}


def port(name: str, data_type: str) -> dict[str, Any]:
    return {"name": name, "type": data_type, "required": True, "multiple": False}


def schema(required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "required": required, "properties": properties}


def integer(default: int, minimum: int, maximum: int) -> dict[str, Any]:
    return {"type": "integer", "default": default, "minimum": minimum, "maximum": maximum}


def number(default: float, minimum: float = 0, maximum: float = 1) -> dict[str, Any]:
    return {"type": "number", "default": default, "minimum": minimum, "maximum": maximum}


def string(default: str, *, values: list[str] | None = None, maximum: int = 40) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "string", "default": default}
    if values:
        result["enum"] = values
    else:
        result.update(minLength=1, maxLength=maximum)
    return result


def node(
    node_type: str, display_name: str, description: str, category: str,
    properties: dict[str, Any], inputs: list[dict[str, Any]], outputs: list[dict[str, Any]],
    template: str, parameter_mapping: dict[str, str], input_mapping: dict[str, str] | None = None,
    *, retry: int = 0, branches: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    result = {
        "type": node_type, "version": "1.0.0", "displayName": display_name,
        "description": description, "category": category,
        "parametersSchema": schema(list(properties), properties) if properties else {"type": "object", "properties": {}, "additionalProperties": False},
        "uiSchema": {"order": list(properties), "fields": {name: deepcopy(PARAMETER_UI.get(name, {"label": name, "group": "其他"})) for name in properties}},
        "inputPorts": inputs, "outputPorts": outputs,
        "workflowTemplateName": "pipeline-demo-nodes", "templateName": template,
        "defaultRetryLimit": retry, "defaultTimeoutSeconds": 180 if category == "训练" else 120,
        "parameterMapping": parameter_mapping, "inputMapping": input_mapping or {},
    }
    if branches:
        result["branchConditions"] = branches
        result["internalOutputs"] = ["decision"]
    return result


APPROVAL_BRANCHES = {
    "approvedDataset": {"output": "decision", "value": "APPROVED"},
    "rejectedDataset": {"output": "decision", "value": "REJECTED"},
    "approvedCandidate": {"output": "decision", "value": "APPROVED"},
    "rejectedCandidate": {"output": "decision", "value": "REJECTED"},
    "approvedDecision": {"output": "decision", "value": "APPROVED"},
    "rejectedDecision": {"output": "decision", "value": "REJECTED"},
}


NODE_TYPES: dict[str, dict[str, Any]] = {
    "dataset-version": node(
        "dataset-version", "选择数据集版本", "模拟从资产目录选择一个不可变数据集版本。", "资产",
        {"datasetName": string("customer-churn"), "version": string("v2026.08", maximum=20),
         "sampleCount": integer(12000, 100, 1000000), "missingRate": number(0.018),
         "classBalance": number(0.42), "durationSeconds": integer(1, 0, 60)},
        [], [port("dataset", "DatasetRef")], "dataset-version",
        {"datasetName": "dataset-name", "version": "version", "sampleCount": "sample-count",
         "missingRate": "missing-rate", "classBalance": "class-balance", "durationSeconds": "duration-seconds"}),
    "data-profile": node(
        "data-profile", "数据画像", "生成样本规模、缺失率和类别平衡等质量摘要。", "数据",
        {"durationSeconds": integer(2, 0, 60)}, [port("dataset", "DatasetRef")], [port("profile", "DataProfileRef")],
        "data-profile", {"durationSeconds": "duration-seconds"}, {"dataset": "dataset"}),
    "data-quality-gate": node(
        "data-quality-gate", "数据质量门禁", "根据样本数和缺失率选择通过或拒绝分支。", "门禁",
        {"minSamples": integer(5000, 100, 1000000), "maxMissingRate": number(0.05)},
        [port("dataset", "DatasetRef"), port("profile", "DataProfileRef")],
        [port("approvedDataset", "DatasetRef"), port("rejectedDataset", "DatasetRef"),
         port("approvedDecision", "GateDecisionRef"), port("rejectedDecision", "GateDecisionRef")],
        "data-quality-gate", {"minSamples": "min-samples", "maxMissingRate": "max-missing-rate"},
        {"dataset": "dataset", "profile": "profile"}, branches=APPROVAL_BRANCHES),
    "feature-preprocess": node(
        "feature-preprocess", "特征预处理", "模拟清洗、编码与标准化，并保留上游数据版本。", "数据",
        {"strategy": string("standardize", values=["standardize", "robust-scale", "one-hot"]), "durationSeconds": integer(2, 0, 60)},
        [port("dataset", "DatasetRef")], [port("processedDataset", "DatasetRef")], "feature-preprocess",
        {"strategy": "strategy", "durationSeconds": "duration-seconds"}, {"dataset": "dataset"}),
    "train-model": node(
        "train-model", "模型训练 / 微调", "模拟受控模型训练，记录算法、超参数和资源规格。", "训练",
        {"algorithm": string("xgboost", values=["xgboost", "lightgbm", "bert-base-chinese", "roberta-wwm-ext", "macbert-base"]), "epochs": integer(40, 1, 500),
         "learningRate": number(0.05, 0.0001, 1), "resourceProfile": string("cpu-small", values=["cpu-small", "cpu-medium", "gpu-demo"]),
         "durationSeconds": integer(8, 1, 120), "baseAccuracy": number(0.88), "baseF1": number(0.84),
         "latencyMs": number(36, 1, 10000), "retryLimit": integer(2, 0, 5), "failMode": string("never", values=["never", "always"])},
        [port("dataset", "DatasetRef")], [port("model", "ModelRef")], "train-model",
        {"algorithm": "algorithm", "epochs": "epochs", "learningRate": "learning-rate", "resourceProfile": "resource-profile",
         "durationSeconds": "duration-seconds", "baseAccuracy": "base-accuracy", "baseF1": "base-f1",
         "latencyMs": "latency-ms", "failMode": "fail-mode"}, {"dataset": "dataset"}, retry=2),
    "evaluate-model": node(
        "evaluate-model", "模型评测", "在固定测试数据上生成 Accuracy、F1 和推理延迟。", "评测",
        {"accuracyAdjustment": number(0.01, -0.2, 0.2), "durationSeconds": integer(2, 0, 60)},
        [port("model", "ModelRef"), port("dataset", "DatasetRef")], [port("evaluation", "EvaluationRef")],
        "evaluate-model", {"accuracyAdjustment": "accuracy-adjustment", "durationSeconds": "duration-seconds"},
        {"model": "model", "dataset": "dataset"}),
    "compare-evaluations": node(
        "compare-evaluations", "排行榜与候选选择", "汇聚两组评测结果，按 Accuracy 选择候选模型。", "评测", {},
        [port("evaluationA", "EvaluationRef"), port("evaluationB", "EvaluationRef")],
        [port("candidate", "CandidateModelRef"), port("leaderboard", "LeaderboardRef")],
        "compare-evaluations", {}, {"evaluationA": "evaluation-a", "evaluationB": "evaluation-b"}),
    "model-admission-gate": node(
        "model-admission-gate", "模型准入门禁", "根据 Accuracy、F1 和延迟决定登记或拒绝。", "门禁",
        {"minAccuracy": number(0.90), "minF1": number(0.84), "maxLatencyMs": number(50, 1, 10000)},
        [port("candidate", "CandidateModelRef")],
        [port("approvedCandidate", "CandidateModelRef"), port("rejectedCandidate", "CandidateModelRef"),
         port("approvedDecision", "GateDecisionRef"), port("rejectedDecision", "GateDecisionRef")],
        "model-admission-gate", {"minAccuracy": "min-accuracy", "minF1": "min-f1", "maxLatencyMs": "max-latency-ms"},
        {"candidate": "candidate"}, branches=APPROVAL_BRANCHES),
    "register-model-version": node(
        "register-model-version", "登记模型版本", "模拟生成不可变模型版本引用，不调用外部模型仓库。", "资产",
        {"versionAlias": string("candidate", maximum=30)}, [port("candidate", "CandidateModelRef")],
        [port("registeredModel", "RegisteredModelRef")], "register-model-version",
        {"versionAlias": "version-alias"}, {"candidate": "candidate"}),
    "inference-smoke-test": node(
        "inference-smoke-test", "推理冒烟测试", "使用固定样本模拟推理输出，验证登记模型可进入服务化阶段。", "评测",
        {"inputSample": string("sample payload", maximum=100),
         "expectedOutput": string("expected", maximum=40),
         "durationSeconds": integer(2, 0, 60)}, [port("registeredModel", "RegisteredModelRef")],
        [port("inferenceTest", "InferenceTestRef")], "inference-smoke-test",
        {"inputSample": "input-sample", "expectedOutput": "expected-output", "durationSeconds": "duration-seconds"},
        {"registeredModel": "registered-model"}),
    "deployment-handoff": node(
        "deployment-handoff", "推理部署交接", "生成受控部署申请，作为未来 ai-platform 推理服务适配器的输入。", "发布",
        {"environment": string("staging", values=["staging", "production"]),
         "resourceProfile": string("cpu-small", values=["cpu-small", "cpu-medium", "gpu-demo"]),
         "replicas": integer(1, 1, 5)}, [port("registeredModel", "RegisteredModelRef"), port("inferenceTest", "InferenceTestRef")],
        [port("deploymentRequest", "DeploymentRequestRef")], "deployment-handoff",
        {"environment": "environment", "resourceProfile": "resource-profile", "replicas": "replicas"},
        {"registeredModel": "registered-model", "inferenceTest": "inference-test"}),
    "qualification-report": node(
        "qualification-report", "生成资格报告", "根据门禁决策生成通过或拒绝报告。", "报告", {},
        [port("decision", "GateDecisionRef")], [port("report", "ReportRef")],
        "qualification-report", {}, {"decision": "decision"}),
}


def list_node_types() -> list[dict[str, Any]]:
    return [deepcopy(item) for item in NODE_TYPES.values()]


def get_node_type(node_type: str) -> dict[str, Any] | None:
    item = NODE_TYPES.get(node_type)
    return deepcopy(item) if item else None
