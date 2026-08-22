import { describe, expect, it } from 'vitest'
import { examplePipeline } from './example'
import { clonePipeline, copyCatalogEntry, deletePipeline, latestCatalogEntries, loadLocalCatalog, saveToCatalog, templateEntry, versionsForPipeline } from './pipelineCatalog'

function memoryStorage() {
  let raw = ''
  return { getItem: () => raw || null, setItem: (_key: string, value: string) => { raw = value } }
}

describe('Pipeline catalog', () => {
  it('keeps immutable versions behind a replaceable storage boundary', () => {
    const storage = memoryStorage()
    let result = saveToCatalog(storage, [], examplePipeline)
    result = saveToCatalog(storage, result.entries, examplePipeline)
    expect(result.entries).toHaveLength(2)
    expect(result.entry.version).toBe(2)
    expect(result.entry.pipeline.metadata.version).toBe(2)
    expect(versionsForPipeline(loadLocalCatalog(storage), examplePipeline.metadata.name).map(item => item.version)).toEqual([2, 1])
    expect(latestCatalogEntries(result.entries)).toHaveLength(1)
  })

  it('deletes all versions of one Pipeline', () => {
    const storage = memoryStorage()
    const first = saveToCatalog(storage, [], examplePipeline)
    const copied = copyCatalogEntry(templateEntry(examplePipeline))
    const second = saveToCatalog(storage, first.entries, copied)
    const remaining = deletePipeline(storage, second.entries, examplePipeline.metadata.name)
    expect(remaining).toHaveLength(1)
    expect(remaining[0].pipeline.metadata.name).toBe(copied.metadata.name)
  })

  it('copies a template without mutating it', () => {
    const entry = templateEntry(examplePipeline)
    const copied = copyCatalogEntry(entry)
    expect(copied.metadata.name).toMatch(/^comment-classification-demo-copy-/)
    expect(copied.metadata.version).toBeUndefined()
    expect(entry.pipeline.metadata.name).toBe('comment-classification-demo')
  })

  it('clones a reactive-looking definition through its JSON contract', () => {
    const proxy = new Proxy(examplePipeline, {})
    expect(() => structuredClone(proxy)).toThrow()
    expect(clonePipeline(proxy)).toEqual(examplePipeline)
  })
})
