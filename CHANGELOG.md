# Changelog

## 0.1.2 - 2026-07-13

Full audit of the engine: correctness, portability, and readability - behavior unchanged unless noted.

- Explicit utf-8 on every file the engine reads or writes (compose, context files, fsjail writes); behavior no longer depends on the OS default encoding.
- Compose loader: clean `compose error` messages for bad yaml, a non-mapping file, and missing required keys (app, paths, llm, context, context levels) instead of raw tracebacks.
- Unknown llm provider is refused at boot, for the head and the worker both; adapter's send() dispatches through a PROVIDERS table and raises ApiError instead of killing the session mid-turn.
- `llm.max_tokens` is a compose key (default 2048) instead of a hardcoded constant; applies to the anthropic and mistral providers.
- http_post survives a non-JSON response body: ApiError instead of an uncaught exception.
- Ctrl-C during a command no longer kills the REPL; the command returns "interrupted by the user" and the session continues.
- engine.py split into named phases (load_compose, load_commands, build_context, run_command, repl, main) - same flow, readable units.
- to_ollama_tools renamed to_openai_tools - mistral sends the same shape.

## 0.1.1 - 2026-07-09

Two boot-and-read hardenings, found by review and verified live.

- Boot refuses a broken law: a missing L1/L2 context file stops the engine (`law incomplete - refusing to start`); the MISSING list now names each file's level. Missing L3 stays a warning.
- Read jail in the commands contract: an app's load command must resolve paths with realpath and refuse anything outside the memory root (`../` escape closed). Applied in the Grimoire app (lives with the app, not in this package); read-side counterpart of the M2 write fsjail.

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
