"""Stable boundary for replacing the PoC executor with ai-platform capabilities later."""

from dataclasses import dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class PlatformContext:
    project_id: str
    tenant_id: str
    actor_id: str


@dataclass(frozen=True)
class CapabilityRequest:
    capability: str
    version: str
    inputs: Mapping[str, Any]
    parameters: Mapping[str, Any]
    idempotency_key: str


@dataclass(frozen=True)
class CapabilityRun:
    external_id: str
    status: str
    outputs: Mapping[str, Any]


class PipelineCapabilityAdapter(Protocol):
    def start(self, context: PlatformContext, request: CapabilityRequest) -> CapabilityRun: ...

    def get(self, context: PlatformContext, external_id: str) -> CapabilityRun: ...

    def cancel(self, context: PlatformContext, external_id: str) -> CapabilityRun: ...
