"""
Маршруты документации и вики проекта
"""

from pathlib import Path

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from markdown import markdown
from markupsafe import Markup

WIKI_DIR = Path(__file__).resolve().parent.parent / "wiki"

docs_bp = Blueprint("docs", __name__)


@docs_bp.route("/docs")
@docs_bp.route("/docs/<path:page>")
@login_required
def wiki_page(page: str = "index"):
    """Просмотр страниц вики."""
    if getattr(current_user, "role", None) != "admin":
        abort(403)

    page_path = (WIKI_DIR / f"{page}.md").resolve()
    if not page_path.exists() or not str(page_path).startswith(str(WIKI_DIR)):
        abort(404)

    pages = sorted(p.stem for p in WIKI_DIR.glob("*.md"))
    with open(page_path, encoding="utf-8") as f:
        html = markdown(f.read(), extensions=["fenced_code"])
    return render_template(
        "wiki_page.html", content=Markup(html), pages=pages, current=page
    )
