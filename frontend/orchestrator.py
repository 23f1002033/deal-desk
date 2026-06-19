"""
Deal Desk — live orchestration for the demo frontend.

This module re-uses the *exact* agent prompts from the project root (prompts.py)
and drives the same multi-agent workflow the Band agents run, but in a single
process so it can be rendered step-by-step in the Streamlit UI:

    Coordinator reads RFP
      -> recruits ONLY the specialists the RFP needs
      -> each specialist drafts its section
      -> Reviewer red-teams each section (revision loop until APPROVED)
      -> business rules: discount > 20% pauses for human approval;
         total > budget bounces back to Pricing
      -> Coordinator assembles one final proposal

In Band, all of this is @mention routing between separate agents. Here the same
roles and prompts talk to one OpenAI-compatible endpoint (AI/ML API) so a judge
can watch the whole thing happen from a browser.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Iterable

from openai import OpenAI

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts import (  # noqa: E402
    COORDINATOR,
    PRICING_SPECIALIST,
    TECHNICAL_SPECIALIST,
    LEGAL_SPECIALIST,
    REVIEWER,
)

DEFAULT_MODEL = "gpt-4o"
DEFAULT_BASE_URL = "https://api.aimlapi.com/v1"
MAX_REVIEW_ROUNDS = 2  

SPECIALISTS = {
    "pricing": {
        "name": "Pricing Specialist",
        "emoji": "💰",
        "prompt": PRICING_SPECIALIST,
        "trigger": "price, budget, cost, discount, or licensing",
    },
    "technical": {
        "name": "Technical Specialist",
        "emoji": "🛠️",
        "prompt": TECHNICAL_SPECIALIST,
        "trigger": "architecture, hosting, integrations, security, scale, or features",
    },
    "legal": {
        "name": "Legal Specialist",
        "emoji": "⚖️",
        "prompt": LEGAL_SPECIALIST,
        "trigger": "contracts, SLA penalties, data processing, or compliance (GDPR/HIPAA/SOC2)",
    },
}


@dataclass
class Event:
    kind: str  # "status" | "recruit" | "skip" | "section" | "review" | "rule" | "final" | "done"
    actor: str  # which agent emitted it
    title: str
    body: str = ""
    meta: dict = field(default_factory=dict)


EventSink = Callable[[Event], None]


@dataclass
class RecruitDecision:
    recruit: list[str]
    skip: list[dict]  # [{"role": ..., "reason": ...}]
    customer: str
    budget: str
    summary: str


class DealDesk:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, model: str = DEFAULT_MODEL):
        if not api_key:
            raise ValueError("An AI/ML API key is required to run the live Deal Desk.")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def _chat(self, system: str, user: str, temperature: float = 0.4) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    def triage(self, rfp: str) -> RecruitDecision:
        instruction = (
            "Read the RFP below. Decide which specialists to recruit. Recruit ONLY "
            "the ones whose topic actually appears in the RFP.\n"
            "- Pricing Specialist if it mentions price, budget, cost, discount, or licensing.\n"
            "- Technical Specialist if it mentions architecture, hosting, integrations, "
            "security, scale, or features.\n"
            "- Legal Specialist if it mentions contracts, liability, SLA penalties, data "
            "processing agreements, or compliance (GDPR/HIPAA/SOC2).\n\n"
            "Return ONLY valid JSON, no prose, in this shape:\n"
            '{"customer": "...", "budget": "... or \'not stated\'", '
            '"summary": "one sentence on what the customer wants", '
            '"recruit": ["pricing","technical","legal"], '
            '"skip": [{"role":"legal","reason":"no contract/compliance topics in RFP"}]}\n'
            "Use only these role keys: pricing, technical, legal.\n\n"
            f"RFP:\n{rfp}"
        )
        raw = self._chat(COORDINATOR, instruction, temperature=0.1)
        data = _extract_json(raw)

        recruit = [r for r in data.get("recruit", []) if r in SPECIALISTS]
        if not recruit:  # safety net — never end up with an empty team
            recruit = _keyword_recruit(rfp)
        skip = [s for s in data.get("skip", []) if s.get("role") in SPECIALISTS]
        return RecruitDecision(
            recruit=recruit,
            skip=skip,
            customer=str(data.get("customer", "the customer")).strip() or "the customer",
            budget=str(data.get("budget", "not stated")).strip() or "not stated",
            summary=str(data.get("summary", "")).strip(),
        )

    def draft(self, role: str, rfp: str, fix_note: str | None = None) -> str:
        spec = SPECIALISTS[role]
        task = (
            f"The Coordinator hands you this RFP. Produce your {spec['name']} section "
            "using your required output format. Use the EXACT figures from the RFP.\n\n"
            f"RFP:\n{rfp}"
        )
        if fix_note:
            task += (
                "\n\nThe Reviewer flagged the following on your previous draft. "
                "Fix EXACTLY these issues and resend the full section:\n" + fix_note
            )
        return self._chat(spec["prompt"], task, temperature=0.4)

    def review(self, role: str, rfp: str, section: str) -> tuple[bool, str]:
        spec = SPECIALISTS[role]
        task = (
            f"Review this {spec['name']} section against the RFP. If it is solid, reply "
            "with APPROVED and a one-line reason. Otherwise give a short numbered list of "
            "the specific problems to fix.\n\n"
            f"RFP:\n{rfp}\n\n--- {spec['name'].upper()} SECTION TO REVIEW ---\n{section}"
        )
        verdict = self._chat(REVIEWER, task, temperature=0.2)
        approved = bool(re.search(r"\bapproved\b", verdict, re.IGNORECASE))
        return approved, verdict

    def analyze(self, rfp: str, decision: "RecruitDecision", sections: dict, final: str) -> dict:
        """One structured pass over the finished proposal for the exec dashboard."""
        instruction = (
            "You are scoring a finished sales proposal for an executive dashboard. "
            "Read the RFP and the proposal, then return ONLY valid JSON (no prose):\n"
            '{"deal_value": "$ figure or \'N/A\'", '
            '"win_probability": <int 0-100>, '
            '"timeline": "short string e.g. \'6 months\'", '
            '"quality_score": <int 0-100, how complete/defensible the proposal is>, '
            '"risks": [{"title": "...", "severity": "low|medium|high", "mitigation": "..."}]}\n'
            "Give 2-5 risks, most material first.\n\n"
            f"RFP:\n{rfp[:3500]}\n\nPROPOSAL:\n{final[:5000]}"
        )
        data = _extract_json(self._chat(COORDINATOR, instruction, temperature=0.2))
        risks = []
        for r in data.get("risks", [])[:5]:
            sev = str(r.get("severity", "medium")).lower()
            risks.append({
                "title": str(r.get("title", "Unspecified risk")).strip(),
                "severity": sev if sev in ("low", "medium", "high") else "medium",
                "mitigation": str(r.get("mitigation", "")).strip(),
            })
        return {
            "deal_value": str(data.get("deal_value", "N/A")).strip() or "N/A",
            "win_probability": _clamp_int(data.get("win_probability"), 70),
            "timeline": str(data.get("timeline", "TBD")).strip() or "TBD",
            "quality_score": _clamp_int(data.get("quality_score"), 80),
            "risks": risks,
        }


def run_deal_desk(
    desk: DealDesk,
    rfp: str,
    emit: EventSink,
    approvals: dict | None = None,
    prior: dict | None = None,
) -> dict:
    """Drive the workflow. Returns the assembled result dict.

    `approvals` lets the caller pre-answer human-in-the-loop gates, e.g.
    {"discount": True}. If a gate is hit without an answer, the run records it
    in the result as `pending_approval` and stops before finalizing.

    `prior` carries the decision + sections from a paused run so resuming after a
    human approval re-uses the exact drafts instead of regenerating (and possibly
    changing) them.
    """
    approvals = approvals or {}

    if prior:
        decision: RecruitDecision = prior["decision"]
        sections: dict[str, str] = dict(prior["sections"])
        emit(Event("status", "Coordinator", "Resuming with the human's decision…"))
    else:
        sections = {}
        emit(Event("status", "Coordinator", "Reading the RFP and deciding who to recruit…"))
        decision = desk.triage(rfp)

        emit(
            Event(
                "status",
                "Coordinator",
                f"Customer: **{decision.customer}** · Budget: **{decision.budget}**",
                decision.summary,
            )
        )

        for role in decision.recruit:
            spec = SPECIALISTS[role]
            emit(
                Event(
                    "recruit",
                    "Coordinator",
                    f"{spec['emoji']} Recruiting the {spec['name']}",
                    f"RFP mentions {spec['trigger']}.",
                    {"role": role},
                )
            )
        for s in decision.skip:
            spec = SPECIALISTS[s["role"]]
            emit(
                Event(
                    "skip",
                    "Coordinator",
                    f"Not recruiting the {spec['name']}",
                    s.get("reason", "Topic absent from the RFP."),
                    {"role": s["role"]},
                )
            )

        for role in decision.recruit:
            spec = SPECIALISTS[role]
            fix_note: str | None = None
            approved = False
            section = ""
            for round_no in range(1, MAX_REVIEW_ROUNDS + 1):
                emit(
                    Event(
                        "status",
                        spec["name"],
                        f"{spec['emoji']} Drafting the {spec['name'].lower().replace(' specialist','')} section"
                        + (f" (revision {round_no})" if round_no > 1 else "…"),
                        meta={"role": role},
                    )
                )
                section = desk.draft(role, rfp, fix_note)
                emit(Event("section", spec["name"], f"{spec['name']} section", section, {"role": role}))

                emit(Event("status", "Reviewer", "🔎 Red-teaming the section…", meta={"role": role}))
                approved, verdict = desk.review(role, rfp, section)
                emit(
                    Event(
                        "review",
                        "Reviewer",
                        "APPROVED" if approved else "Sent back for revision",
                        verdict,
                        {"role": role, "approved": approved},
                    )
                )
                if approved:
                    break
                fix_note = verdict
            sections[role] = section
            if not approved:
                emit(
                    Event(
                        "rule",
                        "Coordinator",
                        "Proceeding after max review rounds",
                        f"The {spec['name']} section is included but was flagged by the Reviewer.",
                        {"role": role},
                    )
                )

    # Business rule — discount > 20% needs human approval.
    discount = _parse_discount(sections.get("pricing", ""))
    if discount is not None and discount > 20:
        emit(
            Event(
                "rule",
                "Coordinator",
                f"⚠️ HUMAN APPROVAL REQUIRED — discount of {discount:g}% exceeds the 20% threshold",
                "The Coordinator halts and pulls the human into the room before finalizing.",
                {"discount": discount},
            )
        )
        if "discount" not in approvals:
            return {
                "pending_approval": {"type": "discount", "discount": discount},
                "decision": decision,
                "sections": sections,
            }
        if not approvals["discount"]:
            emit(Event("rule", "Coordinator", "Human REJECTED the discount", "Proposal halted."))
            return {"rejected": True, "decision": decision, "sections": sections}
        emit(Event("rule", "Human", "✅ Discount approved by human", "Resuming finalization."))

    # Business rule — total over budget bounces back to Pricing (one bounce in the demo).
    over = _over_budget(sections.get("pricing", ""), decision.budget)
    if over:
        emit(
            Event(
                "rule",
                "Coordinator",
                "⚠️ Total exceeds stated budget — sending back to Pricing to revise",
                f"Budget: {decision.budget}.",
            )
        )
        fixed = desk.draft(
            "pricing",
            rfp,
            fix_note=f"The total exceeds the customer's stated budget of {decision.budget}. "
            "Re-price so the TOTAL fits within budget and show the math.",
        )
        sections["pricing"] = fixed
        emit(Event("section", "Pricing Specialist", "Pricing section (revised to fit budget)", fixed, {"role": "pricing"}))

    # Assemble the final proposal.
    emit(Event("status", "Coordinator", "Assembling the final proposal…"))
    final = _assemble(desk, rfp, decision, sections)
    emit(Event("final", "Coordinator", f"Proposal for {decision.customer}", final))

    emit(Event("status", "Coordinator", "Scoring the proposal and surfacing risks…"))
    metrics = desk.analyze(rfp, decision, sections, final)
    emit(Event("metrics", "Coordinator", "Executive metrics", meta=metrics))
    emit(Event("done", "Coordinator", "✅ Proposal complete and ready for the customer."))

    return {"final": final, "decision": decision, "sections": sections, "metrics": metrics}


def _assemble(desk: DealDesk, rfp: str, decision: RecruitDecision, sections: dict[str, str]) -> str:
    ordered = []
    if "technical" in sections:
        ordered.append("## Technical Solution\n" + sections["technical"])
    if "pricing" in sections:
        ordered.append("## Pricing\n" + sections["pricing"])
    if "legal" in sections:
        ordered.append("## Legal & Compliance\n" + sections["legal"])
    body = "\n\n".join(ordered)

    instruction = (
        "Write ONLY the Executive Summary (3-4 sentences: what the customer asked for, "
        "what we propose, the headline price, and the timeline) and a short Next Steps "
        "list (sign-off, proposed kickoff date, point of contact). Do not repeat the "
        "specialist sections. Use the approved sections below as your source.\n\n"
        f"Customer: {decision.customer}\nRFP:\n{rfp}\n\nApproved sections:\n{body}"
    )
    head = desk._chat(COORDINATOR, instruction, temperature=0.3)
    head = _strip_title(head)

    return (
        f"# Proposal for {decision.customer}\n"
        f"**Prepared by:** AI Deal Desk    **Valid for:** 30 days\n\n"
        f"{head}\n\n"
        f"{body}"
    )


def _clamp_int(value, default: int) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _strip_title(head: str) -> str:
    """Drop any leading '# Proposal …' title / 'Prepared by' line the model echoes,
    so we don't render the proposal header twice."""
    lines = head.splitlines()
    out: list[str] = []
    skipping = True
    for line in lines:
        stripped = line.strip()
        if skipping and (
            not stripped
            or stripped.startswith("# ")
            or stripped.lower().startswith("**prepared by")
            or stripped.lower().startswith("**valid for")
        ):
            continue
        skipping = False
        out.append(line)
    return "\n".join(out).strip()


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


def _keyword_recruit(rfp: str) -> list[str]:
    low = rfp.lower()
    out = []
    if any(k in low for k in ("pric", "budget", "cost", "discount", "licens")):
        out.append("pricing")
    if any(k in low for k in ("architect", "integrat", "security", "api", "cloud", "host", "scale", "sso")):
        out.append("technical")
    if any(k in low for k in ("contract", "sla", "gdpr", "hipaa", "soc2", "complian", "liabilit", "data processing")):
        out.append("legal")
    return out or ["pricing"]


def _parse_discount(pricing_section: str) -> float | None:
    if not pricing_section:
        return None
    # Look for an explicit discount percentage, e.g. "Discount: 25%" or "25% discount".
    m = re.search(r"discount[^%\n]*?(\d{1,3}(?:\.\d+)?)\s*%", pricing_section, re.IGNORECASE)
    if not m:
        m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%\s*discount", pricing_section, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _money(text: str) -> float | None:
    m = re.findall(r"\$\s*([\d,]+(?:\.\d+)?)", text)
    if not m:
        return None
    return max(float(x.replace(",", "")) for x in m)


def _over_budget(pricing_section: str, budget: str) -> bool:
    if not pricing_section or not budget or budget.lower() == "not stated":
        return False
    total_m = re.search(r"total[^$\n]*?\$\s*([\d,]+(?:\.\d+)?)", pricing_section, re.IGNORECASE)
    total = float(total_m.group(1).replace(",", "")) if total_m else _money(pricing_section)
    budget_ceiling = _money(budget)
    if total is None or budget_ceiling is None:
        return False
    return total > budget_ceiling
