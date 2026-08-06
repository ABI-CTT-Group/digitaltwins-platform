# Keycloak Login Theme: `keycloak-login-theme`

This theme customizes the Keycloak login page to look similar to the DigitalTWINS frontend login style.

## Folder structure

```text
keycloak-login-theme/
  login/
    theme.properties
    login.ftl
    resources/
      css/
        styles.css
```

## Deploy to Keycloak

### Option A: Docker compose / container mount

Mount the theme folder into Keycloak container:

```yaml
services:
  keycloak:
    image: quay.io/keycloak/keycloak:latest
    volumes:
      - ./keycloak-login-theme:/opt/keycloak/themes/keycloak-login-theme
```

Then restart Keycloak.

### Option B: Copy into running container

```bash
docker cp ./keycloak-login-theme <keycloak-container-name>:/opt/keycloak/themes/keycloak-login-theme
```

Then restart Keycloak.

## Configure in Realm

1. Open Keycloak Admin Console.
2. Go to **Realm Settings** → **Themes**.
3. Set **Login Theme** to: `keycloak-login-theme`.
4. Click **Save**.

## Client settings to verify

For your client (e.g. `api` or `portal-frontend`):

1. Go to **Clients** → `<client>`.
2. Ensure **Valid Redirect URIs** contains your app URLs.
3. Ensure **Web Origins** contains your app origin.
4. If using browser login, ensure standard flow is enabled.

## Cache note

If you do not see changes:
- hard refresh browser
- restart Keycloak container
- clear theme cache (or run Keycloak with disabled cache in dev):

```bash
kc.sh start-dev --spi-theme-cache-themes=false --spi-theme-cache-templates=false
```
