"""Race and subrace mapping from BG3 to D&D 5e."""

from dataclasses import dataclass, field

from ..core.character import ConversionWarning
from ..data import load_game_data


@dataclass
class RaceMapping:
    """Mapping for a race or subrace."""
    bg3_name: str
    dnd5e_name: str
    subrace: str | None = None
    asi: dict[str, int] = field(default_factory=dict)  # Ability Score Increase
    traits: list[str] = field(default_factory=list)
    notes: str | None = None
    speed: int = 30  # Base walking speed in feet


def _build_race_mappings() -> dict[str, RaceMapping]:
    """Build RaceMapping objects from JSON data."""
    data = load_game_data()
    result = {}
    for bg3_name, entry in data["races"]["mappings"].items():
        result[bg3_name] = RaceMapping(
            bg3_name=bg3_name,
            dnd5e_name=entry["dnd5e_name"],
            subrace=entry.get("subrace"),
            asi=entry.get("asi", {}),
            traits=entry.get("traits", []),
            notes=entry.get("notes"),
            speed=entry.get("speed", 30),
        )
    return result


# Main race mappings
RACE_MAPPINGS: dict[str, RaceMapping] = _build_race_mappings()

_data = load_game_data()

# BG3 background UUID → background name mapping
BACKGROUND_UUID_MAPPINGS: dict[str, str] = _data["uuids"]["backgrounds"]

# Background mappings
BACKGROUND_MAPPINGS: dict[str, str] = _data["backgrounds"]["mappings"]


class RaceMapper:
    """Maps BG3 races to D&D 5e equivalents."""

    def __init__(self):
        self.races = RACE_MAPPINGS
        self.backgrounds = BACKGROUND_MAPPINGS

    def map_race(self, bg3_race: str, bg3_subrace: str | None = None) -> tuple[str, str | None, list[ConversionWarning]]:
        """Map a BG3 race to D&D 5e equivalent."""
        warnings: list[ConversionWarning] = []

        # Try exact match first
        if bg3_race in self.races:
            mapping = self.races[bg3_race]
            return mapping.dnd5e_name, mapping.subrace, warnings

        # Try with subrace
        if bg3_subrace:
            combined = f"{bg3_race}_{bg3_subrace}"
            if combined in self.races:
                mapping = self.races[combined]
                return mapping.dnd5e_name, mapping.subrace, warnings

        # Try cleaning up the name
        cleaned = bg3_race.replace("_", " ").replace("-", " ").title()
        if cleaned in self.races:
            mapping = self.races[cleaned]
            return mapping.dnd5e_name, mapping.subrace, warnings

        # Unknown race
        warnings.append(ConversionWarning(
            category="race",
            item_name=bg3_race,
            message=f"Unknown race '{bg3_race}', using as-is",
            severity="warning",
        ))
        return bg3_race, bg3_subrace, warnings

    def map_background(self, bg3_background: str | None) -> tuple[str, list[ConversionWarning]]:
        """Map a BG3 background to D&D 5e equivalent."""
        warnings: list[ConversionWarning] = []

        if not bg3_background:
            return "Custom", warnings

        # Check direct name mapping first
        if bg3_background in self.backgrounds:
            return self.backgrounds[bg3_background], warnings

        # Check UUID mapping (background from LSMF blob)
        if bg3_background in BACKGROUND_UUID_MAPPINGS:
            return BACKGROUND_UUID_MAPPINGS[bg3_background], warnings

        # Unknown background — likely a UUID from a modded or unrecognized background
        warnings.append(ConversionWarning(
            category="background",
            item_name=bg3_background,
            message=f"Unknown background '{bg3_background}', defaulting to Custom",
            severity="info",
        ))
        return "Custom", warnings

    def get_race_mapping(self, bg3_race: str, bg3_subrace: str | None = None) -> RaceMapping | None:
        """Look up the RaceMapping for a BG3 race/subrace string."""
        if bg3_race in self.races:
            return self.races[bg3_race]
        if bg3_subrace:
            combined = f"{bg3_race}_{bg3_subrace}"
            if combined in self.races:
                return self.races[combined]
            if bg3_subrace in self.races:
                return self.races[bg3_subrace]
        return None

    def get_racial_traits(self, race: str, subrace: str | None = None) -> list[str]:
        """Get standard racial traits for a race."""
        traits = load_game_data()["races"]["racial_traits"]
        key = subrace if subrace and subrace in traits else race
        return traits.get(key, [])
