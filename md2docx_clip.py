#!/usr/bin/env python3
"""
md2docx_clip.py
---------------
1. Reads plain text (Markdown) from clipboard
2. Converts it through md2docx -> temp .docx
3. Opens the .docx in a hidden Word instance, selects all, copies
4. Closes Word – clipboard now contains Word-native rich content
5. Paste directly into any Word document with Ctrl+V

Usage:
  md2docx_clip          (uses clipboard)
  md2docx_clip file.txt (uses file, still puts result on clipboard)
"""
from __future__ import annotations

import os
import sys
import tempfile
import subprocess
import traceback

VENV_PY  = r"C:\opt\md2docx\.venv\Scripts\python.exe"
MD2DOCX  = r"C:\opt\md2docx\md2docx.py"


def get_clipboard_text() -> str:
    import win32clipboard
    win32clipboard.OpenClipboard()
    try:
        return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


def copy_docx_to_clipboard(docx_path: str) -> None:
    """Open docx in Word, select all, copy, then close only our doc.
    If Word was already open, we leave it running untouched."""
    import time
    import win32com.client

    # Check if Word is already running — if so, reuse it and NEVER quit
    try:
        word = win32com.client.GetActiveObject("Word.Application")
        word_was_running = True
    except Exception:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word_was_running = False

    doc = None
    try:
        doc = word.Documents.Open(FileName=docx_path, AddToRecentFiles=False, Visible=False)
        word.Selection.WholeStory()
        word.Selection.Copy()
    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
        # Only quit if we were the ones who started Word
        if not word_was_running:
            try:
                word.Quit(SaveChanges=False)
            except Exception:
                pass
        time.sleep(0.5)  # let Word release the file handle


def main() -> None:
    # ── Source text ──────────────────────────────────────────────────────────
    if len(sys.argv) >= 2:
        with open(sys.argv[1], encoding="utf-8") as f:
            text = f.read()
        print(f"Reading from file: {sys.argv[1]}")
    else:
        text = get_clipboard_text()
        if not text.strip():
            print("Clipboard is empty or has no text.")
            sys.exit(1)
        print(f"Read {len(text)} characters from clipboard.")

    # ── Write to temp input file ─────────────────────────────────────────────
    tmp_in  = tempfile.mktemp(suffix=".txt")
    tmp_out = tmp_in.replace(".txt", ".docx")

    try:
        with open(tmp_in, "w", encoding="utf-8") as f:
            f.write(text)

        # ── Convert via md2docx ──────────────────────────────────────────────
        print("Converting to .docx ...")
        result = subprocess.run(
            [VENV_PY, MD2DOCX, tmp_in, "-o", tmp_out],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("md2docx error:\n", result.stderr)
            sys.exit(1)

        # ── Copy rich content to clipboard via Word ──────────────────────────
        print("Copying formatted content to clipboard via Word ...")
        copy_docx_to_clipboard(os.path.abspath(tmp_out))

        print("Done! Paste into Word with Ctrl+V.")

    except Exception:
        traceback.print_exc()
        sys.exit(1)
    finally:
        for f in (tmp_in, tmp_out):
            try:
                os.unlink(f)
            except OSError:
                pass


if __name__ == "__main__":
    main()
