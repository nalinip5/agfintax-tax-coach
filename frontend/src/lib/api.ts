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

export type Strategy = {
  title: string
  description: string
  why_it_applies: string | null
  status: string
  estimated_savings: number | null
}

export type PlanData = {
  tier: string
  found: boolean
  summary?: string
  tax_year?: number
  filing_status?: string
  filing_info?: { state?: string; occupation?: string; spouse_occupation?: string | null }
  age_planning?: { taxpayer_age?: number; spouse_age?: number | null; retirement_age_target?: number }
  income_planning?: {
    wages?: number
    self_employment_income?: number
    investment_income?: number
    federal_tax_withheld?: number
    estimated_payments_made?: number
  }
  retirement_planning?: {
    has_401k?: boolean
    "401k_contribution_pct"?: number
    employer_match_pct?: number
    has_traditional_ira?: boolean
    has_sep_ira?: boolean
    sep_ira_contribution_ytd?: number
  }
  family_education?: { dependents?: { name?: string }[]; has_dependent_care_expenses?: boolean; has_529_plan?: boolean }
  real_estate_assets?: { owns_primary_residence?: boolean; owns_rental_property?: boolean; brokerage_account_value?: number }
  deductions_giving?: { itemizes?: boolean; charitable_contributions_ytd?: number; mortgage_interest_paid?: number; salt_paid_estimate?: number }
  life_changes?: string[]
  agi?: number
  magi?: number
  marginal_rate?: number
  confirmed_savings?: number
  potential_savings?: number
  urgent_observations?: string[]
  missing_questionnaire_items?: string[]
  strategies?: Strategy[]
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

  // Client-facing document upload: OCR (Azure Document Intelligence) -> PII scrub -> ingest.
  // Distinct from uploadDocument above (which is the admin plain-text ingestion path).
  uploadDocumentFile: (user_id: string, title: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    const params = new URLSearchParams({ user_id, title })
    return fetch(`${BASE}/documents/upload?${params}`, { method: 'POST', body: form }).then(json<{
      id: string
      title: string
      published: boolean
      redacted_categories: string[]
      redaction_count: number
      note: string
    }>)
  },

  getLatestPlan: (user_id: string) => fetch(`${BASE}/tax-plan/${user_id}`).then(json<PlanData>),
}
