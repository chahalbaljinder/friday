import os
import requests
from tqdm import tqdm
from pathlib import Path

def download_file(url: str, dest_path: Path):
    """Downloads a file with a progress bar."""
    if dest_path.exists():
        print(f"Skipping {dest_path.name}, already exists.")
        return

    print(f"Downloading {dest_path.name}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    
    with open(dest_path, 'wb') as file, tqdm(
        desc=dest_path.name,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)

def main():
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)

    # Assets for Kokoro-82M (ONNX version)
    assets = {
        "kokoro-v0_19.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx",
        "voices.json": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.json"
    }

    for name, url in assets.items():
        dest = models_dir / name
        try:
            download_file(url, dest)
        except Exception as e:
            print(f"Error downloading {name}: {e}")

    print("\nModel downloads complete. Ensure Ollama is running with 'qwen2.5:3b'.")

if __name__ == "__main__":
    main()
