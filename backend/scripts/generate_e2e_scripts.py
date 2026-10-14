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


COLLECT = [
    {"key": "brand_name_en", "value": "Bean Street", "source": "user"},
    {"key": "brand_name_ar", "value": "بين ستريت", "source": "derived"},
    {"key": "unit_type", "value": "specialty", "source": "derived"},
    {"key": "sales_category", "value": "fnb_cafe", "source": "derived"},
    {"key": "malls", "value": ["riyadh-mall-a"], "source": "user"},
]

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
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "a2"),
        tc("send_otp", {"resend": False}, "a3"),
        say("Enter the code in the box when it arrives."),
        tc("request_documents", {}, "a4"),
        say("Company Profile and Brand Profile are required to submit."),
    ],
    "02-front-loader": [
        tc("verify_cr", {"cr_number": "1010123456"}, "b1"),
        say("Got your CR — check the company card."),
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "b2"),
        tc("send_otp", {"resend": False}, "b3"),
        say("Code sent — use the box below."),
    ],
    "03-no-cr": [
        say("A CR number is the ID on your commercial registration certificate."),
        tc("skip_cr", {}, "c1"),
        tc("update_draft", {"fields": COMPANY}, "c2"),
        say("Tell me about your brand and where you'd like to open."),
    ],
    "04-typos": [
        tc("verify_cr", {"cr_number": "1010123456"}, "d1"),
        tc("update_draft", {"fields": COLLECT}, "d2"),
        say("I've saved what I could — check the card."),
    ],
    "05-arabic": [
        tc("verify_cr", {"cr_number": "1010123456"}, "e1"),
        say("تم — تفاصيل الشركة في البطاقة."),
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "e2"),
        tc("send_otp", {"resend": False}, "e3"),
        say("أدخلي الرمز في المربع."),
    ],
    "06-whatsapp": [
        tc("verify_cr", {"cr_number": "1010123456"}, "f1"),
        say("Happy to help — company details are in the card."),
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "f2"),
        tc("send_otp", {"resend": False}, "f3"),
        say("Pop the code in the box below."),
    ],
    "07-phone-formats": [
        tc("verify_cr", {"cr_number": "1010123456"}, "g1"),
        tc("update_draft", {"fields": COLLECT}, "g2"),
        tc(
            "update_draft",
            {"fields": [{"key": "contact_number", "value": "0501234567", "source": "user"}]},
            "g3",
        ),
        tc("send_otp", {"resend": False}, "g4"),
        say("Verification code sent."),
    ],
    "08-city-only": [
        tc("skip_cr", {}, "h1"),
        tc("show_mall_picker", {"city": "jeddah"}, "h2"),
        say("Pick a mall in Jeddah from the card."),
    ],
    "09-changes-mind": [
        tc("verify_cr", {"cr_number": "1010123456"}, "i1"),
        tc("update_draft", {"fields": COLLECT}, "i2"),
        tc("update_draft", {"fields": [{"key": "unit_type", "value": "store", "source": "user"}]}, "i3"),
        say("Updated to a full store — see the card."),
    ],
    "10-unsure": [
        tc("verify_cr", {"cr_number": "1010123456"}, "j1"),
        tc("update_draft", {"fields": COLLECT}, "j2"),
        say("No problem — we can pick a category together."),
        tc("suggest_replies", {"options": ["Food & drink", "Fashion", "Not sure yet"]}, "j3"),
        say("Which feels closest?"),
    ],
    "11-impatient": [
        say("We still need phone verification and documents before submit."),
    ],
    "12-wrong-code": [
        tc("verify_cr", {"cr_number": "1010123456"}, "k1"),
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "k2"),
        tc("send_otp", {"resend": False}, "k3"),
        say("Enter your code in the box — not here in chat."),
    ],
    "13-wrong-files": [
        tc("request_documents", {}, "l0"),
        say("Company Profile and Brand Profile are required to submit. Other documents are optional."),
    ],
    "14-wants-person": [
        say("Our leasing team will follow up after you submit — happy to keep going here."),
    ],
    "15-asks-price": [
        tc("get_master_data", {"kind": "malls", "city": "riyadh"}, "m1"),
        say("I can't quote rent here, but we can continue your inquiry."),
    ],
    "16-existing-tenant": [
        tc("verify_cr", {"cr_number": "1010000000"}, "n1"),
        say("This CR already has an account — please use Sign In on Tenant Central."),
    ],
    "17-rambler": [
        tc("verify_cr", {"cr_number": "1010123456"}, "o1"),
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "o2"),
        tc("send_otp", {"resend": False}, "o3"),
        say("Thanks — I've saved your details in the draft panel."),
    ],
    "18-demo-sequence": [
        tc("verify_cr", {"cr_number": "1010123456"}, "p1"),
        say("Your company details are in the card below."),
        tc("confirm_fields", {"keys": ["company_name", "company_address"]}, "p2"),
        tc("update_draft", {"fields": [*COLLECT, *CONTACT]}, "p3"),
        tc("confirm_fields", {"keys": ["brand_name_en", "brand_name_ar", "unit_type", "sales_category", "malls"]}, "p4"),
        tc("update_draft", {"fields": [{"key": "unit_type", "value": "store", "source": "user"}]}, "p5"),
        tc("request_documents", {}, "p6"),
        say("Company Profile and Brand Profile are required. CR, VAT, ID, address and articles are optional."),
        tc("show_review", {}, "p7"),
        say("Upload both required PDFs, then review and submit on the card."),
    ],
    "19-cr-chip": [say("Type your 10-digit CR number when you're ready.")],
    "20-formatting": [
        tc("suggest_replies", {"options": ["Got it"]}, "z0"),
        say("Here is a short list:\n\n- First point\n- Second point"),
    ],
    "21-unclear": [
        say("Do you have your company's CR number? It's on your commercial registration certificate."),
        tc("suggest_replies", {"options": ["I have my CR number", "I don't have it", "What is a CR?"]}, "q1"),
        say("Share your CR number, or say if you don't have it handy."),
        tc("suggest_replies", {"options": ["Skip CR for now", "What do I need?"]}, "q2"),
        say("Tell me about your shop idea in a few words, or share your CR to start."),
    ],
    "22-lost-midway": [
        tc("verify_cr", {"cr_number": "1010123456"}, "r1"),
        tc("update_draft", {"fields": COLLECT}, "r2"),
        say("You're on the brand step — check the summary card. What would you like to change?"),
        tc("suggest_replies", {"options": ["Looks good", "Change unit type", "Start over"]}, "r3"),
        say("Next we'll add a contact person after you confirm the brand card."),
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
