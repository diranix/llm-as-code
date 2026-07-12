import json
import os
import time
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
TIMEOUT = 240
DEFAULT_MAX_TOKENS = 2048


class ApiError(Exception):
    pass


def http_post(url, payload, headers, tries=4):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                body = response.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code == 429 and attempt < tries - 1:
                wait = 2 * (attempt + 1)
                print("[rate limited - retrying in", wait, "s]")
                time.sleep(wait)
                continue
            raise ApiError("HTTP " + str(e.code) + " - " + detail)
        except urllib.error.URLError as e:
            raise ApiError(str(e.reason))
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise ApiError(
                "bad response - not json: " + body.decode(errors="replace")[:300]
            )


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


def to_openai_tools(tools):
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
        payload["tools"] = to_openai_tools(tools)
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
    return {
        "role": "assistant",
        "content": blocks,
        "window": answer.get("prompt_eval_count", 0),
    }


def to_mistral_messages(messages):
    out = []
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            out.append({"role": message["role"], "content": content})
            continue
        text = ""
        tool_calls = []
        tool_results = []
        for block in content:
            if block["type"] == "text":
                text += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(
                    {
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    }
                )
            elif block["type"] == "tool_result":
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": block["content"],
                    }
                )
        if text or tool_calls:
            entry = {"role": message["role"], "content": text}
            if tool_calls:
                entry["tool_calls"] = tool_calls
            out.append(entry)
        out.extend(tool_results)
    return out


def send_mistral(context, messages, llm, tools):
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise ApiError("MISTRAL_API_KEY is not set")
    payload = {
        "model": llm["model"],
        "max_tokens": llm.get("max_tokens", DEFAULT_MAX_TOKENS),
        "messages": [{"role": "system", "content": context}]
        + to_mistral_messages(messages),
    }
    if "temperature" in llm:
        payload["temperature"] = llm["temperature"]
    if tools:
        payload["tools"] = to_openai_tools(tools)
    answer = http_post(
        MISTRAL_URL,
        payload,
        {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
    )
    message = answer["choices"][0]["message"]
    blocks = []
    if message.get("content"):
        blocks.append({"type": "text", "text": message["content"]})
    for call in message.get("tool_calls") or []:
        arguments = call["function"].get("arguments") or {}
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        blocks.append(
            {
                "type": "tool_use",
                "id": call["id"],
                "name": call["function"]["name"],
                "input": arguments,
            }
        )
    usage = answer.get("usage") or {}
    if not llm.get("quiet"):
        print(
            "[usage]",
            usage.get("prompt_tokens", 0),
            "in /",
            usage.get("completion_tokens", 0),
            "out",
        )
    return {
        "role": "assistant",
        "content": blocks,
        "window": usage.get("prompt_tokens", 0),
    }


def send_anthropic(context, messages, llm, tools):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ApiError("ANTHROPIC_API_KEY is not set")
    payload = {
        "model": llm["model"],
        "max_tokens": llm.get("max_tokens", DEFAULT_MAX_TOKENS),
        "system": [
            {
                "type": "text",
                "text": context,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": messages,
    }
    if "temperature" in llm:
        payload["temperature"] = llm["temperature"]
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
    if not llm.get("quiet"):
        print(
            "[usage]",
            usage["input_tokens"],
            "in /",
            usage["output_tokens"],
            "out /",
            usage["cache_read_input_tokens"],
            "cached /",
            usage["cache_creation_input_tokens"],
            "written",
        )
    stop = answer.get("stop_reason")
    if stop not in ("end_turn", "tool_use"):
        print("[stop]", stop)
    return {
        "role": "assistant",
        "content": answer["content"],
        "window": usage["input_tokens"]
        + usage["cache_read_input_tokens"]
        + usage["cache_creation_input_tokens"],
    }


PROVIDERS = {
    "anthropic": send_anthropic,
    "mistral": send_mistral,
    "ollama": send_ollama,
}


def send(context, messages, llm, tools=None):
    provider = PROVIDERS.get(llm["provider"])
    if provider is None:
        raise ApiError("unknown llm provider: " + str(llm["provider"]))
    return provider(context, messages, llm, tools)
