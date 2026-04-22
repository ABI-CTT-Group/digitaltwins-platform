# build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY . .

ARG VITE_KEYCLOAK_URL
ARG VITE_KEYCLOAK_REALM
ARG VITE_KEYCLOAK_CLIENT_ID
ENV VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL
ENV VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM
ENV VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID

RUN corepack enable && corepack prepare yarn@stable --activate

RUN yarn install

RUN yarn build

# runtime stage
FROM nginx:stable-alpine

COPY --from=builder /app/build /usr/share/nginx/html

# Copy nginx templates (entry.sh picks HTTP or SSL at runtime)
COPY nginx.http.conf.template /etc/nginx/conf.d/nginx.http.conf.template
COPY nginx.ssl.conf.template /etc/nginx/conf.d/nginx.ssl.conf.template

# Create directory for dynamically generated plugin nginx configs
RUN mkdir -p /etc/nginx/conf.d/plugins

COPY entry.sh /entry.sh
RUN chmod +x /entry.sh

EXPOSE 80 443
ENTRYPOINT ["/entry.sh"]
