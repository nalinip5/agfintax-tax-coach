import { useEffect, useState, type ReactNode } from 'react'
import { api, PlanData } from '../lib/api'

const USER_ID = 'demo-user'

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  )
}

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="font-medium text-slate-900">{title}</h3>
      <div className="mt-3 space-y-1.5 text-sm text-slate-600">{children}</div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string | number | boolean }) {
  const display = typeof value === 'boolean' ? (value ? 'Yes' : 'No') : value === '' || value == null ? '—' : value
  return (
    <div className="flex justify-between gap-4">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-800">{String(display)}</span>
    </div>
  )
}

export default function Dashboard({ onAskCoach }: { onAskCoach: (question: string) => void }) {
  const [plan, setPlan] = useState<PlanData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getLatestPlan(USER_ID).then(setPlan).finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="p-8 text-sm text-slate-500">Loading your plan…</div>
  }

  if (!plan || !plan.found) {
    return (
      <div className="mx-auto max-w-lg p-12 text-center">
        <p className="text-lg font-medium text-slate-900">No tax plan on file yet</p>
        <p className="mt-2 text-sm text-slate-600">{plan?.summary || 'Complete your intake to unlock your dashboard and Tax Coach.'}</p>
      </div>
    )
  }

  const fi = plan.filing_info || {}
  const ap = plan.age_planning || {}
  const ip = plan.income_planning || {}
  const rp = plan.retirement_planning || {}
  const fe = plan.family_education || {}
  const re = plan.real_estate_assets || {}
  const dg = plan.deductions_giving || {}

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-6 flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal-600">Tax year {plan.tax_year}</p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">Your tax plan</h1>
          <p className="mt-1 text-sm text-slate-600">
            {plan.filing_status?.replace('_', ' ')} filer · {plan.tier} plan
          </p>
        </div>
      </header>

      {plan.urgent_observations && plan.urgent_observations.length > 0 && (
        <div className="mb-6 rounded-xl border border-amber-300 bg-amber-50 p-4">
          <p className="text-sm font-medium text-amber-900">Needs your attention</p>
          <ul className="mt-1 space-y-1 text-sm text-amber-800">
            {plan.urgent_observations.map((obs) => (
              <li key={obs}>{obs}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
        <StatCard label="AGI" value={plan.agi != null ? `$${plan.agi.toLocaleString()}` : '—'} />
        <StatCard label="MAGI" value={plan.magi != null ? `$${plan.magi.toLocaleString()}` : '—'} />
        <StatCard label="Marginal rate" value={plan.marginal_rate != null ? `${(plan.marginal_rate * 100).toFixed(0)}%` : '—'} />
        <StatCard label="Confirmed savings" value={`$${(plan.confirmed_savings || 0).toLocaleString()}`} />
        <StatCard label="Potential savings" value={`$${(plan.potential_savings || 0).toLocaleString()}`} />
      </div>

      <h2 className="mb-3 font-medium text-slate-900">Strategies</h2>
      <div className="mb-8 grid gap-4 sm:grid-cols-2">
        {(plan.strategies || []).map((s) => (
          <div key={s.title} className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-medium text-slate-900">{s.title}</h3>
              <span
                className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  s.status === 'confirmed' ? 'bg-teal-100 text-teal-700' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {s.status}
              </span>
            </div>
            {s.estimated_savings != null && (
              <p className="mt-1 text-lg font-semibold text-teal-700">${s.estimated_savings.toLocaleString()}</p>
            )}
            <p className="mt-2 text-sm text-slate-600">{s.why_it_applies || s.description}</p>
            <button
              onClick={() => onAskCoach(`Why does '${s.title}' apply to me, and how much could it save?`)}
              className="mt-3 text-sm font-medium text-teal-700 underline decoration-teal-200 underline-offset-2 hover:decoration-teal-500"
            >
              Ask Tax Coach about this →
            </button>
          </div>
        ))}
        {(!plan.strategies || plan.strategies.length === 0) && (
          <p className="text-sm text-slate-500">No strategies identified yet.</p>
        )}
      </div>

      <h2 className="mb-3 font-medium text-slate-900">Your intake</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <SectionCard title="Filing information">
          <Row label="State" value={fi.state ?? ''} />
          <Row label="Occupation" value={fi.occupation ?? ''} />
          <Row label="Spouse occupation" value={fi.spouse_occupation ?? '—'} />
        </SectionCard>

        <SectionCard title="Age & milestones">
          <Row label="Your age" value={ap.taxpayer_age ?? ''} />
          <Row label="Spouse age" value={ap.spouse_age ?? '—'} />
          <Row label="Target retirement age" value={ap.retirement_age_target ?? ''} />
        </SectionCard>

        <SectionCard title="Income & tax paid">
          <Row label="Wages" value={ip.wages != null ? `$${ip.wages.toLocaleString()}` : ''} />
          <Row label="Self-employment income" value={ip.self_employment_income != null ? `$${ip.self_employment_income.toLocaleString()}` : ''} />
          <Row label="Federal tax withheld" value={ip.federal_tax_withheld != null ? `$${ip.federal_tax_withheld.toLocaleString()}` : ''} />
        </SectionCard>

        <SectionCard title="Retirement contributions">
          <Row label="401(k)" value={rp.has_401k ?? false} />
          <Row label="401(k) contribution" value={rp['401k_contribution_pct'] != null ? `${rp['401k_contribution_pct']}%` : '—'} />
          <Row label="Employer match" value={rp.employer_match_pct != null ? `${rp.employer_match_pct}%` : '—'} />
          <Row label="SEP-IRA" value={rp.has_sep_ira ?? false} />
        </SectionCard>

        <SectionCard title="Dependents & education">
          <Row label="Dependents" value={fe.dependents?.length ?? 0} />
          <Row label="Dependent care expenses" value={fe.has_dependent_care_expenses ?? false} />
          <Row label="529 plan" value={fe.has_529_plan ?? false} />
        </SectionCard>

        <SectionCard title="Real estate & assets">
          <Row label="Owns primary residence" value={re.owns_primary_residence ?? false} />
          <Row label="Owns rental property" value={re.owns_rental_property ?? false} />
          <Row label="Brokerage account value" value={re.brokerage_account_value != null ? `$${re.brokerage_account_value.toLocaleString()}` : '—'} />
        </SectionCard>

        <SectionCard title="Deductions & giving">
          <Row label="Itemizing" value={dg.itemizes ?? false} />
          <Row label="Charitable contributions" value={dg.charitable_contributions_ytd != null ? `$${dg.charitable_contributions_ytd.toLocaleString()}` : '$0'} />
          <Row label="Mortgage interest" value={dg.mortgage_interest_paid != null ? `$${dg.mortgage_interest_paid.toLocaleString()}` : '$0'} />
          <Row label="Est. SALT paid" value={dg.salt_paid_estimate != null ? `$${dg.salt_paid_estimate.toLocaleString()}` : '$0'} />
        </SectionCard>

        <SectionCard title="Life changes">
          {plan.life_changes && plan.life_changes.length > 0 ? (
            plan.life_changes.map((lc) => <Row key={lc} label={lc.replace('_', ' ')} value="Reported" />)
          ) : (
            <p className="text-slate-500">None reported this year.</p>
          )}
        </SectionCard>
      </div>
    </div>
  )
}
