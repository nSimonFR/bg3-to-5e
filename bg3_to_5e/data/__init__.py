"""Game data loader — reads bg3_game_data.json once and caches it."""

import json
from pathlib import Path

_DATA: dict | None = None


def load_game_data() -> dict:
    """Load and cache the canonical game data JSON."""
    global _DATA
    if _DATA is None:
        path = Path(__file__).parent / "bg3_game_data.json"
        with open(path) as f:
            _DATA = json.load(f)
    return _DATA
