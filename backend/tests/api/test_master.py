import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_master_unit_types(client: AsyncClient) -> None:
    response = await client.get("/api/master/unit_types")
    assert response.status_code == 200
    items = response.json()
    assert any(item["id"] == "store" and item["code"] == "STR" for item in items)


@pytest.mark.asyncio
async def test_master_malls_filtered_by_city(client: AsyncClient) -> None:
    response = await client.get("/api/master/malls", params={"city": "riyadh"})
    assert response.status_code == 200
    malls = response.json()
    assert len(malls) == 4
    assert all(m["city"] == "riyadh" for m in malls)

    jeddah = await client.get("/api/master/malls", params={"city": "jeddah"})
    assert len(jeddah.json()) == 2
