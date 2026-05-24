from pathlib import Path

from app.manifest_builder import MANIFEST_FILENAME, update_manifest
from app.settings import DATA_DIR


_WILDCARD_CHARS = {"*", "?", "[", "]"}


def readFile(fname: str) -> str:
    filename = fname.strip()
    if not filename:
        raise ValueError("filename is required")
    if any(char in filename for char in _WILDCARD_CHARS):
        raise ValueError("wildcards are not allowed")
    if Path(filename).name != filename:
        raise ValueError("filename only")
    if filename == MANIFEST_FILENAME:
        update_manifest(DATA_DIR)
    elif Path(filename).suffix.casefold() == ".json":
        raise ValueError("json files are not allowed")

    data_root = DATA_DIR.resolve()
    target = (data_root / filename).resolve()
    if target.parent != data_root:
        raise ValueError("filename only")
    if not target.is_file():
        if target.exists():
            raise ValueError("filename only")
        raise FileNotFoundError(filename)

    return target.read_text(encoding="utf-8")
