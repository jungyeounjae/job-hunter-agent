from pathlib import Path
import io

from docx import Document
from pypdf import PdfReader


TEMPLATE_PATH = Path("knowledge/templates/직무이력서_템플릿.md")


class UnsupportedResumeFormatError(ValueError):
    pass


def parse_resume_bytes(data: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8").strip()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        if not text:
            raise ValueError("PDF에서 텍스트를 추출하지 못했습니다.")
        return text
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs).strip()
        if not text:
            raise ValueError("DOCX에서 텍스트를 추출하지 못했습니다.")
        return text
    raise UnsupportedResumeFormatError(f"지원하지 않는 형식: {filename}")
