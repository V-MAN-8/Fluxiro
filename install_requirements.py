#!/usr/bin/env python3
"""
Requirements installer for Fluxiro video downloader.
- Installs yt-dlp and imageio-ffmpeg (which bundles ffmpeg).
- If requirements.txt exists, installs from that; otherwise installs defaults.
- Installs to the current Python environment with --user (no admin required).
"""

import sys
import subprocess
from pathlib import Path
import shutil

REQ_FILE = Path("requirements.txt")
DEFAULT_PACKAGES = ["yt-dlp>=2024.10.7", "imageio-ffmpeg>=0.4.9", "certifi>=2023.0.0"]


def run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


def install_python_requirements() -> None:
    # Upgrade pip (user scope) to avoid old pip issues
    print("[*] Upgrading pip...")
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "--user"])

    if REQ_FILE.exists():
        print("[*] Installing from requirements.txt ...")
        run([sys.executable, "-m", "pip", "install", "--user", "-r", str(REQ_FILE)])
    else:
        print("[*] requirements.txt not found. Installing default packages (yt-dlp + imageio-ffmpeg)...")
        for pkg in DEFAULT_PACKAGES:
            run([sys.executable, "-m", "pip", "install", "--user", pkg])


def verify_ffmpeg() -> None:
    """Check if ffmpeg is available (system or imageio-ffmpeg bundled)."""
    # Check system PATH
    if cmd_exists("ffmpeg"):
        print("[✓] ffmpeg found on system PATH.")
        return

    # Check imageio-ffmpeg
    try:
        import imageio_ffmpeg as iio
        exe = iio.get_ffmpeg_exe()
        import os
        if exe and os.path.exists(exe):
            print(f"[✓] ffmpeg found via imageio-ffmpeg: {exe}")
            return
    except Exception:
        pass

    print("[!] Warning: ffmpeg not detected. imageio-ffmpeg should have been installed but may need verification.")
    print("    The app will attempt to find ffmpeg automatically, but if downloads fail, install system ffmpeg:")
    print("      macOS: brew install ffmpeg")
    print("      Windows: winget install ffmpeg  (or choco install ffmpeg)")
    print("      Linux: sudo apt-get install ffmpeg")


def main() -> None:
    if sys.version_info < (3, 8):
        sys.exit("Python 3.8+ required.")

    print("="*60)
    print("Fluxiro - Social Media Video Downloader Setup")
    print("="*60)

    install_python_requirements()
    print()
    verify_ffmpeg()

    print("\n" + "="*60)
    print("[✓] Setup complete!")
    print("Run the downloader with:")
    print("  python3 fluxiro.py")
    print("="*60)


if __name__ == "__main__":
    main()
