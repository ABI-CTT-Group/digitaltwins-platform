import json

from typing import Any


def is_truthy(value: Any) -> bool:
    """
    Converts configuration strings (like 'true', '1', 'yes') into a
    Python boolean True, and all other values/None to False.
    """
    # Handles None or empty string gracefully
    if not value:
        return False

    # Converts to lowercase and checks against common truthy strings
    return str(value).lower() in ("true", "1", "yes", "on")

class ConfigLoader(object):
    def __init__(self, file=None):
        self._configs = None
        if file:
            self._configs = self.load_from_json(file)

    @staticmethod
    def load_from_json(file):
        with open(file) as f:
            configs = json.load(f)
        return configs
