import pytest
from httpx import AsyncClient


async def _create_session(client: AsyncClient) -> str:
    response = await client.post("/api/sessions")
    return response.json()["session_id"]


@pytest.mark.asyncio
async def test_upload_success_updates_draft(client: AsyncClient) -> None:
    session_id = await _create_session(client)
    response = await client.post(
        f"/api/sessions/{session_id}/documents",
        data={"doc_type": "company_profile"},
        files={"file": ("company.pdf", b"%PDF-sample", "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["document"]["doc_type"] == "company_profile"
    assert body["document"]["file_name"] == "company.pdf"
    assert body["card"]["card_type"] == "document_upload"
    assert body["draft"]["changed_keys"] == []

    doc_row = next(d for d in body["draft"]["documents"] if d["doc_type"] == "company_profile")
    assert doc_row["uploaded"] is True
    assert body["draft"]["checks"]["required_docs_uploaded"] == 1


@pytest.mark.asyncio
async def test_upload_invalid_extension(client: AsyncClient) -> None:
    session_id = await _create_session(client)
    response = await client.post(
        f"/api/sessions/{session_id}/documents",
        data={"doc_type": "company_profile"},
        files={"file": ("virus.exe", b"bad", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_extension"


@pytest.mark.asyncio
async def test_upload_too_large(client: AsyncClient) -> None:
    session_id = await _create_session(client)
    big = b"x" * (6 * 1024 * 1024)
    response = await client.post(
        f"/api/sessions/{session_id}/documents",
        data={"doc_type": "company_profile"},
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "too_large"


@pytest.mark.asyncio
async def test_upload_unknown_doc_type(client: AsyncClient) -> None:
    session_id = await _create_session(client)
    response = await client.post(
        f"/api/sessions/{session_id}/documents",
        data={"doc_type": "not_a_real_type"},
        files={"file": ("file.pdf", b"x", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unknown_doc_type"


@pytest.mark.asyncio
async def test_delete_document(client: AsyncClient) -> None:
    session_id = await _create_session(client)
    await client.post(
        f"/api/sessions/{session_id}/documents",
        data={"doc_type": "company_profile"},
        files={"file": ("company.pdf", b"x", "application/pdf")},
    )
    response = await client.delete(f"/api/sessions/{session_id}/documents/company_profile")
    assert response.status_code == 200
    body = response.json()
    doc_row = next(d for d in body["draft"]["documents"] if d["doc_type"] == "company_profile")
    assert doc_row["uploaded"] is False
    assert body["draft"]["checks"]["required_docs_uploaded"] == 0
