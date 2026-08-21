import { describe, expect, it } from 'vitest'
import type { NodeTypeDefinition } from '../types/pipeline'
import { examplePipeline } from './example'
import { appendFlowNode, connectFlowNodes, flowToPipeline, pipelineToFlow, terminalStatuses, validateLocally } from './pipeline'

const registry: NodeTypeDefinition[] = [
  { type: 'data-generator', version: '1.0.0', displayName: '生成数据', description: '', category: 'data', parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: [], outputPorts: [{ name: 'dataset', type: 'DatasetRef', required: true, multiple: false }], workflowTemplateName: 'pipeline-demo-nodes', templateName: 'generate-data', defaultRetryLimit: 0, defaultTimeoutSeconds: 10 },
  { type: 'preprocess', version: '1.0.0', displayName: '预处理', description: '', category: 'data', parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: [{ name: 'dataset', type: 'DatasetRef', required: true, multiple: false }], outputPorts: [{ name: 'processedDataset', type: 'DatasetRef', required: true, multiple: false }], workflowTemplateName: 'pipeline-demo-nodes', templateName: 'preprocess-data', defaultRetryLimit: 0, defaultTimeoutSeconds: 10 },
  { type: 'mock-training', version: '1.0.0', displayName: '训练', description: '', category: 'train', parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: [{ name: 'dataset', type: 'DatasetRef', required: true, multiple: false }], outputPorts: [{ name: 'model', type: 'ModelMetricRef', required: true, multiple: false }], workflowTemplateName: 'pipeline-demo-nodes', templateName: 'mock-training', defaultRetryLimit: 2, defaultTimeoutSeconds: 10 },
  { type: 'compare-models', version: '1.0.0', displayName: '对比', description: '', category: 'eval', parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: [{ name: 'modelA', type: 'ModelMetricRef', required: true, multiple: false }, { name: 'modelB', type: 'ModelMetricRef', required: true, multiple: false }], outputPorts: [{ name: 'bestModel', type: 'ModelMetricRef', required: true, multiple: false }], workflowTemplateName: 'pipeline-demo-nodes', templateName: 'compare-models', defaultRetryLimit: 0, defaultTimeoutSeconds: 10 },
  { type: 'generate-report', version: '1.0.0', displayName: '报告', description: '', category: 'output', parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: [{ name: 'model', type: 'ModelMetricRef', required: true, multiple: false }], outputPorts: [{ name: 'report', type: 'ReportRef', required: true, multiple: false }], workflowTemplateName: 'pipeline-demo-nodes', templateName: 'generate-report', defaultRetryLimit: 0, defaultTimeoutSeconds: 10 },
]

describe('Pipeline DSL tools', () => {
  it('appends a dropped node with a new array reference', () => {
    const nodes: ReturnType<typeof pipelineToFlow>['nodes'] = []
    const result = appendFlowNode(nodes, registry[0], { x: 120, y: 80 }, 'data-generator-new')
    expect(result).not.toBe(nodes)
    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({
      id: 'data-generator-new',
      type: 'pipeline',
      position: { x: 120, y: 80 },
      data: { status: 'IDLE', pipelineNode: { type: 'data-generator', name: '生成数据', parameters: {} } },
    })
  })
  it('connects compatible handles with a new edge array and round trips the DSL edge', () => {
    let nodes: ReturnType<typeof pipelineToFlow>['nodes'] = []
    nodes = appendFlowNode(nodes, registry[0], { x: 100, y: 100 }, 'generate')
    nodes = appendFlowNode(nodes, registry[1], { x: 360, y: 100 }, 'preprocess')
    const edges: ReturnType<typeof pipelineToFlow>['edges'] = []
    const result = connectFlowNodes(nodes, edges, { source: 'generate', sourceHandle: 'dataset', target: 'preprocess', targetHandle: 'dataset' })
    expect(result.error).toBeUndefined()
    expect(result.edges).not.toBe(edges)
    expect(result.edges).toHaveLength(1)
    expect(flowToPipeline('connected-pipeline', nodes, result.edges).spec.edges).toEqual([
      { source: 'generate', sourcePort: 'dataset', target: 'preprocess', targetPort: 'dataset' },
    ])
  })
  it('rejects incompatible handles and a second connection to a single input', () => {
    const flow = pipelineToFlow(examplePipeline, registry)
    const incompatible = connectFlowNodes(flow.nodes, [], { source: 'generate', sourceHandle: 'dataset', target: 'compare', targetHandle: 'modelA' })
    expect(incompatible.error).toBe('端口类型不兼容')
    expect(incompatible.edges).toHaveLength(0)

    const first = connectFlowNodes(flow.nodes, [], { source: 'generate', sourceHandle: 'dataset', target: 'preprocess', targetHandle: 'dataset' })
    const duplicate = connectFlowNodes(flow.nodes, first.edges, { source: 'generate', sourceHandle: 'dataset', target: 'preprocess', targetHandle: 'dataset' })
    expect(duplicate.error).toBe('该输入端口只能连接一次')
    expect(duplicate.edges).toBe(first.edges)
  })
  it('loads the complete sample and round trips UI layout separately', () => {
    const flow = pipelineToFlow(examplePipeline, registry)
    expect(flow.nodes).toHaveLength(6); expect(flow.edges).toHaveLength(6)
    const result = flowToPipeline(examplePipeline.metadata.name, flow.nodes, flow.edges)
    expect(result.spec.nodes.map(item => item.id)).toEqual(examplePipeline.spec.nodes.map(item => item.id))
    expect(result.uiLayout.nodes['train-a']).toEqual({ x: 540, y: 90 })
  })
  it('detects a frontend port type mismatch', () => {
    const value = structuredClone(examplePipeline)
    value.spec.edges[3] = { source: 'generate', sourcePort: 'dataset', target: 'compare', targetPort: 'modelA' }
    expect(validateLocally(value, registry).errors.map(item => item.code)).toContain('PORT_TYPE_MISMATCH')
  })
  it('knows terminal unified statuses', () => {
    expect(terminalStatuses.has('SUCCEEDED')).toBe(true); expect(terminalStatuses.has('RUNNING')).toBe(false)
  })
})
