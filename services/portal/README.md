# DigitalTWINS Portal

## Deploy locally

### Docker setup

- Clone the repo to your PC
```sh
# 1. start docker
cd clinical-dashboard
```
- In the root folder, create a `configs.ini` file and fill in the `digitaltwins-api` configuration settings. Here is the template:
```yml
[general]
metadata_service = 
[postgres]
enabled = 
host = 
port = 
database = 
user = 
password = 
program = 
projects =
[gen3]
enabled = 
endpoint = 
api_key =
api_key_id =
cred_file = 
ssl_cert = 
program = 
project = 
[irods]
enabled = 
irods_host = 
irods_port = 
irods_user = 
irods_password = 
irods_zone = 
irods_project_root = 
[seek]
enabled = 
host = 
port = 
api_token = 
[airflow]
enabled = 
airflow_api_url = 
airflow_endpoint = 
username = 
password = 
```
- In the root folder, create a `.env` file. The template is:
```yml
VITE_APP_API_URL=http://your_backend_url:port/api
```

- Then run docker
```sh
docker compose up 
```