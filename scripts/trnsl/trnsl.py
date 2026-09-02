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
import json
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
TRNSL_CONFIG_DIR = Path.home() / ".config" / "trnsl"
TRNSL_MODELS_DB = TRNSL_CONFIG_DIR / "models.json"

# Curated list for translation — models up to 1 GB.
# Format: (model_tag, size_label, description)
TRANSLATION_MODELS = [
    ("smollm2:135m", "270MB",  "Старт — минимальный, базовый перевод (ru/en/de/fr)"),
    ("qwen2.5:0.5b", "394MB",  "Лёгкая — хороший мультиязык (ru/en/de/fr/zh)"),
    ("gemma3:1b",    "815MB",  "Google — ru/en/de/fr/es, сохраняет стиль"),
    ("qwen2.5:1.5b", "986MB",  "Средняя — качественный перевод, все языки"),
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


def load_models_db() -> dict[str, bool]:
    """Load the models database from ~/.config/trnsl/models.json."""
    TRNSL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if TRNSL_MODELS_DB.exists():
        try:
            return json.loads(TRNSL_MODELS_DB.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_models_db(db: dict[str, bool]) -> None:
    """Save the models database to ~/.config/trnsl/models.json."""
    TRNSL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TRNSL_MODELS_DB.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def model_exists_on_disk(model: str) -> bool:
    """Check if a model actually exists in Ollama's storage via CLI."""
    # Try ollama list first (works offline)
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n")[1:]:  # skip header
                name = line.split()[0] if line else ""
                if name == model:
                    return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    # Fallback: check filesystem directly (works even if ollama CLI is broken)
    manifests_dir = Path.home() / ".ollama/models/manifests/registry.ollama.ai/library"
    if not manifests_dir.exists():
        return False
    prefix = model.replace(":", "_")
    for f in manifests_dir.rglob(f"{prefix}*"):
        if f.is_file():
            return True
    # Last resort: check blobs directory
    blobs_dir = Path.home() / ".ollama/models/blobs"
    if blobs_dir.exists():
        for f in blobs_dir.iterdir():
            if model.replace(":", "") in f.name:
                return True
    return False


def pick_model_fzf(local_models: list[str]) -> str | None:
    """Show fzf picker with translation models. Installed models first. Returns model tag or None."""
    # Add any locally installed models that are not in TRANSLATION_MODELS
    all_models = list(TRANSLATION_MODELS)
    for m in local_models:
        if not any(tag == m for tag, _, _ in TRANSLATION_MODELS):
            all_models.append((m, "?", "Другая модель"))

    def sort_key(item):
        tag = item[0]
        installed = 0 if tag in local_models else 1
        return (installed, tag)

    sorted_models = sorted(all_models, key=sort_key)
    lines = "\n".join(
        f"{'✅' if tag in local_models else '☁️'} {tag}|{size}|{desc}"
        for tag, size, desc in sorted_models
    )
    header = "Enter: install | Ctrl+C: cancel"
    if local_models:
        header += f"\n✅ = installed | ☁️ = not installed"
    try:
        result = subprocess.run(
            [
                "fzf",
                "--height=50%",
                "--layout=reverse",
                "--border=rounded",
                "--prompt=Pick a translation model > ",
                f"--header={header}",
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
            raw = result.stdout.strip().split("|")[0]
            # Remove emoji prefix
            return raw.lstrip("✅☁️ ")
    except FileNotFoundError:
        pass
    return None


def pick_model_menu(local_models: list[str]) -> str | None:
    """Fallback numbered menu when fzf is not available. Installed models first."""
    # Add any locally installed models that are not in TRANSLATION_MODELS
    all_models = list(TRANSLATION_MODELS)
    for m in local_models:
        if not any(tag == m for tag, _, _ in TRANSLATION_MODELS):
            all_models.append((m, "?", "Другая модель"))

    def sort_key(item):
        tag = item[0]
        installed = 0 if tag in local_models else 1
        return (installed, tag)

    sorted_models = sorted(all_models, key=sort_key)
    console.print("\n[bold yellow]Available translation models:[/bold yellow]\n")
    for i, (tag, size, desc) in enumerate(sorted_models, 1):
        emoji = "✅" if tag in local_models else "☁️"
        console.print(f"  [cyan]{i}[/cyan]  {emoji} [bold]{tag}[/bold] [dim]({size})[/dim]  {desc}")
    console.print()
    try:
        choice = input("Enter number (Enter = 1, Ctrl+C = cancel): ").strip()
        idx = (int(choice) - 1) if choice else 0
        if 0 <= idx < len(sorted_models):
            return sorted_models[idx][0]
    except (ValueError, KeyboardInterrupt):
        pass
    return None


def ensure_model(requested: str) -> str:
    """If requested model is not installed — prompt user to pick and install one."""
    # Check if ollama is installed
    try:
        subprocess.run(["ollama", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print(
            "\n[red]Ollama is not installed.[/red]\n"
            "To translate files, Ollama must be installed and running.\n\n"
            "  [bold]brew install ollama[/bold]\n"
            "  [dim](then run: ollama serve in background)[/dim]\n"
        )
        console.input("\n[bold]Press Enter to exit...[/bold]")
        sys.exit(1)

    # Load our models database
    db = load_models_db()

    # Always show picker — let user choose
    local = []
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n")[1:]:  # skip header
                name = line.split()[0] if line else ""
                if name:
                    local.append(name)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    console.print(
        "\n[bold yellow]Select a model to use "
        "([bold]smollm2:135m[/bold] recommended — 270 MB, quick start):\n"
    )

    # Get list of installed models for the picker (via CLI)
    local = []
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n")[1:]:  # skip header
                name = line.split()[0] if line else ""
                if name:
                    local.append(name)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    model = pick_model_fzf(local) or pick_model_menu(local)
    if not model:
        console.print("[red]Cancelled.[/red]")
        sys.exit(1)

    # Check if already installed
    if model in local:
        console.print(f"[green]✓[/green] {model} already installed\n")
        return model

    console.print(f"\n[bold]Pulling {model}...[/bold]")
    result = subprocess.run(["ollama", "pull", model], capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]Error pulling {model}:[/red]")
        console.print(result.stderr.strip())
        sys.exit(1)

    # Update DB
    db[model] = True
    save_models_db(db)
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


def _strip_markdown_fence(text: str) -> str:
    """Remove outer ```markdown ... ``` wrapper that LLMs sometimes add."""
    stripped = text.strip()
    for fence in ("```markdown", "```md", "```"):
        if stripped.startswith(fence) and stripped.endswith("```"):
            inner = stripped[len(fence):].lstrip("\n")
            # only strip if the closing ``` is the final one
            inner = inner[:inner.rfind("```")].rstrip("\n")
            return inner
    return text


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

    result = "\n\n".join(translated_parts)
    result = _strip_markdown_fence(result)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")
    console.print(f"[green]✓[/green] saved -> {output_path}")


if __name__ == "__main__":
    main()
