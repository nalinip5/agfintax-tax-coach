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

# --- Augusta Rule (IRC Section 280A(g)) -- a commonly-asked colloquial
# strategy name the IRS itself never uses, so live search frequently
# fails to surface it well. Seeding real, verified content here means
# the answer no longer depends on external search quality for this
# specific, frequently-asked question. ---
if not db.query(Document).filter(Document.title == "The Augusta Rule (IRC Section 280A(g))").first():
    augusta_rule_summary = (
        "The 'Augusta Rule' is a colloquial name -- not IRS terminology -- for the personal "
        "residence rental exclusion under Internal Revenue Code Section 280A(g). It lets a "
        "homeowner rent out a primary or secondary residence for up to 14 days per calendar year "
        "without reporting that rental income as taxable, and without needing to file it on their "
        "return at all.\n\n"
        "Key conditions:\n"
        "- The property must be used personally by the owner for more than 14 days, or more than "
        "10% of the days it is rented at fair value, whichever is greater -- it must genuinely be a "
        "personal residence, not a dedicated rental property.\n"
        "- The 14-day limit is per calendar year, per property; renting for a 15th day makes ALL of "
        "the rental income for that year taxable, not just the income beyond 14 days.\n"
        "- Rent charged must be at a reasonable, fair-market rate for the area and circumstances.\n"
        "- Because the income is excluded, none of the related rental expenses (cleaning, "
        "utilities, depreciation for the rental period) are deductible either.\n\n"
        "The name comes from the strategy's popularity among homeowners near the Masters "
        "Tournament in Augusta, Georgia, who rent out their homes during that week -- but the "
        "underlying rule applies nationwide to any residence, for any short-term rental reason."
    )
    doc2 = Document(title="The Augusta Rule (IRC Section 280A(g))", source_domain="irs.gov", published=True)
    db.add(doc2)
    db.flush()
    db.add(DocumentChunk(document_id=doc2.id, content=augusta_rule_summary))

# --- SEP-IRA governing publications -- the exact question this covers
# ("What IRS publication covers SEP-IRA rules?") was previously falling
# through to a raw 400-character truncated extraction cut off mid-word.
# Seeding real, structured content makes this reliably answerable. ---
if not db.query(Document).filter(Document.title == "SEP-IRA Governing IRS Publications").first():
    sep_ira_pubs_summary = (
        "The primary IRS guide for SEP-IRA rules is Publication 560, Retirement Plans for Small "
        "Business (SEP, SIMPLE, and Qualified Plans). It covers establishing and operating a SEP, "
        "employer contribution and deduction rules, eligibility requirements, and the special "
        "contribution calculation for self-employed individuals.\n\n"
        "Related publications and forms:\n"
        "- Publication 590-A, Contributions to Individual Retirement Arrangements (IRAs): general "
        "IRA contribution rules that also apply to SEP-IRA accounts.\n"
        "- Publication 590-B, Distributions from Individual Retirement Arrangements (IRAs): "
        "withdrawals, rollovers, and required minimum distribution rules for SEP-IRAs.\n"
        "- Form 5305-SEP: the IRS model document an employer can use to establish a basic SEP plan "
        "without a separate, individually-designed plan document.\n\n"
        "For most questions about SEP-IRA setup, contribution limits, and employer "
        "responsibilities, Publication 560 is the right starting point."
    )
    doc3 = Document(title="SEP-IRA Governing IRS Publications", source_domain="irs.gov", published=True)
    db.add(doc3)
    db.flush()
    db.add(DocumentChunk(document_id=doc3.id, content=sep_ira_pubs_summary))

# --- Home Office Deduction -- the exact question that returned garbage
# navigation-menu content when live search's only candidate was a stale
# newsroom press release, now correctly excluded by the authority-tier
# fix. Seeding real content closes the resulting gap rather than leaving
# it as an honest decline. ---
if not db.query(Document).filter(Document.title == "Home Office Deduction (Simplified and Regular Methods)").first():
    home_office_summary = (
        "The home office deduction is available to self-employed individuals (sole proprietors, "
        "independent contractors, partners) who use part of their home regularly and exclusively "
        "for business. W-2 employees generally cannot claim it -- unreimbursed employee business "
        "expenses remain suspended under current law.\n\n"
        "Eligibility requirements:\n"
        "- Exclusive use: the space must be used ONLY for business, not mixed with personal use.\n"
        "- Regular use: used on a continuing basis, not occasionally.\n"
        "- Must be either the principal place of business, a place to regularly meet clients or "
        "customers, or a separate unattached structure used for business.\n\n"
        "Two calculation methods:\n"
        "- Simplified method: $5 per square foot of the home office, up to 300 square feet -- a "
        "maximum deduction of $1,500. Reported directly on Schedule C without extra forms.\n"
        "- Regular method: deduct the business-use percentage of actual home expenses (mortgage "
        "interest, utilities, insurance, depreciation, repairs). Requires Form 8829 and generally "
        "produces a larger deduction for those with high housing costs, at the cost of more "
        "recordkeeping.\n\n"
        "Either method requires the space to pass the exclusive-use and regular-use tests -- a "
        "kitchen table used for both work and family meals would not qualify."
    )
    doc4 = Document(title="Home Office Deduction (Simplified and Regular Methods)", source_domain="irs.gov", published=True)
    db.add(doc4)
    db.flush()
    db.add(DocumentChunk(document_id=doc4.id, content=home_office_summary))

# --- QBI Deduction (Section 199A) -- seeded with the VERIFIED 2026
# threshold specifically because an earlier live-search answer hallucinated
# $214,900 when the actual figure is $201,775. Seeding the correct number
# directly prevents that class of error from recurring on this topic. ---
if not db.query(Document).filter(Document.title == "Qualified Business Income (QBI) Deduction (Section 199A)").first():
    qbi_summary = (
        "The Qualified Business Income (QBI) deduction under Internal Revenue Code Section 199A "
        "allows eligible taxpayers to deduct up to 20% of qualified business income from "
        "pass-through entities -- sole proprietorships, partnerships, and S corporations.\n\n"
        "For 2026, the deduction begins phasing out above a taxable income of $201,775 (single "
        "filers) or $403,500 (married filing jointly). Below these thresholds, eligible taxpayers "
        "can generally claim the full 20% deduction regardless of business type or industry.\n\n"
        "Above the threshold, two additional limitations apply:\n"
        "- Specified service trades or businesses (SSTBs -- law, health, consulting, financial "
        "services, and similar fields) see the deduction phase out entirely at higher income.\n"
        "- For non-SSTB businesses above the threshold, the deduction is limited based on W-2 wages "
        "paid by the business and the unadjusted basis of qualified property held.\n\n"
        "The deduction also applies to 20% of qualified REIT dividends and publicly traded "
        "partnership income, which are not subject to the wage/property limitations above."
    )
    doc5 = Document(title="Qualified Business Income (QBI) Deduction (Section 199A)", source_domain="irs.gov", published=True)
    db.add(doc5)
    db.flush()
    db.add(DocumentChunk(document_id=doc5.id, content=qbi_summary))

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
    dict(domain="congress.gov", description="Federal legislation text, bill status, and Congressional Research Service reports", scope_tags=["legislation", "general"], api_method="tavily_search", enabled=True, tier=["plus", "pro"]),
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
