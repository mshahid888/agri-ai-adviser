"""Generate a small text-based PDF fixture for M10 tests.

This script creates a minimal, valid PDF with known extractable text so the
M10 ingestion pipeline can be tested deterministically without any real
agricultural documents.
"""
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
FIXTURE_PATH = FIXTURE_DIR / "sample_official.pdf"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf() -> bytes:
    # Two pages of known text.
    page1_lines = [
        "Wheat Production Technology",
        "Sahiwal Agriculture Extension",
        "This document describes official wheat production guidance.",
    ]
    page2_lines = [
        "Rice Cultivation Notes",
        "Punjab Agriculture Extension",
        "This document describes official rice cultivation guidance.",
    ]

    objects = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>")

    # Page 1
    objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 7 0 R >> >> >>")
    page1_text = "BT /F1 12 Tf 72 720 Td 14 TL " + " ".join(
        f"({_escape(line)}) Tj T*" for line in page1_lines
    ) + " ET"
    objects.append(b"<< /Length " + str(len(page1_text.encode())).encode() + b" >>\nstream\n" + page1_text.encode() + b"\nendstream")

    # Page 2
    objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>")
    page2_text = "BT /F1 12 Tf 72 720 Td 14 TL " + " ".join(
        f"({_escape(line)}) Tj T*" for line in page2_lines
    ) + " ET"
    objects.append(b"<< /Length " + str(len(page2_text.encode())).encode() + b" >>\nstream\n" + page2_text.encode() + b"\nendstream")

    # Font
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode()

    pdf += b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\nstartxref\n" + str(xref_offset).encode() + b"\n%%EOF\n"
    return pdf


def main() -> None:
    FIXTURE_PATH.write_bytes(_build_pdf())
    print(f"Fixture written to {FIXTURE_PATH}")


if __name__ == "__main__":
    main()