# Deploying the DigitalTWINS Platform

This document describes how to deploy the DigitalTWINS Platform from the [deployment repository](https://github.com/ABI-CTT-Group/digitaltwins-platform). It provides a concise quick-start and expanded steps for each service (Keycloak, Airflow, SEEK, etc.), configuration tips, default credentials, and common troubleshooting commands.

---

## 1. Clone the Repository

Begin by cloning the recursive repository to your local machine:

```bash
git clone --recursive https://github.com/ABI-CTT-Group/digitaltwins-platform.git
cd digitaltwins-platform
```

## 2. Environment Configuration

Set up the necessary environment variables and configuration files for all components.

### 2.1 Main Environment File

First, copy the template `.env` file to create your local `.env`:

```bash
cp .env.template .env
```

Set the following variables in your new `.env` file:

- **Public URLs & Keycloak integration**
  - `PORTAL_BACKEND_HOST`: Your host machine IP address (or domain) for the portal backend. 
    > [!TIP]
    > You can find your host IP address by running `curl ifconfig.me` on a Linux terminal.
  - **Four settings must name the EXACT same public address** (including the `/auth` path) to prevent issuer-mismatch failures:
    - `KC_HOSTNAME`
    - `KEYCLOAK_PUBLIC_URL`
    - `PORTAL_KEYCLOAK_BASE_URL`
    - `ORTHANC_KEYCLOAK_URL`

- **Workflow Service (Airflow)**
  - `AIRFLOW_UID`: Your local user ID. Replace `<YOUR_USER_ID>`.
    > [!TIP]
    > Run `echo $(id -u)` to find your user ID.

- **JupyterHub**
  - `JUPYTERHUB_CRYPT_KEY`: Replace `<YOUR_JUPYTERHUB_CRYPT_KEY>`.
    > [!TIP]
    > Generate a secure random key using the following command:
    > ```bash
    > openssl rand -hex 32
    > ```

### 2.2 SEEK Configuration

Copy the SEEK deployment configuration template:

```bash
cp ./services/seek/ldh-deployment/docker-compose.env.tpl ./services/seek/ldh-deployment/docker-compose.env
```

## 3. Initialise the IAM Service (Keycloak)

> [!NOTE]
> Choose **one** of the following methods to configure Keycloak based on whether you are doing a fresh manual setup or importing from an existing configuration.

### Method 1: Manual Configuration

1. Start Keycloak: 
   ```bash
   sudo docker compose up -d keycloak
   ```
2. *[TODO: Insert manual configuration steps here]*
3. Stop Keycloak: 
   ```bash
   sudo docker compose down
   ```

### Method 2: Auto-Configuration from an Existing Realm

**Step A. Export Realm from an Existing Deployment**

1. Run the export command:
   ```bash
   sudo docker compose run --rm keycloak export --realm <YOUR_REALM> --dir /opt/keycloak/data/export --users realm_file
   ```
2. Copy the export files to your host machine:
   ```bash
   sudo docker compose run --rm --user root --entrypoint /bin/sh -v $(pwd)/export:/backup keycloak -c "cp -r /opt/keycloak/data/export/* /backup/"
   ```
   > [!NOTE]
   > A realm file will be created on your host, e.g., `$(pwd)/export/digitaltwins-realm.json`.

**Step B. Import Realm to the new deployment**

1. Place the exported realm file in the correct directory: `./services/keycloak/import/digitaltwins-realm.json`.
2. Start Keycloak with the import option:
   ```bash
   sudo docker compose up -d keycloak
   ```
3. Retrieve your Keycloak client secret:
   1. Log in to the Keycloak admin console at `http://localhost:8009`. *(Check your username and password in the `.env` file if you changed them; defaults are `admin`/`admin`)*.
   2. Navigate to **Manage realm** > `digitaltwins` > **Clients** > choose `api` from the client list > **Credentials** > copy the **Client Secret**.
   3. Update the `<YOUR_KEYCLOAK_CLIENT_SECRET>` placeholder in your `.env` file with the copied client secret.

## 4. Initialise Workflow Service (Airflow)

1. Initialize `airflow.cfg` by running the CLI tool:
   ```bash
   sudo docker compose run airflow-cli airflow config list
   ```

2. Enable CORS in Airflow. Edit `./services/airflow/config/airflow.cfg` and update the `[api]` section:
   ```ini
   [api]
   access_control_allow_headers = origin, content-type, accept
   access_control_allow_methods = POST, GET, OPTIONS, DELETE
   access_control_allow_origins = 
   ```

3. Initialize the Airflow database:
   ```bash
   sudo docker compose up airflow-init
   ```

## 5. Initialise Catalogue Service (SEEK)

### 5.1 SEEK's Database Setup

Edit `./services/seek/ldh-deployment/docker-compose.env` and replace `<root-password>` and `<db-password>` with secure passwords. 

> [!TIP]
> Optionally, you can use the `openssl` command to generate random secure passwords and save them automatically directly to the `.env` file:
> ```bash
> cat ./services/seek/ldh-deployment/docker-compose.env | sed "s|<db-password>|$(openssl rand -base64 21)|" | sed "s|<root-password>|$(openssl rand -base64 21)|" > ./services/seek/ldh-deployment/docker-compose.env
> ```

### 5.2 Initial Launch & Admin Setup

1. **Launch SEEK**:
   ```bash
   sudo docker compose -f services/seek/ldh-deployment/docker-compose.yml --env-file ./.env up
   ```

2. **Set up Server Admin Account**:
   1. Navigate to `http://localhost:8001`.
   2. Create your first account (the first registered user is automatically assigned as a server admin by default).
   3. Log in and create your profile.

3. **Custom Configuration (Browser)**:
   - **Enable Features** (Go to *Server admin > Enable/disable features*):
     - [x] Omniauth enabled
     - [x] Programmes enabled
     - [x] Workflows enabled
     - [x] GA4GH TRS API enabled
   - *(Optional)* **Branding and Customization** (Go to *Server admin > Branding and customization*).
   - **Site Settings** (Go to *Server admin > Settings*):
     - set **Site base Hostname** to `http://localhost:8001`.

4. **Generate API Token**:
   1. In the SEEK UI, navigate to **My Profile > Actions > API Tokens > New API Token**.
   2. Provide a title and create the token.
   3. Copy and save the generated API token.
   4. Update the `<YOUR_SEEK_API_TOKEN>` placeholder in your `.env` file with the copied API token.

5. **Enable "Git" Support (Command Line)**:
   1. Enter the SEEK container:
      ```bash
      sudo docker exec -it <container_name> bash
      ```
      > [!NOTE]
      > `<container_name>` might be something analogous to `seek-seek-1`.
   2. Start the Rails console:
      ```bash
      bundle exec rails console
      ```
   3. In the Rails console, enable Git support and exit:
      ```ruby
      Seek::Config.git_support_enabled = true
      # Seek::Config.save
      exit
      ```
   4. Exit the container terminal.

## 6. Build all images

```bash
sudo docker compose build
```

## 7. Launch the Entire Platform

Run the following command from the repository root to start all services in detached mode:

```bash
sudo docker compose up -d
```

## 8. Service Access & Default Credentials

Once successfully deployed, the following services and default credentials are available:

| Service            | URL Path | Username | Password | Notes                                     |
|:-------------------|:---------| :--- | :--- |:------------------------------------------|
| **Portal**         | `/`      | *Via Keycloak* | — | Main entry point                          |
| **SEEK**           | `/seek/` | *Via Keycloak* or `<Created User>` | `<Created Pass>` | Catalogue Service                         |
| **Airflow**        | `/airflow/` | `admin` | `admin` | Workflow Management                       |
| **pgAdmin**        | `/pgadmin/` | *Check `.env`* | *Check `.env`* | Database GUI                              |
| **Keycloak**       | `/auth/` | `admin` | `admin` | IAM Service (Admin Console)               |
| **REST API**       | `/digitaltwins-api/` | — | — | Docs at `http://{IP}/digitaltwins-api/docs` |
| **Minio**          | `/minio/` | `minioadmin` | `minioadmin` | Storage Web GUI                           |
| **Orthanc 1**      | `/orthanc-1/` | *Via Keycloak* | — | PACS Service 1                            |
| **Orthanc 2**      | `/orthanc-2/` | *Via Keycloak* | — | PACS Service 2                            |
| **JupyterHub**     | `/jupyter/` | *Via Keycloak* | — | Notebook Service                          |
| **HAPI FHIR**      | `/fhir/` | — | — | EHR Service REST API                      |
| **Postgres**       | `N/A`    | — | — | Internal Database (Connect via pgAdmin)   |