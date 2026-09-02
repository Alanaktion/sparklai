import json
from functools import lru_cache
from pathlib import Path

_SCHEMAS_DIR = Path(__file__).parent / "schemas"


@lru_cache
def load_schema(filename: str) -> dict:
    return json.loads((_SCHEMAS_DIR / filename).read_text())
