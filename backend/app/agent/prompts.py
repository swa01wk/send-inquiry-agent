"""System prompt assembly."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_core.messages import SystemMessage

from app.agent.bundles import next_bundle_hint
from app.domain.fields import document_definitions
from app.domain.master import MasterData
from app.domain.models import InquiryDraft
from app.domain.summary import prompt_summary
from app.policy.config import PolicyConfig, get_policy
from app.services.tenants import Tenant

_PROMPT_PATH = Path(__file__).resolve().parent / "system_prompt.md"


@lru_cache
def _static_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def clear_prompt_cache() -> None:
    """For tests after prompt file edits."""
    _static_prompt.cache_clear()


def rules_in_force(policy: PolicyConfig, master: MasterData) -> str:
    """The "Rules in force" prompt block, rendered from the policy (L3 §3.7).

    The static prompt refers to this block instead of stating these rules, so the
    prompt can never contradict the code.
    """
    lines = [
        "## Rules in force",
        "These come from the business rules the system enforces. Follow them exactly.",
    ]

    products = [master.label_for("unit_types", pid) or pid for pid in policy.product_lines]
    lines.append(f"- Product lines (unit types): {', '.join(products)}.")

    if policy.max_malls_per_inquiry == 1:
        lines.append(
            "- Malls: one mall per inquiry. If the user names several, save none, ask which "
            "one to start with, and say they can raise another inquiry for the others."
        )
    else:
        limit = policy.max_malls_per_inquiry
        lines.append(
            f"- Malls: up to {limit} malls per inquiry. If the user names more than {limit}, "
            "save none, ask which to start with, and say another inquiry can follow for "
            "the others."
        )

    countries = policy.phone.allowed_countries
    if countries == "any":
        lines.append(
            "- Phone numbers: Saudi numbers, or a number from any other country written "
            "with its country code."
        )
    else:
        codes = ", ".join(f"+{code}" for code in countries)
        lines.append(
            f"- Phone numbers: Saudi numbers, or numbers with these country codes: {codes}. "
            "For any other country, kindly ask for a number we can accept."
        )

    lines.append(
        "- Verification: the email by a one-time link; a mobile by a 4-digit SMS code. "
        "A landline-only applicant is verified by the email link alone."
    )

    required = [label for _dt, label, req in document_definitions() if req]
    optional = [label for _dt, label, req in document_definitions() if not req]
    docs_line = f"- Documents required to submit: {', '.join(required) or 'none'}."
    if optional:
        docs_line += f" Optional: {', '.join(optional)}."
    lines.append(docs_line)

    if policy.existing_tenant_policy == "sign_in":
        lines.append(
            "- Existing tenants (the CR already has a Tenant Central account): explain kindly "
            "that they can sign in with that account, point them to Sign In, and stop "
            "collecting."
        )
    else:
        lines.append(
            "- Existing tenants (the CR already has a Tenant Central account): they may "
            "continue this inquiry here; carry on collecting as usual."
        )
    return "\n".join(lines)


def build_system_message(
    draft: InquiryDraft,
    master: MasterData,
    cards_shown: list[str] | None = None,
    *,
    assisted: bool = False,
    tenant_brands: list[str] | None = None,
) -> SystemMessage:
    rules = rules_in_force(get_policy(), master)
    dynamic = prompt_summary(draft, master)
    hint = next_bundle_hint(
        draft,
        cards_shown,
        assisted=assisted,
        tenant_brands=tenant_brands,
    )
    content = f"{_static_prompt()}\n\n{rules}\n\n## Current state\n{dynamic}\n{hint}"
    return SystemMessage(content=content)


# Channel notes (intake channels §3.2, §3.5): appended to the system prompt per session.
# Kept short and factual here; tone and examples live in the static prompt.
ASSISTED_NOTES = """## Channel: assisted (call centre or Guest Service)
- You speak to the executive, never to the caller. Refer to the applicant as "the caller".
- Never address the caller by name or as "you" — the executive reads your reply aloud
  (e.g. "Thanks — I've saved Sara's details.").
- Same bundles as usual, but one short question at a time — they are relaying over the phone.
- Never ask for email or SMS verification, codes, documents or consent; the caller does those
  from the application link.
- As soon as the basic info is complete, call `show_application_link`.
- When an `existing_cr_choice` card appears, give the executive one sentence to say to the
  caller for each option (sign in / continue for them), then wait for their pick."""

EXISTING_TENANT_NOTES = """## Channel: existing tenant (signed in to Tenant Central)
- Greet by first name only if you have not already (the opening greeting is sent by the server).
- Details are on the review card — ask them to press Proceed or Edit there, not to repeat
  the details in chat.
- If the brand is not chosen yet, ask one question naming the brands listed under This account;
  once it is chosen, do not ask what they sell. You may ask for space or budget. Their
  documents on file can be kept or replaced.
- Never ask for verification."""


def tenant_account_notes(tenant: Tenant) -> str:
    """Account context for existing-tenant mode (brands the model cannot infer from the draft)."""
    brand_labels: list[str] = []
    for brand in tenant.brands:
        if brand.name_ar:
            brand_labels.append(f"{brand.name_en} ({brand.name_ar})")
        else:
            brand_labels.append(brand.name_en)
    brands_line = "; ".join(brand_labels)
    return "\n".join(
        [
            "## This account",
            f"- Company: {tenant.company_name}",
            f"- Brands: {brands_line}",
            "- The mall and space type come from the unit they chose; don't ask about mall, "
            "city or space type.",
        ]
    )


def channel_notes(channel: str | None, assisted: bool) -> str:
    if assisted:
        return ASSISTED_NOTES
    if channel == "existing_tenant":
        return EXISTING_TENANT_NOTES
    return ""
