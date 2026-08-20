import { describe, expect, it } from 'vitest'
import type { NodeTypeDefinition } from '../types/pipeline'
import { examplePipeline } from './example'
import { flowToPipeline, pipelineToFlow, terminalStatuses, validateLocally } from './pipeline'

const registry: NodeTypeDefinition[] = [
  { type: 'data-generator', version: '1.0.0', displayName: '生成数据', description: '', category: 'data', parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: [], outputPorts: [{ name: 'dataset', type: 'DatasetRef', required: true, multiple: false }], workflowTemplateName: 'pipeline-demo-nodes', templateName: 'generate-data', defaultRetryLimit: 0, defaultTimeoutSeconds: 10 },
  { type: 'preprocess', version: '1.0.0', displayName: '预处理', description: '', category: 'data', parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: [{ name: 'dataset', type: 'DatasetRef', required: true, multiple: false }], outputPorts: [{ name: 'processedDataset', type: 'DatasetRef', required: true, multiple: false }], workflowTemplateName: 'pipeline-demo-nodes', templateName: 'preprocess-data', defaultRetryLimit: 0, defaultTimeoutSeconds: 10 },
  { type: 'mock-training', version: '1.0.0', displayName: '训练', description: '', category: 'train', parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: [{ name: 'dataset', type: 'DatasetRef', required: true, multiple: false }], outputPorts: [{ name: 'model', type: 'ModelMetricRef', required: true, multiple: false }], workflowTemplateName: 'pipeline-demo-nodes', templateName: 'mock-training', defaultRetryLimit: 2, defaultTimeoutSeconds: 10 },
  { type: 'compare-models', version: '1.0.0', displayName: '对比', description: '', category: 'eval', parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: [{ name: 'modelA', type: 'ModelMetricRef', required: true, multiple: false }, { name: 'modelB', type: 'ModelMetricRef', required: true, multiple: false }], outputPorts: [{ name: 'bestModel', type: 'ModelMetricRef', required: true, multiple: false }], workflowTemplateName: 'pipeline-demo-nodes', templateName: 'compare-models', defaultRetryLimit: 0, defaultTimeoutSeconds: 10 },
  { type: 'generate-report', version: '1.0.0', displayName: '报告', description: '', category: 'output', parametersSchema: { type: 'object', properties: {} }, uiSchema: {}, inputPorts: [{ name: 'model', type: 'ModelMetricRef', required: true, multiple: false }], outputPorts: [{ name: 'report', type: 'ReportRef', required: true, multiple: false }], workflowTemplateName: 'pipeline-demo-nodes', templateName: 'generate-report', defaultRetryLimit: 0, defaultTimeoutSeconds: 10 },
]

describe('Pipeline DSL tools', () => {
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
