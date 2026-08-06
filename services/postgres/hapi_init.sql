-- Creates the HAPI FHIR database in the shared postgres instance. HAPI connects as
-- the admin superuser (SPRING_DATASOURCE_USERNAME/PASSWORD in the hapi-fhir service),
-- so no separate role is needed; the DB is owned by admin.
-- Mounted as 04_hapi.sql in docker-entrypoint-initdb.d/ (runs once, on first init).
CREATE DATABASE hapi;
