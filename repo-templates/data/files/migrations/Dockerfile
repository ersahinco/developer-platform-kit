# syntax=docker/dockerfile:1
#
# Confirm the tag against the Liquibase release you tested, then pin it by digest
# before the first production apply.
ARG LIQUIBASE_VERSION=4.33
FROM liquibase/liquibase:${LIQUIBASE_VERSION}

USER liquibase:liquibase
WORKDIR /liquibase

COPY changelog ./changelog
COPY liquibase.properties ./liquibase.properties

# The lane passes the command, so starting the image changes nothing by itself.
ENTRYPOINT ["/liquibase/liquibase"]
CMD ["--help"]
