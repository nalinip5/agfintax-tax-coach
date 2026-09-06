"""Run with: python -m app.seed"""
from app.db import Base, SessionLocal, engine
from app.models import SourceRegistry, Subscription, TaxConstant, User

Base.metadata.create_all(bind=engine)
db = SessionLocal()

if not db.query(User).filter(User.email == "demo@agfintax.com").first():
    user = User(id="demo-user", email="demo@agfintax.com")
    db.add(user)
    db.add(Subscription(user_id="demo-user", tier="plus"))

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

_default_sources = [
    dict(
        domain="irs.gov",
        description="Federal tax rules, forms, and publications",
        scope_tags=["retirement", "business", "real_estate", "general"],
        api_method="tavily_search",
        enabled=True,
        tier=["basic", "plus", "pro"],
    ),
    dict(
        domain="treasury.gov",
        description="Treasury guidance and rulings",
        scope_tags=["general"],
        api_method="tavily_search",
        enabled=True,
        tier=["plus", "pro"],
    ),
    dict(
        domain="ssa.gov",
        description="Social Security benefits and retirement rules",
        scope_tags=["retirement"],
        api_method="direct_fetch",
        enabled=True,
        tier=["basic", "plus", "pro"],
    ),
    dict(
        domain="cms.gov",
        description="Medicare / health coverage rules relevant to HSAs",
        scope_tags=["retirement"],
        api_method="tavily_search",
        enabled=True,
        tier=["plus", "pro"],
    ),
    dict(
        domain="dol.gov",
        description="Department of Labor guidance on retirement plans",
        scope_tags=["retirement", "business"],
        api_method="tavily_search",
        enabled=True,
        tier=["pro"],
    ),
    dict(
        domain="pbgc.gov",
        description="Pension Benefit Guaranty Corporation rules",
        scope_tags=["retirement"],
        api_method="direct_fetch",
        enabled=False,
        tier=["pro"],
    ),
    dict(
        domain="sec.gov",
        description="Securities rules relevant to investment income",
        scope_tags=["business", "real_estate"],
        api_method="tavily_search",
        enabled=True,
        tier=["pro"],
    ),
]

for src in _default_sources:
    if not db.query(SourceRegistry).filter(SourceRegistry.domain == src["domain"]).first():
        db.add(SourceRegistry(**src))

db.commit()
db.close()
print("Seed complete.")
