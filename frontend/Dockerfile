FROM node:24-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY app.json tsconfig.json ./
COPY src ./src
COPY public ./public
ENV EXPO_NO_DOTENV=1 EXPO_NO_TELEMETRY=1
RUN npm run export:web

FROM caddy:2-alpine AS runtime
COPY --from=build /app/dist /srv
COPY --from=ingress Caddyfile /etc/caddy/Caddyfile
EXPOSE 8080
