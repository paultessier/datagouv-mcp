import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from helpers import datagouv_api_client
from helpers.query_text import extract_catalog_query
from helpers.user_agent import USER_AGENT


@dataclass
class _SectionResult:
    key: str
    title: str
    total: int
    items: list[dict[str, Any]]
    error: str | None = None


def _compact_text(value: str | None, *, limit: int = 260) -> str:
    if not value:
        return ""
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _dataset_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append(
            {
                "result_type": "dataset",
                "title": item.get("title", ""),
                "id": item.get("id", ""),
                "organization": item.get("organization", ""),
                "description": _compact_text(
                    item.get("description_short") or item.get("description")
                ),
                "tags": ", ".join(item.get("tags") or []),
                "resources_count": item.get("resources_count", 0),
                "url": item.get("url", ""),
            }
        )
    return rows


def _dataservice_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append(
            {
                "result_type": "dataservice",
                "title": item.get("title", ""),
                "id": item.get("id", ""),
                "organization": item.get("organization", ""),
                "description": _compact_text(item.get("description")),
                "tags": ", ".join(item.get("tags") or []),
                "base_api_url": item.get("base_api_url", ""),
                "machine_documentation_url": item.get(
                    "machine_documentation_url", ""
                ),
                "url": item.get("url", ""),
            }
        )
    return rows


def _organization_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        metrics = item.get("metrics") or {}
        rows.append(
            {
                "result_type": "organization",
                "title": item.get("name", ""),
                "id": item.get("id", ""),
                "acronym": item.get("acronym", ""),
                "badges": ", ".join(item.get("badges") or []),
                "datasets": metrics.get("datasets", ""),
                "reuses": metrics.get("reuses", ""),
                "followers": metrics.get("followers", ""),
                "views": metrics.get("views", ""),
                "profile_url": item.get("profile_url", ""),
                "url": item.get("url", ""),
            }
        )
    return rows


def _section_payload(section: _SectionResult) -> dict[str, Any]:
    return {
        "key": section.key,
        "title": section.title,
        "total": section.total,
        "displayed": len(section.items),
        "items": section.items,
        "error": section.error,
    }


def _build_summary(
    *,
    question: str,
    search_query: str,
    sections: list[_SectionResult],
) -> str:
    counts = [f"{section.total} {section.title.lower()}" for section in sections]
    return (
        f'Searched for "{question}" using "{search_query}". '
        f"Found {', '.join(counts)}."
    )


def _pick_best_query_candidates(question: str) -> list[str]:
    candidates: list[str] = []
    for candidate in [extract_catalog_query(question), question.strip()]:
        stripped = candidate.strip()
        if stripped and stripped not in candidates:
            candidates.append(stripped)
    return candidates


async def _search_once(
    search_query: str,
    *,
    page_size: int,
) -> tuple[list[_SectionResult], list[str]]:
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as session:
        results = await asyncio.gather(
            datagouv_api_client.search_datasets(
                search_query, page=1, page_size=page_size, session=session
            ),
            datagouv_api_client.search_dataservices(
                search_query, page=1, page_size=page_size, session=session
            ),
            datagouv_api_client.search_organizations(
                query=search_query, page=1, page_size=page_size, session=session
            ),
            return_exceptions=True,
        )

    sections: list[_SectionResult] = []
    errors: list[str] = []

    dataset_result, dataservice_result, organization_result = results

    if isinstance(dataset_result, Exception):
        sections.append(
            _SectionResult(
                key="datasets",
                title="Datasets",
                total=0,
                items=[],
                error=str(dataset_result),
            )
        )
        errors.append(f"datasets: {dataset_result}")
    else:
        sections.append(
            _SectionResult(
                key="datasets",
                title="Datasets",
                total=dataset_result.get("total", 0),
                items=dataset_result.get("data", []),
            )
        )

    if isinstance(dataservice_result, Exception):
        sections.append(
            _SectionResult(
                key="dataservices",
                title="Dataservices",
                total=0,
                items=[],
                error=str(dataservice_result),
            )
        )
        errors.append(f"dataservices: {dataservice_result}")
    else:
        sections.append(
            _SectionResult(
                key="dataservices",
                title="Dataservices",
                total=dataservice_result.get("total", 0),
                items=dataservice_result.get("data", []),
            )
        )

    if isinstance(organization_result, Exception):
        sections.append(
            _SectionResult(
                key="organizations",
                title="Organizations",
                total=0,
                items=[],
                error=str(organization_result),
            )
        )
        errors.append(f"organizations: {organization_result}")
    else:
        sections.append(
            _SectionResult(
                key="organizations",
                title="Organizations",
                total=organization_result.get("total", 0),
                items=organization_result.get("data", []),
            )
        )

    return sections, errors


def _displayed_hits(sections: list[_SectionResult]) -> int:
    return sum(len(section.items) for section in sections)


async def search_catalog(question: str, page_size: int = 6) -> dict[str, Any]:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("question cannot be empty")

    candidate_queries = _pick_best_query_candidates(cleaned_question)
    best_sections: list[_SectionResult] | None = None
    best_query = candidate_queries[0]
    best_errors: list[str] = []

    for candidate_query in candidate_queries:
        sections, candidate_errors = await _search_once(
            candidate_query,
            page_size=page_size,
        )
        if best_sections is None or _displayed_hits(sections) > _displayed_hits(
            best_sections
        ):
            best_sections = sections
            best_query = candidate_query
            best_errors = candidate_errors
        if _displayed_hits(sections) > 0:
            best_sections = sections
            best_query = candidate_query
            best_errors = candidate_errors
            break

    assert best_sections is not None

    export_rows = (
        _dataset_rows(best_sections[0].items)
        + _dataservice_rows(best_sections[1].items)
        + _organization_rows(best_sections[2].items)
    )

    return {
        "question": cleaned_question,
        "search_query": best_query,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "answer": _build_summary(
            question=cleaned_question,
            search_query=best_query,
            sections=best_sections,
        ),
        "sections": [_section_payload(section) for section in best_sections],
        "rows": export_rows,
        "errors": best_errors,
    }
