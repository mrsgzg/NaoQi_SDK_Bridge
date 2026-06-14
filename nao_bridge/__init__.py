"""nao_bridge: JSON-RPC bridge between NAOqi (Python 2.7) and Python 3.

The server side (server.py) runs inside the `naoqi` Python 2.7 conda
environment and talks to the robot via the NAOqi SDK (ALProxy). The
client side (client.py) is plain Python 3 with no NAOqi dependency, so
it can run alongside LLM/VLM code in any modern environment.
"""
