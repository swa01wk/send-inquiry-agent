"""Flow v2 (§3.11, E2): should the RSM ask for Forecasted Sales Data? Facts and the matching
rule only: the reviewer assistant words the suggestion, and the RSM decides."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.domain.models import FieldKey, Source
from app.policy.config import get_policy

if TYPE_CHECKING:
    from app.services.container import ServiceContainer
    from app.workflow.models import Case


@dataclass
class SalesDataAssessment:
    suggest: bool
    new_company: bool
    unit_type: str | None
    area_min: float | None
    area_max: float | None
    rent_min: float | None
    rent_max: float | None
    malls: int
    reasons: list[str] = field(default_factory=list)
    already_requested: bool = False

    def text(self) -> str:
        rule = get_policy().forecasted_sales.suggest_when
        rule_parts = []
        if rule.new_company:
            rule_parts.append("the company is new to Cenomi")
        if rule.area_min_sqm_at_least:
            rule_parts.append(
                f"the smallest area asked for is {rule.area_min_sqm_at_least} sqm or more"
            )
        lines = [
            f"Company new to Cenomi: {'yes' if self.new_company else 'no'}",
            f"Unit type: {self.unit_type or 'not given'}",
            f"Area asked for: {_range(self.area_min, self.area_max, 'sqm')}",
            f"Rent range: {_range(self.rent_min, self.rent_max, 'SAR')}",
            f"Malls: {self.malls}",
            "Rule: suggest asking when " + (" or ".join(rule_parts) or "never") + ".",
        ]
        if self.already_requested:
            lines.append("Result: already requested on this case; nothing to suggest.")
        elif self.suggest:
            lines.append("Result: suggest asking — " + "; ".join(self.reasons) + ".")
        else:
            lines.append("Result: not needed — no condition holds.")
        lines.append("The RSM decides; never send the request yourself.")
        return "\n".join(lines)


def _range(low: float | None, high: float | None, unit: str) -> str:
    if low is None or high is None:
        return "not given"
    return f"{low:g}–{high:g} {unit}"


def _given(case: Case, key: FieldKey) -> Any:
    value = case.draft.fields[key]
    if value.value is None or value.source == Source.DEFAULT:
        return None
    return value.value


def _number(case: Case, key: FieldKey) -> float | None:
    value = _given(case, key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_known_company(case: Case, services: ServiceContainer) -> bool:
    if case.yardi.company_id or case.tenant_id:
        return True
    cr = _given(case, FieldKey.CR_NUMBER)
    if not cr:
        return False
    return bool(services.tenants.get_by_cr(str(cr)) or services.yardi.company_by_cr(str(cr)))


def assess_forecasted_sales(case: Case, services: ServiceContainer) -> SalesDataAssessment:
    rule = get_policy().forecasted_sales.suggest_when
    new_company = not _is_known_company(case, services)
    area_min = _number(case, FieldKey.AREA_MIN)
    threshold = rule.area_min_sqm_at_least
    reasons: list[str] = []
    if rule.new_company and new_company:
        reasons.append("a company new to Cenomi")
    if threshold and area_min is not None and area_min >= threshold:
        reasons.append(f"a minimum area of {area_min:g} sqm")
    malls = _given(case, FieldKey.MALLS)
    unit_type = _given(case, FieldKey.UNIT_TYPE)
    already = any(r.kind == "sales_data" for r in case.requests)
    return SalesDataAssessment(
        suggest=bool(reasons) and not already,
        new_company=new_company,
        unit_type=str(unit_type) if unit_type else None,
        area_min=area_min,
        area_max=_number(case, FieldKey.AREA_MAX),
        rent_min=_number(case, FieldKey.RENT_MIN),
        rent_max=_number(case, FieldKey.RENT_MAX),
        malls=len(malls) if isinstance(malls, list) else (1 if malls else 0),
        reasons=reasons,
        already_requested=already,
    )
