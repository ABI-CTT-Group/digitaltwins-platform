
FROM node:20-alpine

LABEL maintainer="LinkunGao <gaolinkun123@gmail.com>"

WORKDIR /app

COPY . .

RUN corepack enable && corepack prepare yarn@stable --activate

RUN yarn install

ARG VITE_APP_API_URL
ENV VITE_APP_API_URL=$VITE_APP_API_URL

RUN yarn build

ENV HOST=0.0.0.0
ENV PORT=80

EXPOSE 80

CMD ["yarn", "preview"]
