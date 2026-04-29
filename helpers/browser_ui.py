import json
import logging
from pathlib import Path
from typing import Any

from helpers.catalog_ui import search_catalog
from helpers.export_utils import (
    export_filename,
    rows_to_csv_bytes,
    rows_to_json_bytes,
    rows_to_xlsx_bytes,
)
from helpers.logging import MAIN_LOGGER_NAME

logger = logging.getLogger(MAIN_LOGGER_NAME)

_WEB_UI_DIR = Path(__file__).resolve().parent.parent / "web_ui"
_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


def _header_bytes(headers: list[tuple[str, str]]) -> list[tuple[bytes, bytes]]:
    return [(key.encode("utf-8"), value.encode("utf-8")) for key, value in headers]


async def _send_response(
    send,
    *,
    status: int,
    body: bytes,
    headers: list[tuple[str, str]],
) -> None:
    all_headers = headers + [("content-length", str(len(body)))]
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": _header_bytes(all_headers),
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _send_json(send, *, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await _send_response(
        send,
        status=status,
        body=body,
        headers=[("content-type", "application/json; charset=utf-8")],
    )


async def _send_text(send, *, status: int, text: str) -> None:
    await _send_response(
        send,
        status=status,
        body=text.encode("utf-8"),
        headers=[("content-type", "text/plain; charset=utf-8")],
    )


async def _read_body(receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] != "http.request":
            continue
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _safe_web_path(relative_path: str) -> Path | None:
    candidate = (_WEB_UI_DIR / relative_path).resolve()
    try:
        candidate.relative_to(_WEB_UI_DIR.resolve())
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


async def _serve_asset(send, relative_path: str) -> None:
    asset_path = _safe_web_path(relative_path)
    if asset_path is None:
        await _send_text(send, status=404, text="Not found")
        return

    content_type = _CONTENT_TYPES.get(
        asset_path.suffix.lower(),
        "application/octet-stream",
    )
    body = asset_path.read_bytes()
    await _send_response(
        send,
        status=200,
        body=body,
        headers=[("content-type", content_type)],
    )


def _coerce_page_size(value: Any) -> int:
    try:
        page_size = int(value)
    except (TypeError, ValueError):
        return 6
    return max(1, min(page_size, 12))


async def _handle_search(receive, send) -> None:
    try:
        payload = json.loads((await _read_body(receive)).decode("utf-8") or "{}")
    except json.JSONDecodeError:
        await _send_json(send, status=400, payload={"error": "Invalid JSON payload."})
        return

    question = str(payload.get("question", "")).strip()
    page_size = _coerce_page_size(payload.get("page_size"))

    if not question:
        await _send_json(
            send,
            status=400,
            payload={"error": "Please enter a question before searching."},
        )
        return

    try:
        result = await search_catalog(question, page_size=page_size)
    except ValueError as exc:
        await _send_json(send, status=400, payload={"error": str(exc)})
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Browser UI search failed")
        await _send_json(
            send,
            status=502,
            payload={
                "error": (
                    "The catalog search could not be completed right now. "
                    "Please try again."
                ),
                "details": str(exc),
            },
        )
        return

    await _send_json(send, status=200, payload=result)


async def _handle_export(receive, send) -> None:
    try:
        payload = json.loads((await _read_body(receive)).decode("utf-8") or "{}")
    except json.JSONDecodeError:
        await _send_json(send, status=400, payload={"error": "Invalid JSON payload."})
        return

    format_name = str(payload.get("format", "json")).strip().lower()
    question = str(payload.get("question", "datagouv-results")).strip()
    search_query = str(payload.get("search_query", "")).strip()
    rows = payload.get("rows")

    if not isinstance(rows, list):
        await _send_json(
            send,
            status=400,
            payload={"error": "Export rows must be a JSON array."},
        )
        return

    if format_name == "csv":
        body = rows_to_csv_bytes(rows)
        content_type = "text/csv; charset=utf-8"
        filename = export_filename(question, "csv")
    elif format_name == "xlsx":
        body = rows_to_xlsx_bytes(rows)
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = export_filename(question, "xlsx")
    elif format_name == "json":
        body = rows_to_json_bytes(
            question=question,
            search_query=search_query,
            rows=rows,
        )
        content_type = "application/json; charset=utf-8"
        filename = export_filename(question, "json")
    else:
        await _send_json(
            send,
            status=400,
            payload={"error": "Unsupported export format."},
        )
        return

    await _send_response(
        send,
        status=200,
        body=body,
        headers=[
            ("content-type", content_type),
            ("content-disposition", f'attachment; filename="{filename}"'),
        ],
    )


async def browser_ui_app(scope, receive, send) -> None:
    if scope["type"] != "http":
        await _send_text(send, status=404, text="Not found")
        return

    method = scope.get("method", "GET").upper()
    path = scope.get("path", "")

    if method == "GET" and path == "/ui/":
        await _send_response(
            send,
            status=307,
            body=b"",
            headers=[("location", "/ui")],
        )
        return

    if method == "GET" and path == "/ui":
        await _serve_asset(send, "index.html")
        return

    if method == "GET" and path.startswith("/ui/assets/"):
        relative_path = path.removeprefix("/ui/assets/")
        await _serve_asset(send, relative_path)
        return

    if method == "POST" and path == "/ui/api/search":
        await _handle_search(receive, send)
        return

    if method == "POST" and path == "/ui/api/export":
        await _handle_export(receive, send)
        return

    await _send_text(send, status=404, text="Not found")
