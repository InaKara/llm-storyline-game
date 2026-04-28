# Local Image Generation Setup Guide

## FLUX.1-schnell via HuggingFace `diffusers` on Windows (RTX 4060 Laptop)

---

## Hardware Requirements

| Component | Minimum | Recommended (this machine) |
|-----------|---------|---------------------------|
| GPU VRAM | 6 GB | 8 GB (RTX 4060 Laptop) ✓ |
| System RAM | 16 GB | 32 GB ✓ |
| Disk space | ~25 GB for model cache | SSD preferred |
| CUDA support | sm_80+ (Ampere+) | sm_89 (Ada Lovelace) ✓ |

**Note on VRAM:** FLUX.1-schnell in `bfloat16` is ~12 GB when fully loaded onto the GPU. With `enable_model_cpu_offload()` (recommended), the model is split between VRAM and system RAM during inference — your 32 GB system RAM handles the overflow. Expect ~15–30 seconds per image at 1024×1024.

---

## 1. Check GPU Driver and CUDA Version

Open PowerShell and verify your NVIDIA driver is installed:

```powershell
nvidia-smi
```

You should see your GPU listed and a `CUDA Version` in the top-right corner. Any version ≥ 12.1 is sufficient. If `nvidia-smi` is not found, install the latest NVIDIA Game Ready or Studio driver from [nvidia.com/drivers](https://www.nvidia.com/drivers).

---

## 2. Install PyTorch with CUDA Support

PyTorch ships its own bundled CUDA runtime — you do **not** need to install the CUDA Toolkit separately for inference.

**In your project virtual environment:**

```powershell
# Activate your venv first
.\.venv\Scripts\Activate.ps1

# Install PyTorch with CUDA 12.4 (covers RTX 4060 and all Ada Lovelace GPUs)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

Verify the install:

```python
import torch
print(torch.cuda.is_available())          # should print: True
print(torch.cuda.get_device_name(0))      # should print: NVIDIA GeForce RTX 4060 Laptop GPU
print(torch.cuda.get_device_properties(0).total_memory // 1024**3, "GB")  # should print: 8
```

---

## 3. Install `diffusers` and Dependencies

```powershell
pip install diffusers>=0.30 transformers accelerate sentencepiece protobuf
```

| Package | Purpose |
|---------|---------|
| `diffusers` | HuggingFace pipeline for FLUX and SDXL |
| `transformers` | Text encoders (CLIP, T5) used by FLUX |
| `accelerate` | Enables CPU offload and device management |
| `sentencepiece` | Required by FLUX's T5 tokenizer |
| `protobuf` | Required by some tokenizer variants |

---

## 4. Download the FLUX.1-schnell Model

The model weights are downloaded automatically on first use by `from_pretrained`. They are cached in `~/.cache/huggingface/hub/` (~23 GB full, ~12 GB bfloat16 format).

**Option A — Automatic download on first run (simplest):**

Just run the pipeline (see section 6). The first run will download the model. This takes 10–30 minutes depending on your connection.

**Option B — Pre-download with `huggingface-cli` (recommended for slow connections):**

```powershell
pip install huggingface_hub[cli]
huggingface-cli download black-forest-labs/FLUX.1-schnell --local-dir ./models/flux-schnell
```

Then load from the local path:
```python
pipe = FluxPipeline.from_pretrained("./models/flux-schnell", torch_dtype=torch.bfloat16)
```

**Licence:** FLUX.1-schnell is released under the [Apache 2.0 licence](https://huggingface.co/black-forest-labs/FLUX.1-schnell/blob/main/LICENSE). Commercial use is permitted.

---

## 5. Memory Configuration for 8 GB VRAM

Use `enable_sequential_cpu_offload()` — the FLUX.1-schnell transformer alone is ~12 GB, which exceeds the 8 GB VRAM even when fully free. `enable_model_cpu_offload()` will always OOM on this GPU:

```python
import torch
from diffusers import FluxPipeline

pipe = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-schnell",
    torch_dtype=torch.bfloat16,
)
pipe.enable_sequential_cpu_offload()  # required for 8 GB VRAM — do NOT use enable_model_cpu_offload()
```

**Do not call** `pipe.to("cuda")` — `enable_sequential_cpu_offload()` handles device placement internally.

---

## 6. Quick Test — Generate a Single Image

Save this as `tools/test_flux.py` and run it to verify the setup:

```python
import torch
from diffusers import FluxPipeline
from pathlib import Path

pipe = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-schnell",
    torch_dtype=torch.bfloat16,
)
pipe.enable_model_cpu_offload()

prompt = (
    "Oil painting portrait of a stern elderly butler in Victorian livery, "
    "dramatic candlelit manor interior, high detail, dark atmosphere"
)

image = pipe(
    prompt=prompt,
    num_inference_steps=4,   # FLUX.1-schnell is optimized for 4 steps
    guidance_scale=0.0,      # schnell variant uses 0.0 (no CFG)
    width=768,
    height=1024,
    generator=torch.Generator().manual_seed(42),
).images[0]

output_path = Path("test_output.png")
image.save(output_path)
print(f"Saved to {output_path.resolve()}")
```

```powershell
python tools/test_flux.py
```

Expected: image saved to `test_output.png` in under 60 seconds. First run will be slower due to model loading.

---

## 7. CLI Usage (Project Integration)

Once the project's `tools/generate_images.py` is implemented (Step 10), it accepts:

```powershell
# Generate a single character portrait
python tools/generate_images.py --scenario manor --type portrait --id steward

# Generate a single location background
python tools/generate_images.py --scenario manor --type background --id study

# Generate all images for a scenario
python tools/generate_images.py --scenario manor --type all

# Use a specific seed for reproducibility
python tools/generate_images.py --scenario manor --type portrait --id heir --seed 1234
```

Generated images are saved to:
- `assets/scenarios/{scenario_id}/portraits/{character_id}.png`
- `assets/scenarios/{scenario_id}/backgrounds/{location_id}.png`

---

## 8. Troubleshooting

### `torch.cuda.is_available()` returns `False`

- Verify your NVIDIA driver is installed: run `nvidia-smi`
- Ensure you installed the CUDA-enabled PyTorch wheel (the `cu124` index URL above), not the CPU-only version
- Restart your terminal after driver installation

### `OutOfMemoryError: CUDA out of memory`

- Ensure you are calling `enable_model_cpu_offload()` — not `pipe.to("cuda")`
- Lower resolution: use `width=512, height=512` for testing
- Close other GPU-heavy applications (games, browser hardware acceleration)
- If using `enable_model_cpu_offload()` still OOMs, switch to `enable_sequential_cpu_offload()`

### First run is very slow (15+ minutes)

Normal — the model is being downloaded and cached. Subsequent runs reuse the cache. Download size is ~23 GB total.

### `ModuleNotFoundError: No module named 'sentencepiece'`

```powershell
pip install sentencepiece protobuf
```

### Generation looks blurry or low quality

- Do not increase `num_inference_steps` above 4–8 for FLUX.1-schnell — it's trained for few-step generation; more steps can degrade quality
- Ensure `guidance_scale=0.0` (schnell ignores guidance; values >0 may cause artifacts)
- Use descriptive, specific prompts including style keywords and lighting descriptions

### `huggingface-cli` not found

```powershell
pip install "huggingface_hub[cli]"
```

---

## 9. Prompt Tips for Game Assets

**Character portraits:**
```
[art style], portrait of [description], [mood/lighting], [background hint], highly detailed, [era] costume
```
Example: `"Digital painting portrait of a pale young nobleman with cold expression, Victorian formal dress, dark library background, candlelit, dramatic shadows"`

**Location backgrounds:**
```
[art style], [location description], [time of day], [mood], no people, wide shot, [era]
```
Example: `"Oil painting, grand manor study interior, oak bookshelves, fireplace, late evening, candlelit, mysterious atmosphere, no people, wide angle"`

---

## 10. Adding Dependencies to the Project

After verifying the setup, add image generation dependencies to `pyproject.toml`:

```toml
[project.optional-dependencies]
image-gen = [
    "torch>=2.3",
    "diffusers>=0.30",
    "transformers",
    "accelerate",
    "sentencepiece",
    "protobuf",
]
```

Install with:
```powershell
pip install -e ".[image-gen]"
```

This keeps image generation optional — the game backend runs without it if `image-gen` extras are not installed.
