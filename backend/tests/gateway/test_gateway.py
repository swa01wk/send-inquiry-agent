import asyncio

import pytest
from app.audit import AuditLog
from app.gateway import FaultPlan, FaultSpecError, Gateway, GatewayError
from app.services.errors import (
    ReferenceNotFoundError,
    ServiceRejected,
    ServiceTimeout,
    ServiceUnavailable,
)


def test_fault_plan_parses_counts_and_defaults() -> None:
    plan = FaultPlan.parse("submit:timeout:1, otp:unavailable")
    assert plan.take("submit") == "timeout"
    assert plan.take("submit") is None  # count used up
    assert plan.take("otp") == "unavailable"
    assert plan.take("otp") == "unavailable"  # every call
    assert plan.take("cr") is None


@pytest.mark.parametrize(
    "spec", ["cr", "cr:explode", "fax:timeout", "cr:timeout:0", "cr:timeout:x"]
)
def test_bad_fault_specs_are_rejected(spec: str) -> None:
    with pytest.raises(FaultSpecError):
        FaultPlan.parse(spec)


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (ServiceTimeout("t"), "timeout"),
        (TimeoutError(), "timeout"),
        (ServiceUnavailable("u"), "unavailable"),
        (ConnectionError(), "unavailable"),
        (ServiceRejected("r"), "rejected"),
        (ValueError("v"), "invalid"),
    ],
)
def test_errors_map_to_four_kinds(exc: Exception, kind: str) -> None:
    def boom() -> None:
        raise exc

    with pytest.raises(GatewayError) as caught:
        Gateway().call_sync("submit", "submit", boom)
    assert caught.value.kind == kind
    assert caught.value.note == f"service_error submit {kind}"


def test_business_outcomes_pass_through() -> None:
    def missing() -> None:
        raise ReferenceNotFoundError("GEO")

    with pytest.raises(ReferenceNotFoundError):
        Gateway().call_sync("status", "get", missing)


@pytest.mark.asyncio
async def test_async_call_times_out() -> None:
    async def slow() -> str:
        await asyncio.sleep(1)
        return "late"

    gateway = Gateway(timeouts_s={"otp": 0.01})
    with pytest.raises(GatewayError) as caught:
        await gateway.call("otp", "send", slow)
    assert caught.value.kind == "timeout"


def test_session_faults_apply_only_to_that_session() -> None:
    gateway = Gateway()
    gateway.set_session_faults("s1", "cr:rejected:1")
    with pytest.raises(GatewayError):
        gateway.call_sync("cr", "verify", lambda: "ok", inquiry_id="s1")
    assert gateway.call_sync("cr", "verify", lambda: "ok", inquiry_id="s1") == "ok"
    assert gateway.call_sync("cr", "verify", lambda: "ok", inquiry_id="s2") == "ok"


def test_calls_are_audited_with_outcome() -> None:
    audit = AuditLog()
    gateway = Gateway(faults=FaultPlan.parse("cr:unavailable:1"), audit=audit)
    with pytest.raises(GatewayError):
        gateway.call_sync("cr", "verify", lambda: "ok", inquiry_id="s1")
    gateway.call_sync("cr", "verify", lambda: "ok", inquiry_id="s1")
    outcomes = [e["payload"]["outcome"] for e in audit.events("s1")]
    assert outcomes == ["unavailable", "ok"]
    assert all(e["payload"]["name"] == "cr.verify" for e in audit.events("s1"))
