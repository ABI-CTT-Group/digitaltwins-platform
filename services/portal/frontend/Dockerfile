# build stage
FROM node:20-alpine AS builder

WORKDIR /app

# yarn.lock in this repo is Yarn 1 (classic) format. This used to say
# `yarn@stable`, i.e. Yarn 4, which silently migrated the lockfile to v4 on every
# single build — so the lockfile pinned nothing, and the build was only
# reproducible by accident. Pin to the version the lockfile is actually written
# for; --frozen-lockfile then makes an out-of-date lockfile a build failure
# instead of a silent rewrite.
RUN corepack enable && corepack prepare yarn@1.22.22 --activate

# Dependency manifests first, so editing source (or an nginx template) does not
# invalidate the yarn install layer. This used to be a single `COPY . .` ahead of
# `yarn install`, which meant changing one line in an nginx config re-ran the
# whole dependency install and SPA build.
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

COPY . .

ARG VITE_KEYCLOAK_URL
ARG VITE_KEYCLOAK_REALM
ARG VITE_KEYCLOAK_CLIENT_ID
ENV VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL
ENV VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM
ENV VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID

RUN yarn build

# runtime stage
FROM nginx:stable-alpine

COPY --from=builder /app/build /usr/share/nginx/html

# The official image's entrypoint runs envsubst over /etc/nginx/templates/*.template
# and writes the result to /etc/nginx/conf.d/. That replaces the hand-written
# entry.sh, whose only jobs were envsubst and choosing between an HTTP and an SSL
# template — and TLS now terminates at the platform gateway, so only HTTP is left.
# NGINX_ENVSUBST_FILTER (set in docker-compose.yml) restricts substitution to the
# three vars the template actually uses, so nginx's own $host / $scheme survive.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# portal-backend writes plugin route configs here through the nginx_plugin_configs
# volume. nginx.conf's own `include conf.d/*.conf` does not match a subdirectory,
# so these are pulled in solely by the explicit include inside the server block.
RUN mkdir -p /etc/nginx/conf.d/plugins

EXPOSE 80
