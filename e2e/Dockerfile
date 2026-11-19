FROM node:24-slim
WORKDIR /app
COPY support/tmdb-server.ts ./support/tmdb-server.ts
COPY --from=fixture person.json /app/fixture.json
ENV LUMIERE_TEST_FIXTURE_PATH=/app/fixture.json
USER node
EXPOSE 9000
CMD ["node", "support/tmdb-server.ts"]
