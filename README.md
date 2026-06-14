# NaoQi_SDK_Bridge

**Languages:** English | [中文](README.zh-CN.md)

A minimal bridge that connects NAOqi (Python 2.7 only) with Python 3 code
such as LLM/VLM agents.

## Directory Structure

```
NaoQi_SDK_Bridge/
├── nao_bridge/              # Python package: JSON-RPC protocol, server, client, service wrappers
│   ├── protocol.py
│   ├── server.py            # runs in the naoqi (py2.7) env
│   ├── client.py            # stdlib-only py3 client: NaoBridgeClient
│   └── services/
│       ├── motion.py        # ALMotion / ALRobotPosture
│       ├── speech.py        # ALTextToSpeech / ALAnimatedSpeech / ALSpeechRecognition
│       └── system_service.py
├── examples/
│   └── llm_agent_demo.py     # py3 example, including an LLM tool/function-calling schema
├── run_server.sh             # conda activate naoqi + set PYTHONPATH + start the server
└── README.md
```

## Architecture

```
+-----------------------------+        TCP / JSON-RPC        +----------------------------------+
| naoqi conda env (Python 2.7)|  <------------------------>  | Any Python 3 environment (e.g. python312) |
|                              |   127.0.0.1:5050 (default)   |                                  |
|  nao_bridge/server.py        |                              |  nao_bridge/client.py            |
|  - ALMotion / ALRobotPosture |                              |  - NaoBridgeClient                |
|  - ALTextToSpeech            |                              |  - LLM / VLM agent logic          |
|  - ALAnimatedSpeech          |                              |                                  |
|  - ALSpeechRecognition       |                              |                                  |
|  - ALMemory                  |                              |                                  |
+-----------------------------+                              +----------------------------------+
        |
        | NAOqi SDK (ALProxy)
        v
   NAO robot (192.168.x.x:9559)
```

- **server.py** runs inside the `naoqi` (Python 2.7) environment, loads the
  NAOqi SDK, and wraps `ALMotion` / `ALRobotPosture` / `ALTextToSpeech` /
  `ALAnimatedSpeech` / `ALSpeechRecognition` / `ALMemory` into a few "service
  objects", exposed over a local TCP socket as JSON-RPC.
- **client.py** is a stdlib-only Python 3 module (no NAOqi dependency). An
  LLM/VLM agent process imports it to send commands, e.g.
  `nao.motion.go_to_posture(posture_name="StandInit")`.
- Both sides only use `socket` + `json` from the Python 2.7 / 3 standard
  library - no extra dependencies (no Flask/ZeroMQ/gRPC needed).

## Quick Start

### 1. Start the bridge server (in the naoqi / py2.7 env)

No robot needed - verify the link with mock mode first:

```bash
cd NaoQi_SDK_Bridge
./run_server.sh --mock
```

Connect to a real robot:

```bash
./run_server.sh --nao-ip 192.168.1.101 --nao-port 9559
```

`run_server.sh` automatically:
- Adds the NAOqi SDK's Python bindings directory (where `naoqi` /
  `_inaoqi.so` / `qi` live; defaults to
  `/home/sgzg/Naoqi_SDK/lib/python2.7/site-packages`, override with the
  `NAOQI_SDK_PYTHONPATH` env var) to `PYTHONPATH`;
- Runs `conda activate naoqi` (the conda root and env name can be overridden
  with `CONDA_ROOT` / `NAOQI_CONDA_ENV`);
- Runs `nao_bridge/server.py`.

By default it listens on `127.0.0.1:5050`, **bound to localhost only**. If
your LLM/VLM process runs on another machine, don't just change `--host` to
`0.0.0.0` and expose it on the network - use an SSH tunnel instead
(`ssh -L 5050:127.0.0.1:5050 ...`), since this protocol currently has no
authentication.

### 2. Call it from Python 3 (any py3 env, e.g. `python312`)

```python
import sys
sys.path.insert(0, "/path/to/NaoQi_SDK_Bridge")  # repo root, so `nao_bridge` can be imported

from nao_bridge.client import NaoBridgeClient

nao = NaoBridgeClient(host="127.0.0.1", port=5050)

nao.motion.wake_up()
nao.motion.go_to_posture(posture_name="StandInit")
nao.speech.say(text="Hello, I am NAO")

angles = nao.motion.get_joint_angles(joints=["HeadYaw", "HeadPitch"])
print(angles)  # {"joints": [...], "angles_deg": [...]}
```

A complete, runnable example (including an LLM tool/function-calling schema)
lives at `examples/llm_agent_demo.py` - see the docstring at the top of that
file for usage.

### 3. Chat with NAO via the DeepSeek API

`examples/llm_agent_demo.py` also includes an interactive chat mode powered
by the [DeepSeek API](https://api.deepseek.com) (OpenAI-compatible, called
with `urllib` only - no extra dependencies). Set `DEEPSEEK_API_KEY` and run
the same script:

```bash
export DEEPSEEK_API_KEY=sk-...
python examples/llm_agent_demo.py
```

Each line you type is sent to DeepSeek together with `NAO_TOOLS`. If the
model calls a tool (e.g. to change posture or move a joint),
`dispatch_tool_call()` runs it on NAO and the result is fed back to the
model; the model's reply is printed and spoken by NAO via
`client.speech.say()`. Type `exit` to quit. Override the model with
`DEEPSEEK_MODEL` (default: `deepseek-chat`).

## RPC Method Overview

All calls follow `client.<namespace>.<method>(**kwargs)`, which maps to
`registry[namespace].<method>(**kwargs)` on the server. Use
`client.system.list_methods()` to discover what's available at runtime.

### `motion.*` (ALMotion / ALRobotPosture, angles in **degrees**)

| Method | Description |
| --- | --- |
| `wake_up()` | Power on / enter controllable state |
| `rest()` | Enter resting posture, relax joints |
| `is_awake()` | Whether the robot is awake |
| `get_posture()` | Current posture family (e.g. "Standing") |
| `go_to_posture(posture_name, speed=0.5)` | Switch to a named posture ("StandInit"/"Sit"/...) |
| `list_joints(chain="Body")` | List joint names for a chain |
| `get_joint_angles(joints="Body", use_sensors=True)` | Read joint angles (degrees) |
| `set_joint_angles(joints, angles_deg, speed=0.1)` | Non-blocking move toward target angles at a fraction of max speed |
| `move_joints(joints, angles_deg, durations_sec, absolute=True)` | Blocking interpolated motion (`ALMotion.angleInterpolation`); supports multiple waypoints |
| `set_stiffness(joints, value)` | Set joint stiffness 0~1 |
| `walk_to(x, y, theta=0.0)` | Relative walk |
| `stop_walk()` | Stop walking |

### `speech.*` (ALTextToSpeech / ALAnimatedSpeech / ALSpeechRecognition / ALMemory)

| Method | Description |
| --- | --- |
| `say(text, mode="animated", body_language_mode="contextual")` | Speak text; `mode="tts"` uses plain `ALTextToSpeech` |
| `set_language(language)` | Set both TTS and ASR language |
| `set_volume(volume)` | Set TTS volume |
| `asr_set_vocabulary(words, word_spotting=True)` | Set the speech recognition vocabulary |
| `asr_subscribe()` / `asr_unsubscribe()` | Start/stop speech recognition |
| `asr_get_last_recognized()` | Read the most recently recognized word and confidence from `ALMemory` |

`ALAnimatedSpeech` / `ALSpeechRecognition` / `ALMemory` are optional proxies:
if the robot/SDK doesn't provide them, the corresponding field is `None`;
`say()` automatically falls back to `ALTextToSpeech`, and ASR-related methods
raise a clear error.

### `system.*`

| Method | Description |
| --- | --- |
| `ping()` | Connectivity check |
| `list_methods()` | List the currently available `motion.*` / `speech.*` methods |

## Mock Mode

`--mock` runs the server without a robot and without the NAOqi SDK, using
in-memory fake `MotionService` / `SpeechService` (`MockMotionService` /
`MockSpeechService` in `nao_bridge/services/motion.py` /
`nao_bridge/services/speech.py`). This lets you:

- Develop/debug the LLM/VLM agent logic without a robot;
- Verify the JSON-RPC link and parameter shapes before switching to a real
  robot.

## Extending

- **Adding a capability (e.g. camera/vision for a VLM)**: create a new module
  under `nao_bridge/services/` (e.g. `vision.py`) with a `VisionService`
  (wrapping `ALVideoDevice`, e.g. `get_frame_jpeg()` returning a base64-encoded
  JPEG) and a matching `MockVisionService`, then register it as
  `registry["vision"] = ...` in `build_registry()` in `server.py`. No changes
  are needed on the Python 3 side - `client.vision.get_frame_jpeg()` works
  automatically (`_RemoteNamespace` dispatches dynamically).
- **Adding a single method**: just add a public method to the relevant service
  class. The dispatcher in `server.py` exposes it automatically via
  reflection, and `client.system.list_methods()` will list it too.
- **Multiple robots / multiple servers**: each `NaoBridgeClient(host=...,
  port=...)` corresponds to one server process - use a different port per
  robot.

## Known Limitations / Future Work

- The protocol has no authentication - only use it locally or over an SSH
  tunnel.
- Each RPC call opens a new TCP connection (simple, and fine for low-frequency
  commands; if high-frequency joint streaming is needed later, a persistent
  connection + streaming protocol could be added).
- Camera/vision (for VLM use) is not implemented yet - add `vision.py` as
  described in "Extending" above.
