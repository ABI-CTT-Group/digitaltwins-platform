"""Tests for digitaltwins.postgres.querier.Querier."""
import uuid

import pytest

from digitaltwins.postgres.querier import Querier

DATASET_UUID = "11111111-1111-1111-1111-111111111111"
SAMPLE_UUIDS = [
    "22222222-2222-2222-2222-222222222222",
    "33333333-3333-3333-3333-333333333333",
    "44444444-4444-4444-4444-444444444444",
]


def _querier(responses):
    """A Querier with no connection whose _query records calls and returns canned rows."""
    querier = object.__new__(Querier)
    querier.calls = []
    replies = iter(responses)

    def fake_query(sql, values=None):
        querier.calls.append((sql, values))
        return next(replies)

    querier._query = fake_query
    return querier


def test_sample_types_of_a_dataset_with_no_samples_is_empty():
    querier = _querier([[]])

    assert querier.get_dataset_sample_types(DATASET_UUID) == []
    assert len(querier.calls) == 1


def test_sample_types_passes_values_as_query_parameters():
    querier = _querier([
        [{"sample_uuid": u} for u in SAMPLE_UUIDS],
        [{"sample_type": "a"}, {"sample_type": "b"}, {"sample_type": "a"}, {"sample_type": None}],
    ])

    assert querier.get_dataset_sample_types(DATASET_UUID) == ["a", "b"]

    (first_sql, first_values), (second_sql, second_values) = querier.calls
    assert first_values == (DATASET_UUID,)
    assert second_values == (tuple(SAMPLE_UUIDS),)
    for value in [DATASET_UUID, *SAMPLE_UUIDS]:
        assert value not in first_sql
        assert value not in second_sql


@pytest.mark.integration
def test_sample_types_against_postgres(platform_db):
    dataset_uuid = str(uuid.uuid4())
    subject_uuid = str(uuid.uuid4())
    samples = [(str(uuid.uuid4()), t) for t in ["a", "b", "a"]]
    conn = platform_db()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO dataset (dataset_uuid, category) VALUES (%s, 'measurement')", (dataset_uuid,))
        cur.execute("INSERT INTO subject (subject_uuid) VALUES (%s)", (subject_uuid,))
        for sample_uuid, sample_type in samples:
            cur.execute("INSERT INTO sample (sample_uuid, sample_type) VALUES (%s, %s)", (sample_uuid, sample_type))
            cur.execute(
                "INSERT INTO dataset_mapping (dataset_uuid, subject_uuid, sample_uuid) VALUES (%s, %s, %s)",
                (dataset_uuid, subject_uuid, sample_uuid),
            )
    conn.commit()
    conn.close()

    querier = Querier()

    assert sorted(querier.get_dataset_sample_types(dataset_uuid)) == ["a", "b"]
    assert querier.get_dataset_sample_types(str(uuid.uuid4())) == []
