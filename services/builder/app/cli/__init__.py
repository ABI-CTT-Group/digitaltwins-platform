"""Command-line entrypoints that run inside the builder container.

These operate on the service layer directly (DB / MinIO / hapi-fhir), not the
HTTP API, so they bypass API auth — admin authorisation is enforced explicitly
via Keycloak login (see ``keycloak_login``).
"""
