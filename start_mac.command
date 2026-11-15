#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "===================================="
echo " Retail Analytics Lab · Mac 실행"
echo "===================================="
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3가 없습니다. 먼저 https://www.python.org/downloads/ 를 참고하세요."
  exit 1
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
