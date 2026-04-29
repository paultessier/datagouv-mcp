import json
import zipfile
from io import BytesIO

from helpers.export_utils import (
    export_filename,
    rows_to_csv_bytes,
    rows_to_json_bytes,
    rows_to_xlsx_bytes,
)


def test_rows_to_csv_bytes_writes_flat_table():
    rows = [
        {
            "result_type": "dataset",
            "title": "Bike lanes",
            "tags": "paris, mobility",
            "resources_count": 3,
        }
    ]

    csv_text = rows_to_csv_bytes(rows).decode("utf-8")

    assert "result_type,title,tags,resources_count" in csv_text
    assert "dataset,Bike lanes,\"paris, mobility\",3" in csv_text


def test_rows_to_json_bytes_keeps_context():
    payload = rows_to_json_bytes(
        question="bike lanes in paris",
        search_query="bike lanes paris",
        rows=[{"title": "Bike lanes", "result_type": "dataset"}],
    )

    parsed = json.loads(payload.decode("utf-8"))

    assert parsed["question"] == "bike lanes in paris"
    assert parsed["search_query"] == "bike lanes paris"
    assert parsed["rows"][0]["title"] == "Bike lanes"


def test_rows_to_xlsx_bytes_creates_valid_xlsx_archive():
    content = rows_to_xlsx_bytes(
        [
            {
                "result_type": "dataset",
                "title": "Bike lanes",
                "resources_count": 3,
            }
        ]
    )

    archive = zipfile.ZipFile(BytesIO(content))

    assert "[Content_Types].xml" in archive.namelist()
    sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "Bike lanes" in sheet_xml
    assert "resources_count" in sheet_xml


def test_export_filename_slugifies_question():
    filename = export_filename("Bike lanes in Paris?!", "csv")

    assert filename == "bike-lanes-in-paris.csv"
