#!/usr/bin/env bash
# Hermes v3 setup — Arch Linux
set -e
GREEN='\033[0;32m'; BOLD='\033[1m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}▶${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $1"; }
title() { echo -e "\n${BOLD}${CYAN}$1${NC}"; }
DIR="$(cd "$(dirname "$0")" && pwd)"

title "=== Hermes v3 Setup ==="
echo "  LLM:     NousResearch/Hermes-3-Llama-3.1-8B (4-bit NF4)"
echo "  Embed:   BAAI/bge-m3"
echo "  Rerank:  BAAI/bge-reranker-v2-m3"
echo "  Retrieval: Hybrid BM25 + Dense + Rerank"

title "1. GPU check"
if command -v nvidia-smi &>/dev/null; then
  info "$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)"
else
  warn "nvidia-smi not found — install NVIDIA drivers: sudo pacman -S nvidia nvidia-utils"
fi

title "2. Python venv"
cd "$DIR/backend"
python3 -m venv .venv
source .venv/bin/activate

title "3. PyTorch (CUDA 12.1)"
if python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  info "PyTorch + CUDA already installed"
else
  info "Installing PyTorch with CUDA 12.1…"
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 -q
fi

title "4. Python dependencies"
pip install -r requirements.txt -q
info "All dependencies installed"

title "5. Model download"
echo ""
echo "  Models needed (~6.5GB total):"
echo "    BAAI/bge-m3             ~570MB"
echo "    BAAI/bge-reranker-v2-m3 ~570MB"
echo "    Hermes-3-Llama-3.1-8B   ~5.5GB"
echo ""
read -rp "  Download now? [y/N]: " DL
if [[ "$DL" =~ ^[Yy]$ ]]; then
  python3 -c "
from FlagEmbedding import BGEM3FlagModel, FlagReranker
print('Downloading bge-m3...')
BGEM3FlagModel('BAAI/bge-m3', cache_dir='./models', use_fp16=False)
print('Downloading bge-reranker-v2-m3...')
FlagReranker('BAAI/bge-reranker-v2-m3', cache_dir='./models', use_fp16=False)
print('Downloading Hermes-3 (this takes a while)...')
from huggingface_hub import snapshot_download
snapshot_download('NousResearch/Hermes-3-Llama-3.1-8B', cache_dir='./models')
print('All models downloaded.')
"
fi
deactivate

title "6. Frontend"
cd "$DIR/frontend"
if ! command -v node &>/dev/null; then
  warn "Node.js not found: sudo pacman -S nodejs npm"
else
  npm install --silent
  info "Frontend ready"
fi

title "7. Data directories"
cd "$DIR"
mkdir -p backend/data/conversations backend/data/chroma \
         backend/models finetune/adapters
info "Directories created"

title "8. HuggingFace token (optional — for gated models)"
read -rp "  HF token (Enter to skip): " HF_TOKEN
if [[ -n "$HF_TOKEN" ]]; then
  cd "$DIR/backend" && source .venv/bin/activate
  python3 -c "from huggingface_hub import login; login(token='$HF_TOKEN'); print('HF login ok')"
  deactivate
fi

title "✓ Done!"
echo ""
echo "  Run:  bash start.sh"
echo "  URL:  http://localhost:5173"
echo "  Docs: http://localhost:8000/docs"
