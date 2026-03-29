import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.infrastructure.init_db import ensure_repo_selection_column

if __name__ == "__main__":
    asyncio.run(ensure_repo_selection_column())
