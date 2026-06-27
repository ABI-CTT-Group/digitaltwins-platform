-- Creates the Keycloak database and user in the shared postgres instance.
-- Mounted as 03_keycloak.sql in docker-entrypoint-initdb.d/ (runs once on first startup).
CREATE USER keycloak WITH PASSWORD 'keycloak';
CREATE DATABASE keycloak OWNER keycloak;
