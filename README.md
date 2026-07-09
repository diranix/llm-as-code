# LaC - LLM as Code

LaC is a protocol for building LLM applications the way IaC builds infrastructure: behavior is declared in versioned artifacts, not improvised in prompts. An application is a folder of plain files - a compose declaration, law files with explicit authority levels, and a commands module. The engine is generic and knows nothing about any particular application.

This repository holds the reference engine and, eventually, the LaC specification. The engine is intentionally small: a compose loader with a strict parser, a context assembler that loads law in trust order (L1 then L2 then L3), a REPL, and an agentic loop where free-form language and canonical `!commands` are two roads into the same code.

**Status: pre-release.** The spec is the canon; this engine tracks it through milestones M0-M3 (loader, retrieval commands, write perimeter, drift metrics). APIs and the compose schema will change.

## Core ideas

- **Levels are roles.** L1 (admin) and L2 (dev) files carry behavior and load always; L3 (user data) is content, never instructions.
- **Two roads, one code.** Canonical `!commands` bypass the model entirely (zero tokens); free-form requests reach the same functions through tool calling. The model interprets and narrates; code executes.
- **Perimeter in code, not in prose.** Effects on disk are the engine's job. A wrong action must be survivable.

## Quick start

```
pipx install lac-engine
cd your-app
lac
```

An application folder looks like:

```
your-app/
  .lac/
    llm_compose.yaml    # the anchor: all paths resolve relative to the app root
    law/                # L1/L2 law files
    souls/              # personas (L2)
  commands_<app>.py     # the app's command module (TOOLS + COMMANDS registry)
  <memory folders>      # L3 content
```

The engine finds `.lac/llm_compose.yaml` in the current directory (or in the directory passed as the first argument) and resolves every path in the compose against that root. No absolute paths anywhere.

Providers: Anthropic (raw HTTP, prompt caching, `ANTHROPIC_API_KEY` from env only) and Ollama for local models. The vendor surface lives in one function, `adapter.send()`.

## First application

[Grimoire](https://github.com/diranix/grimoire) - a personal memory system and the first LaC application. Its earlier implementation runs the same protocol on Claude Code, with the perimeter enforced by harness permissions instead of engine code: one law, two hosts.

## License

TBD before first tagged release.
