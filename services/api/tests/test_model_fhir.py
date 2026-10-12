"""Model FHIR: ``{"model": {...}}`` descriptions and the Device built from them."""
import pytest

from conftest import FakeHapi
from digitaltwins.measurements.fhir_service import HapiRest
from digitaltwins.models import fhir as model_fhir

SYSTEM = "https://www.auckland.ac.nz/en/abi.html"


def test_server_fills_identity_and_defaults():
    d = model_fhir.build_descriptions("uuid-1", "skin model")["model"]

    assert d == {"uuid": "uuid-1", "name": "skin model", "description": "", "version": ""}


def test_client_fields_are_kept_and_server_fields_overwritten():
    client = {"model": {"uuid": "forged", "name": "forged", "description": "nnUNet skin", "version": "2.1"}}

    d = model_fhir.build_descriptions("uuid-1", "skin model", client)["model"]

    assert d == {"uuid": "uuid-1", "name": "skin model", "description": "nnUNet skin", "version": "2.1"}


def test_default_description_is_used_when_the_client_gives_none():
    d = model_fhir.build_descriptions("uuid-1", "m", {"model": {"version": "1"}}, default_description="From upload")["model"]

    assert d["description"] == "From upload"


@pytest.mark.parametrize("client, message", [
    ({"patients": []}, "model"),
    ({"model": "x"}, "model"),
    ({"model": {"framework": "nnUNet"}}, "framework"),
    ({"model": {"version": 2}}, "version"),
])
def test_invalid_client_descriptions_are_rejected(client, message):
    with pytest.raises(ValueError, match=message):
        model_fhir.build_descriptions("uuid-1", "m", client)


def test_device_carries_identifier_name_version_and_note():
    device = model_fhir.to_device(model_fhir.build_descriptions(
        "uuid-1", "skin model", {"model": {"description": "nnUNet skin", "version": "2.1"}}))

    assert device == {
        "resourceType": "Device",
        "identifier": [{"system": SYSTEM, "value": "uuid-1"}],
        "status": "active",
        "deviceName": [{"name": "skin model", "type": "user-friendly-name"}],
        "type": {"text": "model"},
        "version": [{"value": "2.1"}],
        "note": [{"text": "nnUNet skin"}],
    }


def test_device_leaves_out_empty_version_and_note():
    device = model_fhir.to_device(model_fhir.build_descriptions("uuid-1", "m"))

    assert "version" not in device and "note" not in device


def test_push_replaces_an_existing_device():
    hapi = FakeHapi()
    descriptions = model_fhir.build_descriptions("uuid-1", "m", {"model": {"version": "1"}})
    model_fhir.push(descriptions, hapi)
    model_fhir.push(model_fhir.build_descriptions("uuid-1", "m", {"model": {"version": "2"}}), hapi)

    devices = hapi.search("Device", identifier="uuid-1")
    assert len(devices) == 1 and devices[0]["version"] == [{"value": "2"}]


def test_delete_removes_the_device():
    hapi = FakeHapi()
    model_fhir.push(model_fhir.build_descriptions("uuid-1", "m"), hapi)

    assert model_fhir.delete("uuid-1", hapi) == 1
    assert hapi.search("Device", identifier="uuid-1") == []


class _Response:
    def __init__(self, body, status=201):
        self.body, self.status_code = body, status

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class _Session:
    def __init__(self):
        self.posts = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append((url, json, headers))
        return _Response({**json, "id": "9"})


def test_rest_create_posts_the_resource_to_its_type():
    session = _Session()

    created = HapiRest("http://h/fhir/", session=session).create({"resourceType": "Device", "status": "active"})

    assert created["id"] == "9"
    url, body, headers = session.posts[0]
    assert url == "http://h/fhir/Device" and body["resourceType"] == "Device"
    assert headers["Content-Type"] == "application/fhir+json"
