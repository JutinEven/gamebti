#!/bin/bash

set -e
# 导出环境变量

WORK_DIR="${AGENT_WORKSPACE:-.}"
PORT="${DEPLOY_RUN_PORT:-5000}"

usage() {
  echo "用法: $0 -p <端口>"
}

while getopts "p:h" opt; do
  case "$opt" in
    p)
      PORT="$OPTARG"
      ;;
    h)
      usage
      exit 0
      ;;
    \?)
      echo "无效选项: -$OPTARG"
      usage
      exit 1
      ;;
  esac
done

# 激活 .venv，兼容 Linux/macOS 和 Windows (Git Bash)
if [ -f "${WORK_DIR}/.venv/bin/activate" ]; then
  source "${WORK_DIR}/.venv/bin/activate"
elif [ -f "${WORK_DIR}/.venv/Scripts/activate" ]; then
  source "${WORK_DIR}/.venv/Scripts/activate"
fi

python ${WORK_DIR}/src/main.py -m http -p $PORT
