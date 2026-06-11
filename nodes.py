# SPDX-License-Identifier: GPL-3.0-only

import torch

import comfy.samplers
import nodes

from .variation import build_variations


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
        latent_samples = latent_image.get("samples")
        if latent_samples is None:
            raise ValueError("latent_image does not contain samples")
        if latent_samples.shape[0] != 1:
            raise ValueError(
                "Anima Variation Batch Sampler requires latent batch_size=1. "
                "Use count to control the number of output images."
            )

        variations = build_variations(
            base_prompt,
            shot_recipes,
            expressions,
            count,
            master_seed,
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
            report_lines.append(
                f"{variation.index:02d} | seed={variation.seed} | "
                f"{variation.prompt}"
            )

        return (torch.cat(images, dim=0), "\n".join(report_lines))


NODE_CLASS_MAPPINGS = {
    "AnimaVariationBatchSampler": AnimaVariationBatchSampler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimaVariationBatchSampler": "Anima Variation Batch Sampler",
}
