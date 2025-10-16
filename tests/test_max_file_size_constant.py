"""Проверки константы MAX_FILE_SIZE."""

import ast
from pathlib import Path


def _imports_constant(path: Path) -> bool:
    """Проверяет, что модуль импортирует MAX_FILE_SIZE из utils.constants."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "utils.constants":
            if any(alias.name == "MAX_FILE_SIZE" for alias in node.names):
                return True
    return False


def _defines_constant(path: Path) -> bool:
    """Проверяет, что модуль не содержит собственной константы."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "MAX_FILE_SIZE":
                    return True
    return False


def test_max_file_size_imported():
    path = Path("security_utils.py")
    assert _imports_constant(
        path
    ), "Константа MAX_FILE_SIZE не импортирована из utils.constants"
    assert not _defines_constant(
        path
    ), "Константа MAX_FILE_SIZE не должна определяться в security_utils.py"


def test_max_file_size_value():
    from utils.constants import MAX_FILE_SIZE

    assert MAX_FILE_SIZE == 10 * 1024 * 1024
