FROM liquibase/liquibase:4.33.0

# lpm is a CLI tool for installing Liquibase extensions — never used at runtime.
# Removing it eliminates CVE-2024-24790 and CVE-2025-68121 in its bundled Go stdlib.
# Must switch to root temporarily — the base image runs as a non-root user.
USER root
RUN rm -f /liquibase/bin/lpm
USER liquibase

# Bake the changelog files into the image so the ECS task needs no volume
# mounts or S3 access at runtime. The image is rebuilt and pushed on every
# commit that touches db/**, so the task definition always runs the changelogs
# that match the application code being deployed.
COPY changelog/ /liquibase/changelog/

# Default command — runs all pending changesets. The ECS task definition sets
# LIQUIBASE_COMMAND_URL / USERNAME / PASSWORD via Secrets Manager injection,
# so no credentials are baked into the image.
CMD ["--changelog-file=changelog/db.changelog-master.yaml", "update"]
