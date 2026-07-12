import importlib.util
import os
import readline  # noqa: F401
import sys
from datetime import datetime

import yaml

from lac.adapter import PROVIDERS, ApiError, send


def need(mapping, key):
    value = mapping.get(key)
    if value is None:
        raise SystemExit("compose error: missing key: " + key)
    return value


def load_compose(app_root):
    compose_path = os.path.join(app_root, ".lac", "llm_compose.yaml")
    try:
        with open(compose_path, encoding="utf-8") as compose_file:
            compose = yaml.safe_load(compose_file)
    except FileNotFoundError:
        raise SystemExit("no llm_compose.yaml at " + compose_path)
    except yaml.YAMLError as error:
        raise SystemExit("compose error: bad yaml - " + str(error))
    if not isinstance(compose, dict):
        raise SystemExit("compose error: not a yaml mapping")

    if compose.get("schema_version") != 1:
        raise SystemExit("compose error: schema_version must be 1")

    known_keys = {
        "schema_version",
        "app",
        "paths",
        "levels",
        "context",
        "llm",
        "engine",
    }
    unknown = set(compose) - known_keys
    if unknown:
        raise SystemExit("compose error: unknown keys: " + ", ".join(sorted(unknown)))
    return compose


def load_commands(app_root, app_name):
    module_name = "commands_" + app_name
    module_path = os.path.join(app_root, module_name + ".py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise SystemExit("compose error: no commands module at " + module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_context(app_root, context_cfg):
    missing = []
    loaded = []
    for level in ("L1", "L2", "L3"):
        for path in need(context_cfg, level):
            try:
                with open(os.path.join(app_root, path), encoding="utf-8") as f:
                    loaded.append("# FILE: " + path + "\n" + f.read())
            except FileNotFoundError:
                missing.append((level, path))
    context = "\n\n".join(loaded)
    if missing:
        print("MISSING:")
        for level, path in missing:
            print(" ", level, path)
        if any(level != "L3" for level, _ in missing):
            raise SystemExit("law incomplete (L1/L2 missing) - refusing to start")
    else:
        print("OK:", len(loaded), "files,", len(context), "symbols")
    return context


def confirm(name, params):
    text = params.get("text")
    if text:
        print("--- text to write ---")
        print(text)
        print("---")
    answer = input(
        "[confirm] !" + name + " " + params.get("args", "") + " - y/N? "
    )
    return answer.strip().lower() == "y"


def log_turn(path, role, text):
    stamp = datetime.now().strftime("%H:%M")
    with open(path, "a", encoding="utf-8") as f:
        f.write("## " + role + " [" + stamp + "]\n" + text + "\n\n")


def run_command(command, env, params):
    try:
        return command(env, params)
    except KeyboardInterrupt:
        print()
        return "interrupted by the user"
    except Exception as error:
        return "command failed: " + repr(error)


def repl(env, context, llm_cfg, ask, commands_module):
    TOOLS = commands_module.TOOLS
    COMMANDS = commands_module.COMMANDS
    CONFIRM = commands_module.CONFIRM
    ON_TURN = getattr(commands_module, "ON_TURN", None)
    ON_TEXT = getattr(commands_module, "ON_TEXT", None)

    messages = []
    while True:
        try:
            print()
            user_input = input("> ")
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if user_input == "exit":
            break
        if user_input.startswith("!"):
            name, _, args = user_input[1:].partition(" ")
            command = COMMANDS.get(name)
            if command is None:
                user_input = (
                    user_input
                    + "\n\n[not a canonical command - if it clearly maps "
                    "to ONE available tool, call that tool; "
                    "otherwise ask the user what they meant]"
                )
            elif name in CONFIRM and ask and not confirm(name, {"args": args.strip()}):
                print("cancelled")
                continue
            else:
                output = run_command(command, env, {"args": args.strip()})
                user_input = (
                    user_input
                    + "\n\n[result - already executed by code; "
                    "relay it faithfully, add nothing beyond it]\n"
                    + output
                )
        checkpoint = len(messages)
        messages.append({"role": "user", "content": user_input})
        env["log"]("user", user_input)
        window = 0
        while True:
            try:
                reply = send(context, messages, llm_cfg, TOOLS)
            except ApiError as error:
                print("[api error]", error)
                del messages[checkpoint:]
                break
            except KeyboardInterrupt:
                print()
                print("[cancelled - turn dropped]")
                del messages[checkpoint:]
                break
            window = reply.get("window", 0)
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        b for b in reply["content"] if b["type"] != "thinking"
                    ],
                }
            )
            for block in reply["content"]:
                if block["type"] == "text":
                    if ON_TEXT:
                        block["text"] = ON_TEXT(block["text"])
                    print()
                    print(block["text"])
                    env["log"]("assistant", block["text"])
                elif block["type"] == "thinking" and block.get("thinking"):
                    print()
                    print("[thinking:", len(block["thinking"]), "chars]")
            tool_calls = [b for b in reply["content"] if b["type"] == "tool_use"]
            if not tool_calls:
                break
            results = []
            for call in tool_calls:
                command = COMMANDS.get(call["name"])
                if command is None:
                    output = "unknown tool: " + call["name"]
                elif call["name"] in CONFIRM and ask and not confirm(
                    call["name"], call["input"]
                ):
                    output = "cancelled by the user - do not retry"
                else:
                    output = run_command(command, env, call["input"])
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call["id"],
                        "content": output,
                    }
                )
                env["log"](
                    "tool " + call["name"],
                    "input: " + repr(call["input"]) + "\n" + output,
                )
            messages.append({"role": "user", "content": results})
        if ON_TURN:
            ON_TURN(env, messages, window)


def main():
    app_root = sys.argv[1] if len(sys.argv) > 1 else "."
    compose = load_compose(app_root)

    paths = need(compose, "paths")
    memory_dir = os.path.join(app_root, need(paths, "memory"))
    trash_dir = os.path.join(app_root, need(paths, "trash"))
    env = {"memory": memory_dir, "trash": trash_dir}

    llm_cfg = need(compose, "llm")
    worker_cfg = llm_cfg.pop("worker", None)
    env["budget"] = llm_cfg.pop("context_budget", None) or 30000
    for cfg in (llm_cfg, worker_cfg):
        if cfg is not None and cfg.get("provider") not in PROVIDERS:
            raise SystemExit(
                "compose error: unknown llm provider: " + str(cfg.get("provider"))
            )

    engine_cfg = compose.get("engine") or {}
    ask = engine_cfg.get("confirm") == "ask"

    def worker(task, text):
        reply = send(task, [{"role": "user", "content": text}], worker_cfg)
        return "".join(
            b["text"] for b in reply["content"] if b["type"] == "text"
        )

    env["worker"] = worker if worker_cfg else None

    app_name = need(need(compose, "app"), "name")
    commands_module = load_commands(app_root, app_name)
    context = build_context(app_root, need(compose, "context"))

    sessions_dir = os.path.join(memory_dir, ".sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    env["session_log"] = os.path.join(
        sessions_dir, datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".md"
    )
    env["log"] = lambda role, text: log_turn(env["session_log"], role, text)
    env["main"] = lambda msgs: send(context, msgs, {**llm_cfg, "quiet": True})

    repl(env, context, llm_cfg, ask, commands_module)


if __name__ == "__main__":
    main()
