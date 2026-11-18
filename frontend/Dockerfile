# syntax=docker/dockerfile:1
FROM node:26-bookworm-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
# An empty base URL makes browser requests relative to the deployment origin.
ENV EXPO_PUBLIC_API_URL="" \
    CI=1
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.30-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist/ /usr/share/nginx/html/
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
# Skip configuration-mutating entrypoint scripts; the image works read-only.
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
