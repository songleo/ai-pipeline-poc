export type UnifiedStatus = 'IDLE' | 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'ERROR' | 'CANCELLED' | 'SKIPPED'

export interface PortDefinition { name: string; type: string; required: boolean; multiple: boolean }
export interface ParameterProperty { type: 'string' | 'integer' | 'number' | 'boolean'; default?: unknown; minimum?: number; maximum?: number; enum?: string[]; minLength?: number; maxLength?: number }
export interface ParameterUi { label: string; group: string; unit?: string; help?: string; simulation?: boolean }
export interface NodeTypeDefinition {
  type: string; version: string; displayName: string; description: string; category: string
  parametersSchema: { type: 'object'; required?: string[]; properties: Record<string, ParameterProperty> }
  uiSchema: { order?: string[]; fields?: Record<string, ParameterUi> }; inputPorts: PortDefinition[]; outputPorts: PortDefinition[]
  workflowTemplateName: string; templateName: string; defaultRetryLimit: number; defaultTimeoutSeconds: number
  branchConditions?: Record<string, { output: string; value: string }>
}
export interface PipelineNode { id: string; type: string; version: string; name?: string; parameters: Record<string, unknown> }
export interface PipelineEdge { source: string; sourcePort: string; target: string; targetPort: string }
export interface Pipeline {
  apiVersion: 'demo.pipeline.io/v1alpha1'; kind: 'Pipeline'; metadata: { name: string; experimentName: string; scenario: string; tags: string[]; version?: number }
  spec: { nodes: PipelineNode[]; edges: PipelineEdge[]; runPolicy: { timeoutSeconds: number } }
  uiLayout: { nodes: Record<string, { x: number; y: number }> }
}
export interface ValidationIssue { code: string; message: string; nodeId?: string; field?: string }
export interface ValidationResult { valid: boolean; errors: ValidationIssue[]; warnings: ValidationIssue[] }
export interface RunNode {
  nodeId: string; taskName: string; status: UnifiedStatus; startedAt?: string; finishedAt?: string
  duration?: number; message?: string; retryCount: number; podName?: string; outputs: Record<string, unknown>
  controlState?: 'STOP_REQUESTED'; canStop: boolean; canRerun: boolean
}
export interface RunDetail { workflowName: string; pipelineName: string; experimentName?: string; scenario?: string; tags: string[]; definitionVersion?: number; definitionDigest?: string; pipelineDefinition?: Pipeline; status: UnifiedStatus; startedAt?: string; finishedAt?: string; message?: string; nodes: RunNode[] }
export interface PipelineCatalogEntry {
  id: string; name: string; description: string; version: number; source: 'template' | 'local'; updatedAt: string; pipeline: Pipeline
}
