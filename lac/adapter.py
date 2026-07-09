import json
import os
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def send(context, messages, llm, tools=None):
    if llm["provider"] == "anthropic":
        return send_anthropic(context, messages, llm, tools)
    if llm["provider"] == "ollama":
        return send_ollama(context, messages, llm, tools)
    raise SystemExit("compose error: unknown llm provider: " + llm["provider"])


def send_ollama(context, messages, llm, tools):
    payload = {
        "model": llm["model"],
        "messages": [{"role": "system", "content": context}] + messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        answer = json.loads(response.read())
    return answer["message"]


def send_anthropic(context, messages, llm, tools):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set")
    payload = {
        "model": llm["model"],
        "max_tokens": 2048,
        "system": [
            {
                "type": "text",
                "text": context,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools
    request = urllib.request.Request(
        ANTHROPIC_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(request) as response:
        answer = json.loads(response.read())
        usage = answer["usage"]
        print(
            "[usage]",
            usage["input_tokens"],
            "in /",
            usage["output_tokens"],
            "out /",
            usage["cache_read_input_tokens"],
            "cached",
        )
        stop = answer.get("stop_reason")
        if stop not in ("end_turn", "tool_use"):
            print("[stop]", stop)
    return {"role": "assistant", "content": answer["content"]}
