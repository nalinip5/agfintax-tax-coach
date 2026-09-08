export type Citation = { label: string; url?: string }

export type ChatResponse = {
  conversation_id: string
  intent: string
  reply: string
  citations: Citation[]
  blocked: boolean
}

export type Source = {
  id: string
  domain: string
  description: string
  scope_tags: string[]
  api_method: string
  enabled: boolean
  tier: string[]
}

// In dev, Vite's proxy (vite.config.ts) forwards /api -> localhost:8010.
// In production (e.g. a static host), set VITE_API_BASE to the deployed
// backend's URL at build time, or rely on the host's own /api rewrite rule.
const BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

export const api = {
  chat: (user_id: string, message: string, conversation_id?: string) =>
    fetch(`${BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, message, conversation_id }),
    }).then(json<ChatResponse>),

  usage: (user_id: string) => fetch(`${BASE}/usage/${user_id}`).then(json<{ tier: string; used_today: number; limit: number }>),

  suggestions: (user_id: string) => fetch(`${BASE}/suggestions/${user_id}`).then(json<{ suggestions: string[] }>),

  listSources: () => fetch(`${BASE}/kb/sources`).then(json<Source[]>),

  createSource: (body: Omit<Source, 'id'>) =>
    fetch(`${BASE}/kb/sources`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(json<Source>),

  updateSource: (id: string, body: Omit<Source, 'id'>) =>
    fetch(`${BASE}/kb/sources/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(json<Source>),

  deleteSource: (id: string) => fetch(`${BASE}/kb/sources/${id}`, { method: 'DELETE' }).then(json<{ deleted: string }>),

  uploadDocument: (title: string, source_domain: string, content: string) =>
    fetch(`${BASE}/kb/documents?${new URLSearchParams({ title, source_domain, content })}`, {
      method: 'POST',
    }).then(json<{ id: string; title: string; published: boolean }>),

  publishDocument: (id: string) => fetch(`${BASE}/kb/documents/${id}/publish`, { method: 'POST' }).then(json),
  unpublishDocument: (id: string) => fetch(`${BASE}/kb/documents/${id}/unpublish`, { method: 'POST' }).then(json),
}
