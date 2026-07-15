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
import traceback
from pathlib import Path

MD2DOCX = str(Path(__file__).resolve().with_name("md2docx.py"))


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
        doc.Content.Copy()
        # Materialize delayed OLE clipboard formats before Word/document closes.
        import pythoncom
        pythoncom.OleFlushClipboard()
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
    if os.name != "nt":
        raise RuntimeError("The clipboard helper requires Windows and Microsoft Word.")
    if not os.path.isfile(MD2DOCX):
        raise FileNotFoundError(f"Converter not found next to clipboard helper: {MD2DOCX}")
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

    # Convert into a private temporary DOCX, then let Word copy its content.
    tmp_out = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            tmp_out = f.name
        print("Converting to .docx ...")
        from md2docx import convert_markdown
        Path(tmp_out).write_bytes(convert_markdown(text))

        # ── Copy rich content to clipboard via Word ──────────────────────────
        print("Copying formatted content to clipboard via Word ...")
        copy_docx_to_clipboard(os.path.abspath(tmp_out))

        print("Done! Paste into Word with Ctrl+V.")

    except Exception as exc:
        traceback.print_exc()
        # pythonw/shortcut launches have no console, so make failures visible.
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, str(exc), "md2docx clipboard error", 0x10)
        except Exception:
            pass
        sys.exit(1)
    finally:
        for path in (tmp_out,):
            if not path:
                continue
            try:
                os.unlink(path)
            except OSError:
                pass


if __name__ == "__main__":
    main()
