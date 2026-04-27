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
