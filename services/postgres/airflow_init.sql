-- Creates the Airflow database and user in the shared postgres instance.
-- Mounted as 02_airflow.sql in docker-entrypoint-initdb.d/ (runs once on first startup).
CREATE USER airflow WITH PASSWORD 'airflow';
CREATE DATABASE airflow OWNER airflow;
