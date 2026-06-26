"""Generate `artifacts/dummy_cv.pdf` — a minimal hand-crafted PDF, no new deps.

Run once before sprint3_e2e.py. Stdlib only; pypdf reads the output cleanly.
"""

from __future__ import annotations

from pathlib import Path

CV_LINES: list[str] = [
    "Max Mustermann - Python Developer",
    "",
    "Summary:",
    "Mid-level backend developer with 5 years of experience building REST APIs",
    "and data services in Python. Comfortable with SQL, Git-based workflows, and",
    "agile teams. Looking for a Python role in Berlin.",
    "",
    "Skills: Python, SQL, REST APIs, Git, FastAPI, PostgreSQL, Docker, Linux",
    "",
    "Experience:",
    "Backend Developer at TechCo GmbH, Berlin (2020-01 to 2025-03)",
    "  - Built and operated REST APIs serving 50k daily requests.",
    "  - Designed PostgreSQL schemas; wrote performance-critical SQL.",
    "  - Owned CI/CD pipelines with GitHub Actions.",
    "Junior Developer at Startup AG, Cologne (2018-09 to 2019-12)",
    "  - Contributed to a Django web app; wrote unit tests with pytest.",
    "",
    "Education:",
    "B.Sc. Informatik, FH Koeln (2015-09 to 2018-08)",
    "",
    "Languages: German (native), English (C1)",
]


def _escape(s: str) -> str:
    """Escape PDF string literal special chars."""
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(lines: list[str]) -> bytes:
    """Return raw bytes of a 1-page PDF rendering *lines* in Helvetica 11pt."""
    # Build the content stream: text block with line-by-line newlines.
    instrs: list[str] = ["BT", "/F1 11 Tf", "72 760 Td"]
    for i, raw in enumerate(lines):
        if i > 0:
            instrs.append("0 -14 Td")
        instrs.append(f"({_escape(raw)}) Tj")
    instrs.append("ET")
    content = "\n".join(instrs).encode("latin-1", errors="replace")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> /ProcSet [/PDF /Text] >> >>"
        ),
        b"<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    parts: list[bytes] = [b"%PDF-1.4\n", b"%\xe2\xe3\xcf\xd3\n"]
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(sum(len(p) for p in parts))
        parts.append(f"{i} 0 obj\n".encode("latin-1"))
        parts.append(body)
        parts.append(b"\nendobj\n")

    xref_at = sum(len(p) for p in parts)
    xref_lines = [f"xref\n0 {len(objects) + 1}", "0000000000 65535 f "]
    for off in offsets:
        xref_lines.append(f"{off:010d} 00000 n ")
    parts.append(("\n".join(xref_lines) + "\n").encode("latin-1"))

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    )
    parts.append(trailer.encode("latin-1"))

    return b"".join(parts)


def main() -> None:
    out = Path("artifacts/dummy_cv.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_pdf(CV_LINES))
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
