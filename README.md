# NaoQi_SDK_bridge

把 NAOqi（只支持 Python 2.7）和 LLM/VLM 等 Python 3 代码连接起来的最小桥接层。

## 目录结构

```
NaoQi_SDK_bridge/
├── nao_bridge/              # Python 包：JSON-RPC 协议、server、client、各服务封装
│   ├── protocol.py
│   ├── server.py            # 跑在 naoqi(py2.7) 环境
│   ├── client.py            # 纯标准库 py3 客户端 NaoBridgeClient
│   └── services/
│       ├── motion.py        # ALMotion / ALRobotPosture
│       ├── speech.py        # ALTextToSpeech / ALAnimatedSpeech / ALSpeechRecognition
│       └── system_service.py
├── examples/
│   └── llm_agent_demo.py     # py3 示例，含 LLM tool/function-calling schema
├── run_server.sh             # 一键 conda activate naoqi + 设置 PYTHONPATH + 启动 server
└── README.md
```

## 架构

```
+-----------------------------+        TCP / JSON-RPC        +----------------------------------+
| naoqi conda env (Python 2.7)|  <------------------------>  | 任意 Python 3 环境 (如 python312) |
|                              |   127.0.0.1:5050 (default)   |                                  |
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

- **server.py** 跑在 `naoqi`（Python 2.7）环境里，加载 NAOqi SDK，把 `ALMotion` /
  `ALRobotPosture` / `ALTextToSpeech` / `ALAnimatedSpeech` / `ALSpeechRecognition` /
  `ALMemory` 封装成几个"服务对象"，通过本地 TCP socket 提供 JSON-RPC 接口。
- **client.py** 是纯标准库的 Python 3 模块（无 NAOqi 依赖），LLM/VLM agent 进程
  import 它来发指令，例如 `nao.motion.go_to_posture(posture_name="StandInit")`。
- 两端只用 Python 2.7 / 3 都自带的 `socket` + `json`，没有额外依赖（不需要
  Flask/ZeroMQ/gRPC）。

## 快速开始

### 1. 启动桥接 server（在 naoqi / py2.7 环境里）

无需真机，用 mock 模式先验证链路：

```bash
cd NaoQi_SDK_bridge
./run_server.sh --mock
```

连接真机：

```bash
./run_server.sh --nao-ip 192.168.1.101 --nao-port 9559
```

`run_server.sh` 会自动：
- 把 NAOqi SDK 的 Python 绑定（`naoqi` / `_inaoqi.so` / `qi` 所在目录，默认
  `/home/sgzg/Naoqi_SDK/lib/python2.7/site-packages`，可用环境变量
  `NAOQI_SDK_PYTHONPATH` 覆盖）加到 `PYTHONPATH`；
- `conda activate naoqi`（conda 根目录、env 名也可分别用 `CONDA_ROOT` /
  `NAOQI_CONDA_ENV` 覆盖）；
- 运行 `nao_bridge/server.py`。

默认监听 `127.0.0.1:5050`，**只绑定本机**。如果 LLM/VLM 进程跑在另一台机器上，
不要直接把 `--host` 改成 `0.0.0.0` 暴露到网络上——优先用 SSH 隧道
（`ssh -L 5050:127.0.0.1:5050 ...`），因为这个协议目前没有鉴权。

### 2. 从 Python 3 调用（在任意 py3 环境，如 python312）

```python
import sys
sys.path.insert(0, "/path/to/NaoQi_SDK_bridge")  # 仓库根目录，让 `nao_bridge` 包可被 import

from nao_bridge.client import NaoBridgeClient

nao = NaoBridgeClient(host="127.0.0.1", port=5050)

nao.motion.wake_up()
nao.motion.go_to_posture(posture_name="StandInit")
nao.speech.say(text="你好，我是 NAO")

angles = nao.motion.get_joint_angles(joints=["HeadYaw", "HeadPitch"])
print(angles)  # {"joints": [...], "angles_deg": [...]}
```

完整可运行示例（含给 LLM 用的 tool/function-calling schema）：
`examples/llm_agent_demo.py`，用法见文件头注释。

## RPC 方法一览

调用方式都是 `client.<namespace>.<method>(**kwargs)`，对应 server 端
`registry[namespace].<method>(**kwargs)`。可以用 `client.system.list_methods()`
在线查询当前都有哪些方法。

### `motion.*`（ALMotion / ALRobotPosture，角度单位为**度**）

| 方法 | 说明 |
| --- | --- |
| `wake_up()` | 上电、进入可控状态 |
| `rest()` | 进入休息姿态、放松关节 |
| `is_awake()` | 是否已唤醒 |
| `get_posture()` | 当前姿态族（如 "Standing"） |
| `go_to_posture(posture_name, speed=0.5)` | 切换到预设姿态（"StandInit"/"Sit"/...） |
| `list_joints(chain="Body")` | 列出某条链上的关节名 |
| `get_joint_angles(joints="Body", use_sensors=True)` | 读取关节角度（度） |
| `set_joint_angles(joints, angles_deg, speed=0.1)` | 非阻塞，按比例速度移动到目标角度 |
| `move_joints(joints, angles_deg, durations_sec, absolute=True)` | 阻塞式插值运动（`ALMotion.angleInterpolation`），可传多个航点 |
| `set_stiffness(joints, value)` | 设置关节硬度 0~1 |
| `walk_to(x, y, theta=0.0)` | 相对位移行走 |
| `stop_walk()` | 停止行走 |

### `speech.*`（ALTextToSpeech / ALAnimatedSpeech / ALSpeechRecognition / ALMemory）

| 方法 | 说明 |
| --- | --- |
| `say(text, mode="animated", body_language_mode="contextual")` | 朗读文本；`mode="tts"` 走纯 `ALTextToSpeech` |
| `set_language(language)` | 同时设置 TTS 和 ASR 语言 |
| `set_volume(volume)` | 设置 TTS 音量 |
| `asr_set_vocabulary(words, word_spotting=True)` | 设置语音识别词表 |
| `asr_subscribe()` / `asr_unsubscribe()` | 开始/停止语音识别 |
| `asr_get_last_recognized()` | 读取 `ALMemory` 里最近识别到的词和置信度 |

`ALAnimatedSpeech` / `ALSpeechRecognition` / `ALMemory` 是可选代理：如果机器人/SDK
不提供，对应字段为 `None`；`say()` 会自动降级为 `ALTextToSpeech`，ASR 相关方法
会抛出明确的错误。

### `system.*`

| 方法 | 说明 |
| --- | --- |
| `ping()` | 连通性检查 |
| `list_methods()` | 列出 `motion.*` / `speech.*` 当前有哪些方法 |

## Mock 模式

`--mock` 让 server 不连真机、不依赖 NAOqi SDK，用内存里的假 `MotionService` /
`SpeechService`（`nao_bridge/services/motion.py` / `nao_bridge/services/speech.py`
里的 `MockMotionService` / `MockSpeechService`）。这让你可以：

- 在没有机器人时开发/调试 LLM/VLM agent 逻辑；
- 验证 JSON-RPC 链路、参数格式是否正确，再切到真机。

## 扩展指引

- **新增能力（如摄像头/视觉给 VLM 用）**：在 `nao_bridge/services/` 下新建一个模块
  （例如 `vision.py`），写一个 `VisionService`（包一层 `ALVideoDevice`，
  比如 `get_frame_jpeg()` 返回 base64 编码的 JPEG）和对应的 `MockVisionService`，
  然后在 `server.py` 的 `build_registry()` 里注册成 `registry["vision"] = ...`。
  Python 3 端不用改 `client.py`——`client.vision.get_frame_jpeg()` 会自动可用
  （`_RemoteNamespace` 是动态分发的）。
- **新增单个方法**：直接在对应 Service 类上加一个公开方法即可，`server.py`
  的 dispatcher 通过反射自动暴露它，`client.system.list_methods()` 也会自动列出。
- **多机器人 / 多 server**：每个 `NaoBridgeClient(host=..., port=...)` 对应一个
  server 进程，给不同机器人起不同端口即可。

## 已知限制 / 后续可做

- 协议没有鉴权，仅适合本机或经 SSH 隧道使用。
- 每次 RPC 调用都新建一条 TCP 连接（简单、对低频指令足够；如果以后要做
  高频关节流控制，可以加一个常驻连接 + 流式协议）。
- 摄像头/视觉（VLM 用）尚未实现，按上面"扩展指引"加 `vision.py` 即可。
