import type { NodeTypeDefinition, Pipeline, RunDetail, ValidationResult } from '../types/pipeline'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) } })
  const body = await response.json().catch(() => ({ detail: response.statusText }))
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body))
  return body as T
}
export const api = {
  nodeTypes: () => request<NodeTypeDefinition[]>('/api/node-types'),
  validate: (pipeline: Pipeline) => request<ValidationResult>('/api/pipelines/validate', { method: 'POST', body: JSON.stringify(pipeline) }),
  compile: (pipeline: Pipeline) => request<{ workflow: Record<string, unknown>; yaml: string }>('/api/pipelines/compile', { method: 'POST', body: JSON.stringify(pipeline) }),
  run: (pipeline: Pipeline) => request<{ workflowName: string; status: string }>('/api/runs', { method: 'POST', body: JSON.stringify(pipeline) }),
  runDetail: (name: string) => request<RunDetail>(`/api/runs/${encodeURIComponent(name)}`),
  stop: (name: string) => request<{ workflowName: string; status: string; message: string }>(`/api/runs/${encodeURIComponent(name)}/stop`, { method: 'POST' }),
  stopNode: (name: string, nodeId: string) => request<{ workflowName: string; nodeId: string; status: string; controlState: string; message: string }>(`/api/runs/${encodeURIComponent(name)}/nodes/${encodeURIComponent(nodeId)}/stop`, { method: 'POST' }),
  rerunNode: (name: string, nodeId: string) => request<{ workflowName: string; nodeId: string; status: string; message: string }>(`/api/runs/${encodeURIComponent(name)}/nodes/${encodeURIComponent(nodeId)}/rerun`, { method: 'POST' }),
  logs: (name: string, nodeId: string) => request<{ nodeId: string; logs: string }>(`/api/runs/${encodeURIComponent(name)}/nodes/${encodeURIComponent(nodeId)}/logs`),
  output: (name: string, nodeId: string) => request<{ nodeId: string; outputs: Record<string, unknown> }>(`/api/runs/${encodeURIComponent(name)}/nodes/${encodeURIComponent(nodeId)}/output`),
}
