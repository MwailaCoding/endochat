"""Smoke test: verify curated PDFs are present and readable."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

import filetype
import pdfplumber


DOC_SUBFOLDERS = [
    "medical_guidelines",
    "patient_resources",
    "research",
    "official_sources",
]


def _repo_backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _documents_root() -> Path:
    return _repo_backend_root() / "data" / "documents"


def _find_pdfs(root: Path) -> List[Path]:
    return sorted(root.rglob("*.pdf"))


def _validate_pdf(path: Path) -> Tuple[bool, str]:
    kind = filetype.guess(str(path))
    if not kind or kind.extension.lower() != "pdf":
        return False, "filetype_not_pdf"
    return True, "ok"


def _extract_first_page_text(path: Path) -> Tuple[bool, str]:
    try:
        with pdfplumber.open(str(path)) as pdf:
            if not pdf.pages:
                return False, "no_pages"
            text = (pdf.pages[0].extract_text() or "").strip()
            if len(text) < 20:
                return False, "no_text_on_first_page"
        return True, "ok"
    except Exception as e:
        return False, f"extract_failed: {e}"


def main() -> int:
    docs_root = _documents_root()
    print(f"Documents root: {docs_root}")

    missing_dirs = [d for d in DOC_SUBFOLDERS if not (docs_root / d).exists()]
    if missing_dirs:
        print("Missing subfolders:")
        for d in missing_dirs:
            print(f"  - {docs_root / d}")
        return 2

    pdfs = _find_pdfs(docs_root)
    if not pdfs:
        print("No PDFs found under documents root.")
        return 2

    print(f"Found {len(pdfs)} PDF(s):")
    for p in pdfs:
        print(f"  - {p.relative_to(_repo_backend_root())}")

    failed = 0
    for p in pdfs:
        ok, reason = _validate_pdf(p)
        if not ok:
            failed += 1
            print(f"FAIL validate: {p.name} ({reason})")
            continue

        ok, reason = _extract_first_page_text(p)
        if not ok:
            failed += 1
            print(f"FAIL extract: {p.name} ({reason})")
        else:
            print(f"OK: {p.name}")

    if failed:
        print(f"\nFAILED: {failed} file(s) not valid/readable.")
        return 2

    print("\nPASSED: PDFs are present and readable.")
    print("Next step (full pipeline): run `python backend/scripts/run_migration.py` then `python backend/scripts/process_documents.py --all`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

