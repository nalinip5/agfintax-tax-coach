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

# --- Federal income tax brackets (2026) ---
# Source: IRS Revenue Procedure 2025-32, via Tax Foundation's 2026 Tax
# Brackets summary (taxfoundation.org/data/all/federal/2026-tax-brackets).
if not db.query(TaxConstant).filter(TaxConstant.key == "federal_income_brackets", TaxConstant.tax_year == 2026, TaxConstant.filing_status == "single").first():
    db.add(
        TaxConstant(
            tax_year=2026,
            key="federal_income_brackets",
            filing_status="single",
            value=[
                {"upto": 12400, "rate": 0.10},
                {"upto": 50400, "rate": 0.12},
                {"upto": 105700, "rate": 0.22},
                {"upto": 201775, "rate": 0.24},
                {"upto": 256225, "rate": 0.32},
                {"upto": 640600, "rate": 0.35},
                {"rate": 0.37},
            ],
            source_url="https://www.irs.gov",
        )
    )
if not db.query(TaxConstant).filter(TaxConstant.key == "federal_income_brackets", TaxConstant.tax_year == 2026, TaxConstant.filing_status == "married_joint").first():
    db.add(
        TaxConstant(
            tax_year=2026,
            key="federal_income_brackets",
            filing_status="married_joint",
            value=[
                {"upto": 24800, "rate": 0.10},
                {"upto": 100800, "rate": 0.12},
                {"upto": 211400, "rate": 0.22},
                {"upto": 403550, "rate": 0.24},
                {"upto": 512450, "rate": 0.32},
                {"upto": 768700, "rate": 0.35},
                {"rate": 0.37},
            ],
            source_url="https://www.irs.gov",
        )
    )

# --- PRD 4.3: verified IRS-defined constants Tax Coach must answer from,
# never estimate. All 2026 figures, per IRS Revenue Procedure 2025-32 and
# IRS Notice 2025-67 (retirement plan cost-of-living adjustments). ---
_constants_2026 = [
    ("standard_deduction", "single", 16100),
    ("standard_deduction", "married_joint", 32200),
    ("sep_ira_contribution_limit", None, 72000),
    ("ira_contribution_limit", None, 7500),
    ("ira_catchup_contribution_50plus", None, 1100),
    ("hsa_contribution_limit_self_only", None, 4400),
    ("hsa_contribution_limit_family", None, 8750),
    ("salt_deduction_cap", None, 40400),
    ("niit_threshold", "single", 200000),
    ("niit_threshold", "married_joint", 250000),
    ("qbi_deduction_income_threshold", "single", 201775),
    ("qbi_deduction_income_threshold", "married_joint", 403500),
    ("roth_ira_phaseout_start", "single", 153000),
    ("roth_ira_phaseout_end", "single", 168000),
    ("roth_ira_phaseout_start", "married_joint", 242000),
    ("roth_ira_phaseout_end", "married_joint", 252000),
    ("401k_employee_contribution_limit", None, 24500),
    ("401k_catchup_contribution_50plus", None, 8000),
    ("child_tax_credit_per_child", None, 2200),
]
for key, filing_status, value in _constants_2026:
    exists = (
        db.query(TaxConstant)
        .filter(TaxConstant.key == key, TaxConstant.tax_year == 2026, TaxConstant.filing_status == filing_status)
        .first()
    )
    if not exists:
        db.add(TaxConstant(tax_year=2026, key=key, filing_status=filing_status, value=value, source_url="https://www.irs.gov"))

# --- OBBBA internal knowledge (paraphrased, not copied). Describes what
# OBBBA established starting in 2025; year-specific dollar figures for
# 2026 (which are separately inflation-adjusted per Rev. Proc. 2025-32)
# live in the verified tax_constants table above, not repeated here. ---
if not db.query(Document).filter(Document.title == "OBBBA Summary (One Big Beautiful Bill Act, 2025)").first():
    obbba_summary = (
        "The One Big Beautiful Bill Act (OBBBA, Public Law 119-21) was signed into law on "
        "July 4, 2025, and makes several 2017 Tax Cuts and Jobs Act provisions permanent while "
        "adding new ones, effective tax year 2025 onward. Key provisions:\n\n"
        "- Standard deduction permanently raised starting 2025, indexed for inflation annually "
        "thereafter (see tax_constants for the current year's exact figure).\n"
        "- The 2017 individual tax brackets and rates (including the top 37% rate) are made "
        "permanent, with inflation indexing continuing each year.\n"
        "- SALT deduction cap raised from $10,000 to $40,000 starting 2025, increasing 1% per year "
        "through 2029, phasing out for incomes above roughly $500,000; reverts to $10,000 in 2030.\n"
        "- New deductions for tip income (up to $25,000) and overtime pay (up to $12,500 single / "
        "$25,000 joint), 2025-2028, phasing out above $150,000 MAGI (single) / $300,000 (joint).\n"
        "- Additional $6,000 deduction for filers age 65+, effective 2025-2028.\n"
        "- Child Tax Credit permanently raised to $2,200 per child starting 2025, indexed for "
        "inflation in future years.\n"
        "- Third-party payment apps (Venmo, PayPal, etc.) only required to issue Form 1099-K above "
        "$20,000 and 200 transactions annually -- but all income remains taxable and reportable "
        "regardless of whether a 1099-K is issued.\n\n"
        "This is current law with no sunset yet reached; always verify current-year specific dollar "
        "figures against the tax_constants table or irs.gov before advising on a specific filing."
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
approved_domains = {s["domain"] for s in _default_sources}
for stale in db.query(SourceRegistry).filter(SourceRegistry.domain.notin_(approved_domains)).all():
    db.delete(stale)

db.flush()

# --- Demo plan-aware TaxPlan (PRD 4.1), tax year 2026 ---
existing_plan = db.query(TaxPlan).filter(TaxPlan.user_id == "demo-user", TaxPlan.tax_year == 2026).first()
if not existing_plan:
    plan = TaxPlan(
        user_id="demo-user",
        tax_year=2026,
        filing_status="single",
        agi=142000,
        magi=142500,
        marginal_rate=0.24,
        confirmed_savings=3200,
        potential_savings=5100,
        urgent_observations=["Q4 estimated tax payment due January 15, 2027 -- not yet confirmed as paid"],
        missing_questionnaire_items=["HSA eligibility (high-deductible health plan status not confirmed)"],
        # --- Structured intake data, matching the real product's 8-step
        # intake journey (Filing Information -> Life Changes). ---
        filing_info={"state": "California", "occupation": "Software Engineer", "spouse_occupation": None},
        age_planning={"taxpayer_age": 34, "spouse_age": None, "retirement_age_target": 60},
        income_planning={
            "wages": 118000,
            "self_employment_income": 24000,
            "investment_income": 0,
            "federal_tax_withheld": 21000,
            "estimated_payments_made": 0,
        },
        retirement_planning={
            "has_401k": True,
            "401k_contribution_pct": 8,
            "employer_match_pct": 4,
            "has_traditional_ira": False,
            "has_sep_ira": True,
            "sep_ira_contribution_ytd": 0,
        },
        family_education={"dependents": [], "has_dependent_care_expenses": False, "has_529_plan": False},
        real_estate_assets={"owns_primary_residence": False, "owns_rental_property": False, "brokerage_account_value": 12000},
        deductions_giving={"itemizes": False, "charitable_contributions_ytd": 0, "mortgage_interest_paid": 0, "salt_paid_estimate": 9200},
        life_changes=[],
    )
    db.add(plan)
    db.flush()
    db.add(
        Strategy(
            tax_plan_id=plan.id,
            title="Maximize traditional 401(k) contribution",
            description="Increase 401(k) deferral toward the $24,500 annual limit to reduce taxable income.",
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
            description="Contribute up to 25% of net self-employment earnings (up to $72,000) to a SEP-IRA.",
            why_it_applies="Your 1099 consulting income qualifies for SEP-IRA contributions, which are not available on W-2-only income.",
            status="confirmed",
            estimated_savings=3200,
            citations=["https://www.irs.gov"],
        )
    )

db.commit()
db.close()
print("Seed complete.")
