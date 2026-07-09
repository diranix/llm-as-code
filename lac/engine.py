import importlib.util
import os
import readline  # noqa: F401
import sys

import yaml

from lac.adapter import ApiError, send


def main():
    app_root = sys.argv[1] if len(sys.argv) > 1 else "."
    compose_path = os.path.join(app_root, ".lac", "llm_compose.yaml")

    try:
        with open(compose_path) as compose_file:
            compose = yaml.safe_load(compose_file)
    except FileNotFoundError:
        raise SystemExit("no llm_compose.yaml at " + compose_path)

    if compose.get("schema_version") != 1:
        raise SystemExit("compose error: schema_version must be 1")

    known_keys = {"schema_version", "app", "paths", "levels", "context", "llm"}
    unknown = set(compose) - known_keys
    if unknown:
        raise SystemExit("compose error: unknown keys: " + ", ".join(sorted(unknown)))

    paths = compose["paths"]
    memory_dir = os.path.join(app_root, paths["memory"])

    llm_cfg = compose["llm"]

    app_name = compose["app"]["name"]
    module_name = "commands_" + app_name
    module_path = os.path.join(app_root, module_name + ".py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise SystemExit("compose error: no commands module at " + module_path)
    commands_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(commands_module)
    TOOLS = commands_module.TOOLS
    COMMANDS = commands_module.COMMANDS

    context_cfg = compose["context"]

    missing = []
    loaded = []
    for level in ("L1", "L2", "L3"):
        for path in context_cfg[level]:
            try:
                with open(os.path.join(app_root, path)) as f:
                    text = f.read()
                loaded.append("# FILE: " + path + "\n" + text)
            except FileNotFoundError:
                missing.append((level, path))

    context = "\n\n".join(loaded)

    if missing:
        print("MISSING:")
        for level, path in missing:
            print(" ", level, path)
        if any(level != "L3" for level, path in missing):
            raise SystemExit("law incomplete (L1/L2 missing) - refusing to start")
    else:
        print("OK:", len(loaded), "files,", len(context), "symbols")

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
            if command:
                print(command(memory_dir, args.strip()))
            else:
                print("unknown command:", user_input)
            continue
        checkpoint = len(messages)
        messages.append({"role": "user", "content": user_input})
        while True:
            try:
                reply = send(context, messages, llm_cfg, TOOLS)
            except ApiError as error:
                print("[api error]", error)
                del messages[checkpoint:]
                break
            messages.append({"role": "assistant", "content": reply["content"]})
            for block in reply["content"]:
                if block["type"] == "text":
                    print()
                    print(block["text"])
                elif block["type"] == "thinking":
                    print()
                    print("[thinking:", len(block.get("thinking", "")), "chars]")
            tool_calls = [b for b in reply["content"] if b["type"] == "tool_use"]
            if not tool_calls:
                break
            results = []
            for call in tool_calls:
                command = COMMANDS.get(call["name"])
                if command:
                    output = command(memory_dir, call["input"].get("args", ""))
                else:
                    output = "unknown tool: " + call["name"]
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call["id"],
                        "content": output,
                    }
                )
            messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    main()
