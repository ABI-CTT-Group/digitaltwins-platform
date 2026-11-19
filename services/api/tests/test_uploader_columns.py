"""Column names in the uploader's INSERTs come from spreadsheet headers, so they must be plain identifiers."""
import pytest

from digitaltwins.core import uploader
from digitaltwins.core.uploader import Uploader

DATASET_UUID = "11111111-1111-1111-1111-111111111111"
BAD_COLUMN = "x) VALUES (1); DROP TABLE dataset; --"


class RecordingCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql, values=None):
        self.executed.append((sql, values))

    def fetchone(self):
        return ["22222222-2222-2222-2222-222222222222"]


@pytest.mark.parametrize("table_name", ["dataset_description", "manifest", "subject", "sample"])
def test_insert_rejects_a_column_that_is_not_an_identifier(table_name):
    cur = RecordingCursor()

    with pytest.raises(ValueError, match="column name"):
        Uploader._insert_metadata_rows(
            cur, table_name, table_name, [{"sample_type": "a", BAD_COLUMN: "b"}], DATASET_UUID, {}, []
        )

    assert cur.executed == []


@pytest.mark.parametrize("table_name", ["dataset_description", "manifest", "subject", "sample"])
def test_insert_accepts_plain_column_names(table_name):
    cur = RecordingCursor()

    Uploader._insert_metadata_rows(cur, table_name, table_name, [{"sample_type": "a"}], DATASET_UUID, {}, [])

    (sql, values), = cur.executed
    assert "sample_type" in sql
    assert "a" in values


def test_every_mapped_column_passes_the_check():
    mapping = Uploader._load_element_mapping(None)
    columns = {column for sheet in mapping.values() for column in sheet.values()}

    assert columns
    uploader._column_list(sorted(columns))
