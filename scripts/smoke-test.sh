#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
require_context
command -v jq >/dev/null 2>&1 || { echo "Missing required tool: jq" >&2; exit 1; }

API_URL="${API_URL:-http://localhost:8000}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TMP_DIR"' EXIT

submit_pipeline() {
  local path="$1" response
  response="$(curl -fsS -H 'Content-Type: application/json' --data-binary "@$path" "$API_URL/api/runs")"
  jq -er '.workflowName' <<<"$response"
}

wait_for_status() {
  local workflow="$1" expected="$2" timeout="$3" deadline phase run
  deadline=$((SECONDS + timeout))
  while (( SECONDS < deadline )); do
    run="$(curl -fsS "$API_URL/api/runs/$workflow")"
    phase="$(jq -er '.status' <<<"$run")"
    echo "$workflow status=$phase" >&2
    [[ "$phase" == "$expected" ]] && { printf '%s' "$run"; return 0; }
    if [[ "$phase" =~ ^(SUCCEEDED|FAILED|ERROR|CANCELLED)$ ]]; then
      echo "Expected $expected but reached $phase: $run" >&2
      return 1
    fi
    sleep 2
  done
  echo "Timed out waiting for $workflow to reach $expected" >&2
  return 1
}

curl -fsS "$API_URL/api/health" | grep -q 'ok'
curl -fsS "$API_URL/api/node-types" | grep -q 'model-admission-gate'
curl -fsS -H 'Content-Type: application/json' --data-binary "@$PROJECT_ROOT/examples/training-qualification-pipeline.json" "$API_URL/api/pipelines/validate" | grep -q '"valid":true'

python3 - "$PROJECT_ROOT/examples/training-qualification-pipeline.json" "$TMP_DIR/approved.json" <<'PY'
import json,sys
value=json.load(open(sys.argv[1],encoding="utf-8"))
value["metadata"]["tags"].append("system-test")
json.dump(value,open(sys.argv[2],"w",encoding="utf-8"))
PY
workflow="$(submit_pipeline "$TMP_DIR/approved.json")"
echo "Submitted $workflow"

run="$(wait_for_status "$workflow" SUCCEEDED 360)"

python3 - "$run" <<'PY'
import json,sys
r=json.loads(sys.argv[1]); nodes={n['nodeId']:n for n in r['nodes']}
assert r['pipelineDefinition']['metadata']['name']=='comment-classification-demo'
assert r['definitionDigest'] and len(r['definitionDigest'])==12
a,b=nodes['train-baseline'],nodes['train-candidate']
assert a['startedAt'] < b['finishedAt'] and b['startedAt'] < a['finishedAt'], 'training intervals did not overlap'
assert nodes['register']['status']=='SUCCEEDED'
assert nodes['inference-smoke']['status']=='SUCCEEDED'
assert nodes['deployment']['status']=='SUCCEEDED'
assert nodes['approved-report']['status']=='SUCCEEDED'
assert nodes['rejected-report']['status']=='SKIPPED'
PY
curl -fsS "$API_URL/api/runs/$workflow/nodes/train-baseline/logs" | grep -q 'training completed'
curl -fsS "$API_URL/api/runs/$workflow/nodes/leaderboard/output" | grep -q 'LeaderboardRef'
curl -fsS "$API_URL/api/runs/$workflow/nodes/admission/output" | grep -q 'APPROVED'
curl -fsS "$API_URL/api/runs/$workflow/nodes/inference-smoke/output" | grep -q 'InferenceTestRef'
curl -fsS "$API_URL/api/runs/$workflow/nodes/deployment/output" | grep -q 'READY_FOR_PLATFORM'

python3 - "$PROJECT_ROOT/examples/training-qualification-pipeline.json" "$TMP_DIR/rejected.json" <<'PY'
import json,sys
value=json.load(open(sys.argv[1],encoding="utf-8"))
value["metadata"]["name"]="training-qualification-rejected"
value["metadata"]["tags"].append("system-test")
for node in value["spec"]["nodes"]:
    if node["id"] == "admission":
        node["parameters"]["minAccuracy"]=0.99
    if "durationSeconds" in node["parameters"]:
        node["parameters"]["durationSeconds"]=1
json.dump(value,open(sys.argv[2],"w",encoding="utf-8"))
PY
rejected_workflow="$(submit_pipeline "$TMP_DIR/rejected.json")"
rejected_run="$(wait_for_status "$rejected_workflow" SUCCEEDED 240)"
python3 - "$rejected_run" <<'PY'
import json,sys
nodes={item["nodeId"]:item for item in json.loads(sys.argv[1])["nodes"]}
assert nodes["register"]["status"] == "SKIPPED"
assert nodes["inference-smoke"]["status"] == "SKIPPED"
assert nodes["deployment"]["status"] == "SKIPPED"
assert nodes["approved-report"]["status"] == "SKIPPED"
assert nodes["rejected-report"]["status"] == "SUCCEEDED"
PY
curl -fsS "$API_URL/api/runs/$rejected_workflow/nodes/admission/output" | grep -q 'REJECTED'

python3 - "$PROJECT_ROOT/examples/training-qualification-pipeline.json" "$TMP_DIR/failing.json" <<'PY'
import json,sys
value=json.load(open(sys.argv[1],encoding="utf-8"))
value["metadata"]["tags"].append("system-test")
for node in value["spec"]["nodes"]:
    if node["id"] == "train-baseline":
        node["parameters"].update(failMode="always", retryLimit=2, durationSeconds=1)
    elif node["type"] == "train-model":
        node["parameters"]["durationSeconds"]=1
json.dump(value,open(sys.argv[2],"w",encoding="utf-8"))
PY
failed_workflow="$(submit_pipeline "$TMP_DIR/failing.json")"
failed_run="$(wait_for_status "$failed_workflow" FAILED 180)"
python3 - "$failed_run" <<'PY'
import json,sys
nodes={item["nodeId"]:item for item in json.loads(sys.argv[1])["nodes"]}
assert nodes["train-baseline"]["retryCount"] >= 2, nodes["train-baseline"]
PY
curl -fsS "$API_URL/api/runs/$failed_workflow/nodes/train-baseline/logs" | grep -q 'fixed failure requested'

python3 - "$PROJECT_ROOT/examples/training-qualification-pipeline.json" "$TMP_DIR/stoppable.json" <<'PY'
import json,sys
value=json.load(open(sys.argv[1],encoding="utf-8"))
value["metadata"]["tags"].append("system-test")
for node in value["spec"]["nodes"]:
    if "durationSeconds" in node["parameters"]:
        node["parameters"]["durationSeconds"]=60
json.dump(value,open(sys.argv[2],"w",encoding="utf-8"))
PY
stopped_workflow="$(submit_pipeline "$TMP_DIR/stoppable.json")"
wait_for_status "$stopped_workflow" RUNNING 90 >/dev/null
curl -fsS -X POST "$API_URL/api/runs/$stopped_workflow/stop" | grep -q 'CANCELLED'
wait_for_status "$stopped_workflow" CANCELLED 90 >/dev/null

echo "Smoke test passed: health, registry, validation, recoverable definition snapshot, approved/rejected gates, parallel training, inference smoke, deployment handoff, logs, retries, and manual stop."
