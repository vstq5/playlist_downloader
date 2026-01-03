import json
import os
from typing import List, Dict
from datetime import datetime

HISTORY_FILE = "history.json"


def load_history() -> List[Dict]:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_history_item(item: Dict):
    history = load_history()
    # Add timestamp
    item["timestamp"] = datetime.now().isoformat()
    history.insert(0, item)  # Prepend
    # Keep last 50
    history = history[:50]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def get_history() -> List[Dict]:
    return load_history()

