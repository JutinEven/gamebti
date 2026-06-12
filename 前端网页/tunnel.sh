#!/bin/bash
# Gamebti 隧道守护脚本 — 断开自动重连
# 用法: bash tunnel.sh

while true; do
  echo "[$(date '+%H:%M:%S')] Starting tunnel..."
  npx --yes localtunnel --port 3000 2>&1
  echo "[$(date '+%H:%M:%S')] Tunnel died, restarting in 3s..."
  sleep 3
done
