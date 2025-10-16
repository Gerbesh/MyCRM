import ast
from pathlib import Path

MODULES = [
    Path("routes/request_crud_routes.py"),
    Path("routes/request_process_routes.py"),
    Path("routes.py"),
]


def _imports_constant(path: Path) -> bool:
    """Проверяет, что модуль импортирует MANUFACTURERS из utils.constants."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "utils.constants":
            if any(alias.name == "MANUFACTURERS" for alias in node.names):
                return True
    return False


def test_manufacturers_imported():
    """Все целевые модули должны импортировать константу из общего модуля."""
    for module in MODULES:
        assert _imports_constant(
            module
        ), f"Константа MANUFACTURERS не импортирована в {module}"


def test_manufacturers_content():
    """Проверяем содержимое константы."""
    from utils.constants import MANUFACTURERS

    assert MANUFACTURERS == [
        "Пульсар",
        "Термолайн",
        "Ридан ОВ",
        "Ридан ВК",
        "Ридан ТП",
        "Евра",
        "Протон энергия",
        "Зана",
        "Витрон",
    ]
