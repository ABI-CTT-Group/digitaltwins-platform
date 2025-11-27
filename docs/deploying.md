# Deploying the DigitalTWINS Platform

This document describes how to deploy the DigitalTWINS Platform from the [deployment repository](https://github.com/ABI-CTT-Group/digitaltwins-platform). It provides a concise quick-start and expanded steps for each service (Keycloak, Airflow, SEEK, etc.), configuration tips, default credentials, and common troubleshooting commands.


## 1. Clone the repository

```bash
git clone https://github.com/ABI-CTT-Group/digitaltwins-platform.git
cd digitaltwins-platform
```

## 2. Environment Configuration

Set up the necessary environment variables and configuration files.
    
1. Main environment File

    ```bash
    cp .env.template .env
    ```
   
   Set the necessary variables:
   - Portal service:
     - `PORTAL_BACKEND_HOST_IP`: your host machine IP address for the portal backend. you can get your host ip by `hostname -I` (Linux command)
   - Workflow service (airflow):
     - `AIRFLOW_UID`: Run echo $(id -u) to find your user ID, then Update the AIRFLOW_UID variable in your .env file with this ID

2. API configuration

    ```bash
    cp ./services/api/digitaltwins-api/configs.ini.template ./services/api/digitaltwins-api/configs.ini
    ```
    
3. SEEK configuration

   ```bash
   cp ./services/seek/ldh-deployment/docker-compose.env.tpl ./services/seek/ldh-deployment/docker-compose.env
   ```

## 3. Initialise the IAM service (keycloak)

Choose one of the following methods to configure Keycloak.

### Method 1: Manual Configuration
1. Start keycloak: `sudo docker compose up -d keycloak`
2. [TODO: Insert manual configuration steps here]
3. Stop Keycloak: `sudo docker compose down`

### Method 2: Auto Configuration from an existing Realm
1. (optional) Export Realm from an existing deployment
   1. Stop the existing Keycloak instance
   2. Run the export command:
      ```bash
      sudo docker compose run --rm keycloak export --realm <YOUR_REALM> --dir /opt/keycloak/data/export --users realm_file
      ```
   3. Copy the export files to your host machine
      ```bash
      sudo docker compose run --rm --user root --entrypoint /bin/sh  -v $(pwd)/export:/backup keycloak -c "cp -r /opt/keycloak/data/export/* /backup/"
      ```
      A realm file will be created in your host, e.g. $(pwd)/export/digitaltwins-realm.json
2. Import Realm
      
   Place the exported realm file in `./services/keycloak/import/digitaltwins-realm.json`

## 4. Initialise workflow service (airflow)
1. Initialize `airflow.cfg`
   ```bash
   sudo docker compose run airflow-cli airflow config list
   ```
2. Enable CORS. 
   
   Edit `./services/airflow/config/airflow.cfg` and update the [api] section:
   ```ini
   access_control_allow_headers = origin, content-type, accept
   access_control_allow_methods = POST, GET, OPTIONS, DELETE
   access_control_allow_origins = 
   ```
3. Initialize the airflow database. 
   ```bash
   sudo docker compose up airflow-init
   ```
   
## 5. Initialise catalogue service (SEEK)
1. Fix Pathing in the external submodule
   1. Open `./services/seek/ldh-deployment/docker-compose.yml`
   2. Replace all `${PWD}/` with `./`
2. Create external volumes
   ```bash
   source .env
   sudo docker volume create ${COMPOSE_PROJECT_NAME}_filestore
   sudo docker volume create ${COMPOSE_PROJECT_NAME}_db
   ```
3. SEEK's database setup
   
   Edit `./services/seek/ldh-deployment/docker-compose.env`. Replace `<root-password>` and `<db-password>` with a password. You can use openssl command to generate a password and save in the docker-compose.env file.
   ```bash
   cat docker-compose.env.tpl | sed "s|<db-password>|$(openssl rand -base64 21)|" | sed "s|<root-password>|$(openssl rand -base64 21)|" > docker-compose.env
   ```
4. Initial launch & admin setup
   1. Launch SEEK
      ```bash
      sudo docker compose -f services/seek/ldh-deployment/docker-compose.yml --env-file ./.env up
      ```
   2. Set up server admin account 
      1. Navigate to http://localhost:8001
      2. Create a first account (the first user will then automatically be assigned as a server admin by default). 
      3. Log in and create your profile
   3. Custom configuration (in Browser)
      1. Enable Features (Server admin > Enable/disable features):
         - Tick "Omniauth enabled"
         - Tick "Programmes enabled"
         - Tick "Workflows enabled"
         - Tick "GA4GH TRS API enabled"
      2. (optional) Branding and Customization (Server admin > Branding and customization):
      3. Site Settings (Server admin > Settings):
         - Site base Hostname: http://localhost:8001
   4. Generate API token
      1. In the SEEK UI, go to My Profile > Actions > API Tokens > New API Token
      2. Give it a title and create the token
      3. Copy/save the API token
      4. Update API Config
         - Paste this token into ./services/api/digitaltwins-api/configs.ini under the [seek] section:
         ```ini
         [seek]
         api_token=<your_token>
         ```
   5. Enable "git" support (Command Line)
      1. Enter the SEEK container
         ```bash
         sudo docker exec -it <container_name> bash
         ```
         Note: `<container_name>` might be something like `seek-seek-1`
      2. Start the Rails console
          ```bash
         bundle exec rails console
         ```
      3. In the rails console:
         ```ruby
         Seek::Config.git_support_enabled = true
         Seek::Config.save
         exit
         ```
      4. Exit the container
         
## 6. Launch the entire platform

Run the following command from the repository root to start all services:

```bash
sudo docker compose up -d
```


## 7. Service access & default credentials

Once deployed, the following services are available:

| Service | Port | Username | Password | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Portal** | 80 | `admin` | `admin` | Main entry point |
| **SEEK** | 8001 | `<Created User>` | `<Created Pass>` | Catalogue Service |
| **Airflow** | 8002 | `admin` | `admin` | Workflow Management |
| **Postgres** | 8003 | — | — | Connect via pgAdmin |
| **pgAdmin** | 8004 | *Check .env* | *Check .env* | Database GUI |
| **JupyterLab** | 8008 | — | `admin` | (Token/Password) |
| **Keycloak** | 8009 | `admin` | `admin` | IAM Service |
| **REST API** | 8010 | — | — | Docs at `http://{IP}:8010/docs` |
| **Minio** | 8012 | `minioadmin` | `minioadmin` | Web GUI (API on 8011) |
