"""Action resource UUID mappings and class/deity UUID mappings for BG3.

UUIDs are stable across saves — verified from multiple test saves.
"""

from ..data import load_game_data

_data = load_game_data()

# BG3 class UUID → class name
CLASS_UUID_MAPPINGS: dict[str, str] = _data["uuids"]["classes"]

# BG3 subclass UUID → subclass name
SUBCLASS_UUID_MAPPINGS: dict[str, str] = _data["uuids"]["subclasses"]

# BG3 deity UUID → deity name
DEITY_UUID_MAPPINGS: dict[str, str] = _data["uuids"]["deities"]

# BG3 action resource UUID → resource name
ACTION_RESOURCE_UUIDS: dict[str, str] = _data["uuids"]["action_resources"]

# UUIDs to filter out when building features from action resources.
_FILTERED_RESOURCE_NAMES = set(_data["filters"]["filtered_resource_names"])
