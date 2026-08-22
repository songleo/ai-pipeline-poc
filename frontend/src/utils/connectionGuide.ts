import type { Edge, Node } from '@vue-flow/core'
import type { InjectionKey, Ref } from 'vue'
import type { NodeTypeDefinition, PortDefinition } from '../types/pipeline'
import { connectionError, type PipelineNodeData } from './pipeline'

export type RecommendationDirection = 'downstream' | 'upstream'

export interface ConnectionRecommendation {
  id: string
  direction: RecommendationDirection
  definition: NodeTypeDefinition
  sourcePort: string
  targetPort: string
  artifactType: string
  autoConnect: boolean
  missingAfterConnect: PortDefinition[]
  existingNodeId?: string
  displayName?: string
  proximity?: number
}

export interface PaletteCompatibility {
  downstream: boolean
  upstream: boolean
}

export interface ActiveConnectionHint { artifactType: string; handleType: 'source' | 'target' }
export const connectionHintKey = Symbol('pipelineConnectionHint') as InjectionKey<Ref<ActiveConnectionHint | undefined>>

export function missingRequiredInputs(node: Node<PipelineNodeData>, edges: Edge[]): PortDefinition[] {
  return node.data?.definition.inputPorts.filter(port => port.required && !edges.some(edge => edge.target === node.id && edge.targetHandle === port.name)) ?? []
}

export function connectionRecommendations(
  selected: Node<PipelineNodeData> | undefined,
  nodes: Node<PipelineNodeData>[],
  edges: Edge[],
  registry: NodeTypeDefinition[],
): ConnectionRecommendation[] {
  if (!selected?.data) return []
  const missingInputs = missingRequiredInputs(selected, edges)
  const result: ConnectionRecommendation[] = []
  const distance = (sourceId: string, targetId: string) => {
    const children = new Map(nodes.map(node => [node.id, [] as string[]]))
    for (const edge of edges) children.get(edge.source)?.push(edge.target)
    const queue = [{ id: sourceId, depth: 0 }]
    const visited = new Set<string>()
    while (queue.length) {
      const current = queue.shift()!
      if (current.id === targetId) return current.depth
      if (visited.has(current.id)) continue
      visited.add(current.id)
      queue.push(...(children.get(current.id) ?? []).map(id => ({ id, depth: current.depth + 1 })))
    }
    return Number.MAX_SAFE_INTEGER
  }

  for (const candidate of nodes.filter(node => node.id !== selected.id && node.data)) {
    const downstreamPairs = selected.data.definition.outputPorts.flatMap(output => candidate.data!.definition.inputPorts
      .filter(input => input.type === output.type)
      .map(input => ({ output, input, connection: { source: selected.id, sourceHandle: output.name, target: candidate.id, targetHandle: input.name } })))
      .filter(pair => !connectionError(nodes, edges, pair.connection))
    if (downstreamPairs.length) {
      const pair = downstreamPairs[0]
      result.push({
        id: `existing-downstream:${candidate.id}:${pair.output.name}:${pair.input.name}`,
        direction: 'downstream', definition: candidate.data!.definition, sourcePort: pair.output.name, targetPort: pair.input.name,
        artifactType: pair.output.type, autoConnect: downstreamPairs.length === 1, existingNodeId: candidate.id,
        displayName: candidate.data!.pipelineNode.name,
        proximity: distance(selected.id, candidate.id),
        missingAfterConnect: candidate.data!.definition.inputPorts.filter(port => port.required && port.name !== pair.input.name && !edges.some(edge => edge.target === candidate.id && edge.targetHandle === port.name)),
      })
    }

    const upstreamPairs = candidate.data!.definition.outputPorts.flatMap(output => missingInputs
      .filter(input => input.type === output.type)
      .map(input => ({ output, input, connection: { source: candidate.id, sourceHandle: output.name, target: selected.id, targetHandle: input.name } })))
      .filter(pair => !connectionError(nodes, edges, pair.connection))
    if (upstreamPairs.length) {
      const pair = upstreamPairs[0]
      result.push({
        id: `existing-upstream:${candidate.id}:${pair.output.name}:${pair.input.name}`,
        direction: 'upstream', definition: candidate.data!.definition, sourcePort: pair.output.name, targetPort: pair.input.name,
        artifactType: pair.output.type, autoConnect: upstreamPairs.length === 1, existingNodeId: candidate.id,
        displayName: candidate.data!.pipelineNode.name, proximity: distance(candidate.id, selected.id), missingAfterConnect: [],
      })
    }
  }

  for (const definition of registry) {
    const downstreamPairs = selected.data.definition.outputPorts.flatMap(output => definition.inputPorts
      .filter(input => input.type === output.type)
      .map(input => ({ output, input })))
    if (downstreamPairs.length) {
      const pair = downstreamPairs[0]
      result.push({
        id: `downstream:${definition.type}:${pair.output.name}:${pair.input.name}`,
        direction: 'downstream', definition, sourcePort: pair.output.name, targetPort: pair.input.name,
        artifactType: pair.output.type, autoConnect: downstreamPairs.length === 1,
        missingAfterConnect: definition.inputPorts.filter(port => port.required && port.name !== pair.input.name),
      })
    }

    const upstreamPairs = definition.outputPorts.flatMap(output => missingInputs
      .filter(input => input.type === output.type)
      .map(input => ({ output, input })))
    if (upstreamPairs.length) {
      const pair = upstreamPairs[0]
      result.push({
        id: `upstream:${definition.type}:${pair.output.name}:${pair.input.name}`,
        direction: 'upstream', definition, sourcePort: pair.output.name, targetPort: pair.input.name,
        artifactType: pair.output.type, autoConnect: upstreamPairs.length === 1,
        missingAfterConnect: [],
      })
    }
  }

  const directionRank = (direction: RecommendationDirection) => direction === 'downstream' ? 0 : 1
  return result.sort((left, right) =>
    (left.existingNodeId ? 0 : 1) - (right.existingNodeId ? 0 : 1)
    || (left.proximity ?? Number.MAX_SAFE_INTEGER) - (right.proximity ?? Number.MAX_SAFE_INTEGER)
    || directionRank(left.direction) - directionRank(right.direction)
    || (left.definition.level === 'basic' ? 0 : 1) - (right.definition.level === 'basic' ? 0 : 1)
    || (left.definition.type === selected.data!.definition.type ? 1 : 0) - (right.definition.type === selected.data!.definition.type ? 1 : 0)
    || registry.indexOf(left.definition) - registry.indexOf(right.definition))
}

export function paletteCompatibility(recommendations: ConnectionRecommendation[]): Record<string, PaletteCompatibility> {
  const result: Record<string, PaletteCompatibility> = {}
  for (const item of recommendations) {
    const value = result[item.definition.type] ?? { downstream: false, upstream: false }
    value[item.direction] = true
    result[item.definition.type] = value
  }
  return result
}
