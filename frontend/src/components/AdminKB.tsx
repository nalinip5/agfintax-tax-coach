import { useEffect, useState } from 'react'
import { api, Source } from '../lib/api'

const TIERS = ['basic', 'plus', 'pro']

function emptyDraft(): Omit<Source, 'id'> {
  return { domain: '', description: '', scope_tags: [], api_method: 'tavily_search', enabled: true, tier: [...TIERS] }
}

export default function AdminKB() {
  const [sources, setSources] = useState<Source[]>([])
  const [draft, setDraft] = useState(emptyDraft())
  const [loading, setLoading] = useState(true)

  // Document upload state
  const [docTitle, setDocTitle] = useState('')
  const [docDomain, setDocDomain] = useState('')
  const [docContent, setDocContent] = useState('')
  const [uploadedDoc, setUploadedDoc] = useState<{ id: string; title: string; published: boolean } | null>(null)

  function refresh() {
    setLoading(true)
    api.listSources().then((s) => setSources(s)).finally(() => setLoading(false))
  }

  useEffect(refresh, [])

  async function addSource() {
    if (!draft.domain.trim()) return
    await api.createSource({ ...draft, scope_tags: draft.scope_tags })
    setDraft(emptyDraft())
    refresh()
  }

  async function toggleEnabled(s: Source) {
    await api.updateSource(s.id, { ...s, enabled: !s.enabled })
    refresh()
  }

  async function remove(s: Source) {
    await api.deleteSource(s.id)
    refresh()
  }

  async function upload() {
    if (!docTitle.trim() || !docContent.trim()) return
    const doc = await api.uploadDocument(docTitle, docDomain, docContent)
    setUploadedDoc(doc)
    setDocTitle('')
    setDocDomain('')
    setDocContent('')
  }

  async function togglePublish() {
    if (!uploadedDoc) return
    const fn = uploadedDoc.published ? api.unpublishDocument : api.publishDocument
    await fn(uploadedDoc.id)
    setUploadedDoc({ ...uploadedDoc, published: !uploadedDoc.published })
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <header className="mb-6">
        <h1 className="font-serif text-2xl text-ledger-900">Admin Knowledge Base</h1>
        <p className="text-sm text-ledger-600">
          Manage the source_registry that drives official-source lookups, and publish internal documents.
        </p>
      </header>

      {/* Source registry */}
      <section className="rounded-xl border border-ledger-200 bg-white p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-serif text-lg text-ledger-900">Official source registry</h2>
          <span className="text-xs text-ledger-500">Adding a row here is the only step — no deploy.</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ledger-100 text-xs uppercase tracking-wide text-ledger-500">
                <th className="py-2 pr-3">Domain</th>
                <th className="py-2 pr-3">Description</th>
                <th className="py-2 pr-3">Scope tags</th>
                <th className="py-2 pr-3">Method</th>
                <th className="py-2 pr-3">Tiers</th>
                <th className="py-2 pr-3">Enabled</th>
                <th className="py-2"></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={7} className="py-4 text-ledger-400">
                    Loading…
                  </td>
                </tr>
              )}
              {sources.map((s) => (
                <tr key={s.id} className="border-b border-ledger-50">
                  <td className="py-2 pr-3 font-medium text-ledger-900">{s.domain}</td>
                  <td className="py-2 pr-3 text-ledger-700">{s.description}</td>
                  <td className="py-2 pr-3">
                    <div className="flex flex-wrap gap-1">
                      {s.scope_tags.map((t) => (
                        <span key={t} className="rounded-full bg-ledger-100 px-2 py-0.5 text-xs text-ledger-700">
                          {t}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 pr-3 text-ledger-700">{s.api_method}</td>
                  <td className="py-2 pr-3 text-ledger-700">{s.tier.join(', ')}</td>
                  <td className="py-2 pr-3">
                    <button
                      onClick={() => toggleEnabled(s)}
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        s.enabled ? 'bg-ledger-600/10 text-ledger-700' : 'bg-ledger-100 text-ledger-400'
                      }`}
                    >
                      {s.enabled ? 'Enabled' : 'Disabled'}
                    </button>
                  </td>
                  <td className="py-2 text-right">
                    <button onClick={() => remove(s)} className="text-xs text-clay-600 hover:underline">
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Add new source */}
        <div className="mt-5 grid grid-cols-2 gap-3 rounded-lg border border-dashed border-ledger-200 p-4 md:grid-cols-3">
          <input
            className="col-span-2 rounded-md border border-ledger-200 px-3 py-1.5 text-sm md:col-span-1"
            placeholder="domain, e.g. hud.gov"
            value={draft.domain}
            onChange={(e) => setDraft({ ...draft, domain: e.target.value })}
          />
          <input
            className="col-span-2 rounded-md border border-ledger-200 px-3 py-1.5 text-sm"
            placeholder="description"
            value={draft.description}
            onChange={(e) => setDraft({ ...draft, description: e.target.value })}
          />
          <input
            className="rounded-md border border-ledger-200 px-3 py-1.5 text-sm"
            placeholder="scope_tags (comma separated)"
            value={draft.scope_tags.join(',')}
            onChange={(e) =>
              setDraft({ ...draft, scope_tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean) })
            }
          />
          <select
            className="rounded-md border border-ledger-200 px-3 py-1.5 text-sm"
            value={draft.api_method}
            onChange={(e) => setDraft({ ...draft, api_method: e.target.value })}
          >
            <option value="tavily_search">tavily_search</option>
            <option value="direct_fetch">direct_fetch</option>
            <option value="irs_api">irs_api</option>
          </select>
          <button
            onClick={addSource}
            className="rounded-md bg-ledger-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-ledger-900"
          >
            Add source
          </button>
        </div>
      </section>

      {/* Document upload */}
      <section className="mt-6 rounded-xl border border-ledger-200 bg-white p-5">
        <h2 className="font-serif text-lg text-ledger-900">Internal document upload</h2>
        <p className="mb-3 text-sm text-ledger-600">Ingested, chunked, and held unpublished until reviewed.</p>
        <div className="grid grid-cols-2 gap-3">
          <input
            className="rounded-md border border-ledger-200 px-3 py-1.5 text-sm"
            placeholder="title"
            value={docTitle}
            onChange={(e) => setDocTitle(e.target.value)}
          />
          <input
            className="rounded-md border border-ledger-200 px-3 py-1.5 text-sm"
            placeholder="source domain (optional)"
            value={docDomain}
            onChange={(e) => setDocDomain(e.target.value)}
          />
          <textarea
            className="col-span-2 rounded-md border border-ledger-200 px-3 py-1.5 text-sm"
            placeholder="paste content to ingest…"
            rows={3}
            value={docContent}
            onChange={(e) => setDocContent(e.target.value)}
          />
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={upload}
            className="rounded-md bg-ledger-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-ledger-900"
          >
            Upload &amp; chunk
          </button>
          {uploadedDoc && (
            <div className="flex items-center gap-2 text-sm text-ledger-700">
              <span>"{uploadedDoc.title}" ingested.</span>
              <button onClick={togglePublish} className="rounded-full bg-ledger-100 px-2.5 py-1 text-xs font-medium text-ledger-700">
                {uploadedDoc.published ? 'Unpublish' : 'Publish'}
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
