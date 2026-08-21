import type { RunDetail, UnifiedStatus } from '../types/pipeline'

export type RunScope = 'business' | 'system' | 'all'

const systemPrefixes = ['node-control-', 'training-qualification-', 'model-comparison-', 'untitled-pipeline']

export function isSystemRun(run: RunDetail): boolean {
  return run.tags.includes('system-test') || systemPrefixes.some(prefix => run.pipelineName.startsWith(prefix))
}

export function filterAndSortRuns(
  runs: RunDetail[],
  options: { pipeline?: string; query?: string; status?: UnifiedStatus | ''; scope?: RunScope } = {},
): RunDetail[] {
  const query = options.query?.trim().toLowerCase() ?? ''
  return [...runs]
    .filter(run => !options.pipeline || run.pipelineName === options.pipeline)
    .filter(run => !options.status || run.status === options.status)
    .filter(run => options.scope === 'all' || (options.scope === 'system' ? isSystemRun(run) : !isSystemRun(run)))
    .filter(run => !query || `${run.workflowName} ${run.pipelineName} ${run.experimentName ?? ''}`.toLowerCase().includes(query))
    .sort((a, b) => Date.parse(b.startedAt ?? '1970-01-01') - Date.parse(a.startedAt ?? '1970-01-01'))
}

export function statusLabel(status: UnifiedStatus): string {
  return ({ IDLE: '未运行', PENDING: '等待中', RUNNING: '运行中', SUCCEEDED: '成功', FAILED: '失败', ERROR: '异常', CANCELLED: '已停止', SKIPPED: '已跳过' } as Record<UnifiedStatus, string>)[status]
}
