import pytest

from resume_ingest import TEMPLATE_PATH, UnsupportedResumeFormatError, parse_resume_bytes


def test_template_path_exists():
    assert TEMPLATE_PATH.exists()
    assert TEMPLATE_PATH.suffix == ".md"


def test_parse_txt_utf8():
    text = parse_resume_bytes("안녕하세요\n경력 3년".encode("utf-8"), "resume.txt")
    assert "경력 3년" in text


def test_parse_unsupported_extension():
    with pytest.raises(UnsupportedResumeFormatError):
        parse_resume_bytes(b"data", "resume.xlsx")
