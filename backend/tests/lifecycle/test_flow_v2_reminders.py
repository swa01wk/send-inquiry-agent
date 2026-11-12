"""Flow v2 E4 (spec §3.7, S21, S23): reminders for Forecasted Sales Data at "Tenant Qualified"
and for the contacts after "Approve Lead?" = Yes; no stalled-review flag while the tenant
owes the contacts."""

from __future__ import annotations

import pytest
from tests.lifecycle.conftest import STORE_CENTRAL, act
from tests.lifecycle.test_lead_approval import UNIT, _lead_approved, _qualified
from tests.lifecycle.test_proactive import _items, advance, attention, freeze, riyadh

pytestmark = [pytest.mark.approvals, pytest.mark.lease_admin, pytest.mark.lead_approval]


async def test_forecasted_sales_data_reminder(life) -> None:
    client, app = life
    freeze(app, riyadh(10))
    reference = await _qualified(client, app)
    await act(client, STORE_CENTRAL, reference, "assign_unit", **UNIT)
    asked = await act(client, STORE_CENTRAL, reference, "request_sales_data", remarks="Monthly")
    assert asked.status_code == 200, asked.text

    await advance(client, 71)
    assert _items(await attention(client, STORE_CENTRAL), "applicant_reminder") == []
    await advance(client, 2)
    reminders = _items(await attention(client, STORE_CENTRAL), "applicant_reminder")
    assert len(reminders) == 1
    assert reminders[0]["reference"] == reference
    assert "Forecasted Sales Data" in reminders[0]["text"]


async def test_contacts_reminder_and_no_stall_after_approve_lead(life) -> None:
    client, app = life
    freeze(app, riyadh(10))
    reference = await _lead_approved(client, app)

    await advance(client, 73)
    data = await attention(client, STORE_CENTRAL)
    reminders = _items(data, "applicant_reminder")
    assert len(reminders) == 1 and reminders[0]["reference"] == reference
    assert "Authorized Signatory and Billing Contact" in reminders[0]["text"]
    # 73 h in "Lead Approved", past the 48 h stall threshold: the tenant owes the next step.
    assert _items(data, "stalled_review") == []
    assert _items(data, "escalation") == []
