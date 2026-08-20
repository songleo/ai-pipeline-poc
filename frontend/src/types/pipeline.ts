export type UnifiedStatus = 'IDLE' | 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'ERROR' | 'CANCELLED' | 'SKIPPED'

export interface PortDefinition { name: string; type: string; required: boolean; multiple: boolean }
export interface ParameterProperty { type: 'string' | 'integer' | 'number' | 'boolean'; default?: unknown; minimum?: number; maximum?: number; enum?: string[]; minLength?: number; maxLength?: number }
export interface NodeTypeDefinition {
  type: string; version: string; displayName: string; description: string; category: string
  parametersSchema: { type: 'object'; required?: string[]; properties: Record<string, ParameterProperty> }
  uiSchema: { order?: string[] }; inputPorts: PortDefinition[]; outputPorts: PortDefinition[]
  workflowTemplateName: string; templateName: string; defaultRetryLimit: number; defaultTimeoutSeconds: number
}
export interface PipelineNode { id: string; type: string; version: string; name?: string; parameters: Record<string, unknown> }
export interface PipelineEdge { source: string; sourcePort: string; target: string; targetPort: string }
export interface Pipeline {
  apiVersion: 'demo.ssli.io/v1alpha1'; kind: 'Pipeline'; metadata: { name: string }
  spec: { nodes: PipelineNode[]; edges: PipelineEdge[]; runPolicy: { timeoutSeconds: number } }
  uiLayout: { nodes: Record<string, { x: number; y: number }> }
}
export interface ValidationIssue { code: string; message: string; nodeId?: string; field?: string }
export interface ValidationResult { valid: boolean; errors: ValidationIssue[]; warnings: ValidationIssue[] }
export interface RunNode {
  nodeId: string; taskName: string; status: UnifiedStatus; startedAt?: string; finishedAt?: string
  duration?: number; message?: string; retryCount: number; podName?: string; outputs: Record<string, unknown>
}
export interface RunDetail { workflowName: string; pipelineName: string; status: UnifiedStatus; startedAt?: string; finishedAt?: string; message?: string; nodes: RunNode[] }
