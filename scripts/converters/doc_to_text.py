#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pymupdf",
#   "rich",
#   "python-docx",
#   "beautifulsoup4",
#   "pytesseract",
#   "pillow",
#   "numpy",
#   "openpyxl",
#   "python-pptx",
# ]
# ///

"""
Конвертация документов -> TXT/MD
Поддерживаемые форматы: PDF, XPS, EPUB, MOBI, FB2, CBZ, SVG, DOC, DOCX, RTF, ODT, HTML, XLS, XLSX, PPTX, JPG, PNG
Использование: uv run doc_to_text.py input.[format] [--format md|txt] [--keep-images]

Вложенные изображения (DOCX/PPTX/HTML) извлекаются рядом с выходным файлом
как {stem}_image_N.ext, в текст вставляются ссылки ![Картинка N](...),
a в конце добавляется приложение с их списком.
"""

import argparse
import glob
import multiprocessing
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


# Lazy imports — загружаются только при вызове конвертера
# Это позволяет модулю импортироваться без установленных библиотек
def _import_fitz():
    import fitz  # PyMuPDF

    return fitz


def _import_rich():
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

    return Console, Panel, Progress, SpinnerColumn, TimeElapsedColumn


# Глобальные переменные для настройки вывода
OUTPUT_FORMAT = "md"  # "txt" или "md"
KEEP_IMAGES = True  # Сохранять PNG при конвертации (оптимум для Vision LLM)
FORCE_CONVERT = False  # Принудительная конвертация (игнорировать кэш)


def post_process_ocr(text: str) -> str:
    """
    Пост-обработка OCR: посимвольная замена латиницы→кириллица
    Простой и эффективный подход без огромных словарей
    """
    if not text or len(text.strip()) < 10:
        return text

    # 1. ЗАЩИТА: сохраняем email, URL, номера от замены
    # Используем цифровой placeholder, чтобы LAT_TO_CYR его не трогал
    protected = []

    def protect(match):
        idx = len(protected)
        protected.append(match.group(0))
        return f"<<<__{idx}__>>>"

    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", protect, text)
    text = re.sub(r"https?://\S+|(?:[a-z]+\.){2,}[a-z]+", protect, text, flags=re.I)
    text = re.sub(r"\b\d{2,3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b", protect, text)

    # 2. ТАБЛИЦА ЗАМЕНЫ: латиница→кириллица (визуально похожие + частые OCR-ошибки)
    LAT_TO_CYR = str.maketrans(
        {
            # Визуально идентичные (заглавные)
            "A": "А",
            "B": "В",
            "C": "С",
            "E": "Е",
            "H": "Н",
            "K": "К",
            "M": "М",
            "O": "О",
            "P": "Р",
            "T": "Т",
            "X": "Х",
            "Y": "У",
            # Визуально идентичные (строчные)
            "a": "а",
            "c": "с",
            "e": "е",
            "k": "к",
            "o": "о",
            "p": "р",
            "t": "т",
            "x": "х",
            "y": "у",
            # OCR-артефакты (частые замены заглавных)
            "N": "П",
            "W": "Ш",
            "D": "Д",
            "G": "Г",
            "U": "И",
            "J": "Л",
            "L": "Л",
            "S": "С",
            "F": "Ф",
            "I": "І",
            "R": "Р",
            "Z": "З",
            "Q": "К",
            # OCR-артефакты (частые замены строчных)
            "n": "п",
            "w": "ш",
            "d": "д",
            "g": "г",
            "u": "и",
            "l": "л",
            "b": "б",
            "v": "в",
            "s": "с",
            "m": "м",
            "f": "ф",
            "i": "і",
            "r": "г",
            "z": "з",
            "q": "к",
            # Цифры вместо букв
            "6": "б",
            "3": "з",
        }
    )

    # 3. СПЕЦИФИЧНЫЕ ПАТТЕРНЫ: только то, что нельзя транслитерировать
    SPECIAL_PATTERNS = {
        # Двойные/тройные точки → одна точка
        r"\.{2,}": ".",
        # Сохраняем технические параметры как есть
        r"(type=\d+\.\d+)": r"\1",
        r"(process_id=[a-f0-9-]+)": r"\1",
    }

    for pattern, replacement in SPECIAL_PATTERNS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 4. ГЛОБАЛЬНАЯ ПОСИМВОЛЬНАЯ ЗАМЕНА: применяем ко всему тексту
    text = text.translate(LAT_TO_CYR)

    # 5. ОБРАТНАЯ КОНВЕРТАЦИЯ: email/URL из кириллицы обратно в латиницу
    # Tesseract script/Cyrillic распознаёт email как кириллицу, исправляем это
    CYR_TO_LAT = str.maketrans(
        {
            "А": "A",
            "В": "B",
            "С": "C",
            "Е": "E",
            "Н": "H",
            "К": "K",
            "М": "M",
            "О": "O",
            "Р": "P",
            "Т": "T",
            "Х": "X",
            "У": "Y",
            "а": "a",
            "с": "c",
            "е": "e",
            "к": "k",
            "о": "o",
            "р": "r",
            "т": "t",
            "х": "x",
            "у": "y",
            # Сербские кириллические буквы из script/Cyrillic
            "і": "i",
            "ј": "j",
            "ѕ": "s",
            "ґ": "g",
            "ї": "i",
            "І": "I",
            "Ј": "J",
            "Ѕ": "S",
            "Ґ": "G",
            "Ї": "I",
        }
    )

    def fix_cyrillic_email_url(match):
        """Конвертирует кириллические email/URL обратно в латиницу"""
        cyrillic_text = match.group(0)
        return cyrillic_text.translate(CYR_TO_LAT)

    # Поиск кириллических email (например: БаКһЫк@уа.ги)
    text = re.sub(
        r"[а-яА-ЯіјѕґїІЈЅҐЇ0-9._%+-]+@[а-яА-ЯіјѕґїІЈЅҐЇ0-9.-]+\.[а-яА-ЯіјѕґїІЈЅҐЇ]{2,}",
        fix_cyrillic_email_url,
        text,
    )

    # Поиск кириллических URL (например: еј.ѕиагї.ги)
    text = re.sub(
        r"(?:[а-яА-ЯіјѕґїІЈЅҐЇ]+\.){2,}[а-яА-ЯіјѕґїІЈЅҐЇ]+",
        fix_cyrillic_email_url,
        text,
    )

    # 6. ВОССТАНОВЛЕНИЕ: возвращаем защищённые элементы
    for idx, original in enumerate(protected):
        text = text.replace(f"<<<__{idx}__>>>", original)

    return text


def format_as_markdown(text: str) -> str:
    """Форматирование текста под Markdown для лучшего парсинга нейросетями"""
    lines = text.split("\n")
    formatted_lines = []

    # Стоп-слова для меток (не заголовки)
    label_keywords = [
        "ФИО",
        "СНИЛС",
        "ИНН",
        "ОГРН",
        "ДАТА",
        "АДРЕС",
        "ТЕЛЕФОН",
        "EMAIL",
        "НОМЕР",
        "СЕРИЯ",
        "КОД",
        "ПАСПОРТ",
        "МЕСТО",
        "ЕМАІЛ",
    ]

    for line in lines:
        stripped = line.strip()

        # Пропускаем пустые строки
        if not stripped:
            formatted_lines.append("")
            continue

        # Проверка на метку (ключевое слово + двоеточие)
        is_label = any(stripped.upper().startswith(f"{kw}:") for kw in label_keywords)

        # Заголовки: ЗАГЛАВНЫЕ СТРОКИ → ## Заголовок
        # Условия: длина > 10, не заканчивается на ":", хотя бы 2 слова, не только цифры, не метка
        is_heading = (
            stripped.isupper()
            and len(stripped) > 10
            and not stripped.endswith(":")
            and len(stripped.split()) >= 2
            and not stripped.replace(" ", "").isdigit()
            and not is_label
        )
        if is_heading:
            formatted_lines.append(f"\n## {stripped.title()}\n")
            continue

        # Списки: строки начинающиеся с "-", "•", цифр
        if re.match(r"^[\-•\*]\s+", stripped) or re.match(r"^\d+[\.\)]\s+", stripped):
            formatted_lines.append(f"- {stripped.lstrip('-•*0123456789.) ')}")
            continue

        # Обычный текст
        formatted_lines.append(stripped)

    return "\n".join(formatted_lines)


def needs_conversion(input_path: Path, output_path: Path) -> bool:
    """
    Проверка необходимости конвертации (ленивая конвертация)
    Возвращает True если нужна конвертация:
    - Output файл не существует
    - Input файл новее Output файла (по mtime)
    - Для PNG: если хотя бы один PNG отсутствует
    """
    if FORCE_CONVERT:
        return True

    if not output_path.exists():
        return True

    # Проверяем время модификации
    input_mtime = input_path.stat().st_mtime
    output_mtime = output_path.stat().st_mtime

    if input_mtime > output_mtime:
        return True

    # Если включено сохранение PNG, проверяем наличие хотя бы одного PNG
    # (избегаем открытия PDF через fitz — это дорого для каждого файла)
    if KEEP_IMAGES:
        if input_path.suffix.lower() in [
            ".pdf",
            ".xps",
            ".epub",
            ".mobi",
            ".fb2",
            ".cbz",
            ".svg",
        ]:
            # glob.escape экранирует [ ] ? * в имени файла (например [77RS0015-504-26-0000006])
            escaped_stem = glob.escape(output_path.stem)
            existing_pngs = list(output_path.parent.glob(f"{escaped_stem}_page_*.png"))
            if not existing_pngs:
                return True

    return False


def resolve_output_path(pdf_path: Path) -> Path:
    output_base = os.environ.get("CONVERT_OUTPUT_BASE")
    input_base = os.environ.get("CONVERT_INPUT_BASE")

    # Выбираем расширение на основе формата
    ext = ".md" if OUTPUT_FORMAT == "md" else ".txt"

    if not output_base:
        return pdf_path.with_suffix(ext)

    output_base_path = Path(output_base).resolve()
    pdf_path_abs = pdf_path.resolve()

    if input_base:
        input_base_path = Path(input_base).resolve()
        try:
            relative_parent = pdf_path_abs.parent.relative_to(input_base_path)
        except ValueError:
            # Если не удалось вычислить относительный путь, используем имя файла напрямую
            relative_parent = Path(".")
    else:
        relative_parent = Path(".")

    ext = ".md" if OUTPUT_FORMAT == "md" else ".txt"
    return output_base_path / relative_parent / f"{pdf_path.stem}{ext}"


def ocr_pdf_page(page, output_path: Path = None, page_num: int = 1) -> str:
    """OCR для страницы PDF (если текстовый слой отсутствует)"""
    try:
        import io

        import numpy as np
        import pytesseract
        from PIL import Image, ImageEnhance

        os.environ["TESSDATA_PREFIX"] = "/opt/homebrew/share/tessdata"

        # Рендерим страницу в изображение (высокое разрешение для OCR)
        # PNG уже сохранён в convert_with_pymupdf() если KEEP_IMAGES=True
        _fitz = _import_fitz()
        pix = page.get_pixmap(matrix=_fitz.Matrix(2, 2))  # 2x zoom для качества
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        # Preprocessing для лучшего OCR
        if img.mode != "L":
            img = img.convert("L")

        # Бинаризация
        img_array = np.array(img)
        threshold = 128
        img_array = np.where(img_array > threshold, 255, 0).astype(np.uint8)
        img = Image.fromarray(img_array)

        # Увеличение контраста
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # OCR: КОМБИНИРОВАННАЯ МОДЕЛЬ ДЛЯ СМЕШАННЫХ ТЕКСТОВ
        # script/Cyrillic: кириллическое письмо (удаляет латинские артефакты в русском тексте)
        # +eng: сохраняет латиницу для email/URL (вместо преобразования в кириллицу)
        # --oem 1: LSTM нейросеть
        # --psm 3: автоматическая сегментация страницы
        # -c load_system_dawg=0: отключить системный словарь (предотвращает латинские подстановки)
        # -c load_freq_dawg=0: отключить частотный словарь
        custom_config = r"--oem 1 --psm 3 -c load_system_dawg=0 -c load_freq_dawg=0"
        text = pytesseract.image_to_string(
            img, lang="script/Cyrillic+eng", config=custom_config
        )

        # Пост-обработка: ВКЛЮЧЕНА для очистки оставшихся артефактов
        text = post_process_ocr(text.strip())

        return text.strip()
    except Exception as e:
        return f"[OCR ОШИБКА: {str(e)}]"


def should_render_png(page, text: str) -> bool:
    """Определяет необходимость PNG для страницы (умный режим --smart-images)

    PNG создаётся если страница содержит:
    - Изображения (печати, подписи, фото)
    - Таблицы (много табуляций/границ)
    - Мало текста (скан низкого качества)
    - Низкая плотность текста (много визуального контента)

    Иначе достаточно только OCR текста.
    """
    if not SMART_IMAGES:
        return KEEP_IMAGES  # Обычный режим: все страницы по KEEP_IMAGES

    # 1. Есть изображения (печати, подписи, логотипы, фото)
    images = page.get_images()
    if len(images) > 0:
        return True

    # 2. Есть таблицы (эвристика: много табуляций или символов границ)
    table_indicators = (
        text.count("\t") + text.count("|") + text.count("┃") + text.count("─")
    )
    if table_indicators > 5:
        return True

    # 3. Мало текста (плохой OCR или визуальный контент)
    if len(text.strip()) < 100:
        return True

    # 4. Низкая плотность текста = много визуального (формулы, графики, схемы)
    rect = page.rect
    page_area = rect.width * rect.height
    text_length = len(text)
    density = text_length / page_area if page_area > 0 else 0

    if density < 0.1:  # Эмпирический порог
        return True

    # Иначе текста достаточно для анализа
    return False


def convert_with_pymupdf(path: Path, output_path: Path = None) -> list[str]:
    """Конвертация через PyMuPDF (PDF, XPS, EPUB, MOBI, FB2, CBZ, SVG)
    Автоматически применяет OCR к страницам без текстового слоя
    Если KEEP_IMAGES=True, рендерит каждую страницу в PNG с добавлением ссылок в MD
    Если SMART_IMAGES=True, PNG только для страниц с таблицами/изображениями/печатями"""
    _fitz = _import_fitz()
    doc = _fitz.open(path)
    full_text = []

    for page_num, page in enumerate(doc, start=1):
        page_text_parts = []

        # Сначала извлекаем текст (нужен для should_render_png)
        text = page.get_text().strip()

        # Решаем: нужен PNG для этой страницы?
        render_png = should_render_png(page, text)

        # Рендерим страницу в PNG если нужно (умный режим или KEEP_IMAGES)
        if render_png and output_path:
            pix = page.get_pixmap(matrix=_fitz.Matrix(2, 2))  # 2x zoom для качества
            png_filename = f"{output_path.stem}_page_{page_num}.png"
            png_path = output_path.with_name(png_filename)
            png_path.parent.mkdir(
                parents=True, exist_ok=True
            )  # Создаём папку если не существует
            pix.save(str(png_path))

            # Добавляем ссылку на изображение в Markdown
            if OUTPUT_FORMAT == "md":
                page_text_parts.append(f"![Страница {page_num}]({png_filename})\n")

        # Если текста нет или очень мало (скан без распознавания)
        if len(text) < 20:
            # Применяем OCR только для PDF (не для EPUB/MOBI)
            if path.suffix.lower() == ".pdf":
                ocr_text = ocr_pdf_page(page, output_path, page_num)
                if ocr_text and len(ocr_text) > len(text):
                    text = f"[OCR]\n{ocr_text}"

        page_text_parts.append(f"--- Страница {page_num} ---\n{text}")
        full_text.append("\n".join(page_text_parts))

    return full_text


def convert_doc(path: Path, output_path=None) -> list[str]:
    """Конвертация DOC через antiword"""
    try:
        import subprocess

        result = subprocess.run(
            ["antiword", "-m", "UTF-8", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise Exception(f"antiword: {result.stderr.strip()}")
        return [result.stdout]
    except FileNotFoundError:
        raise Exception("antiword не установлен")


class _ImageSaver:
    """Сохраняет вложенные изображения рядом с выходным файлом.

    Именование: {stem}_image_1.ext, {stem}_image_2.ext, ...
    Одинаковые байты (по SHA-1) сохраняются один раз (дедупликация).
    """

    def __init__(self, output_path: Path | None):
        self.output_path = output_path
        self._names: dict[str, str] = {}  # sha1 -> имя файла
        self._n = 0

    @property
    def count(self) -> int:
        return self._n

    def save(self, blob: bytes, ext: str) -> str | None:
        if self.output_path is None or not blob:
            return None
        import hashlib

        key = hashlib.sha1(blob).hexdigest()[:12]
        if key in self._names:
            return self._names[key]
        self._n += 1
        safe_ext = re.sub(r"[^a-zA-Z0-9.]", "", ext) or ".png"
        if not safe_ext.startswith("."):
            safe_ext = "." + safe_ext
        if len(safe_ext) < 2:
            safe_ext = ".png"
        fname = f"{self.output_path.stem}_image_{self._n}{safe_ext}"
        out = self.output_path.with_name(fname)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
        self._names[key] = fname
        return fname

    @property
    def unique_names(self) -> list[str]:
        return list(dict.fromkeys(self._names.values()))

    def ref(self, fname: str | None) -> str | None:
        """Читаемая ссылка на извлечённую картинку"""
        if not fname:
            return None
        return f"![Картинка {self._n}]({fname})"

    def appendix(self) -> str:
        """Приложение в конец документа: список извлечённых изображений"""
        if not self._names:
            return ""
        listing = "\n".join(
            f"{i}. `{name}`" for i, name in enumerate(self.unique_names, 1)
        )
        return (
            f"\n\n## Приложение: изображения ({len(self.unique_names)})\n\n"
            f"Дополнение к документу — извлечённые вложенные файлы:\n{listing}"
        )


def convert_docx(path: Path, output_path=None) -> list[str]:
    """Конвертация DOCX: текст и таблицы по порядку документа +
    вложенные изображения (word/media) с сносками и приложением"""
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.table import Table

        doc = Document(path)
        saver = _ImageSaver(output_path)
        parts: list[str] = []

        def para_text(p_el) -> str:
            return "".join(n.text or "" for n in p_el.iter(qn("w:t")))

        def para_image_refs(p_el) -> list[str]:
            """Ссылки на вложенные изображения внутри элемента абзаца"""
            refs = []
            for blip in p_el.iter(qn("a:blip")):
                rid = blip.get(qn("r:embed")) or blip.get(qn("r:link"))
                if not rid:
                    continue
                rel = doc.part.rels.get(rid)
                if rel is None or rel.is_external or rel.target_part is None:
                    continue
                fname = saver.save(
                    rel.target_part.blob, Path(rel.target_part.partname).suffix
                )
                ref = saver.ref(fname)
                if ref:
                    refs.append(ref)
            return refs

        def cell_text(tc_el) -> str:
            return " ".join(
                para_text(p) for p in tc_el.iter(qn("w:p"))
            ).strip()

        for child in doc.element.body.iterchildren():
            tag = child.tag.split("}")[-1]
            if tag == "p":
                text = para_text(child).strip()
                if text:
                    parts.append(text)
                parts.extend(para_image_refs(child))
            elif tag == "tbl":
                table = Table(child, doc)
                rows = [
                    "| " + " | ".join(cell_text(tc._tc) for tc in tr.cells) + " |"
                    for tr in table.rows
                ]
                if rows:
                    ncols = len(table.columns)
                    sep_line = "| " + " | ".join("---" for _ in range(ncols)) + " |"
                    # Таблица — один блок (строки через одиночный перенос)
                    parts.append("\n".join([rows[0], sep_line, *rows[1:]]))
                # Изображения, вставленные внутрь ячеек таблицы
                parts.extend(
                    ref
                    for tr in table.rows
                    for tc in tr.cells
                    for p_el in tc._tc.iter(qn("w:p"))
                    for ref in para_image_refs(p_el)
                )

        # В MD блоки разделяются пустой строкой, иначе рендер
        # склеит всё в один абзац, а таблицу «съест» в текст
        sep = "\n\n" if OUTPUT_FORMAT == "md" else "\n"
        text = sep.join(p for p in parts if p)
        text += saver.appendix()
        return [text]
    except ImportError:
        raise Exception("python-docx не установлен")


def convert_html(path: Path, output_path=None) -> list[str]:
    """Конвертация HTML: текст + локальные изображения (<img> с относительным src)"""
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import unquote

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            soup = BeautifulSoup(f, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            if OUTPUT_FORMAT == "md":
                # Пустая строка между блоками, иначе MD склеит всё в один абзац
                text = "\n\n".join(
                    line for line in (x.strip() for x in text.splitlines()) if line
                )

        saver = _ImageSaver(output_path)
        refs = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if not src or src.startswith(("http://", "https://", "data:")):
                continue
            src_path = (path.parent / unquote(src)).resolve()
            if not src_path.exists():
                continue
            ref = saver.ref(saver.save(src_path.read_bytes(), src_path.suffix))
            if ref:
                refs.append(ref)

        if refs:
            text += "\n\n" + "\n".join(refs)
        text += saver.appendix()
        return [text]
    except ImportError:
        raise Exception("beautifulsoup4 не установлен")


def convert_rtf(path: Path, output_path=None) -> list[str]:
    """Конвертация RTF через pandoc"""
    try:
        import subprocess

        result = subprocess.run(
            ["pandoc", str(path), "-t", "plain"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise Exception(f"pandoc: {result.stderr.strip()}")
        return [result.stdout]
    except FileNotFoundError:
        raise Exception("pandoc не установлен")


def convert_odt(path: Path, output_path=None) -> list[str]:
    """Конвертация ODT через pandoc"""
    try:
        import subprocess

        result = subprocess.run(
            ["pandoc", str(path), "-t", "plain"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise Exception(f"pandoc: {result.stderr.strip()}")
        return [result.stdout]
    except FileNotFoundError:
        raise Exception("pandoc не установлен")


def convert_xlsx(path: Path, output_path=None) -> list[str]:
    """Конвертация XLSX (таблицы)"""
    try:
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True)
        lines = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                lines.append("\t".join(cells))
        return ["\n".join(lines)]
    except ImportError:
        raise Exception("openpyxl не установлен")


def convert_xls(path: Path, output_path=None) -> list[str]:
    """Конвертация XLS через antiword"""
    try:
        import subprocess

        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise Exception(f"antiword: {result.stderr.strip()}")
        return [result.stdout]
    except FileNotFoundError:
        raise Exception("antiword не установлен")


def convert_pptx(path: Path, output_path=None) -> list[str]:
    """Конвертация PPTX: текст слайдов + вложенные изображения (ppt/media)"""
    try:
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        prs = Presentation(path)
        saver = _ImageSaver(output_path)
        lines = []

        def walk(shapes, slide_lines: list[str]) -> None:
            for shape in shapes:
                if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                    walk(shape.shapes, slide_lines)
                    continue
                if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    try:
                        ref = saver.ref(
                            saver.save(shape.image.blob, shape.image.ext)
                        )
                        if ref:
                            slide_lines.append(ref)
                    except Exception:
                        pass
                if hasattr(shape, "text") and shape.text.strip():
                    slide_lines.append(shape.text)

        for slide_idx, slide in enumerate(prs.slides, start=1):
            slide_lines: list[str] = []
            walk(slide.shapes, slide_lines)
            if slide_lines:
                lines.append(f"--- Слайд {slide_idx} ---\n" + "\n".join(slide_lines))

        sep = "\n\n" if OUTPUT_FORMAT == "md" else "\n"
        text = sep.join(lines)
        text += saver.appendix()
        return [text]
    except ImportError:
        raise Exception("python-pptx не установлен")


def convert_image_ocr(path: Path, output_path=None) -> list[str]:
    """Конвертация изображений через OCR"""
    try:
        import numpy as np
        import pytesseract
        from PIL import Image, ImageEnhance

        # Установка пути к tessdata для macOS
        os.environ["TESSDATA_PREFIX"] = "/opt/homebrew/share/tessdata"

        img = Image.open(path)

        # Увеличиваем изображение в 2 раза для лучшего распознавания
        width, height = img.size
        img = img.resize((width * 2, height * 2), Image.LANCZOS)

        # Конвертация в grayscale
        if img.mode != "L":
            img = img.convert("L")

        # Бинаризация (threshold) для четкого черно-белого текста
        img_array = np.array(img)
        threshold = 128
        img_array = np.where(img_array > threshold, 255, 0).astype(np.uint8)
        img = Image.fromarray(img_array)

        # Увеличение контраста
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # OCR: КОМБИНИРОВАННАЯ МОДЕЛЬ ДЛЯ СМЕШАННЫХ ТЕКСТОВ
        # script/Cyrillic: кириллическое письмо (удаляет латинские артефакты в русском тексте)
        # +eng: сохраняет латиницу для email/URL (вместо преобразования в кириллицу)
        # --oem 1: LSTM нейросеть
        # --psm 3: автоматическая сегментация страницы
        # -c load_system_dawg=0: отключить системный словарь (предотвращает латинские подстановки)
        # -c load_freq_dawg=0: отключить частотный словарь
        custom_config = r"--oem 1 --psm 3 -c load_system_dawg=0 -c load_freq_dawg=0"
        text = pytesseract.image_to_string(
            img, lang="script/Cyrillic+eng", config=custom_config
        )

        # Пост-обработка: ВКЛЮЧЕНА для очистки оставшихся артефактов
        text = post_process_ocr(text)

        return [f"--- OCR: {path.name} ---\n{text}"]
    except ImportError:
        raise Exception("pytesseract или pillow не установлен")
    except Exception as e:
        raise Exception(f"Ошибка OCR (проверьте установку tesseract): {e}")


# Динамический реестр конвертеров: {расширение: (функция, kwargs)}
# Добавление нового формата = один новый convert_xxx() + запись в REGISTRY
CONVERTERS: dict[str, tuple] = {}


def register(ext: str, func):
    """Регистрация конвертера для расширения."""
    CONVERTERS[ext] = (func, {})


def convert_file_to_text(path: Path, output_path: Path = None) -> list[str]:
    """Универсальная функция конвертации через реестр."""
    ext = path.suffix.lower()

    if ext not in CONVERTERS:
        raise Exception(f"Формат {ext} не поддерживается")

    func, kwargs = CONVERTERS[ext]
    return func(path, output_path=output_path, **kwargs)


# --- Регистрация всех конвертеров ---
register(".pdf", convert_with_pymupdf)
register(".xps", convert_with_pymupdf)
register(".epub", convert_with_pymupdf)
register(".mobi", convert_with_pymupdf)
register(".fb2", convert_with_pymupdf)
register(".cbz", convert_with_pymupdf)
register(".svg", convert_with_pymupdf)
register(".doc", convert_doc)
register(".docx", convert_docx)
register(".rtf", convert_rtf)
register(".odt", convert_odt)
register(".html", convert_html)
register(".htm", convert_html)
register(".xls", convert_xls)
register(".xlsx", convert_xlsx)
register(".pptx", convert_pptx)
register(".jpg", convert_image_ocr)
register(".jpeg", convert_image_ocr)
register(".png", convert_image_ocr)
register(".bmp", convert_image_ocr)
register(".tiff", convert_image_ocr)
register(".tif", convert_image_ocr)
register(".webp", convert_image_ocr)


def convert_pdf_to_text(pdf_path: str) -> bool:
    Console, Panel, Progress, SpinnerColumn, TimeElapsedColumn = _import_rich()
    console = Console()
    path = Path(pdf_path)

    if not path.exists():
        console.print(f"[bold red]Ошибка:[/bold red] Файл {pdf_path} не найден.")
        return False

    try:
        # Определяем output path сначала (нужен для сохранения PNG)
        output_file = resolve_output_path(path)

        # Проверяем: нужна ли конвертация?
        if not needs_conversion(path, output_file):
            console.print(f"[dim cyan]Пропуск:[/dim cyan] {path.name} (уже актуален)")
            return True

        # Определяем формат и конвертируем
        full_text = convert_file_to_text(path, output_file)

        # Применяем форматирование Markdown если включено
        if OUTPUT_FORMAT == "md":
            full_text = [format_as_markdown(text) for text in full_text]

        console.print(f"[cyan]Обработка:[/cyan] {path.name} (формат: {path.suffix})")

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("\n\n".join(full_text), encoding="utf-8")

        console.print(
            Panel(
                f"[bold green]Успешно![/bold green]\nТекст сохранен в: [yellow]{output_file}[/yellow]",
                title="Результат конвертации",
            )
        )
        return True
    except Exception as e:
        console.print(f"[bold red]Ошибка:[/bold red] {e}")
        return False


def convert_single_file_silent(pdf_path: str) -> tuple[str, bool, str]:
    """Тихая конвертация одного файла (для многопоточности)"""
    path = Path(pdf_path)

    if not path.exists():
        return (pdf_path, False, f"Файл не найден")

    try:
        # Определяем output_path ДО конвертации (нужен для сохранения PNG)
        output_file = resolve_output_path(path)

        # Проверяем: нужна ли конвертация?
        if not needs_conversion(path, output_file):
            return (pdf_path, True, f"{str(output_file)} (пропущен)")

        # Конвертируем с передачей output_path
        full_text = convert_file_to_text(path, output_file)

        # Применяем форматирование Markdown если включено
        if OUTPUT_FORMAT == "md":
            full_text = [format_as_markdown(text) for text in full_text]

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("\n\n".join(full_text), encoding="utf-8")
        return (pdf_path, True, str(output_file))
    except Exception as e:
        return (pdf_path, False, str(e))


def batch_convert(file_paths: list[str], max_workers: int = None) -> dict:
    """Batch-конвертация с многопоточностью"""
    Console, Panel, Progress, SpinnerColumn, TimeElapsedColumn = _import_rich()
    if max_workers is None:
        # Для IO-bound операций можем использовать больше потоков
        max_workers = min(multiprocessing.cpu_count() * 2, 16, len(file_paths))

    console = Console()
    results = {"success": [], "failed": []}

    with Progress(
        SpinnerColumn(),
        *Progress.get_default_columns(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Конвертация {len(file_paths)} файлов...", total=len(file_paths)
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(convert_single_file_silent, fp): fp for fp in file_paths
            }

            try:
                for future in as_completed(futures):
                    file_path, success, message = future.result()
                    progress.advance(task)

                    if success:
                        results["success"].append((file_path, message))
                    else:
                        results["failed"].append((file_path, message))
            except KeyboardInterrupt:
                console.print("\n[yellow]Прервано пользователем[/yellow]")
                executor.shutdown(wait=False, cancel_futures=True)
                raise

    # Вывод результатов
    console.print(f"\n[bold green]✓ Успешно:[/bold green] {len(results['success'])}")
    console.print(f"[bold red]✗ Ошибок:[/bold red] {len(results['failed'])}")

    if results["failed"]:
        console.print("\n[bold yellow]Файлы с ошибками:[/bold yellow]")
        for fp, err in results["failed"][:5]:  # Показываем первые 5
            console.print(f"  • {Path(fp).name}: {err}")
        if len(results["failed"]) > 5:
            console.print(f"  ... и еще {len(results['failed']) - 5}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Конвертация документов в текстовый формат с OCR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  uv run doc_to_text.py document.pdf
  uv run doc_to_text.py scan.pdf --format md --keep-images
  uv run doc_to_text.py --batch file1.pdf file2.pdf file3.pdf
        """,
    )

    parser.add_argument("files", nargs="+", help="Путь к файлу(ам) для конвертации")

    parser.add_argument(
        "--format",
        choices=["txt", "md"],
        default="md",
        help="Формат вывода: txt (plain text) или md (Markdown с форматированием). По умолчанию: md",
    )

    parser.add_argument(
        "--keep-images",
        action="store_true",
        default=True,
        help="Сохранять PNG-изображения страниц при OCR (для Vision LLM). По умолчанию: включено",
    )

    parser.add_argument(
        "--no-images",
        dest="keep_images",
        action="store_false",
        help="Отключить сохранение PNG-изображений",
    )

    parser.add_argument(
        "--smart-images",
        action="store_true",
        help="Умный режим: PNG только для страниц с таблицами/печатями/изображениями (3-5x быстрее анализ LLM, без потери точности)",
    )

    parser.add_argument(
        "--batch",
        nargs="?",
        const=-1,
        type=int,
        metavar="N",
        help="Batch-режим с N воркерами (по умолчанию: CPU count)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительная конвертация (игнорировать кэш, пересчитать все файлы)",
    )

    args = parser.parse_args()

    # Установка глобальных переменных из аргументов
    OUTPUT_FORMAT = args.format
    KEEP_IMAGES = args.keep_images
    SMART_IMAGES = args.smart_images
    FORCE_CONVERT = args.force

    file_paths = args.files

    # Batch-режим для нескольких файлов
    if args.batch is not None or len(file_paths) > 3:
        max_workers = args.batch if args.batch and args.batch > 0 else None
        results = batch_convert(file_paths, max_workers)
        sys.exit(0 if not results["failed"] else 1)

    # Последовательная обработка для 1-3 файлов
    overall_success = True
    for pdf_path in file_paths:
        success = convert_pdf_to_text(pdf_path)
        if not success:
            overall_success = False

    sys.exit(0 if overall_success else 1)
