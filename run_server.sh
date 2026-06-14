#!/usr/bin/env bash
# Launch the nao_bridge server inside the `naoqi` (Python 2.7) conda env,
# with the NAOqi SDK on PYTHONPATH.
#
# Usage:
#   ./run_server.sh --mock                       # no robot needed
#   ./run_server.sh --nao-ip 192.168.1.101       # talk to a real robot
#
# Override paths for your own machine via environment variables:
#   NAOQI_SDK_PYTHONPATH   default: /home/sgzg/Naoqi_SDK/lib/python2.7/site-packages
#   CONDA_ROOT             default: ${HOME}/miniconda3
#   NAOQI_CONDA_ENV        default: naoqi
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAOQI_SDK_PYTHONPATH="${NAOQI_SDK_PYTHONPATH:-/home/sgzg/Naoqi_SDK/lib/python2.7/site-packages}"
CONDA_ROOT="${CONDA_ROOT:-${HOME}/miniconda3}"
NAOQI_CONDA_ENV="${NAOQI_CONDA_ENV:-naoqi}"

export PYTHONPATH="${NAOQI_SDK_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}"

source "${CONDA_ROOT}/etc/profile.d/conda.sh"
conda activate "${NAOQI_CONDA_ENV}"

exec python "${SCRIPT_DIR}/nao_bridge/server.py" "$@"
