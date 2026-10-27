"""Values notification templates use: who the applicant is and what they asked about."""

from __future__ import annotations

from typing import Any

from app.domain.master import MasterData
from app.domain.models import FieldKey, InquiryDraft


def message_context(draft: InquiryDraft, master: MasterData) -> dict[str, Any]:
    first_name = draft.fields[FieldKey.FIRST_NAME].value
    brand = draft.fields[FieldKey.BRAND_NAME_EN].value
    malls = draft.fields[FieldKey.MALLS].value
    mall_names = [
        master.label_for("malls", str(mall_id)) or str(mall_id)
        for mall_id in (malls if isinstance(malls, list) else [])
    ]
    return {
        "first_name": str(first_name) if first_name else "there",
        "brand": str(brand) if brand else "your brand",
        "mall": ", ".join(mall_names) if mall_names else "a Cenomi mall",
    }
