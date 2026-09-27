FROM ghcr.io/cnoe-io/backstage-app:9232d633b2698fffa6d0a73b715e06640d170162@sha256:960dcd8b68ba8fed3685727c63b5221e5f95392694d887a12e14d792834636de
USER root
WORKDIR /app
# Add only the missing native backend; the pinned image supplies its dependencies.
RUN curl -fsSL https://registry.npmjs.org/@backstage/plugin-permission-backend/-/plugin-permission-backend-0.5.46.tgz -o /tmp/permission.tgz \
    && echo '3efbadaf99879d0ff25fdd608e5fdd9c079c579cfb8d362fd478398031de46be  /tmp/permission.tgz' | sha256sum -c - \
    && mkdir node_modules/@backstage/plugin-permission-backend \
    && tar -xzf /tmp/permission.tgz --strip-components=1 -C node_modules/@backstage/plugin-permission-backend \
    && rm /tmp/permission.tgz
COPY . /app/platform-permissions/
RUN node platform-permissions/install.cjs && node --test platform-permissions/policy.test.cjs
USER node
