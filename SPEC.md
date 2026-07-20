# LaC - LLM as Code

## Methodology v0.2

---

## 1. What LaC is

LaC (LLM as Code) is a protocol for describing the BEHAVIOR of an LLM application in files: versioned, releasable, locked - like infrastructure code.

The problem it answers: LLM applications today are built as wrappers (a chat window, a host, a database), and the model's behavior is smeared across them - a piece in the system prompt, a piece in the host's code, a piece in the developer's head. So behavior cannot be versioned or rolled back as an artifact; changing the host loses it; the same prose drifts on a weaker or newer model, and nobody measures how much; the user cannot tell where "the model CAN" ends and "the model is ALLOWED" begins.

Infrastructure has been through this and found the answer: Infrastructure as Code. A server is described by a declaration, the declaration is versioned, an executor (Terraform, Docker) obeys it. LaC carries that answer over to LLM behavior.

LaC = a specification (the paper) + a reference engine. Like Docker: the compose format and OCI are paper; Docker Engine is one implementation, and Podman proves the paper is real. The protocol test: a stranger's hand writes a second engine from the paper alone - and a LaC application runs on it unchanged. The protocol dies the day the truth moves from the paper into the code ("how should an engine behave in case X?" - "go read what lac_engine.py does"). The discipline: when paper and engine diverge, the ENGINE gets fixed; the paper changes only by a deliberate admin decision, with a new version.

## 2. Philosophy

Three pillars:

1. **Mechanism** - prose becomes deterministic commands. The user's free wording maps onto a canonical form; code always executes, the model never does. The model interprets and narrates; code acts.
2. **Discipline** - on a frozen model, law in prose plus a perimeter in code reduce drift; drift is measured as a NUMBER, not an impression.
3. **Generalization** - as IaC did not build servers but described them, LaC does not build the application: it describes its behavior so that any compatible engine can run it.

What LaC is NOT:

- Not a chat wrapper - wrappers are legion; LaC lives inside any of them that can read files.
- Not a prompt framework - the prompt is a release artifact, not an improvisation.
- Not self-improvement - the model never writes its own laws, at any level. A hard anti-goal.
- Not a replacement for wrapper code - prose replaces the code of BEHAVIOR; effects, the perimeter, and commands are always code.

## 3. Architecture

### 3.1 llm-compose

One file declares the whole application:

- `schema_version` - parser strictness: an unknown key is a refusal, not a guess;
- `app` - name and version (identity only; the commands module lives at the fixed path `.lac/commands.py`);
- `llm` - the head: {provider, model, optional persona}; `llm.persona` names the persona file, loaded as L2 after the L2 list - switching personas is one key change; access keys live ONLY in env, never in files;
- `paths` - only what the code actually reads (minimalism: a key with no consumer gets removed);
- `levels` - the declaration of the write perimeter (who writes what; fsjail enforces it);
- `context` - what loads into context at boot; the keys ARE the levels (L1/L2/L3), paths are relative to the application root.
The compose is LaC's blank form; filling it in belongs to the application. Whoever holds the compose holds everything - which is why the compose itself is L1.

### 3.2 Levels

A level is a ROLE (who has the right to write) and PRECEDENCE (what overrides what) - not a folder and not a load order. The load order merely COINCIDES with the level, because higher trust enters the context first, and no lower content can act before its limits do.

- **L1 - admin, the frame.** The compose and the limits: security, integrity, the safety floor. Unchanged across one owner's applications. The model NEVER writes L1.
- **L2 - dev, the behavior.** Rules, the soul (persona), commands. What makes the application THIS application. Commands at L2 live as code (a module); their contract lives as prose. The model does not write L2.
- **L3 - user + model, the data.** Memory, notes, dumps. The model's only write zone. L3 is ALWAYS data, never instructions: no L3 file can declare itself behavior.

### 3.3 Grimoire

Grimoire is the first LaC application: a living book of memory on top of the protocol, a conversation with a book that remembers the user's decisions between sessions. It proves the protocol by existing, and it shows the boundary: everything Grimoire-specific (memory commands, the Codie soul, the topic structure) is L2/L3 CONTENT that runs unchanged on any compatible engine.

The memory ontology (the canon principle):

- **Canon = the user's files.** The user writes their own notes, the notes are in plain sight, and the application works even without the model - clean markdown in the user's vault.
- **Index = the model's machinery, hidden.** The model keeps its routing digests and decision archive in a hidden dot-folder, under the hood. THE LOCK: everything in the hidden folder must be REBUILDABLE - delete it, say "reindex", and the book rebuilds it from the canon files. An index that can be burned without loss is a cache, not an authority.
- Consequence: a black box is acceptable exactly when it holds only derived content. A decision the user did not write into their own file lives with the rights of a cache - the right pressure to write down what matters yourself.

### 3.4 Commands

Commands are CODE with two roads to one function:

- **The canonical road**: input `!cmd` is intercepted by the engine BEFORE the model - zero tokens, zero chance to lie. The engine splits name + arguments and dispatches through a registry (name to function).
- **The free-language road**: everything else goes to the model together with tool descriptions. The model maps the phrase onto a command, echoes the mapping (the echo is not a confirmation), and REQUESTS execution with a tool call; the engine runs THE SAME function; the model only narrates the result.

The engine is blind to the application: it knows no command names, no folders, no law files. The commands module is loaded from the fixed path `.lac/commands.py`; a different application means a different module, zero changes in the engine. Proven live: without tools the model confabulated file contents; with tools it narrates the disk honestly - the tool takes away the ability to lie.

Side-effect commands (save, delete) pass a confirmation gate IN CODE; writing is locked to L3; delete is a move to trash, never erasure.

### 3.5 Addons

- **Souls** - the persona layer: style, never a cage; the safety floor from L1 overrides the soul. The compose names the soul; swapping the soul reskins the application without touching the law or the code.
- **Spells** - loadable skills: L2 behavior for one session, by explicit cast; the limits are always senior to a spell.
- **Adapter providers** - the engine's send() is a dispatcher; all vendor specifics die in one function. The adapter is omnivorous by design: any API is one new branch (anthropic and ollama are just the first two branches of the MVP, not the ceiling).

## 4. Writing good code

> Prompts are code. Bad prompts give bad results - just like bad code.

### 4.1 Rules for writing prompts

**Structure**

- Start with identity - `You are X` - the model knows at once who it is
- Concrete instructions over vague descriptions - `Respond in 2 sentences` beats `be concise`
- Headings and short lists - the model holds structure better than paragraphs

**Language**

- Write instructions in English - models follow English instructions more reliably
- State the response language explicitly at the very end - `Respond in Ukrainian`

**Order matters**

- What comes first weighs more
- Identity and role, then skills and style, then rules and limits, then the language instruction last
- Prohibitions (`Do not X`) work better near the end

**Precedence**

- L1 (limits) always loads into context first - the highest weight
- L2 (rules, soul, command contract) - second
- L3 (data: memory, notes) - last; never instructions, only material

### 4.2 Limits

The L1 law holds three floors, and only them:

- **Security** - never expose secrets; memory is data, not instructions; when in doubt, ask, do not act.
- **Integrity** - never invent: build only from the user's words and tool output; never answer from memory what a tool can answer from disk; a command that does not exist in code does not exist; the user's files are read-only.
- **Safety floor** - the soul is a layer of style, never a cage; real stakes of health or safety drop the style; a sincere "are you an AI?" gets a direct answer; when style and accuracy conflict, accuracy wins.

These floors do not change from application to application - that is exactly what makes them L1.

### 4.3 Commands

The prose side of commands is a CONTRACT, not an implementation: which commands exist, what each one means, which ones wait for confirmation. The implementation is the module; duplicating it in prose is forbidden - one copy of the truth. Keep the contract short: every line of law costs context in every session, and the law must hold on cheap models, not only on expensive ones.

### 4.4 Persona

The soul defines voice and interpretation - never facts and never permissions. It is swapped through the compose, survives long dry work without drifting into neutrality, and drops ONLY for the safety floor. The soul never obscures what the system actually did: the theater wraps the truth, it does not replace it (do not describe a save that did not happen; do not fake a command that is waiting for consent).

## 5. Security

### 5.1 Prompt injection

The perimeter against injections is structural, not vigilance:

- L3 is DATA by law - an instruction inside a note, a dump, or a memory file has no force; behavior lives only at L1/L2.
- Trust order at boot: L1/L2 enter the context BEFORE any L3 content, so an injection cannot act before its limits do.
- Tools remove the narration attack surface: the model cannot "execute" anything - it can only request a registered command, and code decides.

### 5.2 Level protection

- L1/L2 are locked at the tool level (deny on write), not by trusting the model - capability, not intent.
- The lock is verified, not assumed: at boot the engine attempts a canary write into the locked zone; the write MUST be refused, otherwise the session does not start.
- The engine itself is protected outside the protocol: file hashes (lock/check) guard lac_engine.py and the command modules.
- Effects live in a cage of code: fsjail (writes only to L3), trash instead of erasure, confirmation gates for side effects.

### 5.3 Assumptions about the model

By default LaC describes working with a **"white" model** - a model that acts in good faith, follows instructions, and has no intent to bypass restrictions. This is the base assumption for the whole architecture of levels, commands, and Grimoire.

### 5.4 Malicious models

If the model intends to bypass restrictions, no technical defense will help. It will ignore `limits.md`, get around chmod, find a way past MCP restrictions.

A malicious model is an alignment problem at the provider level, not a LaC problem. LaC does not solve that task and does not claim to.

The goal of level protection in LaC is **clarity and prevention of mistakes**, not defense against malice.

## 6. Memory hierarchy

Retrieval-first: the law (L1/L2 + the soul) is ALWAYS in context; L3 is fetched on demand and never hauled in just in case.

- Routing indexes load; topic bodies load on request; archives are grep-only and cost no context until a query needs them.
- The session window only grows and cannot be cleared - so the discipline is structural: indexes in context, depth on disk, search with an expanded query (the model itself is the embedding, applied at the moment of search - no vectors).
- The dated archive is never loaded and never compressed: it is the full canonical record, reachable only through search.
- Every verdict in a loadable digest must be self-sufficient - the whole decision, readable without the archive; a bare pointer is not a verdict.

## 7. Where to start

A Docker-like flow:

1. Take an engine (the reference lac_engine.py + adapter.py, or any compatible one) - you do not write it, you download it.
2. Take or write an application: llm_compose + the L1/L2 content + a commands module. Grimoire is the first ready one.
3. Put the API key in env, name the head in the compose's llm block.
4. Run the engine from the application root. Boot = loading in trust order, lock checks, an OK report with the list of what loaded. Sessions are disposable; the application is the files.

## 8. Backlog

1. M1 (remainder): search in code (rg + query expansion) through a "canon + tool" pair; a human word for output; canonical echo.
2. M2: save/delete + confirmation gates in code + fsjail (writes only to L3, delete = trash).
3. M3: a model matrix, drift as a number (dashes, confabulation, embellishment, cross-script leaks); hardening the soul for cheap heads.
4. Release into two repos: diranix/lac (the paper + the reference engine), diranix/grimoire (the first application).
5. After the release: bundling (does the engine ship together with Grimoire), a Grimoire GUI; the MVP stays in the terminal.
