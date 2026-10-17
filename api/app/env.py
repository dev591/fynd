"""Tiny .env loader (no dependency). Real environment variables always win over the file."""
import os
import re
from pathlib import Path


def _clean(raw: str) -> str:
    """The value after '=': quotes removed, and an inline '# comment' (a # after whitespace, or leading) dropped."""
    value = raw.strip()
    if value[:1] in ("\"", "'"):
        end = value.find(value[0], 1)
        return value[1:end] if end > 0 else value[1:]
    m = re.search(r"(^|\s)#", value)
    return (value[:m.start()] if m else value).strip()


def load_env(path: Path | None = None) -> None:
    path = path or Path(__file__).resolve().parent.parent / ".env"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), _clean(value)
        if key and value:
            os.environ.setdefault(key, value)
