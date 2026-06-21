# SPDX-License-Identifier: GPL-3.0-only

import json
import os

import folder_paths
import numpy as np
import torch
from comfy.cli_args import args
from PIL import Image
from PIL import ImageDraw
from PIL.PngImagePlugin import PngInfo

import comfy.samplers
import nodes

from .batch_archive import create_batch_zip
from .variation import (
    add_variation_group,
    build_group_variations,
    build_variations,
)


_REMBG_SESSIONS = {}
_RMBG2_MODELS = {}
_BEN2_MODELS = {}


def _is_unresolved_template(value):
    return "{{" in value or "}}" in value or "RUNPOD_SECRET" in value


def _tensor_to_pil_rgb(image):
    pixels = 255.0 * image.cpu().numpy()
    return Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)).convert("RGB")


def _pil_rgb_to_tensor(image):
    array = np.asarray(image.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(array)


def _mask_to_tensor(mask):
    array = np.asarray(mask.convert("L")).astype(np.float32) / 255.0
    return torch.from_numpy(array)


def _checkerboard(size, cell=24):
    width, height = size
    image = Image.new("RGB", size, (218, 226, 236))
    draw = ImageDraw.Draw(image)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if ((x // cell) + (y // cell)) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(168, 178, 192))
    return image


def _composite_preview(rgba, preview_background):
    if preview_background == "black":
        background = Image.new("RGB", rgba.size, (0, 0, 0))
    elif preview_background == "white":
        background = Image.new("RGB", rgba.size, (255, 255, 255))
    else:
        background = _checkerboard(rgba.size)
    background.paste(rgba.convert("RGB"), mask=rgba.getchannel("A"))
    return background


def _edge_connected_chroma_rgba(image, tolerance):
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = list(rgba.getdata())
    corners = [
        rgba.getpixel((0, 0))[:3],
        rgba.getpixel((width - 1, 0))[:3],
        rgba.getpixel((0, height - 1))[:3],
        rgba.getpixel((width - 1, height - 1))[:3],
    ]
    key = tuple(sum(c[index] for c in corners) // len(corners) for index in range(3))
    seen = [False] * (width * height)
    background = [False] * (width * height)
    queue = []

    def close_to_key(pixel_index):
        r, g, b, _a = pixels[pixel_index]
        return abs(r - key[0]) + abs(g - key[1]) + abs(b - key[2]) <= tolerance

    for x in range(width):
        for y in (0, height - 1):
            index = y * width + x
            if close_to_key(index):
                seen[index] = True
                queue.append(index)
    for y in range(1, height - 1):
        for x in (0, width - 1):
            index = y * width + x
            if not seen[index] and close_to_key(index):
                seen[index] = True
                queue.append(index)

    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        background[current] = True
        x = current % width
        y = current // width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            next_index = ny * width + nx
            if not seen[next_index] and close_to_key(next_index):
                seen[next_index] = True
                queue.append(next_index)

    rgba.putdata(
        [
            (r, g, b, 0 if background[index] else a)
            for index, (r, g, b, a) in enumerate(pixels)
        ]
    )
    return rgba


def _get_rembg_session(model_name):
    try:
        from rembg import new_session
    except ImportError as exc:
        raise RuntimeError(
            "rembg is not installed. Install this custom node's optional "
            "requirements or switch method to edge_connected_chroma."
        ) from exc

    normalized = (model_name or "isnet-general-use").strip() or "isnet-general-use"
    session = _REMBG_SESSIONS.get(normalized)
    if session is None:
        session = new_session(normalized)
        _REMBG_SESSIONS[normalized] = session
    return session


def _get_hf_token():
    token = (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or os.environ.get("HUGGINGFACE_HUB_TOKEN")
        or ""
    )
    token = token.strip()
    if not token or _is_unresolved_template(token):
        return None
    return token


def _get_rmbg2_model(model_name):
    normalized = (model_name or "briaai/RMBG-2.0").strip() or "briaai/RMBG-2.0"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cache_key = (normalized, device)
    cached = _RMBG2_MODELS.get(cache_key)
    if cached is not None:
        return cached

    try:
        from transformers import AutoModelForImageSegmentation
    except ImportError as exc:
        raise RuntimeError(
            "transformers is not installed. Install this custom node's "
            "requirements or switch method to edge_connected_chroma."
        ) from exc

    token = _get_hf_token()
    if normalized.casefold() == "briaai/rmbg-2.0" and token is None:
        raise RuntimeError(
            "BRIA RMBG-2.0 is a gated Hugging Face model. Set a real HF_TOKEN "
            "in the RunPod template, make sure the RunPod secret placeholder "
            "expanded, and accept the model terms at "
            "https://huggingface.co/briaai/RMBG-2.0."
        )

    try:
        model = AutoModelForImageSegmentation.from_pretrained(
            normalized,
            trust_remote_code=True,
            token=token,
        ).eval()
    except Exception as exc:
        raise RuntimeError(
            f"Could not load {normalized}. If this is BRIA RMBG-2.0, accept "
            "the model terms on Hugging Face and set HF_TOKEN in RunPod. "
            f"Underlying error: {exc.__class__.__name__}: {exc}"
        ) from exc
    model.to(device)
    _RMBG2_MODELS[cache_key] = (model, device)
    return model, device


def _resolve_birefnet_size(model_name, requested):
    if requested and requested > 0:
        return int(requested)
    # BiRefNet-HR checkpoints are trained at 2048x2048; the rest use 1024x1024.
    if "hr" in (model_name or "").casefold():
        return 2048
    return 1024


def _normalize_rmbg2_input(image, device, size=1024):
    resized = image.convert("RGB").resize((size, size), Image.BILINEAR)
    array = np.asarray(resized).astype(np.float32) / 255.0
    mean = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
    array = (array - mean) / std
    array = np.transpose(array, (2, 0, 1))
    return torch.from_numpy(array).unsqueeze(0).to(device)


def _remove_background_with_rmbg2(image, model_name, infer_size=0):
    model, device = _get_rmbg2_model(model_name)
    size = _resolve_birefnet_size(model_name, infer_size)
    input_tensor = _normalize_rmbg2_input(image, device, size=size)
    # Match the model's parameter dtype so fp16-loaded checkpoints (common in
    # baked ComfyUI images) do not raise "Input type (float) and bias type
    # (c10::Half) should be the same".
    try:
        param_dtype = next(model.parameters()).dtype
        input_tensor = input_tensor.to(param_dtype)
    except StopIteration:
        pass
    with torch.no_grad():
        prediction = model(input_tensor)[-1].sigmoid().detach().float().cpu()[0].squeeze()

    mask_array = np.clip(prediction.numpy() * 255.0, 0, 255).astype(np.uint8)
    mask = Image.fromarray(mask_array, mode="L").resize(image.size, Image.BILINEAR)
    rgba = image.convert("RGBA")
    rgba.putalpha(mask)
    return rgba


def _get_ben2_model(model_name):
    normalized = (model_name or "PramaLLC/BEN2").strip() or "PramaLLC/BEN2"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cache_key = (normalized, device)
    cached = _BEN2_MODELS.get(cache_key)
    if cached is not None:
        return cached

    try:
        from ben2 import BEN_Base
    except ImportError as exc:
        raise RuntimeError(
            "ben2 is not installed. Add 'ben2' to this custom node's "
            "requirements (pip install ben2) or switch method to "
            "birefnet / rembg / edge_connected_chroma."
        ) from exc

    token = _get_hf_token()
    try:
        try:
            model = BEN_Base.from_pretrained(normalized, token=token)
        except TypeError:
            # Older ben2 releases do not accept a token kwarg.
            model = BEN_Base.from_pretrained(normalized)
    except Exception as exc:
        raise RuntimeError(
            f"Could not load BEN2 model {normalized}. "
            f"Underlying error: {exc.__class__.__name__}: {exc}"
        ) from exc

    model.to(device).eval()
    _BEN2_MODELS[cache_key] = (model, device)
    return model, device


def _remove_background_with_ben2(image, model_name):
    model, _device = _get_ben2_model(model_name)
    rgb = image.convert("RGB")
    with torch.no_grad():
        foreground = model.inference(rgb, refine_foreground=False)

    rgba = image.convert("RGBA")
    rgba.putalpha(foreground.convert("RGBA").getchannel("A"))
    return rgba


def _remove_background_with_rembg(
    image,
    model_name,
    alpha_matting,
    foreground_threshold,
    background_threshold,
    erode_size,
):
    try:
        from rembg import remove
    except ImportError as exc:
        raise RuntimeError(
            "rembg is not installed. Install this custom node's optional "
            "requirements or switch method to edge_connected_chroma."
        ) from exc

    session = _get_rembg_session(model_name)
    return remove(
        image,
        session=session,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=foreground_threshold,
        alpha_matting_background_threshold=background_threshold,
        alpha_matting_erode_size=erode_size,
    ).convert("RGBA")


def sample_variations(
    variations,
    model,
    clip,
    vae,
    negative,
    latent_image,
    steps,
    cfg,
    sampler_name,
    scheduler,
    denoise,
):
    latent_samples = latent_image.get("samples")
    if latent_samples is None:
        raise ValueError("latent_image does not contain samples")
    if latent_samples.shape[0] != 1:
        raise ValueError(
            "Anima Variation Batch Sampler requires latent batch_size=1. "
            "Use count to control the number of output images."
        )

    images = []
    report_lines = []
    for variation in variations:
        tokens = clip.tokenize(variation.prompt)
        positive = clip.encode_from_tokens_scheduled(tokens)

        sampled = nodes.common_ksampler(
            model,
            variation.seed,
            steps,
            cfg,
            sampler_name,
            scheduler,
            positive,
            negative,
            latent_image,
            denoise=denoise,
        )[0]
        decoded = vae.decode(sampled["samples"])
        if len(decoded.shape) == 5:
            decoded = decoded.reshape(
                -1,
                decoded.shape[-3],
                decoded.shape[-2],
                decoded.shape[-1],
            )
        images.append(decoded)
        details = getattr(variation, "selection_report", "")
        details = f" | {details}" if details else ""
        report_lines.append(
            f"{variation.index:02d} | seed={variation.seed}{details} | "
            f"{variation.prompt}"
        )

    return (torch.cat(images, dim=0), "\n".join(report_lines))


class AnimaVariationGroup:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "category_name": (
                    "STRING",
                    {
                        "default": "Angle",
                        "dynamicPrompts": False,
                    },
                ),
                "options": (
                    "STRING",
                    {
                        "multiline": True,
                        "dynamicPrompts": False,
                        "default": "from above, from side, from below",
                    },
                ),
            },
            "optional": {
                "previous_groups": ("ANIMA_VARIATION_GROUPS",),
            },
        }

    RETURN_TYPES = ("ANIMA_VARIATION_GROUPS",)
    RETURN_NAMES = ("variation_groups",)
    FUNCTION = "build"
    CATEGORY = "Anima/batch"
    DESCRIPTION = (
        "Adds one unlimited variation category. Enter short prompt tags "
        "separated by commas or new lines, then chain more Group nodes."
    )

    def build(self, category_name, options, previous_groups=None):
        return (
            add_variation_group(previous_groups, category_name, options),
        )


class AnimaVariationBatchSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
                "base_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "dynamicPrompts": False,
                        "default": "masterpiece, best quality, 1girl",
                    },
                ),
                "shot_recipes": (
                    "STRING",
                    {
                        "multiline": True,
                        "dynamicPrompts": False,
                        "default": (
                            "close-up portrait, eye-level, head tilted\n"
                            "upper body shot, low angle, leaning forward\n"
                            "cowboy shot, three-quarter view, hand on hip\n"
                            "full body shot, high angle, dynamic standing pose"
                        ),
                    },
                ),
                "expressions": (
                    "STRING",
                    {
                        "multiline": True,
                        "dynamicPrompts": False,
                        "default": (
                            "gentle smile, closed mouth\n"
                            "laughing, open mouth, closed eyes\n"
                            "surprised expression, wide eyes\n"
                            "embarrassed expression, blush"
                        ),
                    },
                ),
                "count": ("INT", {"default": 4, "min": 1, "max": 32, "step": 1}),
                "master_seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
                "steps": ("INT", {"default": 8, "min": 1, "max": 10000}),
                "cfg": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.1,
                        "round": 0.01,
                    },
                ),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "denoise": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "prompt_report")
    OUTPUT_TOOLTIPS = (
        "A batch containing one independently sampled and decoded image per prompt.",
        "The expanded prompts and seeds used for the batch.",
    )
    FUNCTION = "sample"
    CATEGORY = "Anima/batch"
    DESCRIPTION = (
        "Creates unique shot/expression prompt combinations and samples each one "
        "with an independent seed in a single queued execution."
    )

    def sample(
        self,
        model,
        clip,
        vae,
        negative,
        latent_image,
        base_prompt,
        shot_recipes,
        expressions,
        count,
        master_seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
    ):
        variations = build_variations(
            base_prompt,
            shot_recipes,
            expressions,
            count,
            master_seed,
        )
        return sample_variations(
            variations,
            model,
            clip,
            vae,
            negative,
            latent_image,
            steps,
            cfg,
            sampler_name,
            scheduler,
            denoise,
        )


class AnimaFlexibleVariationBatchSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
                "variation_groups": ("ANIMA_VARIATION_GROUPS",),
                "base_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "dynamicPrompts": False,
                        "default": "masterpiece, best quality, 1girl",
                    },
                ),
                "count": ("INT", {"default": 4, "min": 1, "max": 32, "step": 1}),
                "master_seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
                "steps": ("INT", {"default": 8, "min": 1, "max": 10000}),
                "cfg": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.1,
                        "round": 0.01,
                    },
                ),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "denoise": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "prompt_report")
    OUTPUT_TOOLTIPS = (
        "A batch containing one independently sampled and decoded image per prompt.",
        "The selected category values, expanded prompts, and seeds.",
    )
    FUNCTION = "sample"
    CATEGORY = "Anima/batch"
    DESCRIPTION = (
        "Uses every option in each connected Variation Group once before "
        "reshuffling that category. Chain any number of groups."
    )

    def sample(
        self,
        model,
        clip,
        vae,
        negative,
        latent_image,
        variation_groups,
        base_prompt,
        count,
        master_seed,
        steps,
        cfg,
        sampler_name,
        scheduler,
        denoise,
    ):
        variations = build_group_variations(
            base_prompt,
            variation_groups,
            count,
            master_seed,
        )
        return sample_variations(
            variations,
            model,
            clip,
            vae,
            negative,
            latent_image,
            steps,
            cfg,
            sampler_name,
            scheduler,
            denoise,
        )


class AnimaSaveBatchZip:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": (
                            "anima_batches/"
                            "%year%-%month%-%day%/"
                            "anima_batch"
                        ),
                    },
                ),
                "auto_download": (
                    "BOOLEAN",
                    {
                        "default": True,
                    },
                ),
            },
            "optional": {
                "prompt_report": (
                    "STRING",
                    {
                        "forceInput": True,
                    },
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "Anima/batch"
    DESCRIPTION = (
        "Saves one generation as a numbered folder of PNG files and creates "
        "one downloadable ZIP containing the images and prompt report."
    )

    def save(
        self,
        images,
        filename_prefix,
        auto_download=True,
        prompt_report="",
        prompt=None,
        extra_pnginfo=None,
    ):
        if len(images) == 0:
            raise ValueError("images must contain at least one image")

        (
            full_output_folder,
            filename,
            counter,
            subfolder,
            _filename_prefix,
        ) = folder_paths.get_save_image_path(
            filename_prefix,
            self.output_dir,
            images[0].shape[1],
            images[0].shape[0],
        )

        batch_name = f"{filename}_{counter:05}"
        batch_folder = os.path.join(full_output_folder, batch_name)
        os.makedirs(batch_folder, exist_ok=False)

        saved_paths = []
        image_results = []
        image_subfolder = os.path.join(subfolder, batch_name).replace("\\", "/")
        for batch_number, image in enumerate(images, start=1):
            pixels = 255.0 * image.cpu().numpy()
            output_image = Image.fromarray(
                np.clip(pixels, 0, 255).astype(np.uint8)
            )
            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for key, value in extra_pnginfo.items():
                        metadata.add_text(key, json.dumps(value))

            image_filename = f"image_{batch_number:02}.png"
            image_path = os.path.join(batch_folder, image_filename)
            output_image.save(
                image_path,
                pnginfo=metadata,
                compress_level=self.compress_level,
            )
            saved_paths.append(image_path)
            image_results.append(
                {
                    "filename": image_filename,
                    "subfolder": image_subfolder,
                    "type": self.type,
                }
            )

        zip_filename = f"{batch_name}.zip"
        zip_path = os.path.join(full_output_folder, zip_filename)
        create_batch_zip(zip_path, saved_paths, prompt_report or "")

        return {
            "ui": {
                "images": image_results,
                "zip": [
                    {
                        "filename": zip_filename,
                        "subfolder": subfolder.replace("\\", "/"),
                        "type": self.type,
                        "count": len(saved_paths),
                        "auto_download": bool(auto_download),
                    }
                ],
            }
        }


class AnimaRemoveBackground:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "method": (
                    ["birefnet", "ben2", "rmbg2", "rembg", "edge_connected_chroma"],
                    {
                        "default": "birefnet",
                    },
                ),
                "rembg_model": (
                    "STRING",
                    {
                        "default": "isnet-general-use",
                    },
                ),
                "rmbg2_model": (
                    "STRING",
                    {
                        "default": "briaai/RMBG-2.0",
                    },
                ),
                "birefnet_model": (
                    "STRING",
                    {
                        "default": "ZhengPeng7/BiRefNet_HR",
                    },
                ),
                "ben2_model": (
                    "STRING",
                    {
                        "default": "PramaLLC/BEN2",
                    },
                ),
                "infer_size": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 2048,
                        "step": 32,
                    },
                ),
                "alpha_matting": (
                    "BOOLEAN",
                    {
                        "default": False,
                    },
                ),
                "foreground_threshold": (
                    "INT",
                    {
                        "default": 240,
                        "min": 0,
                        "max": 255,
                    },
                ),
                "background_threshold": (
                    "INT",
                    {
                        "default": 10,
                        "min": 0,
                        "max": 255,
                    },
                ),
                "erode_size": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 64,
                    },
                ),
                "edge_tolerance": (
                    "INT",
                    {
                        "default": 34,
                        "min": 0,
                        "max": 765,
                    },
                ),
                "preview_background": (
                    ["checker", "black", "white"],
                    {
                        "default": "checker",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("preview_images", "alpha_masks")
    FUNCTION = "remove"
    CATEGORY = "Anima/background"
    DESCRIPTION = (
        "Removes backgrounds from generated images. The IMAGE output is only "
        "for preview; connect alpha_masks to Anima Save Transparent Batch ZIP "
        "to write real transparent PNG files."
    )

    def remove(
        self,
        images,
        method,
        rembg_model,
        rmbg2_model,
        birefnet_model,
        ben2_model,
        infer_size,
        alpha_matting,
        foreground_threshold,
        background_threshold,
        erode_size,
        edge_tolerance,
        preview_background,
    ):
        previews = []
        masks = []
        for image in images:
            pil_image = _tensor_to_pil_rgb(image)
            if method == "birefnet":
                rgba = _remove_background_with_rmbg2(
                    pil_image, birefnet_model, infer_size
                )
            elif method == "ben2":
                rgba = _remove_background_with_ben2(pil_image, ben2_model)
            elif method == "rmbg2":
                rgba = _remove_background_with_rmbg2(
                    pil_image, rmbg2_model, infer_size
                )
            elif method == "rembg":
                rgba = _remove_background_with_rembg(
                    pil_image,
                    rembg_model,
                    alpha_matting,
                    foreground_threshold,
                    background_threshold,
                    erode_size,
                )
            else:
                rgba = _edge_connected_chroma_rgba(pil_image, edge_tolerance)

            previews.append(_pil_rgb_to_tensor(_composite_preview(rgba, preview_background)))
            masks.append(_mask_to_tensor(rgba.getchannel("A")))

        return (torch.stack(previews, dim=0), torch.stack(masks, dim=0))


class AnimaSaveTransparentBatchZip:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "alpha_masks": ("MASK",),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": (
                            "anima_transparent/"
                            "%year%-%month%-%day%/"
                            "anima_transparent"
                        ),
                    },
                ),
                "auto_download": (
                    "BOOLEAN",
                    {
                        "default": True,
                    },
                ),
            },
            "optional": {
                "prompt_report": (
                    "STRING",
                    {
                        "forceInput": True,
                    },
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "Anima/background"
    DESCRIPTION = (
        "Saves RGB images plus alpha masks as transparent PNG files and a "
        "downloadable ZIP."
    )

    def save(
        self,
        images,
        alpha_masks,
        filename_prefix,
        auto_download=True,
        prompt_report="",
        prompt=None,
        extra_pnginfo=None,
    ):
        if len(images) == 0:
            raise ValueError("images must contain at least one image")
        if len(alpha_masks) not in (1, len(images)):
            raise ValueError(
                "alpha_masks batch must contain one mask or match images batch size"
            )

        (
            full_output_folder,
            filename,
            counter,
            subfolder,
            _filename_prefix,
        ) = folder_paths.get_save_image_path(
            filename_prefix,
            self.output_dir,
            images[0].shape[1],
            images[0].shape[0],
        )

        batch_name = f"{filename}_{counter:05}"
        batch_folder = os.path.join(full_output_folder, batch_name)
        os.makedirs(batch_folder, exist_ok=False)

        saved_paths = []
        image_results = []
        image_subfolder = os.path.join(subfolder, batch_name).replace("\\", "/")
        for batch_index, image in enumerate(images):
            pixels = 255.0 * image.cpu().numpy()
            output_image = Image.fromarray(
                np.clip(pixels, 0, 255).astype(np.uint8)
            ).convert("RGBA")

            mask_index = batch_index if len(alpha_masks) > 1 else 0
            alpha = 255.0 * alpha_masks[mask_index].cpu().numpy()
            alpha_image = Image.fromarray(
                np.clip(alpha, 0, 255).astype(np.uint8)
            ).convert("L")
            output_image.putalpha(alpha_image)

            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for key, value in extra_pnginfo.items():
                        metadata.add_text(key, json.dumps(value))

            image_filename = f"image_{batch_index + 1:02}.png"
            image_path = os.path.join(batch_folder, image_filename)
            output_image.save(
                image_path,
                pnginfo=metadata,
                compress_level=self.compress_level,
            )
            saved_paths.append(image_path)
            image_results.append(
                {
                    "filename": image_filename,
                    "subfolder": image_subfolder,
                    "type": self.type,
                }
            )

        zip_filename = f"{batch_name}.zip"
        zip_path = os.path.join(full_output_folder, zip_filename)
        create_batch_zip(zip_path, saved_paths, prompt_report or "")

        return {
            "ui": {
                "images": image_results,
                "zip": [
                    {
                        "filename": zip_filename,
                        "subfolder": subfolder.replace("\\", "/"),
                        "type": self.type,
                        "count": len(saved_paths),
                        "auto_download": bool(auto_download),
                    }
                ],
            }
        }


NODE_CLASS_MAPPINGS = {
    "AnimaVariationGroup": AnimaVariationGroup,
    "AnimaVariationBatchSampler": AnimaVariationBatchSampler,
    "AnimaFlexibleVariationBatchSampler": AnimaFlexibleVariationBatchSampler,
    "AnimaSaveBatchZip": AnimaSaveBatchZip,
    "AnimaRemoveBackground": AnimaRemoveBackground,
    "AnimaSaveTransparentBatchZip": AnimaSaveTransparentBatchZip,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimaVariationGroup": "Anima Variation Group",
    "AnimaVariationBatchSampler": "Anima Variation Batch Sampler",
    "AnimaFlexibleVariationBatchSampler": "Anima Flexible Variation Batch Sampler",
    "AnimaSaveBatchZip": "Anima Save Batch ZIP",
    "AnimaRemoveBackground": "Anima Remove Background",
    "AnimaSaveTransparentBatchZip": "Anima Save Transparent Batch ZIP",
}
