FROM ghcr.io/astral-sh/uv:0.11.8 AS uv

FROM python:3.14-bookworm

ENV PATH="/home/vscode/.local/bin:/usr/local/go/bin:/usr/local/bin:${PATH}" \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/workspaces/aws-sdlc-containers/.venv

COPY --from=uv /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        jq \
        make \
        sudo \
        tar \
        unzip \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash vscode \
    && echo "vscode ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode

RUN for tool in bash curl git jq make tar unzip; do command -v "$tool"; done

RUN python -m pip install --no-cache-dir \
        checkov==3.2.526 \
        pre-commit==4.6.0

ARG ACTIONLINT_VERSION=1.7.12
ARG GO_VERSION=1.26.2
ARG GITLEAKS_VERSION=8.30.1
ARG HADOLINT_VERSION=2.14.0
ARG LYCHEE_VERSION=0.24.1
ARG NODE_VERSION=24.15.0
ARG NPM_VERSION=11.13.0
ARG TFLINT_VERSION=0.62.0
ARG TYPESCRIPT_VERSION=6.0.3

COPY install-tools.sh /tmp/install-tools.sh
RUN bash /tmp/install-tools.sh \
    && rm /tmp/install-tools.sh

USER vscode
