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
_PROMPT_V2_PATH = Path(__file__).resolve().parent / "system_prompt_v2.md"


@lru_cache
def _static_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


@lru_cache
def _static_prompt_v2() -> str:
    return _PROMPT_V2_PATH.read_text(encoding="utf-8").strip()


def _static_for_draft(draft: InquiryDraft) -> str:
    if draft.intake_flow == "v2":
        return _static_prompt_v2()
    return _static_prompt()


def clear_prompt_cache() -> None:
    """For tests after prompt file edits."""
    _static_prompt.cache_clear()
    _static_prompt_v2.cache_clear()


def rules_in_force(policy: PolicyConfig, master: MasterData, *, assisted: bool = False) -> str:
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

    if policy.public_cr_check == "verify_or_skip":
        ttl = policy.flow_v2_intake.pending_inquiry_ttl_minutes
        ttl_text = f"{ttl // 60} hours" if ttl % 60 == 0 and ttl >= 120 else f"{ttl} minutes"
        lines.append(
            "- Saving: nothing is kept until the email (and a mobile, when given) is verified; "
            f"after that the inquiry is saved as pending for {ttl_text}."
        )
        lines.append(
            "- Company Registration on the public page: the card takes the CR (Verify) or "
            "Skip with confirmation. Never repeat a CR number in chat. Never say whether a "
            "CR, company or person is known to Cenomi except the one registered-customer line "
            "in the prompt."
        )
    elif assisted or policy.public_cr_check != "ask_then_sign_in":
        if policy.existing_tenant_policy == "sign_in":
            lines.append(
                "- Existing tenants (the CR already has a Tenant Central account): explain "
                "kindly that they can sign in with that account, point them to Sign In, and "
                "stop collecting."
            )
        else:
            lines.append(
                "- Existing tenants (the CR already has a Tenant Central account): they may "
                "continue this inquiry here; carry on collecting as usual."
            )
    else:
        lines.append(
            "- CR on the public page: ask whether the company has a CR (the card buttons). "
            "Never ask for, look up or repeat a CR number. Never say whether a CR, company "
            "or person is known to Cenomi. If they have a CR, signing in to Tenant Central "
            "is the path — stop collecting in chat."
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
    rules = rules_in_force(get_policy(), master, assisted=assisted)
    dynamic = prompt_summary(draft, master)
    hint = next_bundle_hint(
        draft,
        cards_shown,
        assisted=assisted,
        tenant_brands=tenant_brands,
    )
    content = f"{_static_for_draft(draft)}\n\n{rules}\n\n## Current state\n{dynamic}\n{hint}"
    return SystemMessage(content=content)


# Channel notes (intake channels §3.2, §3.5): appended to the system prompt per session.
# Kept short and factual here; tone and examples live in the static prompt.
ASSISTED_NOTES = """## Channel: assisted (call centre or Guest Service)
- You speak to the executive, never to the caller. Refer to the applicant as "the caller".
- Never address the caller by name or as "you" — the executive reads your reply aloud
  (e.g. "Thanks — I've saved Sara's details.").
- The example replies above are for the public page. Here never write "Thanks, <name>" or
  "Hi <name>", and never say you sent an email link or SMS code: no verification is sent
  from this channel.
- **Company (assisted):** the CR number. One answer fills CR, company name and address
  through `verify_cr`. If they don't have it, ask for company name and address together.
  If the caller says they have their CR but hasn't given it, invite them to read it out.
- **Tools (assisted):** `verify_cr` whenever you hear a CR number — if the account already
  exists, follow "Existing tenants" under Rules in force. If they don't have the CR, offer
  to skip and call `skip_cr` only after they agree.
- Same bundles as usual, but one short question at a time — they are relaying over the phone.
- Never ask for email or SMS verification, codes, documents or consent; the caller does those
  from the application link.
- As soon as the basic info is complete, call `show_application_link`.
- When an `existing_cr_choice` card appears, give the executive one sentence to say to the
  caller for each option (sign in / continue for them), then wait for their pick."""

EXISTING_TENANT_NOTES = """## Channel: existing tenant (signed in to Tenant Central)
- Greet by first name only if you have not already (the opening greeting is sent by the server
  and says the company details came from their Cenomi record).
- Company and contact are on the review card — ask them to press Proceed or Edit there, not
  to repeat the details in chat. Never ask for the company name or address.
- This inquiry is for a new brand. Ask what it is, offering once to fill it from the Brand
  Profile or have them type it; call `suggest_replies` with "I'll type it" and "I'll upload
  the Brand Profile". Either is fine. Once the brand name is known, don't ask what they sell.
- If the brand they give matches one listed under This account, ask once whether this inquiry
  is for that brand or a new one. Never refuse either answer.
- Say in one line, when the documents come up, that a new brand needs both the Company Profile
  and the Brand Profile, even if they sent them before. Their other documents on file can be
  kept or replaced.
- You may ask for space or budget. Never ask for verification."""


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
            f"- Brands already on the account: {brands_line} (this inquiry is for a new brand)",
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
