from app.agent.checkpointer import memory_checkpointer
from app.domain.models import DocType, InquiryDraft, Source, new_inquiry_draft
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


def test_memory_checkpointer_allows_domain_types_in_msgpack() -> None:
    serde = memory_checkpointer().serde
    assert isinstance(serde, JsonPlusSerializer)
    draft = new_inquiry_draft()
    payload = {"draft": draft, "source": Source.USER, "doc": DocType.CR_CERTIFICATE}
    packed = serde.dumps_typed(payload)
    restored = serde.loads_typed(packed)
    assert isinstance(restored["draft"], InquiryDraft)
    assert restored["source"] is Source.USER
    assert restored["doc"] is DocType.CR_CERTIFICATE
