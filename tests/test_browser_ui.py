from httpx import ASGITransport, AsyncClient

from main import asgi_app


async def test_ui_index_is_served():
    transport = ASGITransport(app=asgi_app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/ui")

    assert response.status_code == 200
    assert "data.gouv.fr Explorer" in response.text
    assert "/ui/assets/app.js" in response.text


async def test_ui_search_endpoint_returns_catalog_payload(monkeypatch):
    async def fake_search_catalog(question: str, page_size: int = 6):
        assert question == "bike lanes"
        assert page_size == 4
        return {
            "question": question,
            "search_query": "bike lanes",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "answer": 'Searched for "bike lanes" using "bike lanes".',
            "sections": [
                {
                    "key": "datasets",
                    "title": "Datasets",
                    "total": 1,
                    "displayed": 1,
                    "items": [{"title": "Bike lanes"}],
                    "error": None,
                }
            ],
            "rows": [{"result_type": "dataset", "title": "Bike lanes"}],
            "errors": [],
        }

    monkeypatch.setattr("helpers.browser_ui.search_catalog", fake_search_catalog)

    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/ui/api/search",
            json={"question": "bike lanes", "page_size": 4},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["rows"][0]["title"] == "Bike lanes"
    assert payload["sections"][0]["total"] == 1


async def test_ui_export_json_endpoint_downloads_attachment():
    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/ui/api/export",
            json={
                "format": "json",
                "question": "bike lanes in paris",
                "search_query": "bike lanes paris",
                "rows": [{"result_type": "dataset", "title": "Bike lanes"}],
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert '"title": "Bike lanes"' in response.text


async def test_ui_export_xlsx_endpoint_returns_spreadsheet():
    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/ui/api/export",
            json={
                "format": "xlsx",
                "question": "bike lanes in paris",
                "search_query": "bike lanes paris",
                "rows": [{"result_type": "dataset", "title": "Bike lanes"}],
            },
        )

    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.content[:2] == b"PK"
