from app.parsers.transcript import extract_text_from_pdf
from typing import List, Dict, Any

def parse_syllabus(pdf_path: str) -> Dict[str, Any]:
    text = extract_text_from_pdf(pdf_path)
    return {
        "raw_text": text,
        "filename": pdf_path
    }

def parse_syllabi(paths: List[str]) -> List[Dict[str, Any]]:
    return [parse_syllabus(p) for p in paths]
