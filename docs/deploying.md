# Deploying the DigitalTWINS Platform

Use the [deployment repository](https://github.com/ABI-CTT-Group/digitaltwins-platform) to deploy the platform or see the platform services section for individual deployment for each service.

1. Clone the repository from GitHub to the deployment server
    1. Run: `git clone https://github.com/ABI-CTT-Group/digitaltwins-platform.git`
2. Navigate to the repository
    1. Run: `cd digitaltwins-platform`
3. Create docker volumes and networks
4. Set up the environment and configuration files
    1. Copy `.env.template` to `.env`
    2. Copy `./services/api/digitaltwins-api/config.ini.template` to `./services/api/digitaltwins-api/config.ini`
    3. (optional) Place the Keycloak realm file exported from an existing deployment in `./service/keycloak/import/digitaltwins-realm.json`
5. Initialise the IAM service (keycloak)
6. Configure keycloak for the platform use
    * **Method 1: manual configuration**
        1. Start keycloak: `sudo docker compose up keycloak`
        2. todo
        3. Stop Keycloak: `Ctr + C`
    * **Method 2: auto configuration from an existing Realm**
        1. (optional) exporting your realm from an existing deployment
            1. From the existing Keycloak deployment
            2. Stop your existing keycloak
            3. Export your Keycloak realm: `sudo docker compose run --rm keycloak export --realm <YOUR_REALM> --dir /opt/keycloak/data/export --users realm_file`
            4. `<YOUR_REALM>`: set it to digitaltwins in our case
            5. Copy export files to your local machine: `sudo docker compose run --rm --user root --entrypoint /bin/sh -v $(pwd)/export:/backup keycloak -c "cp -r /opt/keycloak/data/export/* /backup/"`
            6. A realm file will be created in your host, e.g. `$(pwd)/export/digitaltwins-realm.json`
        2. Place the realm file (exported from an existing deployment) in `./service/keycloak/import/digitaltwins-realm.json`
7. Initialise the workflow service (airflow)
    1. Edit `./env`
        1. Set `AIRFLOW_UID` to your user id. To get your user id, run: `echo $(id -u)`
        2. (optional) change the default username and password
            1. `_AIRFLOW_WWW_USER_USERNAME=admin`
            2. `_AIRFLOW_WWW_USER_PASSWORD=admin`
    2. Initialize airflow.cfg: `sudo docker compose run airflow-cli airflow config list`
    3. Enable CORS. edit airflow.cfg
        1. `[api]`
        2. `access_control_allow_headers = origin, content-type, accept`
        3. `access_control_allow_methods = POST, GET, OPTIONS, DELETE`
        4. `access_control_allow_origins =`
    4. Initialize the airflow database. Run: `sudo docker compose up airflow-init`
8. Initialise the catalogue service (SEEK)
    1. Fix external submodule error in `./services/seek/ldh-deployment/docker-compose.yml`
        1. Replace all `${PWD}/` with `./`
    2. Create external volumes
        1. Run: `source .env`
        2. Run: `sudo docker volume create ${COMPOSE_PROJECT_NAME}_filestore`
        3. Run: `sudo docker volume create ${COMPOSE_PROJECT_NAME}_db`
    3. Set database configurations
        1. Copy `./services/seek/ldh-deployment/docker-compose.env.tpl` to `./services/seek/ldh-deployment/docker-compose.env`
        2. Edit `./services/seek/ldh-deployment/docker-compose.env`
            1. Replace `<root-password>` and `<db-password>` with a password. You can use openssl command to generate a password and save in the docker-compose.env file.
            2. Run: `cat docker-compose.env.tpl | sed "s|<db-password>|$(openssl rand -base64 21)|" | sed "s|<root-password>|$(openssl rand -base64 21)|" > docker-compose.env`
    4. Launch SEEK for initial setup: `sudo docker compose -f services/seek/ldh-deployment/docker-compose.yml --env-file ./.env up`
    5. Setting up server admin account
        1. From your browser, access: `http://localhost:8001`
        2. Register an account (first user will be set as a server admin by default)
        3. Login and you will be asked to create your profile
    6. Custom configurations
        1. Server admin > Enable/disable features
            1. Tick "Omniauth enabled"
            2. Tick "Programmes enabled"
            3. Tick "Workflows enabled"
            4. Tick "GA4GH TRS API enabled"
        2. Server admin > Branding and customization
            1. Name: DigitalTWINS AI Platform
            2. Link: [http://130.216.216.26/](http://130.216.216.26/) (public demo)
            3. Instance administrator name: Auckland bioengineering institute
            4. Instance administrator link: https://www.auckland.ac.nz/en/abi.html
            5. Header logo image enabled
                1. Upload a header logo image file
                2. Header image alternative title: Auckland bioengineering institute
        3. Server admin > settings
            1. Site base Hostname: `http://localhost:8001`
            2. (TBC) "Registration disabled"
        4. Enable "git" support for workflow creation
            1. Jump into seek container: `sudo docker exec <container_name> bash`
            2. Where `<container_name>` might be something like "seek-seek-1"
            3. Start rails console: `bundle exec rails console`
            4. Check whether git support is enabled: `Seek::Config.git_support_enabled`
            5. Enable git support: `Seek::Config.git_support_enabled = true`
            6. Save changes: `Seek::Config.save`
            7. Exit rails console: `exit`
            8. Exit SEEK container: `exit`
            9. Restart SEEK: `sudo docker compose restart <seek_service_name>`
    7. Create an user API token
        1. From top-right: My Profile/Actions/API Tokens/New API Token
        2. Title: `<any_titile>`
        3. Copy/save the API token: `5uePEmE__sEAar-ygtSUXYiHkBK8J1h2sj-eA330`
        4. You will need to paste the SEEK API token into the REST API service configuration file: `./services/api/digitaltwins-api/config.ini`
            1. under in `[seek]` section
            2. `api_token=<your_token>`
9. Launch the entire platform with docker compose
    1. From the repository root, run: `sudo docker compose up -d`
10. Done. You can now access the portal or other services. See below for default login details for some of the web services of the platform
    * **Portal:**
        * Port: 80
        * Username: admin
        * Password: admin
    * **SEEK:**
        * Port: 8001
        * Username: `<your_seek_username>`
        * Password: `<your_seek_password>`
    * **Airflow:**
        * Port: 8002
        * Username: admin
        * Password: admin
    * **Postgres:**
        * Port: 8003
        * You can connect to the postgres from pdAdmin
        * Port: 8004
        * Username: `<check your .env>`
        * Password: `<check your .env>`
    * **JupyterLab:**
        * Port: 8008
        * password/token: admin
    * **Keycloak:**
        * Port: 8009
        * Username: admin
        * Password: admin
    * **REST API:**
        * Port: 8010
        * API docs: `http://{IP}:8010/docs`
    * **Minio:**
        * API: 8011
        * Web GUI: 8012
        * Username: minioadmin
        * Password: minioadmin
