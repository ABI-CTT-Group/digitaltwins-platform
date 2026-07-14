-- Create the Airflow database and user on the shared platform PostgreSQL instance.
-- This script runs automatically on first initialisation (empty data volume).

DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'airflow') THEN
      CREATE ROLE airflow WITH LOGIN PASSWORD 'airflow';
   END IF;
END
$$;

SELECT 'CREATE DATABASE airflow OWNER airflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow')\gexec
