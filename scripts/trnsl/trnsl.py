#!/usr/bin/env python3
# /// script
# dependencies = [
#   "ollama",
#   "rich",
# ]
# ///
"""
trnsl — translate a file to any language via Ollama (local LLM).

Usage:
    trnsl -ru path/to/file.md
    trnsl -ru path/to/file.md path/to/output.ru.md
    trnsl --lang fr path/to/file.md

Output: <stem>.<lang>.md next to source file (or explicit path).
Model:  TRNSL_MODEL env var, default: qwen2.5:7b
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import ollama
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

DEFAULT_MODEL = os.environ.get("TRNSL_MODEL", "qwen2.5:7b")
CHUNK_SOFT_LIMIT = 2000  # chars

# Curated list for translation. smollm2:135m first as the minimal default.
# Format: (model_tag, size_label, description)
TRANSLATION_MODELS = [
    ("smollm2:135m", "270MB", "Старт — минимальный размер, базовый перевод (ru/en)"),
    ("qwen2.5:0.5b", "394MB", "Лёгкая — хороший мультиязычный (ru/en/de/fr/zh)"),
    ("gemma3:1b",    "815MB", "Google — ru/en/de/fr/es, сохраняет стиль"),
    ("qwen2.5:1.5b", "986MB", "Средняя — качественный перевод, все языки"),
    ("qwen2.5:3b",   "1.9GB", "Баланс — лучший выбор для юридических текстов"),
    ("mistral:7b",   "4.1GB", "Mistral — лучший для европейских языков (de/fr/es/it)"),
    ("aya:8b",       "4.8GB", "Aya (Cohere) — специализирован на 23 языках"),
    ("qwen2.5:7b",   "4.7GB", "Топ — максимальное качество, все языки включая zh/ar"),
]

LANG_NAMES = {
    "ru": "Russian",
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "zh": "Chinese",
    "ar": "Arabic",
}

SYSTEM_PROMPT = (
    "You are a professional translator. "
    "Translate the following text to {lang}. "
    "Preserve all markdown formatting exactly: headings, bold, italic, lists, tables, links, code spans. "
    "Do NOT translate content inside fenced code blocks (``` ... ```). "
    "Do NOT add explanations. Output only the translated text."
)


def list_local_models() -> list[str]:
    try:
        return [m.model for m in ollama.list().models]
    except Exception:
        return []


def pick_model_fzf() -> str | None:
    """Show fzf picker with translation models. Returns model tag or None."""
    lines = "\n".join(
        f"{tag}|{size}|{desc}" for tag, size, desc in TRANSLATION_MODELS
    )
    try:
        result = subprocess.run(
            [
                "fzf",
                "--height=50%",
                "--layout=reverse",
                "--border=rounded",
                "--prompt=Pick a translation model > ",
                "--header=Enter: install | Ctrl+C: cancel",
                "--with-nth=1,2,3",
                "--delimiter=|",
                "--preview=echo {} | awk -F'|' '{print \"Model: \"$1\"  \"$2\"\\n\\n\"$3}'",
                "--preview-window=right:45%:wrap",
            ],
            input=lines,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("|")[0]
    except FileNotFoundError:
        pass
    return None


def pick_model_menu() -> str | None:
    """Fallback numbered menu when fzf is not available."""
    console.print("\n[bold yellow]Available translation models:[/bold yellow]\n")
    for i, (tag, size, desc) in enumerate(TRANSLATION_MODELS, 1):
        console.print(f"  [cyan]{i}[/cyan]  [bold]{tag}[/bold] [dim]({size})[/dim]  {desc}")
    console.print()
    try:
        choice = input("Enter number (Enter = 1, Ctrl+C = cancel): ").strip()
        idx = (int(choice) - 1) if choice else 0
        if 0 <= idx < len(TRANSLATION_MODELS):
            return TRANSLATION_MODELS[idx][0]
    except (ValueError, KeyboardInterrupt):
        pass
    return None


def ensure_model(requested: str) -> str:
    """If no local models exist — prompt user to pick and install one."""
    if list_local_models():
        return requested

    console.print(
        "\n[bold yellow]No local Ollama models found.[/bold yellow]\n"
        "Select a model to install "
        "([bold]smollm2:135m[/bold] recommended — 270 MB, quick start):\n"
    )
    model = pick_model_fzf() or pick_model_menu()
    if not model:
        console.print("[red]Cancelled.[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Pulling {model}...[/bold]")
    subprocess.run(["ollama", "pull", model], check=True)
    console.print(f"[green]✓[/green] {model} installed\n")
    return model


def split_chunks(text: str, limit: int = CHUNK_SOFT_LIMIT) -> list[str]:
    """Split by double newline, merge small chunks up to limit."""
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = (current + "\n\n" + para).lstrip("\n") if current else para
        if len(candidate) > limit and current:
            chunks.append(current)
            current = para
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def translate_chunk(chunk: str, lang: str, model: str) -> str:
    system = SYSTEM_PROMPT.format(lang=LANG_NAMES.get(lang, lang))
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": chunk},
        ],
    )
    return response["message"]["content"]


def resolve_output(input_path: Path, output_arg: str | None, lang: str) -> Path:
    if output_arg:
        return Path(output_arg).expanduser().resolve()
    stem = input_path.stem
    # strip existing lang suffix to avoid file.ru.ru.md on re-run
    for code in LANG_NAMES:
        if stem.endswith(f".{code}"):
            stem = stem[: -(len(code) + 1)]
            break
    return input_path.parent / f"{stem}.{lang}.md"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate a text file to another language via Ollama."
    )
    parser.add_argument("input", help="Input file (.md, .txt, ...)")
    parser.add_argument("output", nargs="?", default=None, help="Output file (optional)")
    parser.add_argument(
        "--lang", "-l", default="ru", metavar="LANG",
        help="Target language code or name (default: ru)",
    )
    # Shortcut flags: -ru, -en, -fr, etc.
    for code in LANG_NAMES:
        parser.add_argument(f"-{code}", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--model", "-m", default=DEFAULT_MODEL,
        help=f"Ollama model (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    # Resolve language from shortcut flags
    lang = args.lang
    for code in LANG_NAMES:
        if getattr(args, code, False):
            lang = code
            break

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        console.print(f"[red]Error:[/red] file not found: {input_path}")
        sys.exit(1)

    output_path = resolve_output(input_path, args.output, lang)
    model = ensure_model(args.model)

    text = input_path.read_text(encoding="utf-8")
    chunks = split_chunks(text)
    lang_label = LANG_NAMES.get(lang, lang)

    console.print(f"[bold]trnsl[/bold]  {input_path.name} -> [cyan]{output_path.name}[/cyan]")
    console.print(
        f"model: [yellow]{model}[/yellow]  "
        f"lang: [green]{lang_label}[/green]  "
        f"chunks: {len(chunks)}"
    )

    translated_parts: list[str] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("translating...", total=len(chunks))
        for i, chunk in enumerate(chunks, 1):
            progress.update(task, description=f"chunk {i}/{len(chunks)}...")
            translated_parts.append(translate_chunk(chunk, lang, model))
            progress.advance(task)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(translated_parts), encoding="utf-8")
    console.print(f"[green]✓[/green] saved -> {output_path}")


if __name__ == "__main__":
    main()
