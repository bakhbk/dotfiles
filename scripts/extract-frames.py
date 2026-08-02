#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
# Запуск: uv run ~/dotfiles/scripts/extract-frames.py /path/to/video.mp4 --count 10
"""Извлекает N равномерно распределённых кадров из видеофайла через ffmpeg.

Сохраняет кадры в ту же директорию, что и исходное видео:
basename_frame001.jpg, basename_frame002.jpg, ...
"""

import argparse
import subprocess
from pathlib import Path


def extract_frames(video_path: Path, count: int) -> list[Path]:
    """Извлекает count кадров из видео равномерно распределённо.

    Возвращает список сохранённых файлов.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Файл не найден: {video_path}")

    if not video_path.is_file():
        raise ValueError(f"Путь не является файлом: {video_path}")

    # Проверяем наличие ffmpeg
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise RuntimeError(
            "ffmpeg не найден. Установите ffmpeg перед использованием этого скрипта."
        )

    output_dir = video_path.parent
    stem = video_path.stem
    frame_files: list[Path] = []

    # Получаем длительность видео через ffprobe
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        raise RuntimeError(f"Не удалось получить длительность видео: {e}")

    if duration <= 0:
        raise ValueError(f"Некорректная длительность видео: {duration}")

    # Вычисляем интервал между кадрами
    interval = duration / count

    print(f"Видео: {video_path}")
    print(f"Длительность: {duration:.2f} сек")
    print(f"Интервал между кадрами: {interval:.3f} сек")
    print(f"Сохранение в: {output_dir}")
    print()

    for i in range(1, count + 1):
        # Время извлечения: (i - 0.5) * interval — середина каждого интервала
        timestamp = (i - 0.5) * interval
        frame_num = f"{i:03d}"
        output_path = output_dir / f"{stem}_frame{frame_num}.jpg"

        print(f"[{i}/{count}] Извлечение кадра в {timestamp:.3f} сек → {output_path.name}")

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",  # перезаписывать без вопросов
                    "-ss", str(timestamp),
                    "-i", str(video_path),
                    "-vframes", "1",
                    "-q:v", "2",  # хорошее качество JPEG
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            frame_files.append(output_path)
        except subprocess.CalledProcessError as e:
            print(f"  error: не удалось извлечь кадр {i}: {e.stderr.strip()}")

    print()
    if frame_files:
        print(f"Сохранено {len(frame_files)} кадров:")
        for f in frame_files:
            print(f"  {f}")
    else:
        print("Кадры не сохранены.")

    return frame_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Извлекает N равномерно распределённых кадров из видеофайла."
    )
    parser.add_argument(
        "video",
        type=Path,
        help="Путь к видеофайлу",
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=10,
        help="Количество кадров для извлечения (по умолчанию: 10)",
    )

    args = parser.parse_args()

    if args.count < 1:
        parser.error("count должно быть не менее 1")

    try:
        extract_frames(args.video, args.count)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"error: {e}", file=__import__("sys").stderr)
        __import__("sys").exit(1)


if __name__ == "__main__":
    main()
