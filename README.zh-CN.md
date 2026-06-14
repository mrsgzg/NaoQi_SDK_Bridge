# NaoQi_SDK_Bridge

**Languages:** [English](README.md) | 中文

一个轻量级桥接层，用于连接只能运行在 Python 2.7 上的 NAOqi，与运行 LLM/VLM
等技术所需的 Python 3 代码。

## 目录结构

```
NaoQi_SDK_Bridge/
├── nao_bridge/              # Python 包：JSON-RPC 协议、服务端、客户端、服务封装
│   ├── protocol.py
│   ├── server.py            # 运行在 naoqi (py2.7) 环境中
│   ├── client.py            # 仅依赖标准库的 py3 客户端：NaoBridgeClient
│   └── services/
│       ├── motion.py        # ALMotion / ALRobotPosture
│       ├── speech.py        # ALTextToSpeech / ALAnimatedSpeech / ALSpeechRecognition
│       └── system_service.py
├── examples/
│   └── llm_agent_demo.py     # py3 示例，包含 LLM 工具/函数调用 schema
├── run_server.sh             # conda activate naoqi + 设置 PYTHONPATH + 启动服务端
└── README.md
```

## 架构

```
+-----------------------------+        TCP / JSON-RPC        +----------------------------------+
| naoqi conda 环境 (Python 2.7) |  <------------------------>  | 任意 Python 3 环境 (如 python312)  |
|                              |   127.0.0.1:5050 (默认)      |                                  |
|  nao_bridge/server.py        |                              |  nao_bridge/client.py            |
|  - ALMotion / ALRobotPosture |                              |  - NaoBridgeClient                |
|  - ALTextToSpeech            |                              |  - LLM / VLM agent 逻辑           |
|  - ALAnimatedSpeech          |                              |                                  |
|  - ALSpeechRecognition       |                              |                                  |
|  - ALMemory                  |                              |                                  |
+-----------------------------+                              +----------------------------------+
        |
        | NAOqi SDK (ALProxy)
        v
   NAO 机器人 (192.168.x.x:9559)
```

- **server.py** 运行在 `naoqi` (Python 2.7) 环境中，加载 NAOqi SDK，将
  `ALMotion` / `ALRobotPosture` / `ALTextToSpeech` / `ALAnimatedSpeech` /
  `ALSpeechRecognition` / `ALMemory` 封装为若干"服务对象"，通过本地 TCP
  socket 以 JSON-RPC 的形式暴露出来。
- **client.py** 是一个仅依赖标准库的 Python 3 模块（不依赖 NAOqi）。
  LLM/VLM agent 进程导入它来发送指令，例如
  `nao.motion.go_to_posture(posture_name="StandInit")`。
- 双方仅使用 Python 2.7 / 3 标准库中的 `socket` + `json` —— 不需要额外依赖
  （不需要 Flask / ZeroMQ / gRPC）。

## 快速开始

### 1. 启动桥接服务端（在 naoqi / py2.7 环境中）

不需要机器人，先用 mock 模式验证链路：

```bash
cd NaoQi_SDK_Bridge
./run_server.sh --mock
```

连接真实机器人：

```bash
./run_server.sh --nao-ip 192.168.1.101 --nao-port 9559
```

`run_server.sh` 会自动完成以下工作：
- 将 NAOqi SDK 的 Python 绑定目录（`naoqi` / `_inaoqi.so` / `qi` 所在目录；
  默认为 `/home/sgzg/Naoqi_SDK/lib/python2.7/site-packages`，可通过环境变量
  `NAOQI_SDK_PYTHONPATH` 覆盖）加入 `PYTHONPATH`；
- 执行 `conda activate naoqi`（conda 根目录与环境名可通过 `CONDA_ROOT` /
  `NAOQI_CONDA_ENV` 覆盖）；
- 运行 `nao_bridge/server.py`。

默认监听 `127.0.0.1:5050`，**仅绑定本机**。如果你的 LLM/VLM 进程跑在另一台
机器上，请不要直接把 `--host` 改成 `0.0.0.0` 并暴露到网络上，而是使用 SSH
隧道（`ssh -L 5050:127.0.0.1:5050 ...`），因为该协议目前没有任何鉴权机制。

### 2. 从 Python 3 调用（任意 py3 环境，如 `python312`）

```python
import sys
sys.path.insert(0, "/path/to/NaoQi_SDK_Bridge")  # 仓库根目录，使 nao_bridge 可被导入

from nao_bridge.client import NaoBridgeClient

nao = NaoBridgeClient(host="127.0.0.1", port=5050)

nao.motion.wake_up()
nao.motion.go_to_posture(posture_name="StandInit")
nao.speech.say(text="Hello, I am NAO")

angles = nao.motion.get_joint_angles(joints=["HeadYaw", "HeadPitch"])
print(angles)  # {"joints": [...], "angles_deg": [...]}
```

一个完整可运行的示例（包含 LLM 工具/函数调用 schema）位于
`examples/llm_agent_demo.py`，具体用法见该文件开头的 docstring。

## RPC 方法一览

所有调用遵循 `client.<namespace>.<method>(**kwargs)` 的形式，对应服务端的
`registry[namespace].<method>(**kwargs)`。可通过
`client.system.list_methods()` 在运行时查询当前可用的方法。

### `motion.*`（ALMotion / ALRobotPosture，角度单位均为**度**）

| 方法 | 说明 |
| --- | --- |
| `wake_up()` | 上电 / 进入可控状态 |
| `rest()` | 进入休息姿态，放松关节 |
| `is_awake()` | 机器人是否处于唤醒状态 |
| `get_posture()` | 当前姿态分类（如 "Standing"） |
| `go_to_posture(posture_name, speed=0.5)` | 切换到指定姿态（"StandInit"/"Sit"/...） |
| `list_joints(chain="Body")` | 列出指定运动链的关节名称 |
| `get_joint_angles(joints="Body", use_sensors=True)` | 读取关节角度（度） |
| `set_joint_angles(joints, angles_deg, speed=0.1)` | 非阻塞地以最大速度的一定比例移动到目标角度 |
| `move_joints(joints, angles_deg, durations_sec, absolute=True)` | 阻塞式插值运动（`ALMotion.angleInterpolation`），支持多个路径点 |
| `set_stiffness(joints, value)` | 设置关节刚度 0~1 |
| `walk_to(x, y, theta=0.0)` | 相对位置行走 |
| `stop_walk()` | 停止行走 |

### `speech.*`（ALTextToSpeech / ALAnimatedSpeech / ALSpeechRecognition / ALMemory）

| 方法 | 说明 |
| --- | --- |
| `say(text, mode="animated", body_language_mode="contextual")` | 朗读文本；`mode="tts"` 时使用纯 `ALTextToSpeech` |
| `set_language(language)` | 同时设置 TTS 和 ASR 的语言 |
| `set_volume(volume)` | 设置 TTS 音量 |
| `asr_set_vocabulary(words, word_spotting=True)` | 设置语音识别词表 |
| `asr_subscribe()` / `asr_unsubscribe()` | 开启/关闭语音识别 |
| `asr_get_last_recognized()` | 从 `ALMemory` 读取最近识别到的词及置信度 |

`ALAnimatedSpeech` / `ALSpeechRecognition` / `ALMemory` 均为可选代理：如果
机器人/SDK 未提供，对应字段为 `None`；`say()` 会自动回退到
`ALTextToSpeech`，ASR 相关方法会抛出明确的错误信息。

### `system.*`

| 方法 | 说明 |
| --- | --- |
| `ping()` | 连通性检查 |
| `list_methods()` | 列出当前可用的 `motion.*` / `speech.*` 方法 |

## Mock 模式

`--mock` 模式下，服务端无需机器人、也无需 NAOqi SDK，使用内存中的假
`MotionService` / `SpeechService`（即 `nao_bridge/services/motion.py` /
`nao_bridge/services/speech.py` 中的 `MockMotionService` /
`MockSpeechService`）。这样可以：

- 在没有机器人的情况下开发/调试 LLM/VLM agent 逻辑；
- 在切换到真实机器人之前，先验证 JSON-RPC 链路和参数格式是否正确。

## 扩展指引

- **新增能力（例如为 VLM 添加摄像头/视觉）**：在 `nao_bridge/services/` 下
  新建一个模块（如 `vision.py`），实现 `VisionService`（封装
  `ALVideoDevice`，例如提供返回 base64 编码 JPEG 的 `get_frame_jpeg()`）以及
  对应的 `MockVisionService`，然后在 `server.py` 的 `build_registry()` 中注册
  为 `registry["vision"] = ...`。Python 3 端无需任何改动——
  `client.vision.get_frame_jpeg()` 会自动可用（`_RemoteNamespace` 是动态
  分发的）。
- **新增单个方法**：只需在相应的 service 类中添加一个公开方法。
  `server.py` 中的分发器会通过反射自动暴露该方法，
  `client.system.list_methods()` 也会列出它。
- **多机器人 / 多服务端**：每个 `NaoBridgeClient(host=..., port=...)`
  对应一个服务端进程——为每个机器人使用不同的端口即可。

## 已知限制 / 后续可做

- 协议没有任何鉴权机制——只应在本机使用，或通过 SSH 隧道访问。
- 每次 RPC 调用都会新建一个 TCP 连接（实现简单，对低频指令足够；如果未来
  需要高频关节流式控制，可以再加一个长连接 + 流式协议）。
- 摄像头/视觉（VLM 所需）尚未实现——按照上面"扩展指引"中的方式新增
  `vision.py` 即可。
