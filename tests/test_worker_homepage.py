"""Public download-tracker Worker UI mark copy.

Official /sigil.png (~75035 on live). Empty brandmark alt. No stamp.
Non-UI verify strings stay. Aziel Eliab only.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOMEPAGE = (ROOT / "workers/download-tracker/src/homepage.js").read_text(encoding="utf-8")


def test_public_brandmark_alt_empty_keeps_non_ui_everblooming() -> None:
    header, html = HOMEPAGE.split("export function renderHomepage", 1)
    assert "Everblooming sigil" in header
    assert "Aziel Eliab" in header
    assert 'class="brandmark"' in html
    assert 'src="/sigil.png"' in html
    assert '<img class="brandmark" src="/sigil.png" width="52" height="52" alt="" decoding="async">' in html
    assert "everblooming" not in html.lower()
    assert "stamp" not in html.lower()
    assert "Aziel Eliab only" in html
