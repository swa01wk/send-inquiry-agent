#!/usr/bin/env python3
"""Generate backend/tests/e2e_scripts/*.json for Playwright @scripted runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "tests" / "e2e_scripts"


def tc(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {
        "content": "",
        "tool_calls": [{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    }


def say(content: str) -> dict[str, Any]:
    return {"content": content}


# Guard rejects a text-only reply when the user sent saveable data;
# scripts include this once per retry.
GUARD_DECOY = say("Thanks — one moment.")


COLLECT = [
    {"key": "brand_name_en", "value": "Bean Street", "source": "user"},
    {"key": "brand_name_ar", "value": "بين ستريت", "source": "derived"},
    {"key": "unit_type", "value": "specialty", "source": "derived"},
    {"key": "sales_category", "value": "fnb_cafe", "source": "derived"},
    {"key": "malls", "value": ["riyadh-mall-a"], "source": "user"},
]

COLLECT_NO_MALLS = [f for f in COLLECT if f["key"] != "malls"]

CONTACT = [
    {"key": "first_name", "value": "Sara", "source": "user"},
    {"key": "last_name", "value": "Ali", "source": "user"},
    {"key": "email", "value": "sara@beanstreet.example", "source": "user"},
    {"key": "contact_number", "value": "0501234567", "source": "user"},
]

COMPANY = [
    {"key": "company_name", "value": "Acme Trading LLC", "source": "user"},
    {"key": "company_address", "value": "King Abdullah Road, Riyadh", "source": "user"},
]

SCRIPTS: dict[str, list[dict[str, Any]]] = {
    "01-shop-owner": [
        say("Hi — when you're ready, send your company's CR number."),
        tc("verify_cr", {"cr_number": "1010123456"}, "a1"),
        say("Thanks — your company details are in the card below."),
        tc("update_draft", {"fields": COLLECT}, "a2"),
        say("Got it — check the brand summary card."),
        tc("update_draft", {"fields": CONTACT}, "a3"),
        tc("send_verification", {"resend": False}, "a4"),
        say("Open the link we emailed you and enter the SMS code in the box."),
    ],
    "02-front-loader": [
        tc("verify_cr", {"cr_number": "1010123456"}, "b1"),
        say("Got your CR — check the company card."),
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "b2"),
        tc("send_verification", {"resend": False}, "b3"),
        say("Code sent — use the box below."),
    ],
    "03-no-cr": [
        say("A CR number is the 10-digit ID on your commercial registration certificate."),
        tc("skip_cr", {}, "c1"),
        say("No problem — tell me your company name and address."),
        tc("update_draft", {"fields": COMPANY}, "c2"),
        say("Saved — tell me about your brand and where you'd like to open."),
    ],
    "04-typos": [
        tc("verify_cr", {"cr_number": "1010123456"}, "d1"),
        say("Thanks — company details are in the card."),
        tc("update_draft", {"fields": COLLECT_NO_MALLS}, "d2"),
        tc("show_mall_picker", {"city": "riyadh"}, "d3"),
        say("I've saved what I could — pick a mall from the card."),
    ],
    "05-arabic": [
        say("مرحباً — أرسلي رقم السجل التجاري عندما تكونين جاهزة."),
        tc("verify_cr", {"cr_number": "1010123456"}, "e1"),
        say("تم — تفاصيل الشركة في البطاقة."),
        tc("update_draft", {"fields": COLLECT}, "e2"),
        say("تم حفظ العلامة — راجعي البطاقة."),
        tc("update_draft", {"fields": CONTACT}, "e3"),
        tc("send_verification", {"resend": False}, "e4"),
        say("أدخلي الرمز في المربع."),
    ],
    "06-whatsapp": [
        say("Hi — happy to help with your leasing inquiry."),
        tc("verify_cr", {"cr_number": "1010123456"}, "f1"),
        say("Got your CR — company details are in the card."),
        tc("update_draft", {"fields": COLLECT}, "f2"),
        say("Got it — tell me who to contact for this inquiry."),
        tc("update_draft", {"fields": CONTACT}, "f3"),
        tc("send_verification", {"resend": False}, "f4"),
        say("Pop the code in the box below."),
    ],
    "07-phone-formats": [
        tc("verify_cr", {"cr_number": "1010123456"}, "g1"),
        say("Thanks — company card below."),
        tc("update_draft", {"fields": COLLECT}, "g2"),
        say("Almost there — what's the best mobile number?"),
        tc(
            "update_draft",
            {"fields": [{"key": "contact_number", "value": "0501234567", "source": "user"}]},
            "g3",
        ),
        tc("send_verification", {"resend": False}, "g4"),
        say("Verification code sent."),
    ],
    "08-city-only": [
        tc("show_mall_picker", {"city": "jeddah"}, "h1"),
        say("Pick a mall in Jeddah from the card."),
    ],
    "09-changes-mind": [
        tc("verify_cr", {"cr_number": "1010123456"}, "i1"),
        say("Company saved — see the card."),
        tc("update_draft", {"fields": COLLECT}, "i2"),
        say("Brand summary is in the card — confirm when ready."),
        tc(
            "update_draft",
            {"fields": [{"key": "unit_type", "value": "store", "source": "user"}]},
            "i3",
        ),
        say("Updated to a full store — see the card."),
    ],
    "10-unsure": [
        tc("verify_cr", {"cr_number": "1010123456"}, "j1"),
        say("Thanks — company card below."),
        tc("update_draft", {"fields": COLLECT}, "j2"),
        say("No problem — we can pick a category together."),
        tc("suggest_replies", {"options": ["Food & drink", "Fashion", "Not sure yet"]}, "j3"),
        say("Which feels closest?"),
    ],
    "11-impatient": [
        say("We still need phone verification and documents before you can submit."),
    ],
    "12-wrong-code": [
        tc("verify_cr", {"cr_number": "1010123456"}, "k1"),
        say("Thanks — company card below."),
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "k2"),
        tc("send_verification", {"resend": False}, "k3"),
        say("Enter your code in the box — not here in chat."),
    ],
    "13-wrong-files": [
        tc("verify_cr", {"cr_number": "1010123456"}, "l1"),
        say("Thanks — company card below."),
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "l2"),
        tc("send_verification", {"resend": False}, "l3"),
        say("Use the verification card — open the link, then enter the SMS code in the box."),
        tc("request_documents", {}, "l4"),
        say("Company Profile and Brand Profile are required. Other documents are optional."),
        say(
            "Thanks — optional documents can still be added; the review card is ready when you are."
        ),
    ],
    "14-wants-person": [
        say("Our leasing team can follow up after you submit — happy to keep going here."),
    ],
    "15-asks-price": [
        tc("search_faq", {"query": "rent riyadh mall"}, "m1"),
        say("I can't quote rent here, but we can continue your inquiry."),
    ],
    "16-existing-tenant": [
        tc("verify_cr", {"cr_number": "1010000000"}, "n1"),
        say("This CR already has an account — please use Sign In on Tenant Central."),
    ],
    "17-rambler": [
        tc("verify_cr", {"cr_number": "1010123456"}, "o1"),
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "o2"),
        tc("send_verification", {"resend": False}, "o3"),
        say("You're set for verification — use the code box when ready."),
    ],
    "18-demo-sequence": [
        say("Marhaba — send your CR number when you're ready."),
        tc("verify_cr", {"cr_number": "1010123456"}, "p1"),
        say("Your company details are in the card below."),
        tc("confirm_fields", {"keys": ["company_name", "company_address"]}, "p2"),
        say("Thanks — company details confirmed."),
        tc(
            "update_draft",
            {
                "fields": [
                    *COLLECT,
                    *CONTACT,
                    {"key": "area_min", "value": 30, "source": "user"},
                    {"key": "rent_max", "value": 250000, "source": "user"},
                    {"key": "lease_period", "value": "3 years", "source": "user"},
                ]
            },
            "p3",
        ),
        say("Saved — check the brand summary card."),
        tc(
            "confirm_fields",
            {
                "keys": [
                    "brand_name_en",
                    "brand_name_ar",
                    "unit_type",
                    "sales_category",
                    "malls",
                ]
            },
            "p4",
        ),
        tc("send_verification", {"resend": False}, "p5"),
        say("Open the link we emailed you and enter the SMS code in the box."),
        tc(
            "update_draft",
            {"fields": [{"key": "unit_type", "value": "store", "source": "user"}]},
            "p6",
        ),
        say("Updated to a full store — see the card."),
        tc("request_documents", {}, "p7"),
        say(
            "Company Profile and Brand Profile are required. "
            "CR, VAT, ID, address and articles are optional."
        ),
        say(
            "Thanks — optional documents can still be added; "
            "check the review card when you're ready."
        ),
    ],
    "19-cr-chip": [say("Type your 10-digit CR number when you're ready.")],
    "20-formatting": [
        tc("suggest_replies", {"options": ["Got it"]}, "z0"),
        say("Here is a short list:\n\n- First point\n- Second point"),
    ],
    "21-unclear": [
        say("Got it."),
        say(
            "Do you have your company's CR number? "
            "It's on your commercial registration certificate."
        ),
        tc(
            "suggest_replies",
            {"options": ["I have my CR number", "I don't have it", "What is a CR?"]},
            "q1",
        ),
        say("Share your CR number, or say if you don't have it handy."),
        tc("suggest_replies", {"options": ["Skip CR for now", "What do I need?"]}, "q2"),
        say("Tell me about your shop idea in a few words, or share your CR to start."),
        say("Start with your CR number, or say you don't have it yet."),
    ],
    "22-lost-midway": [
        tc("verify_cr", {"cr_number": "1010123456"}, "r1"),
        say("Company saved — see the card."),
        tc("update_draft", {"fields": COLLECT}, "r2"),
        say("You're on the brand step — check the summary card."),
        say("That card is your brand summary — tap Looks right when it matches."),
        tc("suggest_replies", {"options": ["Looks good", "Change unit type", "Start over"]}, "r3"),
        say("Next we'll add a contact person after you confirm the brand card."),
    ],
    "23-guard-missed-save": [
        say("Got it."),
        tc("verify_cr", {"cr_number": "1010123456"}, "g23a"),
        say("Thanks — your company details are in the card below."),
    ],
}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, steps in SCRIPTS.items():
        path = ROOT / f"{name}.json"
        path.write_text(json.dumps(steps, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(SCRIPTS)} scripts to {ROOT}")


if __name__ == "__main__":
    main()
