import type { Pipeline, PipelineCatalogEntry } from '../types/pipeline'

export const CATALOG_KEY = 'pipeline-demo.catalog.v1'

export function templateEntry(pipeline: Pipeline): PipelineCatalogEntry {
  return {
    id: 'template-training-qualification',
    name: '小林的 AI 评论分类项目',
    description: '一份使用通用 Pipeline 节点编排出的评论分类业务模板。',
    version: 1,
    source: 'template',
    updatedAt: '内置模板',
    pipeline: structuredClone(pipeline),
  }
}

export function loadLocalCatalog(storage: Pick<Storage, 'getItem'>): PipelineCatalogEntry[] {
  try {
    const value = JSON.parse(storage.getItem(CATALOG_KEY) ?? '[]')
    return Array.isArray(value) ? value.filter(item => item?.source === 'local' && item?.pipeline?.kind === 'Pipeline') : []
  } catch {
    return []
  }
}

export function saveToCatalog(storage: Pick<Storage, 'setItem'>, entries: PipelineCatalogEntry[], pipeline: Pipeline): PipelineCatalogEntry[] {
  const current = entries.find(item => item.source === 'local' && item.pipeline.metadata.name === pipeline.metadata.name)
  const entry: PipelineCatalogEntry = {
    id: current?.id ?? `pipeline-${pipeline.metadata.name}`,
    name: pipeline.metadata.experimentName || pipeline.metadata.name,
    description: `${pipeline.spec.nodes.length} 个节点 · ${pipeline.metadata.tags.join(' / ')}`,
    version: (current?.version ?? 0) + 1,
    source: 'local',
    updatedAt: new Date().toISOString(),
    pipeline: structuredClone(pipeline),
  }
  const next = [...entries.filter(item => item.id !== entry.id), entry]
  storage.setItem(CATALOG_KEY, JSON.stringify(next))
  return next
}

export function copyCatalogEntry(entry: PipelineCatalogEntry): Pipeline {
  const pipeline = structuredClone(entry.pipeline)
  pipeline.metadata.name = `${pipeline.metadata.name.replace(/-copy-\d+$/, '')}-copy-${Date.now().toString().slice(-5)}`
  pipeline.metadata.experimentName = `${pipeline.metadata.experimentName} 副本`
  return pipeline
}
