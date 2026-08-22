import { addEdge, type Connection, type Edge, type Node } from '@vue-flow/core'
import type { NodeTypeDefinition, Pipeline, PipelineNode, UnifiedStatus, ValidationResult } from '../types/pipeline'

export interface PipelineNodeData { definition: NodeTypeDefinition; pipelineNode: PipelineNode; status: UnifiedStatus; validationError?: boolean }
export interface ConnectFlowResult { edges: Edge[]; error?: string }
export interface FlowMutationResult { nodes: Node<PipelineNodeData>[]; edges: Edge[] }

export function connectionError(nodes: Node<PipelineNodeData>[], edges: Edge[], connection: Connection): string | undefined {
  const source = nodes.find(item => item.id === connection.source)
  const target = nodes.find(item => item.id === connection.target)
  const output = source?.data?.definition.outputPorts.find(item => item.name === connection.sourceHandle)
  const input = target?.data?.definition.inputPorts.find(item => item.name === connection.targetHandle)
  if (!source || !target || !output || !input || output.type !== input.type) return '端口类型不兼容'
  if (source.id === target.id) return '节点不能连接到自身'
  if (edges.some(edge => edge.source === source.id && edge.sourceHandle === connection.sourceHandle && edge.target === target.id && edge.targetHandle === connection.targetHandle)) return '该连线已经存在'
  if (!input.multiple && edges.some(edge => edge.target === target.id && edge.targetHandle === connection.targetHandle)) return '该输入端口只能连接一次'

  const children = new Map(nodes.map(node => [node.id, [] as string[]]))
  for (const edge of edges) children.get(edge.source)?.push(edge.target)
  const stack = [target.id]
  const visited = new Set<string>()
  while (stack.length) {
    const nodeId = stack.pop()!
    if (nodeId === source.id) return '该连线会形成环路'
    if (visited.has(nodeId)) continue
    visited.add(nodeId)
    stack.push(...(children.get(nodeId) ?? []))
  }
  return undefined
}

export function defaultParameters(definition: NodeTypeDefinition): Record<string, unknown> {
  return Object.fromEntries(Object.entries(definition.parametersSchema.properties).flatMap(([key, value]) => value.default === undefined ? [] : [[key, value.default]]))
}

export function appendFlowNode(
  nodes: Node<PipelineNodeData>[],
  definition: NodeTypeDefinition,
  position: { x: number; y: number },
  id: string,
): Node<PipelineNodeData>[] {
  return [...nodes, {
    id,
    type: 'pipeline',
    position,
    data: {
      definition,
      status: 'IDLE',
      pipelineNode: {
        id,
        type: definition.type,
        version: definition.version,
        name: definition.displayName,
        parameters: defaultParameters(definition),
      },
    },
  }]
}

export function connectFlowNodes(
  nodes: Node<PipelineNodeData>[],
  edges: Edge[],
  connection: Connection,
): ConnectFlowResult {
  const error = connectionError(nodes, edges, connection)
  if (error) return { edges, error }
  const source = nodes.find(item => item.id === connection.source)!
  const output = source.data!.definition.outputPorts.find(item => item.name === connection.sourceHandle)!
  const condition = source?.data?.definition.branchConditions?.[connection.sourceHandle ?? '']
  const semanticLabel = condition ? `${connection.sourceHandle} · ${condition.value === 'APPROVED' ? '通过' : '拒绝'}` : `${output.name} · ${output.type}`
  return { edges: addEdge({ ...connection, label: semanticLabel, labelBgPadding: [7, 4], labelBgBorderRadius: 4 }, [...edges]) as Edge[] }
}

export function removeFlowNode(nodes: Node<PipelineNodeData>[], edges: Edge[], nodeId: string): FlowMutationResult {
  return {
    nodes: nodes.filter(node => node.id !== nodeId),
    edges: edges.filter(edge => edge.source !== nodeId && edge.target !== nodeId),
  }
}

export function clearFlow(): FlowMutationResult {
  return { nodes: [], edges: [] }
}

export function autoLayoutFlow(nodes: Node<PipelineNodeData>[], edges: Edge[]): Node<PipelineNodeData>[] {
  const indegree = new Map(nodes.map(node => [node.id, 0]))
  const children = new Map(nodes.map(node => [node.id, [] as string[]]))
  for (const edge of edges) {
    if (!indegree.has(edge.source) || !indegree.has(edge.target)) continue
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1)
    children.get(edge.source)?.push(edge.target)
  }
  const layer = new Map<string, number>()
  const queue = nodes.filter(node => indegree.get(node.id) === 0).map(node => node.id)
  for (const id of queue) layer.set(id, 0)
  for (let index = 0; index < queue.length; index += 1) {
    const source = queue[index]
    for (const target of children.get(source) ?? []) {
      layer.set(target, Math.max(layer.get(target) ?? 0, (layer.get(source) ?? 0) + 1))
      indegree.set(target, (indegree.get(target) ?? 1) - 1)
      if (indegree.get(target) === 0) queue.push(target)
    }
  }
  const fallbackLayer = Math.max(0, ...layer.values()) + 1
  for (const node of nodes) if (!layer.has(node.id)) layer.set(node.id, fallbackLayer)
  const rows = new Map<number, string[]>()
  for (const node of nodes) {
    const column = layer.get(node.id) ?? fallbackLayer
    const bucket = rows.get(column) ?? []
    bucket.push(node.id)
    rows.set(column, bucket)
  }
  return nodes.map(node => {
    const column = layer.get(node.id) ?? 0
    const row = rows.get(column)?.indexOf(node.id) ?? 0
    return { ...node, position: { x: 70 + column * 255, y: 55 + row * 145 } }
  })
}

export function pipelineToFlow(pipeline: Pipeline, registry: NodeTypeDefinition[]): { nodes: Node<PipelineNodeData>[]; edges: Edge[] } {
  const definitions = new Map(registry.map(item => [item.type, item]))
  return {
    nodes: pipeline.spec.nodes.map(node => ({
      id: node.id, type: 'pipeline', position: pipeline.uiLayout.nodes[node.id] ?? { x: 0, y: 0 },
      data: { definition: definitions.get(node.type)!, pipelineNode: structuredClone(node), status: 'IDLE' },
    })),
    edges: pipeline.spec.edges.map((edge, index) => {
      const source = pipeline.spec.nodes.find(item => item.id === edge.source)
      const definition = source ? definitions.get(source.type) : undefined
      const output = definition?.outputPorts.find(item => item.name === edge.sourcePort)
      const condition = definition?.branchConditions?.[edge.sourcePort]
      return { id: `e-${index}-${edge.source}-${edge.target}`, source: edge.source, sourceHandle: edge.sourcePort, target: edge.target, targetHandle: edge.targetPort, animated: false,
        label: condition ? `${edge.sourcePort} · ${condition.value === 'APPROVED' ? '通过' : '拒绝'}` : `${edge.sourcePort} · ${output?.type ?? 'Artifact'}`,
        labelBgPadding: [7, 4] as [number, number], labelBgBorderRadius: 4 }
    }),
  }
}

export function flowToPipeline(name: string, experimentName: string, tags: string[], nodes: Node<PipelineNodeData>[], edges: Edge[], timeoutSeconds = 300, version?: number): Pipeline {
  return {
    apiVersion: 'demo.pipeline.io/v1alpha1', kind: 'Pipeline', metadata: { name, experimentName, scenario: 'training-evaluation-admission', tags, ...(version ? { version } : {}) },
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
  if (!pipeline.spec.nodes.length) errors.push({ code: 'EMPTY_PIPELINE', message: 'Pipeline 至少需要一个节点。' })
  for (const node of pipeline.spec.nodes) {
    const definition = definitions.get(node.type)
    if (!definition) { errors.push({ code: 'UNKNOWN_NODE_TYPE', message: `节点类型 ${node.type} 不在受控 Registry 中。`, nodeId: node.id }); continue }
    for (const required of definition.parametersSchema.required ?? []) {
      if (!(required in node.parameters)) errors.push({ code: 'MISSING_PARAMETER', message: `缺少必填参数：${required}。`, nodeId: node.id, field: `parameters.${required}` })
    }
    for (const input of definition.inputPorts.filter(port => port.required)) {
      if (!pipeline.spec.edges.some(edge => edge.target === node.id && edge.targetPort === input.name)) {
        errors.push({ code: 'MISSING_INPUT', message: `必填输入 ${input.name}: ${input.type} 尚未连接。`, nodeId: node.id, field: `inputs.${input.name}` })
      }
    }
  }
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
