"""Predetermined ScriptedChatModel steps for scenario tests."""

from __future__ import annotations

from typing import Any

COLLECT_FIELDS: list[dict[str, Any]] = [
    {"key": "brand_name_en", "value": "Bean Street", "source": "user"},
    {"key": "brand_name_ar", "value": "بين ستريت", "source": "derived"},
    {"key": "unit_type", "value": "specialty", "source": "derived"},
    {"key": "sales_category", "value": "fnb_cafe", "source": "derived"},
    {"key": "malls", "value": ["riyadh-mall-a"], "source": "user"},
    {"key": "first_name", "value": "Sara", "source": "user"},
    {"key": "last_name", "value": "Ali", "source": "user"},
    {"key": "email", "value": "sara@beanstreet.example", "source": "user"},
    {"key": "contact_number", "value": "+966501234567", "source": "user"},
]

COMPANY_FIELDS: list[dict[str, Any]] = [
    {"key": "company_name", "value": "Acme Trading LLC", "source": "user"},
    {"key": "company_address", "value": "King Abdullah Road, Riyadh", "source": "user"},
]


def tool_step(name: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {
        "content": "",
        "tool_calls": [
            {
                "name": name,
                "args": args,
                "id": call_id,
                "type": "tool_call",
            }
        ],
    }


def say(content: str) -> dict[str, Any]:
    return {"content": content}


HAPPY_PATH_CR_STEPS: list[dict[str, Any]] = [
    tool_step("verify_cr", {"cr_number": "1010123456"}, "s1"),
    say("Thanks — I pulled your company details from the CR. Please confirm them on the card."),
    say("Tell me about the brand and format you want to open."),
    tool_step("update_draft", {"fields": COLLECT_FIELDS}, "s2"),
    say("Please confirm the details I filled in for you."),
    tool_step("send_otp", {"resend": False}, "s3"),
    say("Enter the verification code in the box when you receive it."),
    say("When you're ready, upload Company Profile and Brand Profile in the checklist."),
]

SKIP_CR_STEPS: list[dict[str, Any]] = [
    tool_step("skip_cr", {}, "s1"),
    say("No problem — what is your registered company name and address?"),
    tool_step(
        "update_draft",
        {"fields": [*COMPANY_FIELDS, *COLLECT_FIELDS]},
        "s2",
    ),
    say("Please confirm the derived brand details."),
    tool_step("send_otp", {"resend": False}, "s3"),
    say("Enter the verification code in the box."),
    say("Upload the required documents when you're ready."),
]

EXISTING_CR_STEPS: list[dict[str, Any]] = [
    tool_step("verify_cr", {"cr_number": "1010000000"}, "s1"),
    say("This CR is linked to an existing account — please use Sign In on Tenant Central."),
]

MANY_FIELDS_STEPS: list[dict[str, Any]] = [
    tool_step("skip_cr", {}, "s1"),
    say("Got it — share your company and brand details whenever you're ready."),
    tool_step(
        "update_draft",
        {
            "fields": [
                *COMPANY_FIELDS,
                *COLLECT_FIELDS,
            ]
        },
        "s2",
    ),
    say("Great — I captured everything from your message."),
]

UNIT_TYPE_CORRECTION_STEPS: list[dict[str, Any]] = [
    tool_step("skip_cr", {}, "s1"),
    say("What company and brand are you planning to open?"),
    tool_step(
        "update_draft",
        {
            "fields": [
                *COMPANY_FIELDS,
                *COLLECT_FIELDS,
            ]
        },
        "s2",
    ),
    say("Does specialty kiosk sound right for your format?"),
    tool_step(
        "update_draft",
        {"fields": [{"key": "unit_type", "value": "store", "source": "user"}]},
        "s3",
    ),
    say("Store it is — thanks for clarifying."),
]

SMALL_TALK_STEPS: list[dict[str, Any]] = [
    say("It's a busy season for new brands — what would you like to open with us?"),
]

FAQ_STEPS: list[dict[str, Any]] = [
    tool_step("search_faq", {"query": "required documents upload"}, "s1"),
    say("Company Profile and Brand Profile are required; the rest are optional but helpful."),
]

OFF_TOPIC_STEPS: list[dict[str, Any]] = [
    say(
        "I'm here to help with leasing inquiries at Cenomi — "
        "shall we continue with your brand details?"
    ),
]

INJECTION_STEPS: list[dict[str, Any]] = [
    say(
        "I can't skip verification or submit early — "
        "let's start with your CR number when you're ready."
    ),
]

STATUS_LOOKUP_STEPS: list[dict[str, Any]] = [
    tool_step("get_inquiry_status", {"reference": "GEO-STR-100001"}, "s1"),
    say("Reference GEO-STR-100001 is under review with our leasing team."),
]

MISSING_DOC_STEPS: list[dict[str, Any]] = [
    tool_step("show_review", {}, "s1"),
    say("Please upload your Company Profile first — I'll show review once that's done."),
]

REVIEW_EDIT_STEPS: list[dict[str, Any]] = [
    say("I've updated your draft — take another look at the review card."),
]
