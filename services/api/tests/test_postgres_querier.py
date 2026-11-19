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


SUBJECT_UUID = "55555555-5555-5555-5555-555555555555"
INJECTION = "x') OR ('1'='1"


@pytest.mark.parametrize("method, kwargs, responses, expected_values", [
    ("get_datasets", {"categories": ["measurement", INJECTION]}, [[]], [(("measurement", INJECTION),)]),
    ("get_dataset", {"dataset_uuid": INJECTION}, [[{}]], [(INJECTION,)]),
    ("get_dataset_uuid_by_seek_id", {"seek_id": INJECTION}, [[]], [(INJECTION,)]),
    ("get_dataset_descriptions", {"dataset_uuid": INJECTION}, [[]], [(INJECTION,)]),
    ("get_subjects", {"dataset_uuid": INJECTION}, [[]], [(INJECTION,)]),
    ("get_subject_by_sample", {"sample_uuid": INJECTION},
     [[{"subject_uuid": SUBJECT_UUID}], []], [(INJECTION,), (SUBJECT_UUID,)]),
    ("get_sample", {"sample_uuid": INJECTION}, [[]], [(INJECTION,)]),
    ("get_dataset_samples", {"dataset_uuid": DATASET_UUID, "sample_type": INJECTION},
     [[]], [(DATASET_UUID, INJECTION)]),
])
def test_values_are_query_parameters(method, kwargs, responses, expected_values):
    querier = _querier(responses)

    getattr(querier, method)(**kwargs)

    assert [values for _, values in querier.calls] == expected_values
    for sql, values in querier.calls:
        for value in values:
            for item in value if isinstance(value, tuple) else (value,):
                assert item not in sql


def test_datasets_without_categories_queries_every_dataset():
    querier = _querier([[]])

    querier.get_datasets(categories=[])

    assert querier.calls == [("SELECT * FROM dataset", None)]


def test_methods_on_missing_tables_are_gone():
    assert not hasattr(Querier, "get_samples")
    assert not hasattr(Querier, "get_workflow")


@pytest.fixture
def seeded(platform_db):
    """One measurement dataset with a description, a subject and two samples."""
    ids = {
        "dataset": str(uuid.uuid4()),
        "other_dataset": str(uuid.uuid4()),
        "subject": str(uuid.uuid4()),
        "samples": [str(uuid.uuid4()), str(uuid.uuid4())],
    }
    conn = platform_db()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO dataset (dataset_uuid, category, seek_id) VALUES (%s, 'measurement', '42')",
                    (ids["dataset"],))
        cur.execute("INSERT INTO dataset (dataset_uuid, category) VALUES (%s, 'workflow')", (ids["other_dataset"],))
        cur.execute("INSERT INTO dataset_description (dataset_uuid, title) VALUES (%s, 'Heart')", (ids["dataset"],))
        cur.execute("INSERT INTO subject (subject_uuid) VALUES (%s)", (ids["subject"],))
        for sample_uuid, sample_type in zip(ids["samples"], ["ax dyn pre", "ax dyn post"]):
            cur.execute("INSERT INTO sample (sample_uuid, sample_type) VALUES (%s, %s)", (sample_uuid, sample_type))
            cur.execute(
                "INSERT INTO dataset_mapping (dataset_uuid, subject_uuid, sample_uuid) VALUES (%s, %s, %s)",
                (ids["dataset"], ids["subject"], sample_uuid),
            )
    conn.commit()
    conn.close()
    return ids


@pytest.mark.integration
def test_get_datasets_against_postgres(seeded):
    querier = Querier()

    assert len(querier.get_datasets()) == 2
    assert [d["dataset_uuid"] for d in querier.get_datasets(categories=["measurement"])] == [seeded["dataset"]]
    assert querier.get_datasets(categories=[INJECTION]) == []


@pytest.mark.integration
def test_get_dataset_against_postgres(seeded):
    assert Querier().get_dataset(seeded["dataset"])["category"] == "measurement"


@pytest.mark.integration
def test_get_dataset_uuid_by_seek_id_against_postgres(seeded):
    querier = Querier()

    assert querier.get_dataset_uuid_by_seek_id("42") == seeded["dataset"]
    assert querier.get_dataset_uuid_by_seek_id(INJECTION) is None


@pytest.mark.integration
def test_get_dataset_descriptions_against_postgres(seeded):
    import psycopg2

    querier = Querier()

    assert [d["title"] for d in querier.get_dataset_descriptions(seeded["dataset"])] == ["Heart"]
    with pytest.raises(psycopg2.DataError):
        querier.get_dataset_descriptions(f"{seeded['other_dataset']}' OR '1'='1")


@pytest.mark.integration
def test_get_subjects_against_postgres(seeded):
    rows = Querier().get_subjects(seeded["dataset"])

    assert sorted(r["sample_uuid"] for r in rows) == sorted(seeded["samples"])


@pytest.mark.integration
def test_get_subject_by_sample_against_postgres(seeded):
    rows = Querier().get_subject_by_sample(seeded["samples"][0])

    assert [r["subject_uuid"] for r in rows] == [seeded["subject"]]


@pytest.mark.integration
def test_get_sample_against_postgres(seeded):
    rows = Querier().get_sample(seeded["samples"][1])

    assert [r["sample_type"] for r in rows] == ["ax dyn post"]


@pytest.mark.integration
def test_get_dataset_samples_against_postgres(seeded):
    querier = Querier()

    rows = querier.get_dataset_samples(seeded["dataset"], sample_type="ax dyn pre")
    assert [r["sample_uuid"] for r in rows] == [seeded["samples"][0]]
    assert querier.get_dataset_samples(seeded["dataset"], sample_type=INJECTION) == []


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
