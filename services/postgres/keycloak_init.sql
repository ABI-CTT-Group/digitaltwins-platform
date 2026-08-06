-- Creates the Keycloak database and role in the shared postgres instance.
-- Mounted as 03_keycloak.sql in docker-entrypoint-initdb.d/ (runs once, on first
-- initialisation of an empty postgres_data volume). The password here must match
-- KC_DB_PASSWORD in services/keycloak/docker-compose.yml (both default to 'keycloak'
-- unless KEYCLOAK_DB_PASSWORD is set). The role is internal to the docker network.
CREATE USER keycloak WITH PASSWORD 'keycloak';
CREATE DATABASE keycloak OWNER keycloak;
