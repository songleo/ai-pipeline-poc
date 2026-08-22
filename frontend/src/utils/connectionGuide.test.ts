import { describe, expect, it } from 'vitest'
import type { Edge, Node } from '@vue-flow/core'
import type { NodeTypeDefinition, PortDefinition } from '../types/pipeline'
import { appendFlowNode, type PipelineNodeData } from './pipeline'
import { connectionRecommendations, missingRequiredInputs, paletteCompatibility } from './connectionGuide'

const port = (name: string, type: string): PortDefinition => ({ name, type, required: true, multiple: false })
const definition = (type: string, inputs: PortDefinition[], outputs: PortDefinition[], level: 'basic' | 'advanced' = 'basic'): NodeTypeDefinition => ({
  type, version: '1.0.0', displayName: type, description: '', category: 'test', level,
  parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: inputs, outputPorts: outputs,
  workflowTemplateName: 'pipeline-demo-nodes', templateName: type, defaultRetryLimit: 0, defaultTimeoutSeconds: 120,
})
const registry = [
  definition('dataset-version', [], [port('dataset', 'DatasetRef')]),
  definition('feature-preprocess', [port('dataset', 'DatasetRef')], [port('processedDataset', 'DatasetRef')]),
  definition('train-model', [port('dataset', 'DatasetRef')], [port('model', 'ModelRef')]),
  definition('evaluate-model', [port('model', 'ModelRef'), port('dataset', 'DatasetRef')], [port('evaluation', 'EvaluationRef')]),
  definition('data-quality-gate', [port('dataset', 'DatasetRef')], [port('approvedDataset', 'DatasetRef'), port('rejectedDataset', 'DatasetRef')], 'advanced'),
]
function node(type: string, id = type): Node<PipelineNodeData> {
  return appendFlowNode([], registry.find(item => item.type === type)!, { x: 0, y: 0 }, id)[0]
}

describe('connection guidance', () => {
  it('recommends downstream nodes and explains remaining required inputs', () => {
    const selected = node('dataset-version', 'dataset')
    const recommendations = connectionRecommendations(selected, [selected], [], registry)
    const preprocess = recommendations.find(item => item.definition.type === 'feature-preprocess' && item.direction === 'downstream')!
    const evaluation = recommendations.find(item => item.definition.type === 'evaluate-model' && item.direction === 'downstream')!
    expect(preprocess.autoConnect).toBe(true)
    expect(preprocess).toMatchObject({ sourcePort: 'dataset', targetPort: 'dataset', artifactType: 'DatasetRef' })
    expect(evaluation.missingAfterConnect.map(item => item.name)).toEqual(['model'])
    expect(paletteCompatibility(recommendations)['feature-preprocess'].downstream).toBe(true)
  })

  it('only recommends upstream artifacts for inputs that are still missing', () => {
    const selected = node('evaluate-model', 'evaluate')
    const modelEdge = { source: 'train', sourceHandle: 'model', target: 'evaluate', targetHandle: 'model' } as Edge
    expect(missingRequiredInputs(selected, [modelEdge]).map(item => item.name)).toEqual(['dataset'])
    const upstream = connectionRecommendations(selected, [selected], [modelEdge], registry).filter(item => item.direction === 'upstream')
    expect(upstream.some(item => item.definition.type === 'train-model')).toBe(false)
    expect(upstream.some(item => item.definition.type === 'feature-preprocess')).toBe(true)
  })

  it('does not auto-connect an ambiguous conditional output', () => {
    const selected = node('data-quality-gate', 'gate')
    const preprocess = connectionRecommendations(selected, [selected], [], registry).find(item => item.definition.type === 'feature-preprocess' && item.direction === 'downstream')!
    expect(preprocess.autoConnect).toBe(false)
  })

  it('ranks progression before repeating the selected transform type', () => {
    const selected = node('feature-preprocess', 'preprocess')
    const recommendations = connectionRecommendations(selected, [selected], [], registry).filter(item => item.direction === 'downstream')
    expect(recommendations[0].definition.type).toBe('train-model')
  })

  it('prefers a compatible existing canvas node over adding a duplicate', () => {
    const evaluation = node('evaluate-model', 'evaluate')
    const preprocess = node('feature-preprocess', 'preprocess')
    const dataset = node('dataset-version', 'dataset')
    const training = node('train-model', 'train')
    const edges = [
      { source: 'dataset', sourceHandle: 'dataset', target: 'preprocess', targetHandle: 'dataset' },
      { source: 'preprocess', sourceHandle: 'processedDataset', target: 'train', targetHandle: 'dataset' },
      { source: 'train', sourceHandle: 'model', target: 'evaluate', targetHandle: 'model' },
    ] as Edge[]
    const recommendations = connectionRecommendations(evaluation, [dataset, preprocess, training, evaluation], edges, registry)
    const firstDatasetInput = recommendations.find(item => item.direction === 'upstream' && item.artifactType === 'DatasetRef')!
    expect(firstDatasetInput).toMatchObject({ existingNodeId: 'preprocess', sourcePort: 'processedDataset', targetPort: 'dataset', autoConnect: true })
  })
})
