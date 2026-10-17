"""Start from the seed data again: python -m app.reset  (stop the API first)."""
from .persist import db_path

path = db_path()
removed = []
for suffix in ("", "-wal", "-shm"):
    p = path.parent / (path.name + suffix)
    if p.exists():
        p.unlink()
        removed.append(p.name)
print(f"Removed {', '.join(removed)} in {path.parent}" if removed else f"Nothing to remove at {path}")
print("The next start of the API will seed fresh demo data.")
