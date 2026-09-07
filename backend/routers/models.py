"""
routers/models.py
Model management endpoints — switch LLMs, load LoRA adapters, check VRAM.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

AVAILABLE_MODELS = [
    {
        "id":     "NousResearch/Hermes-3-Llama-3.1-8B",
        "name":   "Hermes 3 (8B)",
        "desc":   "Best for agentic tasks, tool use, structured output. Recommended.",
        "vram":   "~5.5GB",
        "recommended": True,
    },
    {
        "id":     "Qwen/Qwen2.5-7B-Instruct",
        "name":   "Qwen 2.5 (7B)",
        "desc":   "Best instruction following at 7B. Great JSON output. Good alternative.",
        "vram":   "~4.5GB",
        "recommended": False,
    },
    {
        "id":     "mistralai/Mistral-7B-Instruct-v0.3",
        "name":   "Mistral 7B v0.3",
        "desc":   "Fast, solid reasoning. Lighter on VRAM.",
        "vram":   "~4.1GB",
        "recommended": False,
    },
    {
        "id":     "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "name":   "Llama 3.1 (8B)",
        "desc":   "128k context, good tool use. Requires HF gated access approval.",
        "vram":   "~5.5GB",
        "recommended": False,
        "gated": True,
    },
    {
        "id":     "microsoft/Phi-3.5-mini-instruct",
        "name":   "Phi 3.5 Mini (3.8B)",
        "desc":   "Smallest option. Good for low VRAM situations.",
        "vram":   "~2.5GB",
        "recommended": False,
    },
]


class SwitchModelRequest(BaseModel):
    model_id: str
    lora_adapter_path: Optional[str] = None


class HFTokenRequest(BaseModel):
    token: str


@router.get("")
def list_models():
    from engine.llm import get_model_info
    current = get_model_info()
    for m in AVAILABLE_MODELS:
        m["active"] = current.get("model_id") == m["id"]
    return {"models": AVAILABLE_MODELS, "current": current}


@router.post("/switch")
def switch_model(req: SwitchModelRequest):
    """Hot-swap the loaded LLM. Unloads current, loads new one."""
    import os
    if req.lora_adapter_path:
        os.environ["HERMES_LORA"] = req.lora_adapter_path
    else:
        os.environ["HERMES_LORA"] = ""

    from engine.llm import load_model
    load_model(req.model_id, force_reload=True)
    from engine.llm import get_model_info
    return {"message": f"Switched to {req.model_id}", "info": get_model_info()}


@router.get("/vram")
def vram_status():
    from engine.llm import get_vram_usage
    import torch
    info = {"vram_summary": get_vram_usage()}
    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        info["gpu_name"]   = props.name
        info["total_vram"] = f"{props.total_memory / 1e9:.1f}GB"
        info["used_vram"]  = f"{torch.cuda.memory_allocated() / 1e9:.2f}GB"
        info["free_vram"]  = f"{(props.total_memory - torch.cuda.memory_allocated()) / 1e9:.2f}GB"
    return info


@router.post("/hf-login")
def hf_login(req: HFTokenRequest):
    """Save HuggingFace token for gated model access (Llama etc.)"""
    from huggingface_hub import login
    try:
        login(token=req.token)
        return {"message": "Logged in to HuggingFace"}
    except Exception as e:
        return {"error": str(e)}
