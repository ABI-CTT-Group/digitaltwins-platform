# build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY . .

RUN corepack enable && corepack prepare yarn@stable --activate

RUN yarn install


RUN yarn build

# runtime stage
FROM nginx:stable-alpine

COPY --from=builder /app/build /usr/share/nginx/html

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY entry.sh /entry.sh
RUN chmod +x /entry.sh

EXPOSE 80
ENTRYPOINT ["/entry.sh"]
