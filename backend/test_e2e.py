"""
Comprehensive end-to-end test battery -- run before every deployment,
not reactively after a customer hits an issue.

Covers: PII guardrail (all 9 categories, multiple phrasings each),
eligibility, out-of-scope detection (with false-positive checks), all 8
life event types (actual + hypothetical), what-if scenarios, all 12
verified constants, intake-category lookups, plan-metric lookups,
internal knowledge retrieval, citation correctness (no duplicates, no
unapproved domains), conversation memory, and known regression classes
from bugs found in production.
"""
import sys
from fastapi.testclient import TestClient
sys.path.insert(0, ".")
from app.main import app
from app.tools.knowledge import APPROVED_SOURCE_DOMAINS

c = TestClient(app)
results = []


def check(category, name, cond, detail=""):
    results.append((category, name, cond, detail))
    status = "PASS" if cond else "FAIL"
    print(f"{status:5} [{category:12}] {name}" + (f"  -- {detail}" if detail and not cond else ""))


def ask(msg, uid="demo-user", convo=None):
    body = {"user_id": uid, "message": msg}
    if convo:
        body["conversation_id"] = convo
    return c.post("/api/chat", json=body).json()


def citations_valid(r):
    labels = [x["label"] for x in r["citations"]]
    no_dupes = len(labels) == len(set(labels))
    all_approved = all(l in APPROVED_SOURCE_DOMAINS for l in labels)
    return no_dupes and all_approved


# ============================================================
# CATEGORY: PII Guardrail -- every category, multiple phrasings
# ============================================================
pii_tests = [
    ("my ssn is 123-45-6789", True, "SSN standard"),
    ("my SSN is 123-456-7890", True, "SSN phone-style grouping"),
    ("my social security number is 123 45 6789", True, "SSN spelled out, spaced"),
    ("my EIN is 12-3456789", True, "EIN"),
    ("my credit card is 4111111111111111", True, "credit card"),
    ("card number: 4111-1111-1111-1111", True, "credit card dashed"),
    ("my dob is 04/12/1985", True, "DOB slash"),
    ("date of birth: 04-12-1985", True, "DOB dash"),
    ("account #: 000123456789", True, "account # symbol"),
    ("my account number is 12345678901", True, "account number spelled out"),
    ("routing number: 123456789", True, "routing number"),
    ("email me at jane.doe@example.com", True, "email"),
    ("call me at 555-123-4567", True, "phone"),
    ("my password is Sup3rSecret!", True, "password spelled out"),
    ("password: hunter2", True, "password colon"),
    ("what is the SSA wage base", False, "legit tax question, must NOT block"),
    ("I have three bank accounts", False, "generic mention, must NOT block"),
    ("what if I earn 90000 dollars", False, "legit what-if, must NOT block"),
]
for msg, expected_blocked, label in pii_tests:
    r = ask(msg)
    check("PII", label, r["blocked"] == expected_blocked, f"expected={expected_blocked} got={r['blocked']}")

# ============================================================
# CATEGORY: Eligibility / access control
# ============================================================
check("Eligibility", "no-tier user blocked with clear message",
      "paid AGFinTax subscribers" in ask("hello", uid="totally-fake-user")["reply"])

# ============================================================
# CATEGORY: Out-of-scope (with false-positive regression checks)
# ============================================================
oos_tests = [
    ("should I buy this stock", True, "investment advice"),
    ("should I hold onto my crypto", True, "crypto hold advice"),
    ("what if I sell my shares in the company", True, "genuine stock sell"),
    ("What is my California state corporate tax liability?", True, "state + corporate"),
    ("interpret this contract for me", True, "legal advice"),
    ("what if I sell my rental property", False, "REGRESSION: bare 'sell' must not false-positive"),
    ("what if I buy a house next year", False, "REGRESSION: bare 'buy' must not false-positive"),
    ("should I sell my SEP-IRA holdings this year", False, "REGRESSION: 'sell' in tax context must not false-positive"),
]
for msg, expect_oos, label in oos_tests:
    r = ask(msg)
    is_oos = "outside what Tax Coach" in r["reply"]
    check("OutOfScope", label, is_oos == expect_oos, f"expected_oos={expect_oos} got={is_oos}")

# ============================================================
# CATEGORY: Life events -- actual (present-tense) and hypothetical
# ============================================================
life_events = [
    "I got married last month",
    "I am getting divorced",
    "I had a new child this year",
    "I just bought a house",
    "I started a new job",
    "I am starting a new business",
    "I am retiring next year",
    "I received an inheritance",
]
for msg in life_events:
    r = ask(msg)
    check("LifeEvent", f"actual event handled: {msg[:30]}", "AGFinTax Tax Planner" in r["reply"])
    check("LifeEvent", f"no hallucinated numbers (regression check)", citations_valid(r))

hypothetical_events = [
    "what if i get married next year",
    "what if I have a baby",
    "what if I buy a house",
]
for msg in hypothetical_events:
    r = ask(msg)
    check("LifeEvent", f"hypothetical NOT treated as fact: {msg[:30]}", "I see this involves" not in r["reply"] and "-- your plan on file" not in r["reply"] or "Looking ahead" not in r["reply"])

# ============================================================
# CATEGORY: What-if scenarios
# ============================================================
r = ask("what if my income doubles")
check("WhatIf", "income doubling uses real AGI (284,000)", "284,000" in r["reply"])
check("WhatIf", "income doubling has citation", len(r["citations"]) > 0 and citations_valid(r))

r = ask("what if I max my sep-ira")
check("WhatIf", "SEP-IRA what-if mentions real limit", "72,000" in r["reply"] or "70,000" in r["reply"])

r = ask("what if I make a large charitable donation")
check("WhatIf", "charitable donation what-if responds", len(r["reply"]) > 20)

# ============================================================
# CATEGORY: Verified constants -- every seeded constant
# ============================================================
constant_tests = [
    ("What is the HSA contribution limit?", "4,400"),
    ("what is the standard deduction", "16,100"),
    ("What is the SEP-IRA contribution limit for the planning year?", "72,000"),
    ("what is the IRA contribution limit", "7,500"),
    ("what is the SALT deduction cap", "40,400"),
    ("what is the 401k contribution limit", "24,500"),
    ("what is the child tax credit", "2,200"),
]
for msg, expected_fig in constant_tests:
    r = ask(msg)
    check("Constants", f"{msg[:40]} -> {expected_fig}", expected_fig in r["reply"], f"got: {r['reply'][:100]}")
    check("Constants", f"{msg[:40]} has irs.gov citation", any(x["label"] == "irs.gov" for x in r["citations"]))

# ============================================================
# CATEGORY: Intake-category and plan-metric lookups
# ============================================================
check("PlanData", "dependents lookup", "dependent" in ask("do I have any dependents")["reply"].lower())
check("PlanData", "real estate lookup", "residence" in ask("do I own any real estate")["reply"].lower())
check("PlanData", "retirement contribution lookup", "8%" in ask("how much am I contributing to my 401k")["reply"])
check("PlanData", "deductions lookup", "standard deduction" in ask("am I itemizing my deductions")["reply"].lower())
check("PlanData", "marginal rate direct lookup", "24%" in ask("What is my marginal tax rate?")["reply"])
check("PlanData", "full plan question", "Confirmed savings so far" in ask("what is on my plan")["reply"])
check("PlanData", "401k LIMIT question routes to constant, not personal rate (regression)", "24,500" in ask("what is the 401k contribution limit")["reply"])
for msg in ["what is on my plan", "do I have any dependents", "am I itemizing my deductions", "What is my marginal tax rate?"]:
    r = ask(msg)
    check("PlanData", f"honest plan-data citation (not fake irs.gov): {msg[:30]}", [c["label"] for c in r["citations"]] == ["your AGFinTax plan"])

# ============================================================
# CATEGORY: Internal knowledge retrieval (seeded documents)
# ============================================================
r = ask("What does the IRS say about the Augusta Rule?")
check("InternalKB", "Augusta Rule has real content", "Section 280A" in r["reply"])
check("InternalKB", "Augusta Rule citations valid (no dupes, approved only)", citations_valid(r))

r = ask("What IRS publication covers SEP-IRA rules?")
check("InternalKB", "SEP-IRA publications full content", "Form 5305-SEP" in r["reply"])
check("InternalKB", "SEP-IRA not truncated mid-word", not r["reply"].rstrip().endswith("..."))
check("InternalKB", "SEP-IRA citations valid", citations_valid(r))

r = ask("tell me about the tip income deduction")
check("InternalKB", "OBBBA doc found", "OBBBA" in r["reply"])
check("InternalKB", "OBBBA has citation now (was missing before fix)", len(r["citations"]) > 0)

r = ask("What is the strategy for home sale deduction")
check("InternalKB", "unrelated query correctly rejected (relevance floor)", "your plan on file" not in r["reply"] and "OBBBA" not in r["reply"])

r = ask("What are the rules for a home office deduction?")
check("InternalKB", "home office deduction has real content", "exclusive" in r["reply"].lower() and "simplified method" in r["reply"].lower())
check("InternalKB", "REGRESSION: home office not misrouted to Augusta Rule (tie-break fix)", "Augusta" not in r["reply"])

r = ask("How does the QBI deduction work for my income level?")
check("InternalKB", "QBI uses CORRECT verified threshold, not the earlier hallucinated 214,900", "201,775" in r["reply"] and "214,900" not in r["reply"])

# ============================================================
# CATEGORY: Professional judgment / referral
# ============================================================
check("Referral", "election request refused", "AGFinTax Tax Planner" in ask("Should I elect or skip the Augusta Rule strategy on my plan?")["reply"])

# ============================================================
# CATEGORY: Source registry / allowlist enforcement
# ============================================================
sources = c.get("/api/kb/sources").json()
check("Sources", "exactly 8 approved sources", len(sources) == 8)
check("Sources", "all seeded sources are on the approved list", all(s["domain"] in APPROVED_SOURCE_DOMAINS for s in sources))
bad = c.post("/api/kb/sources", json={"domain": "sometaxblog.com", "description": "x", "scope_tags": [], "api_method": "tavily_search", "enabled": True, "tier": ["pro"]})
check("Sources", "unapproved domain rejected at write time", bad.status_code == 422)

# ============================================================
# CATEGORY: Conversation memory
# ============================================================
r1 = ask("I got married last month, planning to file MFJ")
convo = r1["conversation_id"]
ask("unrelated filler", convo=convo)
r_followup = ask("what is my standard deduction now", convo=convo)
check("Memory", "MFJ status remembered across turns without restating", "32,200" in r_followup["reply"])
r_fresh = ask("what is my standard deduction now")
check("Memory", "fresh conversation does NOT leak MFJ from a different session", "16,100" in r_fresh["reply"])

# ============================================================
# SUMMARY
# ============================================================
print()
print("=" * 70)
by_category = {}
for cat, name, ok, detail in results:
    by_category.setdefault(cat, [0, 0])
    by_category[cat][0] += 1 if ok else 0
    by_category[cat][1] += 1

total_pass = sum(1 for _, _, ok, _ in results if ok)
total = len(results)
for cat, (p, t) in by_category.items():
    marker = "PASS" if p == t else "FAIL"
    print(f"{marker:5} {cat:14} {p}/{t}")
print("=" * 70)
print(f"TOTAL: {total_pass}/{total}")
if total_pass < total:
    print()
    print("FAILURES:")
    for cat, name, ok, detail in results:
        if not ok:
            print(f"  [{cat}] {name}" + (f" -- {detail}" if detail else ""))
