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
"""

import os
import sys

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


def main():
    client = NaoBridgeClient(host="127.0.0.1", port=5050)

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
    except NaoBridgeError as exc:
        print("[ERROR] {0}".format(exc))
        sys.exit(1)
