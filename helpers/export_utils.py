import csv
import io
import json
import re
import zipfile
from typing import Any
from xml.sax.saxutils import escape

_PREFERRED_COLUMNS = [
    "result_type",
    "title",
    "id",
    "organization",
    "description",
    "tags",
    "resources_count",
    "base_api_url",
    "machine_documentation_url",
    "acronym",
    "badges",
    "datasets",
    "reuses",
    "followers",
    "views",
    "profile_url",
    "url",
]


def _normalize_value(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, str | int | float | bool]]:
    normalized: list[dict[str, str | int | float | bool]] = []
    for row in rows:
        normalized.append({key: _normalize_value(value) for key, value in row.items()})
    return normalized


def ordered_columns(rows: list[dict[str, Any]]) -> list[str]:
    discovered = {key for row in rows for key in row.keys()}
    ordered = [key for key in _PREFERRED_COLUMNS if key in discovered]
    ordered.extend(sorted(discovered - set(ordered)))
    return ordered


def rows_to_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    normalized = normalize_rows(rows)
    columns = ordered_columns(normalized)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(normalized)
    return buffer.getvalue().encode("utf-8")


def rows_to_json_bytes(
    *,
    question: str,
    search_query: str,
    rows: list[dict[str, Any]],
) -> bytes:
    payload = {
        "question": question,
        "search_query": search_query,
        "rows": normalize_rows(rows),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _xlsx_column_name(index: int) -> str:
    letters: list[str] = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters))


def _xlsx_cell(reference: str, value: str | int | float | bool) -> str:
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{reference}"><v>{value}</v></c>'
    escaped = escape(str(value))
    return f'<c r="{reference}" t="inlineStr"><is><t>{escaped}</t></is></c>'


def rows_to_xlsx_bytes(rows: list[dict[str, Any]]) -> bytes:
    normalized = normalize_rows(rows)
    columns = ordered_columns(normalized)

    sheet_rows: list[str] = []
    header_cells = [
        _xlsx_cell(f"{_xlsx_column_name(index)}1", column)
        for index, column in enumerate(columns, start=1)
    ]
    sheet_rows.append(f"<row r=\"1\">{''.join(header_cells)}</row>")

    for row_index, row in enumerate(normalized, start=2):
        cells: list[str] = []
        for column_index, column in enumerate(columns, start=1):
            reference = f"{_xlsx_column_name(column_index)}{row_index}"
            cells.append(_xlsx_cell(reference, row.get(column, "")))
        sheet_rows.append(f"<row r=\"{row_index}\">{''.join(cells)}</row>")

    worksheet_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        f"<dimension ref=\"A1:{_xlsx_column_name(max(len(columns), 1))}{max(len(normalized) + 1, 1)}\"/>"
        "<sheetViews><sheetView workbookViewId=\"0\"/></sheetViews>"
        "<sheetFormatPr defaultRowHeight=\"15\"/>"
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )

    workbook_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        "<sheets><sheet name=\"Results\" sheetId=\"1\" r:id=\"rId1\"/></sheets>"
        "</workbook>"
    )

    workbook_rels_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" "
        "Target=\"worksheets/sheet1.xml\"/>"
        "<Relationship Id=\"rId2\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" "
        "Target=\"styles.xml\"/>"
        "</Relationships>"
    )

    root_rels_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" "
        "Target=\"xl/workbook.xml\"/>"
        "</Relationships>"
    )

    content_types_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/xl/workbook.xml\" "
        "ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
        "<Override PartName=\"/xl/worksheets/sheet1.xml\" "
        "ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
        "<Override PartName=\"/xl/styles.xml\" "
        "ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>"
        "</Types>"
    )

    styles_xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<styleSheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        "<fonts count=\"1\"><font><sz val=\"11\"/><name val=\"Calibri\"/></font></fonts>"
        "<fills count=\"1\"><fill><patternFill patternType=\"none\"/></fill></fills>"
        "<borders count=\"1\"><border/></borders>"
        "<cellStyleXfs count=\"1\"><xf/></cellStyleXfs>"
        "<cellXfs count=\"1\"><xf xfId=\"0\"/></cellXfs>"
        "<cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles>"
        "</styleSheet>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", root_rels_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet_xml)

    return buffer.getvalue()


def export_filename(question: str, extension: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")
    if not slug:
        slug = "datagouv-results"
    return f"{slug[:48]}.{extension}"
