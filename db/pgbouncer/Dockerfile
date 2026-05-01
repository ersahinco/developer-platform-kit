ARG PGBOUNCER_TAG=v1.25.1-p0

FROM edoburu/pgbouncer:${PGBOUNCER_TAG}

USER root

# Keep the upstream PgBouncer release while picking up Alpine security fixes.
# hadolint ignore=DL3018
RUN apk upgrade --no-cache libcrypto3 libssl3

USER postgres
