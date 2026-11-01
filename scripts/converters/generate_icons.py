# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pillow",
# ]
# ///

#!/usr/bin/env python3
"""
generate_icons.py

Один файл. Принимает путь к исходной картинке и генерирует:
 - Android adaptive icons (foreground + background + example xml)
 - iOS AppIcon.appiconset (pngs + Contents.json)

Зависимость: Pillow
Запуск: uv run generate_icons.py <path_to_image>
"""

from __future__ import annotations
import argparse
from pathlib import Path
from typing import Tuple, List, Dict
from PIL import Image, ImageStat

# -----------------------
# Константы и размеры
# -----------------------

IOS_SIZES = [
    # (point size, scales)
    (20, [1, 2, 3]),
    (29, [1, 2, 3]),
    (40, [1, 2, 3]),
    (60, [2, 3]),      # app icon on iPhone (60pt)
    (76, [1, 2]),      # iPad
    (83.5, [2]),       # iPad Pro
    (1024, [1]),       # App Store
]

# Для удобства задаём размеры как (pt, scale) -> px = pt*scale (iOS uses float 83.5)
IOS_EXPORT_LIST: List[Tuple[float, int]] = []
for pt, scales in IOS_SIZES:
    for s in scales:
        IOS_EXPORT_LIST.append((pt, s))

# Android adaptive recommended foreground size: 432x432 (Google recommendation: vector or 108x108 etc.
# but we use 432 to be safe for high density)
ANDROID_FOREGROUND_SIZE = (432, 432)
ANDROID_BACKGROUND_SIZE = (432, 432)

# -----------------------
# Утилиты
# -----------------------

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def pick_background_color_from_image(img: Image.Image) -> Tuple[int,int,int]:
    """
    Берём средний цвет маленького участка в левом верхнем углу.
    Это простой, детерминированный способ выбрать фон, сочетающийся с картинкой.
    """
    thumb = img.copy()
    thumb.thumbnail((50, 50))
    stat = ImageStat.Stat(thumb)
    r, g, b = [int(x) for x in stat.mean[:3]]
    return (r, g, b)

def save_png(image: Image.Image, path: Path) -> None:
    ensure_dir(path.parent)
    image.save(path, format="PNG")
    # No alpha flattening here — we preserve alpha if present

# -----------------------
# iOS: AppIcon.appiconset generator
# -----------------------

def generate_ios_icons(src: Image.Image, out_dir: Path) -> None:
    """
    Генерирует AppIcon.appiconset в out_dir/AppIcon.appiconset
    """
    appicon_dir = out_dir / "AppIcon.appiconset"
    ensure_dir(appicon_dir)

    images_entries = []

    for pt, scale in IOS_EXPORT_LIST:
        px = int(round(pt * scale))
        # iOS uses some non-integer pt (83.5), so compute px carefully
        filename = f"Icon-{int(pt*10)}pt@{scale}x.png" if float(pt).is_integer() is False else f"Icon-{int(pt)}pt@{scale}x.png"
        # but easier: keep deterministic filenames without decimals:
        filename = f"AppIcon-{int(round(pt*10))}pt@{scale}x.png"  # e.g. AppIcon-835pt@2x for 83.5pt@2x
        # Compute pixel size for saving:
        px_size = px
        icon = src.copy().convert("RGBA")
        icon = icon.resize((px_size, px_size), Image.Resampling.LANCZOS)
        path = appicon_dir / filename
        save_png(icon, path)

        images_entries.append({
            "size": f"{pt}x{pt}",
            "idiom": "universal",
            "filename": filename,
            "scale": f"{scale}x"
        })

    # Add App Store icon (1024x1024) with standard filename
    appstore_name = "AppIcon-1024pt@1x.png"
    appstore_icon = src.copy().convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
    save_png(appstore_icon, appicon_dir / appstore_name)
    images_entries.append({
        "size": "1024x1024",
        "idiom": "ios-marketing",
        "filename": appstore_name,
        "scale": "1x"
    })

    # Contents.json creation (simple but accepted by Xcode)
    contents = {
        "images": images_entries,
        "info": {
            "version": 1,
            "author": "xcode"
        }
    }

    import json
    with open(appicon_dir / "Contents.json", "w", encoding="utf-8") as f:
        json.dump(contents, f, indent=2, ensure_ascii=False)

# -----------------------
# Android: adaptive icons
# -----------------------

def generate_android_adaptive(src: Image.Image, out_dir: Path) -> None:
    """
    Генерирует:
      - res/mipmap-anydpi-v26/ic_launcher.xml  (пример adaptive icon xml)
      - ic_launcher_foreground.png
      - ic_launcher_background.png
    """
    android_dir = out_dir / "android_adaptive"
    ensure_dir(android_dir)

    # Foreground
    fg = src.copy().convert("RGBA")
    fg = fg.resize(ANDROID_FOREGROUND_SIZE, Image.Resampling.LANCZOS)
    fg_path = android_dir / "ic_launcher_foreground.png"
    save_png(fg, fg_path)

    # Background: try взять аккуратный сплошной цвет
    bg_color = pick_background_color_from_image(src)
    bg = Image.new("RGBA", ANDROID_BACKGROUND_SIZE, bg_color + (255,))
    bg_path = android_dir / "ic_launcher_background.png"
    save_png(bg, bg_path)

    # Example adaptive icon XML (simple template)
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
  <background android:drawable="@mipmap/ic_launcher_background"/>
  <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
</adaptive-icon>
"""
    # Save the XML into an exemplary path
    ensure_dir(android_dir / "mipmap-anydpi-v26")
    with open(android_dir / "mipmap-anydpi-v26" / "ic_launcher.xml", "w", encoding="utf-8") as f:
        f.write(xml)

    # Also create a sample README explaining how to place these into an Android project
    readme = android_dir / "README.txt"
    readme.write_text(
        "Place ic_launcher_foreground.png and ic_launcher_background.png into res/mipmap-*/ or drawable folders.\n"
        "Place ic_launcher.xml into res/mipmap-anydpi-v26/ic_launcher.xml\n"
        "In AndroidManifest or project settings, reference @mipmap/ic_launcher as your adaptive icon.\n"
    )

# -----------------------
# CLI и main
# -----------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate iOS AppIcon.appiconset and Android adaptive icons from a source image.")
    p.add_argument("src", type=Path, help="Path to source image (png / jpg).")
    p.add_argument("--out", type=Path, default=Path("./output_icons"), help="Output root directory.")
    p.add_argument("--force-bg", action="store_true", help="Force a flat background color (from image) for Android background instead of using alpha-transparent background.")
    return p.parse_args()

def validate_image_path(p: Path) -> None:
    if not p.exists():
        raise FileNotFoundError(f"Source image not found: {p}")
    if not p.is_file():
        raise ValueError(f"Source path is not a file: {p}")

def main() -> None:
    args = parse_args()
    src_path: Path = args.src
    out_root: Path = args.out

    validate_image_path(src_path)

    src_img = Image.open(src_path)
    # Normalize to RGBA for consistent handling
    src_img = src_img.convert("RGBA")

    # Create outputs
    ensure_dir(out_root)
    print(f"[+] Generating iOS AppIcon.appiconset -> {out_root / 'AppIcon.appiconset'}")
    generate_ios_icons(src_img, out_root)

    print(f"[+] Generating Android adaptive icons -> {out_root / 'android_adaptive'}")
    generate_android_adaptive(src_img, out_root)

    print("[+] Done. Check the output folder for AppIcon.appiconset and android_adaptive.")
    print(f"Example input used: {src_path}")

if __name__ == "__main__":
    main()

# uv run generate_icons.py ~/Downloads/launcher.png --out ~/Downloads/my_icons