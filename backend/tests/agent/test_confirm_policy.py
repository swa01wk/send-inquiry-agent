from app.agent.confirm_policy import keys_blocked_from_confirmation
from app.domain.models import FieldKey


def test_category_doubt_blocks_sales_category() -> None:
    blocked = keys_blocked_from_confirmation("Hmm, not sure about the category")
    assert FieldKey.SALES_CATEGORY.value in blocked


def test_clear_acceptance_does_not_block() -> None:
    assert keys_blocked_from_confirmation("Yes, that's all correct") == frozenset()
