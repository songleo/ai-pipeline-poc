from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Metadata(BaseModel):
    name: str


class PipelineNode(BaseModel):
    id: str
    type: str
    version: str = "1.0.0"
    name: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    source: str
    sourcePort: str
    target: str
    targetPort: str


class RunPolicy(BaseModel):
    timeoutSeconds: int = Field(default=300, ge=1, le=3600)


class PipelineSpec(BaseModel):
    nodes: list[PipelineNode]
    edges: list[Edge]
    runPolicy: RunPolicy = Field(default_factory=RunPolicy)


class Position(BaseModel):
    x: float
    y: float


class UiLayout(BaseModel):
    nodes: dict[str, Position] = Field(default_factory=dict)


class Pipeline(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    apiVersion: Literal["demo.ssli.io/v1alpha1"]
    kind: Literal["Pipeline"]
    metadata: Metadata
    spec: PipelineSpec
    uiLayout: UiLayout = Field(default_factory=UiLayout)


class ValidationIssue(BaseModel):
    code: str
    message: str
    nodeId: str | None = None
    field: str | None = None


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
