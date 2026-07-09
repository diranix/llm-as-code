# Changelog

## 0.1.0 - 2026-07-09

First packaged release of the reference engine.

- Engine as an installable package: `pipx install lac-engine`, global `lac` command.
- App root anchor: the engine finds `.lac/llm_compose.yaml` in the current directory (or the directory given as an argument); all compose paths resolve relative to the app root. No absolute paths.
- Compose loader with a strict parser: schema_version gate, unknown-key rejection, clear errors for a missing compose or commands module.
- Context assembler: law loads in trust order L1 -> L2 -> L3, always in context.
- Commands module loaded per app by explicit file path (`commands_<app>.py`, TOOLS + COMMANDS registry).
- Two roads to the same code: canonical `!commands` intercepted before the model (zero tokens); free-form language through tool calling into the same functions.
- Providers behind `adapter.send()`: Anthropic (raw HTTP, prompt caching on system, usage line, API key from env only) and Ollama.
- Published on PyPI as `lac-engine`.
- SPEC.md: the LaC methodology (v0.2) - definition, philosophy, compose schema, levels, commands, security model, memory hierarchy.
- Adapter hardened: request timeout, readable api errors instead of tracebacks, soft recovery (an API failure prints one line and rolls the conversation back; the REPL survives).
- Ollama path reconciled with the agentic loop: messages and tools translate both ways; the loop no longer sees the provider.
- Known debt: drift metrics (M3) not started; no tests or CI yet.
