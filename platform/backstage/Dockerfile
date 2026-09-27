# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c AS base
USER root
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 build-essential git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

FROM base AS upstream
ADD --checksum=sha256:2302aeb71fb062f0886c6d0c3734789d7a15aeb391006a30c20042d879b52e63 \
    https://codeload.github.com/cnoe-io/backstage-app/tar.gz/6a5087c2fb6aeccdee5f2b5665f7d93cb89640b3 /tmp/backstage.tgz
RUN tar -xzf /tmp/backstage.tgz --strip-components=1 -C /app && rm /tmp/backstage.tgz

FROM upstream AS build
COPY source.patch /tmp/source.patch
RUN git apply /tmp/source.patch
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn,sharing=locked \
    yarn install --frozen-lockfile --network-timeout 600000
COPY . /app/platform/
RUN yarn tsc && yarn --cwd packages/backend build
RUN mkdir packages/backend/dist/skeleton packages/backend/dist/bundle \
    && tar xzf packages/backend/dist/skeleton.tar.gz -C packages/backend/dist/skeleton \
    && tar xzf packages/backend/dist/bundle.tar.gz -C packages/backend/dist/bundle

FROM base AS runtime
COPY --from=build /app/yarn.lock /app/package.json /app/packages/backend/dist/skeleton/ ./
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn,sharing=locked \
    yarn install --frozen-lockfile --production --network-timeout 600000
COPY --from=build --chown=node:node /app/packages/backend/dist/bundle/ ./
COPY --from=build /app/README.md /app/README.cnoe.md
COPY --chown=node:node . /app/platform/
ENV NODE_ENV=production
ENV NODE_OPTIONS=--no-node-snapshot
RUN node --test platform/policy.test.cjs platform/entra.test.cjs
USER node
CMD ["node", "packages/backend", "--config", "platform/entra.yaml"]
