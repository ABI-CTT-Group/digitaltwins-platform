from digitaltwins_on_fhir.core import Adapter
from fhirpy import AsyncFHIRClient, SyncFHIRClient
import os

fhir_async_client = None
fhir_sync_client = None
adapter = None


def get_fhir_adapter() -> Adapter:
    """Get the global FHIR Adapter instance"""
    global adapter
    if adapter is None:
        endpoint = os.getenv('FHIR_ENDPOINT', "localhost:8080/fhir")
        use_ssl = os.getenv('USE_SSL', "false").lower() == 'true'
        endpoint_url = f"http{'s' if use_ssl else ''}://{endpoint}"
        adapter = Adapter(endpoint_url)
    return adapter


def get_fhir_sync_client() -> SyncFHIRClient:
    """Get the global FHIR sync client instance"""
    global fhir_sync_client
    if fhir_sync_client is None:
        fhir_sync_client = get_fhir_adapter().sync_client
    return fhir_sync_client


def get_fhir_async_client() -> AsyncFHIRClient:
    """Get the global FHIR async client instance"""
    global fhir_async_client
    if fhir_async_client is None:
        fhir_async_client = get_fhir_adapter().async_client
    return fhir_async_client
