#!/bin/bash
cd /app && uv run python src/main.py -m http -p "${PORT:-5000}"
