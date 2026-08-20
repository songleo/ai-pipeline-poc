#!/usr/bin/env bash
set -uo pipefail
source "$(dirname "$0")/lib.sh"

status=0
check() {
  local command_name="$1"
  if command -v "$command_name" >/dev/null 2>&1; then
    printf 'OK   %-10s %s\n' "$command_name" "$(command -v "$command_name")"
  else
    printf 'MISS %-10s required\n' "$command_name"
    status=1
  fi
}

owned_port_forward() {
  local port="$1" name pid_file pid command_line
  case "$port" in
    5173) name="frontend" ;;
    8000) name="backend" ;;
    2746) name="argo" ;;
    *) return 1 ;;
  esac
  pid_file="$PROJECT_ROOT/.port-forward-$name.pid"
  [[ -f "$pid_file" ]] || return 1
  pid="$(cat "$pid_file")"
  kill -0 "$pid" 2>/dev/null || return 1
  command_line="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  [[ "$command_line" == *"kubectl --context $EXPECTED_CONTEXT"*"port-forward"*"$port:"* ]]
}

if command -v uname >/dev/null 2>&1; then
  echo "OS: $(uname -a)"
else
  echo "OS: ${OSTYPE:-unknown} (uname unavailable)"
fi
for item in docker kind kubectl helm node npm python3 jq; do check "$item"; done

if command -v docker >/dev/null 2>&1; then
  docker version || status=1
fi
command -v kind >/dev/null 2>&1 && kind version || true
command -v kubectl >/dev/null 2>&1 && kubectl version --client || true
command -v helm >/dev/null 2>&1 && helm version || true
command -v node >/dev/null 2>&1 && node --version || true
command -v python3 >/dev/null 2>&1 && python3 --version || true

for port in 5173 8000 8080 2746; do
  if command -v ss >/dev/null 2>&1 && ss -ltn "sport = :$port" | tail -n +2 | grep -q .; then
    if owned_port_forward "$port"; then
      echo "OWNED port $port (pipeline-demo port-forward)"
    else
      echo "BUSY port $port"
      status=1
    fi
  elif command -v python3 >/dev/null 2>&1; then
    if python3 -c "import socket; s=socket.socket(); s.settimeout(.2); raise SystemExit(0 if s.connect_ex(('127.0.0.1',$port)) else 1)"; then
      echo "FREE port $port"
    else
      if owned_port_forward "$port"; then
        echo "OWNED port $port (pipeline-demo port-forward)"
      else
        echo "BUSY port $port"
        status=1
      fi
    fi
  else
    echo "UNKNOWN port $port (need ss or python3)"
    status=1
  fi
done

if (( status != 0 )); then
  echo 'Preflight failed. Resolve the MISS, BUSY, or UNKNOWN items above. No installation was attempted.'
fi
exit "$status"

