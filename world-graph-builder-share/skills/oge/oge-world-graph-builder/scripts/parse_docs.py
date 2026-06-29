#!/usr/bin/env python3
"""
parse_docs.py - turn scenario / supplementary documents into clean text.

Phase 0 (Ingest) helper. Reads PDF, DOCX, TXT, and MD and emits plain text the
generation prompts can consume. PDF uses PyPDF2 (project convention), DOCX uses
python-docx. Both are optional; the script degrades gracefully and tells you
what to install if a format is needed but its dependency is missing.

Usage:
    python3 parse_docs.py scenario.pdf
    python3 parse_docs.py scenario.pdf intel.docx notes.md --out frame_input.txt
"""
import argparse
import os
import sys


def parse_pdf(path):
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        try:
            from pypdf import PdfReader
        except ImportError:
            return None, "PDF support needs PyPDF2 (or pypdf): pip install PyPDF2"
    try:
        reader = PdfReader(path)
        return "\n".join((p.extract_text() or "") for p in reader.pages), None
    except Exception as ex:
        return None, f"failed to read PDF {path}: {ex}"


def parse_docx(path):
    try:
        from docx import Document
    except ImportError:
        return None, "DOCX support needs python-docx: pip install python-docx"
    try:
        d = Document(path)
        return "\n".join(p.text for p in d.paragraphs), None
    except Exception as ex:
        return None, f"failed to read DOCX {path}: {ex}"


def parse_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(), None
    except Exception as ex:
        return None, f"failed to read {path}: {ex}"


def parse_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return parse_pdf(path)
    if ext == ".docx":
        return parse_docx(path)
    if ext in (".txt", ".md", ".markdown", ".text"):
        return parse_text(path)
    # default: try as text
    return parse_text(path)


def main():
    ap = argparse.ArgumentParser(description="Parse scenario documents to clean text.")
    ap.add_argument("files", nargs="+", help="document paths (pdf/docx/txt/md)")
    ap.add_argument("--out", default=None, help="write concatenated text here instead of stdout")
    args = ap.parse_args()

    chunks = []
    had_error = False
    for path in args.files:
        if not os.path.exists(path):
            print(f"ERROR: not found: {path}", file=sys.stderr)
            had_error = True
            continue
        text, err = parse_file(path)
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            had_error = True
            continue
        chunks.append(f"===== FILE: {os.path.basename(path)} =====\n{text.strip()}\n")

    output = "\n".join(chunks)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"wrote {len(output)} chars from {len(chunks)} file(s) -> {args.out}")
    else:
        sys.stdout.write(output)
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
