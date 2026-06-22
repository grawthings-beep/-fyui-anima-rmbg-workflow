#!/usr/bin/env python3
import argparse
import pathlib
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfyui-dir", required=True)
    parser.add_argument("--model-root", required=True)
    args = parser.parse_args()

    print(f"python: {sys.executable}")
    print(f"python_version: {sys.version.split()[0]}")
    try:
        import torch

        print(f"torch: {torch.__version__}")
        print(f"cuda_available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"cuda_device: {torch.cuda.get_device_name(0)}")
            print(f"cuda_capability: {torch.cuda.get_device_capability(0)}")
    except Exception as exc:
        print(f"torch_check_error: {exc}")

    comfyui_dir = pathlib.Path(args.comfyui_dir)
    model_root = pathlib.Path(args.model_root)
    print(f"comfyui_dir: {comfyui_dir} exists={comfyui_dir.exists()}")
    for path in [
        model_root / "models" / "diffusion_models",
        model_root / "models" / "text_encoders",
        model_root / "models" / "vae",
        model_root / "models" / "controlnet",
        model_root / "models" / "loras",
        model_root / "models" / "loras" / "anima",
        comfyui_dir / "custom_nodes" / "ComfyUI-Anima-LLLite",
    ]:
        print(f"path: {path} exists={path.exists()}")


if __name__ == "__main__":
    main()
