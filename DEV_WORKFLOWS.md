# Developer workflows

This file is for local developer and agent workflow notes that are useful while
working on the repo, but are not part of the project runtime or deployment
contract.

## Codex command setup

The Codex binary may already exist inside an installed OpenAI extension bundle,
while still being unavailable as a shell command because that extension path is
not on `PATH`. Adding a symlink in `~/.local/bin` makes the existing binary
discoverable from normal terminal sessions, assuming `~/.local/bin` is on
`PATH`.

This does not install a new Codex. It enables commands like `codex mcp list`
without requiring the full extension path.

```bash
ln -sf ~/.vscode/extensions/openai.chatgpt-26.422.21459-darwin-arm64/bin/macos-aarch64/codex ~/.local/bin/codex
hash -r
codex mcp list
```

Why `hash -r`: shells cache command lookup results. If `codex` failed before
the symlink existed, `hash -r` clears that cache so the shell checks
`~/.local/bin` again.

## Ogham shared memory

Ogham is the shared-memory store for Codex sessions. In the local setup, the
database is the `local-pgvector` Docker container, which exposes
Postgres/pgvector on `localhost:5432` with database `ogham`, user `ogham`, and
the local development password from `~/.ogham/config.env`.

Use shared memory selectively for durable context that should survive across
Codex sessions: project conventions, environment setup notes, recurring
pitfalls, and decisions that future agents should remember. Avoid storing
secrets, one-off test artifacts, transient debugging output, or details that are
already obvious from the repository.

Check the runtime before relying on memory:

```bash
ogham config
ogham health
ollama list
```

Search existing memory before adding new context:

```bash
ogham search --json "what you need to remember or recover"
ogham list --json --limit 10
```

Store a concise memory only when it will help future sessions:

```bash
ogham store --json "durable memory text to store"
```

If the configured embedding model is missing, pull the model shown by
`ogham config`. For the local Ollama setup, that commonly looks like:

```bash
ollama pull embeddinggemma
```

If the local `ogham` executable is missing the Postgres extra and fails with
`ModuleNotFoundError: No module named 'psycopg'`, reinstall the CLI with the
Postgres extra:

```bash
uv tool install --force 'ogham-mcp[postgres]'
```
