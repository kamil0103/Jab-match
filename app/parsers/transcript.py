import fitz
import re
import os
from typing import List, Dict, Any

def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def parse_transcript(pdf_path: str) -> Dict[str, Any]:
    text = extract_text_from_pdf(pdf_path)
    # Basic heuristic: split into lines and try to find course-like patterns
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return {
        "raw_text": text,
        "lines": lines,
        "page_count": fitz.open(pdf_path).page_count
    }
