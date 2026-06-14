#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example: drive NAO from Python 3 through the nao_bridge server.

1. Start the bridge server (inside the `naoqi` conda env):

     ./run_server.sh --mock          # no robot needed, good for development
     ./run_server.sh --nao-ip <ip>   # talk to a real robot

2. Run this script from any Python 3 environment (e.g. `python312`):

     python examples/llm_agent_demo.py

This file also shows one way to wire NAO up to an LLM: NAO_TOOLS is a set of
OpenAI-style "function calling" tool definitions, and dispatch_tool_call()
maps a (name, arguments) tool call - as returned by an LLM - onto
NaoBridgeClient calls. A real agent loop would feed NAO_TOOLS to the model,
get back tool calls, run dispatch_tool_call(), and feed the results back to
the model.

3. Optional: chat with NAO via the DeepSeek API.

     export DEEPSEEK_API_KEY=sk-...
     python examples/llm_agent_demo.py

   If DEEPSEEK_API_KEY is set, this script starts an interactive text chat
   instead of running the scripted demo below: each line you type is sent to
   DeepSeek (https://api.deepseek.com) along with NAO_TOOLS, any tool calls
   the model makes are run on NAO via dispatch_tool_call(), and the model's
   reply is printed and spoken by NAO. Only the Python standard library
   (urllib) is used to call the API, so no extra dependencies are required.
"""

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from nao_bridge.client import NaoBridgeClient, NaoBridgeError  # noqa: E402


NAO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "nao_say",
            "description": "Make NAO speak a sentence out loud.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to speak."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nao_go_to_posture",
            "description": "Move NAO into a named posture (e.g. StandInit, Sit, Crouch, LyingBack).",
            "parameters": {
                "type": "object",
                "properties": {
                    "posture_name": {"type": "string"},
                    "speed": {"type": "number", "default": 0.5},
                },
                "required": ["posture_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nao_set_joint_angles",
            "description": "Set one or more joint angles, in degrees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "joints": {"type": "array", "items": {"type": "string"}},
                    "angles_deg": {"type": "array", "items": {"type": "number"}},
                    "speed": {"type": "number", "default": 0.1, "description": "Fraction of max joint speed"},
                },
                "required": ["joints", "angles_deg"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nao_listen",
            "description": "Return the last word NAO's speech recognizer heard, and its confidence.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def dispatch_tool_call(client, name, arguments):
    if name == "nao_say":
        return client.speech.say(text=arguments["text"])
    if name == "nao_go_to_posture":
        return client.motion.go_to_posture(
            posture_name=arguments["posture_name"],
            speed=arguments.get("speed", 0.5),
        )
    if name == "nao_set_joint_angles":
        return client.motion.set_joint_angles(
            joints=arguments["joints"],
            angles_deg=arguments["angles_deg"],
            speed=arguments.get("speed", 0.1),
        )
    if name == "nao_listen":
        return client.speech.asr_get_last_recognized()
    raise ValueError("unknown tool: {0}".format(name))


DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

CHAT_SYSTEM_PROMPT = (
    "You are the onboard assistant for a NAO humanoid robot, chatting with a "
    "person standing in front of you. Reply with short, natural spoken "
    "sentences - your reply text is read aloud by NAO's text-to-speech, so "
    "do not use markdown, code blocks or emojis. Use the provided tools when "
    "the user asks you to change NAO's posture, move its joints, or check "
    "what it last heard."
)


def call_deepseek(api_key, messages, tools=None):
    """Call the DeepSeek chat-completions API (OpenAI-compatible) using only urllib."""
    body = {"model": DEEPSEEK_MODEL, "messages": messages}
    if tools:
        body["tools"] = tools

    request = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(api_key),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError("DeepSeek API error {0}: {1}".format(exc.code, detail))


def chat_with_nao(client, api_key):
    """Interactive text chat with NAO, powered by the DeepSeek API.

    Each line you type is sent to DeepSeek together with NAO_TOOLS. If the
    model responds with tool calls, dispatch_tool_call() runs them on NAO and
    the results are fed back to the model. The model's final reply is printed
    and spoken by NAO via client.speech.say().
    """
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    print("Chatting with NAO via DeepSeek ({0}). Type 'exit' to quit.".format(DEEPSEEK_MODEL))

    while True:
        try:
            user_text = input("You: ").strip()
        except EOFError:
            break
        if user_text.lower() in ("exit", "quit"):
            break
        if not user_text:
            continue

        messages.append({"role": "user", "content": user_text})
        message = call_deepseek(api_key, messages, tools=NAO_TOOLS)["choices"][0]["message"]
        messages.append(message)

        for call in message.get("tool_calls") or []:
            name = call["function"]["name"]
            arguments = json.loads(call["function"]["arguments"] or "{}")
            print("[tool] {0}({1})".format(name, arguments))
            try:
                result = dispatch_tool_call(client, name, arguments)
            except NaoBridgeError as exc:
                result = {"error": str(exc)}
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result),
            })

        if message.get("tool_calls"):
            message = call_deepseek(api_key, messages, tools=NAO_TOOLS)["choices"][0]["message"]
            messages.append(message)

        reply = (message.get("content") or "").strip()
        if reply:
            print("NAO:", reply)
            client.speech.say(text=reply)


def main():
    client = NaoBridgeClient(host="127.0.0.1", port=5050)

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if api_key:
        chat_with_nao(client, api_key)
        return

    print("ping:", client.system.ping())
    print("available methods:", client.system.list_methods())

    print(dispatch_tool_call(client, "nao_go_to_posture", {"posture_name": "StandInit"}))
    print(dispatch_tool_call(client, "nao_say", {"text": "Hello, I am being controlled from Python 3."}))

    # A small "gesture": raise the right arm by setting a couple of joints.
    print(dispatch_tool_call(client, "nao_set_joint_angles", {
        "joints": ["RShoulderPitch", "RShoulderRoll"],
        "angles_deg": [20.0, -30.0],
        "speed": 0.2,
    }))

    client.speech.asr_set_vocabulary(words=["hello", "stop", "go"], word_spotting=True)
    client.speech.asr_subscribe()
    print("heard:", dispatch_tool_call(client, "nao_listen", {}))

    print("joint angles:", client.motion.get_joint_angles(joints="Body"))


if __name__ == "__main__":
    try:
        main()
    except (NaoBridgeError, RuntimeError) as exc:
        print("[ERROR] {0}".format(exc))
        sys.exit(1)
