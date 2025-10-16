"""Скрипт генерации gRPC-кода из proto-файлов."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTO_DIR = ROOT / "proto"


def main() -> None:
    """Генерировать Python-код из всех .proto в каталоге."""
    files = [str(p) for p in PROTO_DIR.glob("*.proto")]
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{PROTO_DIR}",
        f"--python_out={PROTO_DIR}",
        f"--grpc_python_out={PROTO_DIR}",
        *files,
    ]
    subprocess.run(cmd, check=True)

    # справляем абсолютные импорты на относительные
    for path in PROTO_DIR.glob("*_pb2_grpc.py"):
        text = path.read_text(encoding="utf-8")
        text = re.sub(
            r"^import (.+_pb2) as", r"from . import \1 as", text, flags=re.MULTILINE
        )
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
