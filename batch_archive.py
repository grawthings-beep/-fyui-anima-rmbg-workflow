# SPDX-License-Identifier: GPL-3.0-only

import pathlib
import zipfile


def create_batch_zip(zip_path, image_paths, prompt_report=""):
    zip_path = pathlib.Path(zip_path)
    image_paths = [pathlib.Path(path) for path in image_paths]
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(
        zip_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for image_path in image_paths:
            archive.write(image_path, arcname=image_path.name)
        if prompt_report.strip():
            archive.writestr(
                "prompt_report.txt",
                prompt_report.strip() + "\n",
            )

    return zip_path
