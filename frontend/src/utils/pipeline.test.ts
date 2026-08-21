import { describe, expect, it } from 'vitest'
import type { NodeTypeDefinition, PortDefinition } from '../types/pipeline'
import { examplePipeline } from './example'
import { appendFlowNode, connectFlowNodes, flowToPipeline, pipelineToFlow, terminalStatuses, validateLocally } from './pipeline'

const port = (name: string, type: string): PortDefinition => ({ name, type, required: true, multiple: false })
const definition = (type: string, inputs: PortDefinition[], outputs: PortDefinition[]): NodeTypeDefinition => ({
  type, version: '1.0.0', displayName: type, description: '', category: 'test',
  parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: inputs, outputPorts: outputs,
  workflowTemplateName: 'pipeline-demo-nodes', templateName: type, defaultRetryLimit: 0, defaultTimeoutSeconds: 120,
})
const registry = [
  definition('dataset-version', [], [port('dataset', 'DatasetRef')]),
  definition('data-profile', [port('dataset', 'DatasetRef')], [port('profile', 'DataProfileRef')]),
  definition('data-quality-gate', [port('dataset', 'DatasetRef'), port('profile', 'DataProfileRef')], [port('approvedDataset', 'DatasetRef'), port('rejectedDataset', 'DatasetRef'), port('approvedDecision', 'GateDecisionRef'), port('rejectedDecision', 'GateDecisionRef')]),
  definition('feature-preprocess', [port('dataset', 'DatasetRef')], [port('processedDataset', 'DatasetRef')]),
  definition('train-model', [port('dataset', 'DatasetRef')], [port('model', 'ModelRef')]),
  definition('evaluate-model', [port('model', 'ModelRef'), port('dataset', 'DatasetRef')], [port('evaluation', 'EvaluationRef')]),
  definition('compare-evaluations', [port('evaluationA', 'EvaluationRef'), port('evaluationB', 'EvaluationRef')], [port('candidate', 'CandidateModelRef'), port('leaderboard', 'LeaderboardRef')]),
  definition('model-admission-gate', [port('candidate', 'CandidateModelRef')], [port('approvedCandidate', 'CandidateModelRef'), port('rejectedCandidate', 'CandidateModelRef'), port('approvedDecision', 'GateDecisionRef'), port('rejectedDecision', 'GateDecisionRef')]),
  definition('register-model-version', [port('candidate', 'CandidateModelRef')], [port('registeredModel', 'RegisteredModelRef')]),
  definition('qualification-report', [port('decision', 'GateDecisionRef')], [port('report', 'ReportRef')]),
]

describe('Pipeline DSL tools', () => {
  it('appends a dropped node with a new array reference', () => {
    const nodes: ReturnType<typeof pipelineToFlow>['nodes'] = []
    const result = appendFlowNode(nodes, registry[0], { x: 120, y: 80 }, 'dataset-new')
    expect(result).not.toBe(nodes)
    expect(result[0]).toMatchObject({ id: 'dataset-new', type: 'pipeline', position: { x: 120, y: 80 }, data: { status: 'IDLE', pipelineNode: { type: 'dataset-version' } } })
  })

  it('connects compatible handles and round trips experiment metadata', () => {
    let nodes: ReturnType<typeof pipelineToFlow>['nodes'] = []
    nodes = appendFlowNode(nodes, registry[0], { x: 100, y: 100 }, 'dataset')
    nodes = appendFlowNode(nodes, registry[1], { x: 360, y: 100 }, 'profile')
    const result = connectFlowNodes(nodes, [], { source: 'dataset', sourceHandle: 'dataset', target: 'profile', targetHandle: 'dataset' })
    const pipeline = flowToPipeline('connected-pipeline', '资格实验', ['p0'], nodes, result.edges)
    expect(pipeline.metadata).toMatchObject({ experimentName: '资格实验', tags: ['p0'] })
    expect(pipeline.spec.edges).toEqual([{ source: 'dataset', sourcePort: 'dataset', target: 'profile', targetPort: 'dataset' }])
  })

  it('rejects incompatible handles and duplicate single input', () => {
    const flow = pipelineToFlow(examplePipeline, registry)
    const incompatible = connectFlowNodes(flow.nodes, [], { source: 'dataset', sourceHandle: 'dataset', target: 'admission', targetHandle: 'candidate' })
    expect(incompatible.error).toBe('端口类型不兼容')
    const first = connectFlowNodes(flow.nodes, [], { source: 'dataset', sourceHandle: 'dataset', target: 'profile', targetHandle: 'dataset' })
    const duplicate = connectFlowNodes(flow.nodes, first.edges, { source: 'dataset', sourceHandle: 'dataset', target: 'profile', targetHandle: 'dataset' })
    expect(duplicate.error).toBe('该输入端口只能连接一次')
  })

  it('loads the professional sample and round trips its layout', () => {
    const flow = pipelineToFlow(examplePipeline, registry)
    expect(flow.nodes).toHaveLength(13); expect(flow.edges).toHaveLength(16)
    const result = flowToPipeline(examplePipeline.metadata.name, examplePipeline.metadata.experimentName, examplePipeline.metadata.tags, flow.nodes, flow.edges, 420)
    expect(result.spec.nodes.map(item => item.id)).toEqual(examplePipeline.spec.nodes.map(item => item.id))
    expect(result.uiLayout.nodes['train-baseline']).toEqual({ x: 930, y: 90 })
  })

  it('detects a frontend port type mismatch', () => {
    const value = structuredClone(examplePipeline)
    value.spec.edges[10] = { source: 'dataset', sourcePort: 'dataset', target: 'leaderboard', targetPort: 'evaluationA' }
    expect(validateLocally(value, registry).errors.map(item => item.code)).toContain('PORT_TYPE_MISMATCH')
  })

  it('knows terminal unified statuses', () => {
    expect(terminalStatuses.has('SUCCEEDED')).toBe(true); expect(terminalStatuses.has('RUNNING')).toBe(false)
  })
})
