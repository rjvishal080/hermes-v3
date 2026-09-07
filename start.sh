#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
GREEN='\033[0;32m'; BOLD='\033[1m'; NC='\033[0m'

launch() {
  local title="$1"; shift
  if command -v kitty &>/dev/null; then
    kitty --title "$title" bash -c "$*; read -rp 'Press Enter…'" &
  else
    eval "$*" &>/tmp/hermes-$(echo "$title" | tr ' ' '-').log &
  fi
}

echo -e "${BOLD}Starting Hermes v3…${NC}"

launch "Hermes v3 — Backend" "
  cd '$DIR/backend'
  source .venv/bin/activate
  export HERMES_MODEL='NousResearch/Hermes-3-Llama-3.1-8B'
  export HERMES_EMBED_MODEL='BAAI/bge-m3'
  export HERMES_RERANK_MODEL='BAAI/bge-reranker-v2-m3'
  export HERMES_DATA_DIR='./data'
  export HERMES_MODELS_DIR='./models'
  python main.py
"

sleep 3

launch "Hermes v3 — Frontend" "
  cd '$DIR/frontend'
  npm run dev
"

sleep 2
echo ""
echo -e "  ${GREEN}Frontend${NC}  → http://localhost:5173"
echo -e "  ${GREEN}API docs${NC}  → http://localhost:8000/docs"
echo -e "  ${GREEN}Health${NC}    → http://localhost:8000/api/health"
echo ""
echo "  Models loading into VRAM (~60s). Watch status bar in Chat."
echo ""
command -v xdg-open &>/dev/null && sleep 5 && xdg-open http://localhost:5173 &
