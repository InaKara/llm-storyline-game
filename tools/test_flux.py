import torch
from datetime import datetime
from diffusers import FluxPipeline
# from diffusers import FluxImg2ImgPipeline  # uncomment for image-to-image mode
from pathlib import Path
from PIL import Image
from rembg import remove  # uncomment for background removal

# ── Mode: choose one ──────────────────────────────────────────────────────────

# TEXT-TO-IMAGE (default)
pipe = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-schnell",
    torch_dtype=torch.bfloat16,
)

# IMAGE-TO-IMAGE -- comment out the block above and uncomment this block
# TARGET_W, TARGET_H = 1024, 2048  # set desired output dimensions
# input_image = Image.open("input.png").convert("RGB").resize((TARGET_W, TARGET_H), Image.LANCZOS)
# input_image.save(Path("input_image.png"))  # save resized input for reference
# pipe = FluxImg2ImgPipeline.from_pretrained(
#     "black-forest-labs/FLUX.1-schnell",
#     torch_dtype=torch.bfloat16,
# )

pipe.enable_sequential_cpu_offload()  # required: FLUX transformer is ~12GB, exceeds 8GB VRAM

# ── Prompt ────────────────────────────────────────────────────────────────────



prompt = (
    "Photorealistic full body portrait of an attractive, elegant woman in her early 30s. "
    
    )

# ── Generation ────────────────────────────────────────────────────────────────
print(f"Generating with prompt: {prompt}")
for seed in [123, 456, 789]:  # generate multiple variations by changing the seed
    # TEXT-TO-IMAGE call (default)
    image = pipe(
        prompt=prompt,
        num_inference_steps=4,   # FLUX.1-schnell is optimized for 4 steps
        guidance_scale=0.0,      # schnell variant uses 0.0 (no CFG)
        width=1024,
        height=2048,              # reduced resolution to lower peak VRAM
        generator=torch.Generator().manual_seed(seed),  # change seed to vary composition
    ).images[0]

    # IMAGE-TO-IMAGE call -- replace the block above with this
    # image = pipe(
    #     prompt=prompt,
    #     image=input_image,
    #     strength=0.80,           # 0.0 = identical to input, 1.0 = ignore input entirely
    #     num_inference_steps=4,
    #     guidance_scale=0.0,
    #     width=TARGET_W,
    #     height=TARGET_H,
    #     generator=torch.Generator().manual_seed(42),
    # ).images[0]

    # ── Post-processing ───────────────────────────────────────────────────────────

    ts = datetime.now().strftime("%Y%m%d_%H%M")

    # BACKGROUND REMOVAL -- uncomment to strip background (output saved as PNG with alpha)
    output_path = Path(f"test_output_seed{seed}_{ts}_bg.png")
    image.save(output_path)

    image = remove(image)

    output_path = Path(f"test_output_seed{seed}_{ts}.png")
    image.save(output_path)
    print(f"Saved to {output_path.resolve()}")
