import { describe, expect, it } from 'vitest'
import { examplePipeline } from './example'
import { copyCatalogEntry, loadLocalCatalog, saveToCatalog, templateEntry } from './pipelineCatalog'

describe('Pipeline catalog', () => {
  it('saves versioned local definitions behind a replaceable storage boundary', () => {
    let raw = ''
    const storage = { getItem: () => raw || null, setItem: (_key: string, value: string) => { raw = value } }
    let entries = saveToCatalog(storage, [], examplePipeline)
    entries = saveToCatalog(storage, entries, examplePipeline)
    expect(entries).toHaveLength(1)
    expect(entries[0].version).toBe(2)
    expect(loadLocalCatalog(storage)[0].pipeline.metadata.name).toBe('comment-classification-demo')
  })

  it('copies a template without mutating it', () => {
    const entry = templateEntry(examplePipeline)
    const copied = copyCatalogEntry(entry)
    expect(copied.metadata.name).toMatch(/^comment-classification-demo-copy-/)
    expect(entry.pipeline.metadata.name).toBe('comment-classification-demo')
  })
})
