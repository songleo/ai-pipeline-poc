"""Fixed implementations used only by the allow-listed Argo WorkflowTemplates."""

import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.node_control import controlled_sleep, ensure_node_running


OUTPUT_DIR = Path("/tmp")


def load(value: str) -> dict[str, Any]:
    return json.loads(value)


def write(name: str, value: dict[str, Any] | str) -> None:
    text = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
    (OUTPUT_DIR / f"{name}.json").write_text(text, encoding="utf-8")


def ref_id(prefix: str, *values: Any) -> str:
    digest = sha256("|".join(map(str, values)).encode()).hexdigest()[:10]
    return f"{prefix}-{digest}"


def dataset_version(node: str, workflow: str, args: list[str]) -> None:
    name, version, sample_count, missing_rate, class_balance, duration = args
    controlled_sleep(workflow, node, float(duration))
    dataset = {"kind": "DatasetRef", "id": ref_id("dataset", name, version), "name": name, "version": version,
               "checksum": f"sha256:{sha256(f'{name}:{version}'.encode()).hexdigest()}", "sampleCount": int(sample_count),
               "missingRate": float(missing_rate), "classBalance": float(class_balance)}
    write("dataset", dataset)
    print(f"[{node}] selected dataset={dataset['id']} version={version}", flush=True)


def data_profile(node: str, workflow: str, args: list[str]) -> None:
    dataset, duration = load(args[0]), args[1]
    controlled_sleep(workflow, node, float(duration))
    profile = {"kind": "DataProfileRef", "id": ref_id("profile", dataset["id"]), "datasetId": dataset["id"],
               "sampleCount": dataset["sampleCount"], "missingRate": dataset["missingRate"],
               "classBalance": dataset["classBalance"], "schemaDrift": False}
    write("profile", profile)
    print(f"[{node}] samples={profile['sampleCount']} missingRate={profile['missingRate']}", flush=True)


def gate_outputs(prefix: str, subject: dict[str, Any], decision: dict[str, Any]) -> None:
    outcome = decision["outcome"]
    write("decision", outcome)
    write(f"{prefix}Decision" if prefix in {"approved", "rejected"} else prefix, decision)
    write("approvedDecision", decision)
    write("rejectedDecision", decision)
    if subject["kind"] == "DatasetRef":
        write("approvedDataset", subject); write("rejectedDataset", subject)
    else:
        write("approvedCandidate", subject); write("rejectedCandidate", subject)


def data_quality_gate(node: str, workflow: str, args: list[str]) -> None:
    ensure_node_running(workflow, node)
    dataset, profile, min_samples, max_missing = load(args[0]), load(args[1]), int(args[2]), float(args[3])
    checks = {"sampleCount": profile["sampleCount"] >= min_samples, "missingRate": profile["missingRate"] <= max_missing}
    outcome = "APPROVED" if all(checks.values()) else "REJECTED"
    decision = {"kind": "GateDecisionRef", "id": ref_id("data-gate", dataset["id"], outcome), "gate": "data-quality",
                "outcome": outcome, "checks": checks, "subjectId": dataset["id"]}
    gate_outputs(outcome.lower(), dataset, decision)
    print(f"[{node}] outcome={outcome} checks={checks}", flush=True)


def feature_preprocess(node: str, workflow: str, args: list[str]) -> None:
    dataset, strategy, duration = load(args[0]), args[1], args[2]
    controlled_sleep(workflow, node, float(duration))
    processed = {**dataset, "id": ref_id("processed", dataset["id"], strategy), "parentId": dataset["id"],
                 "transform": strategy, "kind": "DatasetRef"}
    write("processedDataset", processed)
    print(f"[{node}] transform={strategy} output={processed['id']}", flush=True)


def train_model(node: str, workflow: str, args: list[str]) -> None:
    dataset = load(args[0])
    algorithm, epochs, learning_rate, resource_profile, duration, accuracy, f1, latency, fail_mode = args[1:]
    print(f"[{node}] algorithm={algorithm} epochs={epochs} resource={resource_profile}", flush=True)
    for progress in (25, 50, 75, 100):
        controlled_sleep(workflow, node, float(duration) / 4)
        print(f"[{node}] progress={progress}%", flush=True)
    if fail_mode == "always":
        print(f"[{node}] fixed failure requested", flush=True)
        raise SystemExit(42)
    model = {"kind": "ModelRef", "id": ref_id("model", dataset["id"], algorithm, epochs, learning_rate),
             "datasetId": dataset["id"], "algorithm": algorithm, "parameters": {"epochs": int(epochs), "learningRate": float(learning_rate)},
             "resourceProfile": resource_profile, "resourceMode": "SIMULATED" if resource_profile == "gpu-demo" else "K8S_LIMITED",
             "baseMetrics": {"accuracy": float(accuracy), "f1": float(f1), "latencyMs": float(latency)}}
    write("model", model)
    print(f"[{node}] model={model['id']} training completed", flush=True)


def evaluate_model(node: str, workflow: str, args: list[str]) -> None:
    model, dataset, adjustment, duration = load(args[0]), load(args[1]), float(args[2]), args[3]
    controlled_sleep(workflow, node, float(duration))
    base = model["baseMetrics"]
    metrics = {"accuracy": round(min(1, max(0, base["accuracy"] + adjustment)), 4),
               "f1": round(min(1, max(0, base["f1"] + adjustment / 2)), 4), "latencyMs": base["latencyMs"]}
    result = {"kind": "EvaluationRef", "id": ref_id("evaluation", model["id"], dataset["id"]),
              "model": model, "datasetId": dataset["id"], "metrics": metrics}
    write("evaluation", result)
    print(f"[{node}] accuracy={metrics['accuracy']} f1={metrics['f1']} latencyMs={metrics['latencyMs']}", flush=True)


def compare_evaluations(node: str, workflow: str, args: list[str]) -> None:
    ensure_node_running(workflow, node)
    evaluations = [load(args[0]), load(args[1])]
    evaluations.sort(key=lambda item: item["metrics"]["accuracy"], reverse=True)
    best = evaluations[0]
    candidate = {"kind": "CandidateModelRef", "id": ref_id("candidate", best["model"]["id"]),
                 "model": best["model"], "evaluationId": best["id"], "metrics": best["metrics"]}
    leaderboard = {"kind": "LeaderboardRef", "id": ref_id("leaderboard", *(item["id"] for item in evaluations)),
                   "entries": [{"rank": rank, "modelId": item["model"]["id"], "algorithm": item["model"]["algorithm"], **item["metrics"]}
                               for rank, item in enumerate(evaluations, 1)]}
    write("candidate", candidate); write("leaderboard", leaderboard)
    print(f"[{node}] champion={candidate['model']['id']} accuracy={candidate['metrics']['accuracy']}", flush=True)


def model_admission_gate(node: str, workflow: str, args: list[str]) -> None:
    ensure_node_running(workflow, node)
    candidate, min_accuracy, min_f1, max_latency = load(args[0]), float(args[1]), float(args[2]), float(args[3])
    metrics = candidate["metrics"]
    checks = {"accuracy": metrics["accuracy"] >= min_accuracy, "f1": metrics["f1"] >= min_f1,
              "latencyMs": metrics["latencyMs"] <= max_latency}
    outcome = "APPROVED" if all(checks.values()) else "REJECTED"
    decision = {"kind": "GateDecisionRef", "id": ref_id("model-gate", candidate["id"], outcome), "gate": "model-admission",
                "outcome": outcome, "checks": checks, "subjectId": candidate["id"], "metrics": metrics}
    gate_outputs(outcome.lower(), candidate, decision)
    print(f"[{node}] outcome={outcome} checks={checks}", flush=True)


def register_model_version(node: str, workflow: str, args: list[str]) -> None:
    ensure_node_running(workflow, node)
    candidate, alias = load(args[0]), args[1]
    registered = {"kind": "RegisteredModelRef", "id": ref_id("registered-model", candidate["id"], alias),
                  "candidateId": candidate["id"], "alias": alias, "status": "SIMULATED_REGISTERED",
                  "metrics": candidate["metrics"]}
    write("registeredModel", registered)
    print(f"[{node}] registered={registered['id']} alias={alias} mode=SIMULATED", flush=True)


def qualification_report(node: str, workflow: str, args: list[str]) -> None:
    ensure_node_running(workflow, node)
    decision = load(args[0])
    report = {"kind": "ReportRef", "id": ref_id("qualification-report", decision["id"]),
              "outcome": decision["outcome"], "gate": decision["gate"], "subjectId": decision["subjectId"],
              "summary": f"{decision['gate']} result: {decision['outcome']}"}
    write("report", report)
    print(f"[{node}] {report['summary']}", flush=True)


OPERATIONS = {
    "dataset-version": dataset_version, "data-profile": data_profile, "data-quality-gate": data_quality_gate,
    "feature-preprocess": feature_preprocess, "train-model": train_model, "evaluate-model": evaluate_model,
    "compare-evaluations": compare_evaluations, "model-admission-gate": model_admission_gate,
    "register-model-version": register_model_version, "qualification-report": qualification_report,
}


def main() -> None:
    operation, node, workflow, *args = sys.argv[1:]
    OPERATIONS[operation](node, workflow, args)


if __name__ == "__main__":
    main()
