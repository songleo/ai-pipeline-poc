from functools import lru_cache

import yaml
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from kubernetes.client.exceptions import ApiException

from app.compiler import compile_pipeline, validate_pipeline
from app.kubernetes import KubernetesWorkflowClient, workflow_detail
from app.models.pipeline import Pipeline
from app.registry import get_node_type, list_node_types


app = FastAPI(title="ssli-demo Pipeline API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


@lru_cache
def workflow_client() -> KubernetesWorkflowClient:
    return KubernetesWorkflowClient()


def _kube_error(exc: ApiException) -> HTTPException:
    if exc.status == 404:
        return HTTPException(404, "Workflow not found")
    return HTTPException(503, f"Kubernetes API error ({exc.status}): {exc.reason}")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/node-types")
def node_types() -> list[dict]:
    return list_node_types()


@app.get("/api/node-types/{node_type}")
def node_type(node_type: str) -> dict:
    definition = get_node_type(node_type)
    if not definition:
        raise HTTPException(404, "Node type not found")
    return definition


@app.post("/api/pipelines/validate")
def validate(pipeline: Pipeline) -> dict:
    return validate_pipeline(pipeline).model_dump(mode="json")


@app.post("/api/pipelines/compile")
def compile_only(pipeline: Pipeline) -> dict:
    validation = validate_pipeline(pipeline)
    if not validation.valid:
        raise HTTPException(422, validation.model_dump(mode="json"))
    workflow = compile_pipeline(pipeline)
    return {"workflow": workflow, "yaml": yaml.safe_dump(workflow, sort_keys=False, allow_unicode=True)}


@app.post("/api/runs", status_code=201)
def create_run(pipeline: Pipeline, kube: KubernetesWorkflowClient = Depends(workflow_client)) -> dict:
    validation = validate_pipeline(pipeline)
    if not validation.valid:
        raise HTTPException(422, validation.model_dump(mode="json"))
    try:
        created = kube.create(compile_pipeline(pipeline))
    except ApiException as exc:
        raise _kube_error(exc) from exc
    return {"workflowName": created["metadata"]["name"], "status": "PENDING"}


@app.get("/api/runs")
def list_runs(kube: KubernetesWorkflowClient = Depends(workflow_client)) -> list[dict]:
    try:
        return [workflow_detail(item) for item in kube.list()]
    except ApiException as exc:
        raise _kube_error(exc) from exc


@app.get("/api/runs/{workflow_name}")
def get_run(workflow_name: str, kube: KubernetesWorkflowClient = Depends(workflow_client)) -> dict:
    try:
        return workflow_detail(kube.get(workflow_name))
    except ApiException as exc:
        raise _kube_error(exc) from exc


@app.get("/api/runs/{workflow_name}/nodes/{node_id}/logs")
def node_logs(workflow_name: str, node_id: str, kube: KubernetesWorkflowClient = Depends(workflow_client)) -> dict:
    try:
        return {"nodeId": node_id, "logs": kube.logs(kube.get(workflow_name), node_id)}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ApiException as exc:
        raise _kube_error(exc) from exc


@app.get("/api/runs/{workflow_name}/nodes/{node_id}/output")
def node_output(workflow_name: str, node_id: str, kube: KubernetesWorkflowClient = Depends(workflow_client)) -> dict:
    try:
        detail = workflow_detail(kube.get(workflow_name))
    except ApiException as exc:
        raise _kube_error(exc) from exc
    node = next((item for item in detail["nodes"] if item["nodeId"] == node_id), None)
    if not node:
        raise HTTPException(404, "Pipeline node not found")
    return {"nodeId": node_id, "outputs": node["outputs"]}


@app.post("/api/runs/{workflow_name}/stop")
def stop_run(workflow_name: str, kube: KubernetesWorkflowClient = Depends(workflow_client)) -> dict:
    try:
        return kube.stop(workflow_name)
    except ApiException as exc:
        raise _kube_error(exc) from exc
