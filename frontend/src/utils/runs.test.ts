import { describe, expect, it } from 'vitest'
import type { RunDetail } from '../types/pipeline'
import { filterAndSortRuns, isSystemRun, statusLabel } from './runs'

const run = (name: string, startedAt: string, tags: string[] = []): RunDetail => ({
  workflowName: `${name}-abc`, pipelineName: name, tags, status: 'SUCCEEDED', startedAt, nodes: [],
})

describe('run list presentation', () => {
  it('sorts newest first and hides system validation by default', () => {
    const values = [run('business-pipeline', '2026-08-20T01:00:00Z'), run('node-control-smoke', '2026-08-21T01:00:00Z'), run('another-business', '2026-08-22T01:00:00Z')]
    expect(filterAndSortRuns(values).map(item => item.pipelineName)).toEqual(['another-business', 'business-pipeline'])
    expect(filterAndSortRuns(values, { scope: 'all' })[1].pipelineName).toBe('node-control-smoke')
  })

  it('recognizes tagged system runs and localizes status', () => {
    expect(isSystemRun(run('comment-classification-demo', '2026-08-21T01:00:00Z', ['system-test']))).toBe(true)
    expect(statusLabel('FAILED')).toBe('失败')
  })
})
