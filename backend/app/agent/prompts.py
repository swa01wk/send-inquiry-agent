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
        # 18 Nov B1 (§3.3): the example answers come from the policy, not the prompt.
        examples = policy.flow_v2_intake.examples
        lines.append(
            "- Examples to quote, in the chat's language: what customers come for "
            f"({examples.what_you_sell}); for an office, what the company does "
            f"({examples.office_business}); a Basic Info answer, shown once "
            f"({examples.basic_info_answer})."
        )
        if policy.flow_v2_intake.category_from_options_only:
            lines.append(
                "- Sales category: set only by the user's tap on the options from "
                "`show_category_options` (or typing one option's name); never write it "
                "with `update_draft`."
            )
    elif assisted:
        lines.append(
            "- Existing tenants (the CR already has a Tenant Central account): the contact "
            "check card decides what happens next — see Channel: assisted."
        )
    else:
        lines.append(
            "- Existing tenants (the CR already has a Tenant Central account): explain "
            "kindly that they can sign in with that account, point them to Sign In, and "
            "stop collecting."
        )
    return "\n".join(lines)


def build_system_message(
    draft: InquiryDraft,
    master: MasterData,
    cards_shown: list[str] | None = None,
    *,
    assisted: bool = False,
) -> SystemMessage:
    rules = rules_in_force(get_policy(), master, assisted=assisted)
    dynamic = prompt_summary(draft, master)
    hint = next_bundle_hint(
        draft,
        cards_shown,
        assisted=assisted,
    )
    content = f"{_static_for_draft(draft)}\n\n{rules}\n\n## Current state\n{dynamic}\n{hint}"
    return SystemMessage(content=content)


# Channel notes (intake channels §3.2, §3.5): appended to the system prompt per session.
# Kept short and factual here; tone and examples live in the static prompt.
ASSISTED_NOTES = """## Channel: assisted (call centre or Guest Service)
- You speak to the executive, never to the caller: call them "you" (never "the
  executive"), and refer to the applicant as "the caller".
- Never address the caller by name or as "you" — the executive reads your reply aloud
  (e.g. "Thanks — I've saved Sara's details.").
- The example replies above are for the public page. Here never write "Thanks, <name>" or
  "Hi <name>", and never say you sent an email link or SMS code: no verification is sent
  from this channel.
- **Company (assisted):** the CR number. Call `verify_cr` whenever you hear one. For a CR
  new to Tenant Central it fills company name and address from the registry. If they don't
  have it, ask for company name and address together, and call `skip_cr` only after they
  agree to skip. If the caller says they have their CR but hasn't given it, invite them to
  read it out.
- Same bundles as usual, but one short question at a time — they are relaying over the phone.
- Never ask for or mention email or SMS verification, codes, documents or consent; the
  caller does those from the application link. After the basic info, the only next step
  you name is the **Send application link** card.
- As soon as the basic info is complete, call `show_application_link`.
- **CR already has a Tenant Central account:** the contact check card appears. Ask the
  executive only for the caller's email and to press **Check contact** — nothing else until
  the check is done. Never say what the company has on file.
- `[ui_event] contact_existing inform`: the caller already has a login, so no inquiry is
  raised here. Give the executive one or two sentences to say, e.g. "You already have a
  Tenant Central account — please sign in and raise the inquiry from Leasing Opportunities."
  Then point to **Email sign-in link** on the card if they'd like the link. You never send
  it yourself. Collect nothing more.
- `[ui_event] sign_in_link_sent`: confirm in one line that the sign-in link went to the
  caller's email. Nothing else to collect.
- `[ui_event] contact_new fresh_capture`: a new contact for this company. Capture the inquiry
  fresh, in the app's order: unit type and what they sell; then basic info (company name and
  address, brand, the caller's name and mobile — the email is in); then property details
  (malls, area, budget). Nothing comes from the company's records. Never ask for documents.
- `[ui_event] link_blocked existing_contact`: the application link isn't available for an
  existing contact; repeat the sign-in words in one line."""


def duplicate_notes(reference: str, policy: str) -> str:
    """Chart S15: a notice card already told them about the open inquiry (once, from code)."""
    after = (
        "they can still send this one"
        if policy == "warn"
        else "this one can't be sent while that one is open; they can choose another mall"
    )
    return (
        "## Open inquiry with the same CR and mall\n"
        f"A notice on screen already told them an open inquiry ({reference}) has the same CR "
        f"and mall, and that {after}. Don't repeat it unless they ask; if they do, say that "
        "plainly and neutrally. Never suggest they did something wrong."
    )


def channel_notes(channel: str | None, assisted: bool) -> str:
    if assisted:
        return ASSISTED_NOTES
    return ""
