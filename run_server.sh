#!/usr/bin/env bash
set -e
python3 -m venv .venv || true
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python server.py
