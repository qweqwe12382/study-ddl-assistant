FROM node:24-alpine AS build

WORKDIR /src/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
COPY online/prepare-frontend.mjs /tmp/prepare-frontend.mjs
RUN node /tmp/prepare-frontend.mjs /src/frontend/src/App.vue

ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM caddy:2-alpine

COPY --from=build /src/frontend/dist /srv
COPY online/Caddyfile /etc/caddy/Caddyfile

EXPOSE 80 443
