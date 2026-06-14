# SPDX-License-Identifier: GPL-3.0-only

import json
import os

import folder_paths
import numpy as np
import torch
from comfy.cli_args import args
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import comfy.samplers
import nodes

from .batch_archive import create_batch_zip
from .variation import (
    add_variation_group,
    build_group_variations,
    build_variations,
)


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


NODE_CLASS_MAPPINGS = {
    "AnimaVariationGroup": AnimaVariationGroup,
    "AnimaVariationBatchSampler": AnimaVariationBatchSampler,
    "AnimaFlexibleVariationBatchSampler": AnimaFlexibleVariationBatchSampler,
    "AnimaSaveBatchZip": AnimaSaveBatchZip,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimaVariationGroup": "Anima Variation Group",
    "AnimaVariationBatchSampler": "Anima Variation Batch Sampler",
    "AnimaFlexibleVariationBatchSampler": "Anima Flexible Variation Batch Sampler",
    "AnimaSaveBatchZip": "Anima Save Batch ZIP",
}
