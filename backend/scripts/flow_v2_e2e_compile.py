"""Turn flow-v2 scenario steps into scripted model JSON (day F3)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "docs" / "flow-v2" / "scenarios.json"
# Turn counts the step heuristics can't predict (profile uploads make their own confirm cards).
# S13, and the 18 Nov stories NV01… (tool calls such as `show_category_options` that the
# step heuristics below don't produce): written by hand in tests/e2e_scripts/.
HAND_WRITTEN = frozenset({"S13", "NV01", "NV02"})


def _load_catalogue() -> list[dict[str, Any]]:
    data = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    scenarios = data["scenarios"]
    assert isinstance(scenarios, list)
    return scenarios


def _load_demo_paths() -> list[dict[str, Any]]:
    """The demo script's intake (`demo` in the catalogue file; docs/demo-script.md beat 1)."""
    data = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    demo = data.get("demo", [])
    assert isinstance(demo, list)
    return demo


def _agent_turns_after_cr_registered() -> list[dict[str, Any]]:
    return [
        {
            "content": (
                "You're already registered with us — please sign in to Tenant Central "
                "using the button below."
            )
        },
        {
            "content": (
                "Signing in is still the quickest way — your company details are already "
                "on file there."
            )
        },
    ]


def _registered_crs() -> frozenset[str]:
    tenants = ROOT / "backend" / "app" / "data" / "mock_world" / "tenants.json"
    data = json.loads(tenants.read_text(encoding="utf-8"))
    return frozenset(str(t.get("cr_number", "")) for t in data["tenants"])


def _agent_turns_after_cr_new() -> list[dict[str, Any]]:
    """A valid CR that isn't in Tenant Central (S2, S15): one reply, then Store or Office.

    The unit answer ("a store") is saved by the guard and by the next turn's update_draft;
    no second reply is consumed here (the guard no longer retries a saved Store answer).
    """
    return [{"content": "Thanks — let's continue. Are you looking for a store or an office?"}]


def _agent_turns_after_cr_skipped() -> list[dict[str, Any]]:
    return [
        {
            "content": "",
            "tool_calls": [
                {
                    "name": "suggest_replies",
                    "args": {"options": ["Store", "Office", "Media", "Specialty"]},
                    "id": "fv2-unit-offer",
                    "type": "tool_call",
                }
            ],
        },
        {
            "content": (
                "Got it, a store. Tell me a little about the business. What will customers "
                "come to you for?"
            )
        },
    ]


def _step_to_turns(step: dict[str, Any], *, after_cr: str | None) -> list[dict[str, Any]]:
    if "say" in step:
        text = step["say"]
        # A contact line can name a coffee brand (S7): read it as the contact first.
        if "@" in text or re.search(r"\d{9,}", text):
            return [
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "update_draft",
                            "args": {"fields": _contact_fields_from_say(text)},
                            "id": "fv2-contact",
                            "type": "tool_call",
                        },
                        {
                            "name": "send_verification",
                            "args": {},
                            "id": "fv2-v",
                            "type": "tool_call",
                        },
                    ],
                },
                {
                    "content": (
                        "Thanks — I've sent the verification link and SMS code on the card below."
                    )
                },
            ]
        if re.search(r"\bstore\b", text, re.I):
            return [
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "update_draft",
                            "args": {
                                "fields": [
                                    {"key": "unit_type", "value": "store", "source": "user"},
                                ]
                            },
                            "id": "fv2-ut",
                            "type": "tool_call",
                        }
                    ],
                },
                {
                    "content": (
                        "Tell me a little about the business. What will customers come to you for?"
                    )
                },
            ]
        if re.search(r"\boffice\b", text, re.I):
            return [
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "update_draft",
                            "args": {
                                "fields": [
                                    {"key": "unit_type", "value": "office", "source": "user"}
                                ]
                            },
                            "id": "fv2-cat",
                            "type": "tool_call",
                        }
                    ],
                },
                {"content": "An office, got it. What does the company do?"},
            ]
        if re.search(r"sell|coffee", text, re.I):
            # 18 Nov B1 (§3.2): the category is offered as option buttons; the user taps one
            # (`choose_option`), the agent never writes it.
            category = "fnb_cafe" if "coffee" in text.lower() else "fashion"
            return [
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "show_category_options",
                            "args": {"candidates": [category], "evidence": text[:80]},
                            "id": "fv2-cat",
                            "type": "tool_call",
                        }
                    ],
                },
                {"content": "Tap the option that fits best."},
            ]
        if re.search(r"mall|sqm|year", text, re.I):
            return [
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "update_draft",
                            "args": {"fields": _property_fields_from_say(text)},
                            "id": "fv2-prop",
                            "type": "tool_call",
                        }
                    ],
                },
                {
                    "content": (
                        "Your property details are on the card — confirm them when you're ready."
                    )
                },
            ]
        return [{"content": "Thanks — let's keep going with the next step."}]
    if "choose_option" in step:
        return [
            {
                "content": (
                    "Thanks. Tell me a bit more about you and your company: your name, the "
                    "company name and address, your brand, an email and a phone number."
                )
            }
        ]
    if "confirm_card" in step:
        return [{"content": "Looks good — here's what's next in the flow."}]
    if step.get("accept_terms"):
        return [
            {
                "content": (
                    "Thanks — upload the Company Profile and Brand Profile on the card below."
                )
            }
        ]
    if after_cr == "registered":
        return _agent_turns_after_cr_registered()
    if after_cr == "skipped":
        return _agent_turns_after_cr_skipped()
    return []


def _contact_fields_from_say(text: str) -> list[dict[str, Any]]:
    """`First Last, Company, Address, brand EN / AR, email, mobile` (the catalogue's form);
    shorter lines (`Sara Ali, email, mobile`) give the contact only."""
    email = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    mobile = re.search(r"0?5\d{8}", text.replace(" ", ""))
    parts = [p.strip() for p in text.split(",")]
    names = parts[0].split() if parts else []
    fields: list[dict[str, Any]] = [
        {"key": "first_name", "value": names[0] if names else "Sara", "source": "user"},
        {"key": "last_name", "value": " ".join(names[1:]) or "Ali", "source": "user"},
        {
            "key": "email",
            "value": email.group(0) if email else "sara@beanstreet.example",
            "source": "user",
        },
    ]
    if mobile:
        fields.append({"key": "contact_number", "value": mobile.group(0), "source": "user"})
    brand = next((p for p in parts if p.lower().startswith("brand ")), None)
    if len(parts) >= 6 and brand is not None:
        en, _, ar = brand[len("brand ") :].partition("/")
        fields.extend(
            [
                {"key": "company_name", "value": parts[1], "source": "user"},
                {"key": "company_address", "value": parts[2], "source": "user"},
                {"key": "brand_name_en", "value": en.strip(), "source": "user"},
            ]
        )
        if ar.strip():
            fields.append({"key": "brand_name_ar", "value": ar.strip(), "source": "user"})
    return fields


def _property_fields_from_say(text: str) -> list[dict[str, Any]]:
    malls = []
    if "Riyadh Mall A" in text:
        malls.append("riyadh-mall-a")
    if "Jeddah Mall A" in text:
        malls.append("jeddah-mall-a")
    if "Mall of Arabia" in text or "mall b" in text.lower():
        malls.append("riyadh-mall-b")
    fields: list[dict[str, Any]] = []
    if malls:
        fields.append({"key": "malls", "value": malls, "source": "user"})
    if "sqm" in text.lower() and "around 40" in text.lower():
        fields.extend(
            [
                {"key": "area_min", "value": 40, "source": "user"},
                {"key": "area_max", "value": 40, "source": "user"},
            ]
        )
    elif "sqm" in text.lower():
        fields.extend(
            [
                {"key": "area_min", "value": 30, "source": "user"},
                {"key": "area_max", "value": 50, "source": "user"},
            ]
        )
    if "250" in text or "180" in text:
        fields.append({"key": "rent_max", "value": 250000, "source": "user"})
    if "3 year" in text.lower():
        fields.append({"key": "lease_period", "value": "3y", "source": "user"})
    return fields


def compile_scenario(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    after_cr: str | None = None
    for step in scenario.get("steps", []):
        if step.get("cr_skip_confirm"):
            after_cr = "skipped"
            steps.extend(_agent_turns_after_cr_skipped())
            continue
        if "cr_verify" in step:
            cr = str(step["cr_verify"])
            if re.fullmatch(r"\d{10}", cr) and cr not in _registered_crs():
                after_cr = "new"
                steps.extend(_agent_turns_after_cr_new())
            else:
                after_cr = "registered"
                steps.extend(_agent_turns_after_cr_registered())
            continue
        if step.get("cr_skip"):
            continue
        if (
            step.get("verify_email")
            or step.get("enter_code")
            or step.get("upload")
            or step.get("submit")
        ):
            continue
        steps.extend(_step_to_turns(step, after_cr=after_cr))
    if not steps:
        steps = [{"content": "Thanks — let's continue with your inquiry."}]
    return steps


def write_intake_scripts(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for scenario in _load_catalogue():
        sid = scenario.get("id", "")
        if not re.fullmatch(r"S([1-9]|1[0-7])", sid or ""):
            continue
        if sid in HAND_WRITTEN:
            continue
        name = f"flow-v2-{sid.lower()}"
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(compile_scenario(scenario), indent=2) + "\n", encoding="utf-8")
        written += 1
    for demo in _load_demo_paths():
        path = out_dir / f"flow-v2-{demo['id']}.json"
        path.write_text(json.dumps(compile_scenario(demo), indent=2) + "\n", encoding="utf-8")
        written += 1
    return written


if __name__ == "__main__":
    n = write_intake_scripts(ROOT / "backend" / "tests" / "e2e_scripts")
    print(f"Wrote {n} flow-v2 intake scripts")
