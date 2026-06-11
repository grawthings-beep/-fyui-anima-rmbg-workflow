# SPDX-License-Identifier: GPL-3.0-only

import itertools
import random
from dataclasses import dataclass


def parse_lines(value):
    return list(
        dict.fromkeys(
            line.strip()
            for line in value.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    )


def join_prompt(*parts):
    return ", ".join(
        part.strip(" \t\r\n,") for part in parts if part.strip(" \t\r\n,")
    )


@dataclass(frozen=True)
class Variation:
    index: int
    seed: int
    shot: str
    expression: str
    prompt: str


def build_variations(
    base_prompt,
    shot_recipes,
    expressions,
    count,
    master_seed,
):
    shots = parse_lines(shot_recipes)
    faces = parse_lines(expressions)
    if not shots:
        raise ValueError("shot_recipes must contain at least one non-empty line")
    if not faces:
        raise ValueError("expressions must contain at least one non-empty line")

    combinations = list(itertools.product(shots, faces))
    if count > len(combinations):
        raise ValueError(
            f"count={count} requires at least {count} unique combinations, "
            f"but only {len(combinations)} are available"
        )

    rng = random.Random(master_seed)
    selected = rng.sample(combinations, count)
    used_seeds = set()
    variations = []

    for index, (shot, expression) in enumerate(selected, start=1):
        seed = rng.getrandbits(64)
        while seed in used_seeds:
            seed = rng.getrandbits(64)
        used_seeds.add(seed)
        variations.append(
            Variation(
                index=index,
                seed=seed,
                shot=shot,
                expression=expression,
                prompt=join_prompt(base_prompt, shot, expression),
            )
        )

    return variations
