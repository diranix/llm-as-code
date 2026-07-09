import json
import os
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
TIMEOUT = 240


class ApiError(Exception):
    pass


def http_post(url, payload, headers):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise ApiError("HTTP " + str(e.code) + " - " + detail)
    except urllib.error.URLError as e:
        raise ApiError(str(e.reason))


def send(context, messages, llm, tools=None):
    if llm["provider"] == "anthropic":
        return send_anthropic(context, messages, llm, tools)
    if llm["provider"] == "ollama":
        return send_ollama(context, messages, llm, tools)
    raise SystemExit("compose error: unknown llm provider: " + llm["provider"])


def to_ollama_messages(messages):
    out = []
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            out.append({"role": message["role"], "content": content})
            continue
        text = ""
        tool_calls = []
        for block in content:
            if block["type"] == "text":
                text += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(
                    {
                        "function": {
                            "name": block["name"],
                            "arguments": block["input"],
                        }
                    }
                )
            elif block["type"] == "tool_result":
                out.append({"role": "tool", "content": block["content"]})
        if text or tool_calls:
            entry = {"role": message["role"], "content": text}
            if tool_calls:
                entry["tool_calls"] = tool_calls
            out.append(entry)
    return out


def to_ollama_tools(tools):
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in tools
    ]


def send_ollama(context, messages, llm, tools):
    payload = {
        "model": llm["model"],
        "messages": [{"role": "system", "content": context}]
        + to_ollama_messages(messages),
        "stream": False,
    }
    if tools:
        payload["tools"] = to_ollama_tools(tools)
    answer = http_post(OLLAMA_URL, payload, {"Content-Type": "application/json"})
    message = answer["message"]
    blocks = []
    if message.get("content"):
        blocks.append({"type": "text", "text": message["content"]})
    for index, call in enumerate(message.get("tool_calls") or []):
        blocks.append(
            {
                "type": "tool_use",
                "id": "ollama_" + str(index),
                "name": call["function"]["name"],
                "input": call["function"].get("arguments") or {},
            }
        )
    return {"role": "assistant", "content": blocks}


def send_anthropic(context, messages, llm, tools):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ApiError("ANTHROPIC_API_KEY is not set")
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
    answer = http_post(
        ANTHROPIC_URL,
        payload,
        {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
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
