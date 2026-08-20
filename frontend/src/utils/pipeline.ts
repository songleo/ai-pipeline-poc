import type { Edge, Node } from '@vue-flow/core'
import type { NodeTypeDefinition, Pipeline, PipelineNode, UnifiedStatus, ValidationResult } from '../types/pipeline'

export interface PipelineNodeData { definition: NodeTypeDefinition; pipelineNode: PipelineNode; status: UnifiedStatus }

export function defaultParameters(definition: NodeTypeDefinition): Record<string, unknown> {
  return Object.fromEntries(Object.entries(definition.parametersSchema.properties).flatMap(([key, value]) => value.default === undefined ? [] : [[key, value.default]]))
}

export function pipelineToFlow(pipeline: Pipeline, registry: NodeTypeDefinition[]): { nodes: Node<PipelineNodeData>[]; edges: Edge[] } {
  const definitions = new Map(registry.map(item => [item.type, item]))
  return {
    nodes: pipeline.spec.nodes.map(node => ({
      id: node.id, type: 'pipeline', position: pipeline.uiLayout.nodes[node.id] ?? { x: 0, y: 0 },
      data: { definition: definitions.get(node.type)!, pipelineNode: structuredClone(node), status: 'IDLE' },
    })),
    edges: pipeline.spec.edges.map((edge, index) => ({ id: `e-${index}-${edge.source}-${edge.target}`, source: edge.source, sourceHandle: edge.sourcePort, target: edge.target, targetHandle: edge.targetPort, animated: false })),
  }
}

export function flowToPipeline(name: string, nodes: Node<PipelineNodeData>[], edges: Edge[], timeoutSeconds = 300): Pipeline {
  return {
    apiVersion: 'demo.pipeline.io/v1alpha1', kind: 'Pipeline', metadata: { name },
    spec: {
      nodes: nodes.map(node => JSON.parse(JSON.stringify(node.data!.pipelineNode)) as PipelineNode),
      edges: edges.map(edge => ({ source: edge.source, sourcePort: edge.sourceHandle ?? '', target: edge.target, targetPort: edge.targetHandle ?? '' })),
      runPolicy: { timeoutSeconds },
    },
    uiLayout: { nodes: Object.fromEntries(nodes.map(node => [node.id, { x: node.position.x, y: node.position.y }])) },
  }
}

export function validateLocally(pipeline: Pipeline, registry: NodeTypeDefinition[]): ValidationResult {
  const errors: ValidationResult['errors'] = []
  const definitions = new Map(registry.map(item => [item.type, item]))
  const ids = new Set(pipeline.spec.nodes.map(item => item.id))
  for (const edge of pipeline.spec.edges) {
    const source = pipeline.spec.nodes.find(item => item.id === edge.source); const target = pipeline.spec.nodes.find(item => item.id === edge.target)
    if (!source || !target) { errors.push({ code: 'UNKNOWN_EDGE_NODE', message: '连线引用了不存在的节点。' }); continue }
    const output = definitions.get(source.type)?.outputPorts.find(item => item.name === edge.sourcePort)
    const input = definitions.get(target.type)?.inputPorts.find(item => item.name === edge.targetPort)
    if (!output || !input) errors.push({ code: 'UNKNOWN_PORT', message: '连线端口不存在。', nodeId: target.id })
    else if (output.type !== input.type) errors.push({ code: 'PORT_TYPE_MISMATCH', message: `${output.type} 不能连接到 ${input.type}。`, nodeId: target.id })
  }
  if (ids.size !== pipeline.spec.nodes.length) errors.push({ code: 'DUPLICATE_NODE_ID', message: '节点 ID 必须唯一。' })
  return { valid: errors.length === 0, errors, warnings: [] }
}

export const terminalStatuses = new Set<UnifiedStatus>(['SUCCEEDED', 'FAILED', 'ERROR', 'CANCELLED'])
