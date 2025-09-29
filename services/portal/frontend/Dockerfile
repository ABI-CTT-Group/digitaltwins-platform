
FROM node:20-alpine

LABEL maintainer="LinkunGao <gaolinkun123@gmail.com>"

WORKDIR /app

COPY . .

RUN corepack enable && corepack prepare yarn@stable --activate

RUN yarn install

ARG VITE_PORTAL_API_URL
ARG VITE_PORTAL_PORT

RUN echo "Build ARG VITE_APP_API_URL = $VITE_APP_API_URL"

ENV VITE_PORTAL_API_URL=$VITE_PORTAL_API_URL
ENV VITE_PORTAL_PORT=$VITE_PORTAL_PORT


RUN yarn build

ENV HOST=0.0.0.0
ENV PORT=80

EXPOSE 80

CMD ["yarn", "preview"]

