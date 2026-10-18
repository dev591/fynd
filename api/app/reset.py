"""Start from the seed data again: python -m app.reset  (stop the API first).
With PERSIST_BACKEND=supabase this empties the Supabase state table, so be sure you mean it."""
from .env import load_env

load_env()
from . import persist  # noqa: E402

print(f"Removed {persist.clear()} ({persist.backend()}).")
print("The next start of the API will seed fresh demo data.")
