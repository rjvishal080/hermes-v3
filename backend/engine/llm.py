import os, json, threading, requests
from typing import Generator

OLLAMA_BASE  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("HERMES_MODEL", "qwen2.5-coder:7b")
MAX_TOKENS   = int(os.getenv("HERMES_MAX_TOKENS", "1024"))
TEMPERATURE  = float(os.getenv("HERMES_TEMP", "0.7"))
_ready = False
_lock  = threading.Lock()

def load_model(*a, **kw):
    global _ready
    with _lock:
        try:
            r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            _ready = any(OLLAMA_MODEL.split(":")[0].split("/")[-1].lower() in m.lower() for m in models)
            print(f"[Engine] Ollama {'ready' if _ready else 'WARNING: model not found'}")
        except Exception as e:
            print(f"[Engine] Ollama unreachable: {e}")

def get_model_info() -> dict:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return {"loaded": _ready, "model_id": OLLAMA_MODEL, "backend": "ollama",
                "all_models": [m["name"] for m in r.json().get("models", [])]}
    except:
        return {"loaded": False, "model_id": OLLAMA_MODEL, "backend": "ollama"}

def get_vram_usage() -> str:
    try:
        import subprocess
        r = subprocess.run(["nvidia-smi","--query-gpu=memory.used,memory.total",
                           "--format=csv,noheader,nounits"],
                          capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            used, total = r.stdout.strip().split(", ")
            return f"VRAM: {int(used)/1024:.1f}GB / {int(total)/1024:.1f}GB"
    except: pass
    return "VRAM: unknown"

def stream_generate(system, messages, max_new_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE, top_p=0.9, **kw) -> Generator[str, None, None]:
    msgs = []
    if system: msgs.append({"role": "system", "content": system})
    msgs.extend(messages)
    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": msgs, "stream": True,
                  "options": {"temperature": temperature, "top_p": top_p,
                             "num_predict": max_new_tokens,
                             **({"stop": kw["stop"]} if kw.get("stop") else {})}},
            stream=True, timeout=120
        )
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.strip():
                continue
            try:
                chunk = json.loads(line.strip())
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done", False):
                    break
            except json.JSONDecodeError as e:
                print(f"[LLM] JSON error: {e} | line: {repr(line[:100])}")
                continue
    except Exception as e:
        print(f"[LLM] stream_generate error: {e}")
        yield f"Error: {e}"

def generate(system, messages, max_new_tokens=MAX_TOKENS, temperature=0.3, **kw) -> str:
    return "".join(stream_generate(system, messages, max_new_tokens, temperature, **kw))
