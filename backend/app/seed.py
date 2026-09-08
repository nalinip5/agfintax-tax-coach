"""Run with: python -m app.seed"""
from app.db import Base, SessionLocal, engine
from app.models import (
    Document,
    DocumentChunk,
    SourceRegistry,
    Strategy,
    Subscription,
    TaxConstant,
    TaxPlan,
    User,
)

Base.metadata.create_all(bind=engine)
db = SessionLocal()

if not db.query(User).filter(User.email == "demo@agfintax.com").first():
    user = User(id="demo-user", email="demo@agfintax.com")
    db.add(user)
    db.add(Subscription(user_id="demo-user", tier="plus"))

# --- Federal income tax brackets (2025) ---
if not db.query(TaxConstant).filter(TaxConstant.key == "federal_income_brackets").first():
    db.add(
        TaxConstant(
            tax_year=2025,
            key="federal_income_brackets",
            filing_status="single",
            value=[
                {"upto": 11925, "rate": 0.10},
                {"upto": 48475, "rate": 0.12},
                {"upto": 103350, "rate": 0.22},
                {"upto": 197300, "rate": 0.24},
                {"upto": 250525, "rate": 0.32},
                {"upto": 626350, "rate": 0.35},
                {"rate": 0.37},
            ],
            source_url="https://www.irs.gov",
        )
    )

# --- PRD 4.3: verified IRS-defined constants Tax Coach must answer from,
# never estimate. All 2025 figures. ---
_constants_2025 = [
    ("standard_deduction", "single", 15750),
    ("standard_deduction", "married_joint", 31500),
    ("sep_ira_contribution_limit", None, 70000),
    ("ira_contribution_limit", None, 7000),
    ("ira_catchup_contribution_50plus", None, 1000),
    ("hsa_contribution_limit_self_only", None, 4300),
    ("hsa_contribution_limit_family", None, 8550),
    ("salt_deduction_cap", None, 40000),
    ("niit_threshold", "single", 200000),
    ("niit_threshold", "married_joint", 250000),
    ("qbi_deduction_income_threshold", "single", 197300),
    ("qbi_deduction_income_threshold", "married_joint", 394600),
    ("roth_ira_phaseout_start", "single", 150000),
    ("roth_ira_phaseout_end", "single", 165000),
    ("roth_ira_phaseout_start", "married_joint", 236000),
    ("roth_ira_phaseout_end", "married_joint", 246000),
    ("401k_employee_contribution_limit", None, 23500),
    ("401k_catchup_contribution_50plus", None, 7500),
    ("child_tax_credit_per_child", None, 2200),
]
for key, filing_status, value in _constants_2025:
    exists = (
        db.query(TaxConstant)
        .filter(TaxConstant.key == key, TaxConstant.tax_year == 2025, TaxConstant.filing_status == filing_status)
        .first()
    )
    if not exists:
        db.add(TaxConstant(tax_year=2025, key=key, filing_status=filing_status, value=value, source_url="https://www.irs.gov"))

# --- OBBBA internal knowledge (paraphrased, not copied) ---
if not db.query(Document).filter(Document.title == "OBBBA Summary (One Big Beautiful Bill Act, 2025)").first():
    obbba_summary = (
        "The One Big Beautiful Bill Act (OBBBA, Public Law 119-21) was signed into law on "
        "July 4, 2025, and makes several 2017 Tax Cuts and Jobs Act provisions permanent while "
        "adding new ones. Key changes for individual filers, tax year 2025 onward:\n\n"
        "- Standard deduction permanently raised to $15,750 (single) / $31,500 (married filing "
        "jointly), indexed for inflation annually.\n"
        "- The 2017 individual tax brackets and rates (including the top 37% rate) are made "
        "permanent, with inflation indexing for the 10%, 12%, and 22% brackets starting 2026.\n"
        "- SALT deduction cap raised from $10,000 to $40,000 for 2025-2029 (increasing 1% per year), "
        "phasing out for incomes above $500,000; reverts to $10,000 in 2030.\n"
        "- New deductions for tip income (up to $25,000) and overtime pay (up to $12,500 single / "
        "$25,000 joint), 2025-2028, phasing out above $150,000 MAGI (single) / $300,000 (joint).\n"
        "- Additional $6,000 deduction for filers age 65+, effective 2025-2028.\n"
        "- Child Tax Credit permanently raised to $2,200 per child, indexed for inflation.\n"
        "- Third-party payment apps (Venmo, PayPal, etc.) only required to issue Form 1099-K above "
        "$20,000 and 200 transactions annually -- but all income remains taxable and reportable "
        "regardless of whether a 1099-K is issued.\n\n"
        "This is current law with no sunset yet reached; always verify current-year specifics "
        "against irs.gov before advising on a specific filing."
    )
    doc = Document(title="OBBBA Summary (One Big Beautiful Bill Act, 2025)", source_domain="irs.gov", published=True)
    db.add(doc)
    db.flush()
    db.add(DocumentChunk(document_id=doc.id, content=obbba_summary))

# --- PRD Section 5: the ONLY approved official sources. No other domain
# may ever be added here -- see app/tools/knowledge.py's
# APPROVED_SOURCE_DOMAINS, which is enforced independently of this seed. ---
_default_sources = [
    dict(domain="irs.gov", description="Federal tax law, publications, forms, instructions, and tax constants", scope_tags=["retirement", "business", "real_estate", "general", "legislation"], api_method="tavily_search", enabled=True, tier=["basic", "plus", "pro"]),
    dict(domain="treasury.gov", description="Treasury regulations, proposed rules, and final rules", scope_tags=["general"], api_method="tavily_search", enabled=True, tier=["plus", "pro"]),
    dict(domain="ssa.gov", description="Social Security wage base and FICA contribution limits", scope_tags=["retirement"], api_method="tavily_search", enabled=True, tier=["basic", "plus", "pro"]),
    dict(domain="cms.gov", description="IRMAA income thresholds and Medicare premium surcharges", scope_tags=["retirement"], api_method="tavily_search", enabled=True, tier=["plus", "pro"]),
    dict(domain="dol.gov", description="401k, 403b, and ERISA contribution limits and rules", scope_tags=["retirement", "business"], api_method="tavily_search", enabled=True, tier=["plus", "pro"]),
    dict(domain="pbgc.gov", description="Defined benefit pension plan rules and premium rates", scope_tags=["retirement"], api_method="tavily_search", enabled=True, tier=["pro"]),
    dict(domain="sec.gov", description="Accredited investor definitions -- high-net-worth strategies only", scope_tags=["business"], api_method="tavily_search", enabled=True, tier=["pro"]),
]
for src in _default_sources:
    if not db.query(SourceRegistry).filter(SourceRegistry.domain == src["domain"]).first():
        db.add(SourceRegistry(**src))
# Remove anything ever inserted outside the approved list (e.g. congress.gov,
# added ad hoc before the PRD's closed list was formalized).
approved_domains = {s["domain"] for s in _default_sources}
for stale in db.query(SourceRegistry).filter(SourceRegistry.domain.notin_(approved_domains)).all():
    db.delete(stale)

db.flush()

# --- Demo plan-aware TaxPlan (PRD 4.1) ---
existing_plan = db.query(TaxPlan).filter(TaxPlan.user_id == "demo-user", TaxPlan.tax_year == 2025).first()
if not existing_plan:
    plan = TaxPlan(
        user_id="demo-user",
        tax_year=2025,
        filing_status="single",
        agi=142000,
        magi=142500,
        marginal_rate=0.24,
        confirmed_savings=3200,
        potential_savings=5100,
        urgent_observations=["Q4 estimated tax payment due January 15, 2026 -- not yet confirmed as paid"],
        missing_questionnaire_items=["HSA eligibility (high-deductible health plan status not confirmed)"],
        data={"income_sources": ["W-2", "1099 consulting"]},
    )
    db.add(plan)
    db.flush()
    db.add(
        Strategy(
            tax_plan_id=plan.id,
            title="Maximize traditional 401(k) contribution",
            description="Increase 401(k) deferral toward the $23,500 annual limit to reduce taxable income.",
            why_it_applies="Your AGI of $142,000 puts you in the 24% marginal bracket -- each additional dollar deferred saves $0.24 in federal tax.",
            status="potential",
            estimated_savings=1800,
            citations=["https://www.irs.gov"],
        )
    )
    db.add(
        Strategy(
            tax_plan_id=plan.id,
            title="SEP-IRA contribution from 1099 consulting income",
            description="Contribute up to 25% of net self-employment earnings (up to $70,000) to a SEP-IRA.",
            why_it_applies="Your 1099 consulting income qualifies for SEP-IRA contributions, which are not available on W-2-only income.",
            status="confirmed",
            estimated_savings=3200,
            citations=["https://www.irs.gov"],
        )
    )

db.commit()
db.close()
print("Seed complete.")
