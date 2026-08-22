import type { Pipeline, PipelineCatalogEntry } from '../types/pipeline'

export const CATALOG_KEY = 'pipeline-demo.catalog.v1'
type CatalogStorage = Pick<Storage, 'getItem' | 'setItem'>
export interface SaveVersionResult { entries: PipelineCatalogEntry[]; entry: PipelineCatalogEntry }
export function clonePipeline(pipeline: Pipeline): Pipeline { return JSON.parse(JSON.stringify(pipeline)) as Pipeline }

export function templateEntry(pipeline: Pipeline): PipelineCatalogEntry {
  const definition = clonePipeline(pipeline)
  definition.metadata.version = 1
  return {
    id: 'template-training-qualification',
    name: '小林的 AI 评论分类项目',
    description: '一份使用通用 Pipeline 节点编排出的评论分类业务模板。',
    version: 1,
    source: 'template',
    updatedAt: '内置模板',
    pipeline: definition,
  }
}

function normalizeEntry(item: PipelineCatalogEntry): PipelineCatalogEntry {
  const entry = structuredClone(item)
  entry.pipeline.metadata.version = entry.version
  entry.id = `pipeline-${entry.pipeline.metadata.name}-v${entry.version}`
  return entry
}

export function loadLocalCatalog(storage: Pick<Storage, 'getItem'>): PipelineCatalogEntry[] {
  try {
    const value = JSON.parse(storage.getItem(CATALOG_KEY) ?? '[]')
    return Array.isArray(value) ? value.filter(item => item?.source === 'local' && item?.pipeline?.kind === 'Pipeline').map(normalizeEntry) : []
  } catch {
    return []
  }
}

export function nextVersion(entries: PipelineCatalogEntry[], pipelineName: string): number {
  return Math.max(0, ...entries.filter(item => item.source === 'local' && item.pipeline.metadata.name === pipelineName).map(item => item.version)) + 1
}

export function saveToCatalog(storage: CatalogStorage, entries: PipelineCatalogEntry[], pipeline: Pipeline): SaveVersionResult {
  const version = nextVersion(entries, pipeline.metadata.name)
  const definition = clonePipeline(pipeline)
  definition.metadata.version = version
  const entry: PipelineCatalogEntry = {
    id: `pipeline-${definition.metadata.name}-v${version}`,
    name: definition.metadata.experimentName || definition.metadata.name,
    description: `${definition.spec.nodes.length} 个节点 · ${definition.metadata.tags.join(' / ')}`,
    version,
    source: 'local',
    updatedAt: new Date().toISOString(),
    pipeline: definition,
  }
  const next = [entry, ...entries]
  storage.setItem(CATALOG_KEY, JSON.stringify(next))
  return { entries: next, entry }
}

export function latestCatalogEntries(entries: PipelineCatalogEntry[]): PipelineCatalogEntry[] {
  const latest = new Map<string, PipelineCatalogEntry>()
  for (const entry of entries.filter(item => item.source === 'local')) {
    const name = entry.pipeline.metadata.name
    if (!latest.has(name) || entry.version > latest.get(name)!.version) latest.set(name, entry)
  }
  return [...latest.values()].sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt))
}

export function versionsForPipeline(entries: PipelineCatalogEntry[], pipelineName: string): PipelineCatalogEntry[] {
  return entries.filter(item => item.source === 'local' && item.pipeline.metadata.name === pipelineName).sort((left, right) => right.version - left.version)
}

export function deletePipeline(storage: CatalogStorage, entries: PipelineCatalogEntry[], pipelineName: string): PipelineCatalogEntry[] {
  const next = entries.filter(item => item.pipeline.metadata.name !== pipelineName)
  storage.setItem(CATALOG_KEY, JSON.stringify(next))
  return next
}

export function copyCatalogEntry(entry: PipelineCatalogEntry): Pipeline {
  const pipeline = clonePipeline(entry.pipeline)
  pipeline.metadata.name = `${pipeline.metadata.name.replace(/-copy-\d+$/, '')}-copy-${Date.now().toString().slice(-5)}`
  pipeline.metadata.experimentName = `${pipeline.metadata.experimentName} 副本`
  delete pipeline.metadata.version
  return pipeline
}
