import json
import os
import sys
import time
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen


CONTROL_STOP_EXIT_CODE = 64


def _control_url(workflow_name: str, node_id: str) -> str:
    base = os.getenv("PIPELINE_CONTROL_URL", "http://pipeline-demo-backend:8000").rstrip("/")
    return f"{base}/api/internal/runs/{quote(workflow_name, safe='')}/nodes/{quote(node_id, safe='')}/control"


def ensure_node_running(workflow_name: str, node_id: str) -> None:
    try:
        with urlopen(_control_url(workflow_name, node_id), timeout=1) as response:
            control = json.load(response).get("controlState")
    except (OSError, URLError, ValueError):
        return
    if control == "STOP_REQUESTED":
        print(f"[{node_id}] stop requested; exiting without automatic retry", flush=True)
        sys.exit(CONTROL_STOP_EXIT_CODE)


def controlled_sleep(workflow_name: str, node_id: str, duration_seconds: float) -> None:
    deadline = time.monotonic() + max(0, duration_seconds)
    while True:
        ensure_node_running(workflow_name, node_id)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(1, remaining))
