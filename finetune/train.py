"""
finetune/train.py
─────────────────────────────────────────────────────────────────────────────
QLoRA fine-tuning of Hermes-3 on YOUR personal data.
Uses unsloth for 2x faster training, fits in 6GB VRAM.

What this does:
  1. Loads your conversation history + memories + profile
  2. Generates synthetic training pairs (Q&A about your life)
  3. Fine-tunes with QLoRA on this data
  4. Saves LoRA adapter (~200MB, not the full 8B model)
  5. Hermes loads the adapter on top of the base model

Run:
  python finetune/train.py
  python finetune/train.py --epochs 3 --base-model Qwen/Qwen2.5-7B-Instruct

After training:
  Set HERMES_LORA=./finetune/adapters/hermes-personal in .env
  or switch via API: POST /api/models/switch
"""

import argparse
import json
import os
import sys
import datetime
from pathlib import Path

DATA_DIR    = Path(os.getenv("HERMES_DATA_DIR",    "../data"))
ADAPTERS_DIR = Path(__file__).parent / "adapters"
MODELS_DIR  = Path(os.getenv("HERMES_MODELS_DIR", "../models"))
ADAPTERS_DIR.mkdir(exist_ok=True)


# ── Dataset builder ───────────────────────────────────────────────────────────
def load_all_data() -> dict:
    """Load profile + memories + conversations."""
    profile_path = DATA_DIR / "profile.json"
    profile = {}
    if profile_path.exists():
        with open(profile_path) as f:
            profile = json.load(f)

    # Load all conversation history
    conversations = []
    for p in sorted((DATA_DIR / "conversations").glob("*.jsonl")):
        lines = p.read_text().strip().split("\n")
        msgs  = [json.loads(l) for l in lines if l.strip()]
        if len(msgs) >= 2:
            conversations.append(msgs)

    return {"profile": profile, "conversations": conversations}


def build_training_samples(data: dict) -> list[dict]:
    """
    Build ChatML format training samples from personal data.
    Three types:
      1. Direct conversation pairs (from history)
      2. Profile Q&A (synthetic but grounded in real data)
      3. Memory recall (teach model to know your facts)
    """
    samples = []
    profile = data["profile"]
    name    = profile.get("name", "User")

    SYSTEM = f"""You are Hermes, a deeply personal AI that knows {name} intimately.
You have access to their memories, finances, academics, health, and life events.
You speak like someone who genuinely knows and cares about this person."""

    # Type 1: Real conversation pairs
    for conv in data["conversations"]:
        turns = []
        for msg in conv:
            turns.append({"role": msg["role"], "content": msg["content"]})
        if turns:
            samples.append({"system": SYSTEM, "messages": turns})

    # Type 2: Profile Q&A (synthetic)
    a = profile.get("academic", {})
    f = profile.get("finances", {})
    h = profile.get("health", {})

    qa_pairs = []

    if a.get("cgpa"):
        qa_pairs.append((
            f"What's my CGPA?",
            f"Your CGPA is {a['cgpa']} at {a.get('college', 'your college')}, currently in semester {a.get('semester', '?')}."
        ))
    if a.get("courses"):
        qa_pairs.append((
            "What courses am I taking this semester?",
            f"You're taking {', '.join(a['courses'])} this semester."
        ))
    if a.get("attendance"):
        low = [(s, v) for s, v in a["attendance"].items() if float(v) < 75]
        if low:
            qa_pairs.append((
                "Which subjects have low attendance?",
                f"You have attendance below 75% in: {', '.join([f'{s} ({v}%)' for s, v in low])}. This needs attention."
            ))
    if f.get("categories"):
        top = list(f["categories"].items())[:3]
        qa_pairs.append((
            "Where am I spending the most money?",
            f"Your top spending categories are: {', '.join([f'{k} (₹{int(v)})' for k,v in top])}."
        ))
    if h.get("sleep_avg_hrs"):
        qa_pairs.append((
            "How's my sleep?",
            f"You're averaging {h['sleep_avg_hrs']} hours of sleep per night."
        ))
    if profile.get("goals"):
        qa_pairs.append((
            "What are my goals?",
            f"Your current goals are: {', '.join(profile['goals'])}."
        ))

    for q, a_text in qa_pairs:
        samples.append({
            "system": SYSTEM,
            "messages": [
                {"role": "user",      "content": q},
                {"role": "assistant", "content": a_text},
            ]
        })

    print(f"[Finetune] Built {len(samples)} training samples ({len(data['conversations'])} real convos + {len(qa_pairs)} synthetic Q&A)")
    return samples


def format_chatml(sample: dict) -> str:
    """Format a sample into ChatML string for training."""
    parts = [f"<|im_start|>system\n{sample['system']}<|im_end|>"]
    for msg in sample["messages"]:
        parts.append(f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>")
    return "\n".join(parts) + "\n"


# ── Training ──────────────────────────────────────────────────────────────────
def train(
    base_model:  str = "NousResearch/Hermes-3-Llama-3.1-8B",
    epochs:      int = 2,
    batch_size:  int = 1,       # gradient accumulation handles effective batch
    grad_accum:  int = 4,
    lr:          float = 2e-4,
    max_seq_len: int = 2048,
    output_name: str = "hermes-personal",
):
    try:
        from unsloth import FastLanguageModel
        import torch
        from trl import SFTTrainer
        from transformers import TrainingArguments
        from datasets import Dataset
    except ImportError:
        print("ERROR: Fine-tuning dependencies not installed.")
        print("Run: pip install unsloth trl datasets peft")
        sys.exit(1)

    print(f"[Finetune] Loading base model: {base_model}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model,
        max_seq_length=max_seq_len,
        dtype=None,              # auto (bfloat16 on Ampere)
        load_in_4bit=True,
        cache_dir=str(MODELS_DIR),
    )

    # QLoRA config — tuned for 6GB VRAM
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,                    # rank — higher = more expressive, more VRAM
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",   # saves VRAM
        random_state=42,
    )

    # Build dataset
    data     = load_all_data()
    samples  = build_training_samples(data)

    if len(samples) < 5:
        print("WARNING: Very few training samples. Chat more with Hermes and ingest more data first.")
        print(f"Current samples: {len(samples)}")

    texts   = [format_chatml(s) for s in samples]
    dataset = Dataset.from_dict({"text": texts})

    output_dir = ADAPTERS_DIR / output_name
    output_dir.mkdir(exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=max_seq_len,
        dataset_num_proc=2,
        args=TrainingArguments(
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=grad_accum,
            warmup_steps=5,
            num_train_epochs=epochs,
            learning_rate=lr,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            output_dir=str(output_dir / "checkpoints"),
            report_to="none",
        ),
    )

    print(f"[Finetune] Training for {epochs} epochs on {len(samples)} samples...")
    print(f"[Finetune] This will take ~{len(samples) * epochs // 10} minutes on RTX 3050")
    trainer.train()

    # Save LoRA adapter only (~200MB vs 16GB for full model)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # Save metadata
    meta = {
        "base_model":    base_model,
        "trained_at":    datetime.datetime.utcnow().isoformat(),
        "epochs":        epochs,
        "samples":       len(samples),
        "adapter_path":  str(output_dir),
    }
    with open(output_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n[Finetune] ✓ Done! Adapter saved to: {output_dir}")
    print(f"[Finetune] To use it, set in .env:")
    print(f"  HERMES_LORA={output_dir}")
    print(f"Or switch via API: POST /api/models/switch with lora_adapter_path")
    return str(output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune Hermes on your personal data")
    parser.add_argument("--base-model", default="NousResearch/Hermes-3-Llama-3.1-8B")
    parser.add_argument("--epochs",     type=int,   default=2)
    parser.add_argument("--lr",         type=float, default=2e-4)
    parser.add_argument("--output",     default="hermes-personal")
    args = parser.parse_args()

    train(
        base_model=args.base_model,
        epochs=args.epochs,
        lr=args.lr,
        output_name=args.output,
    )
