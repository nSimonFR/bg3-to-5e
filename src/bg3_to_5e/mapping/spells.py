"""Spell mapping from BG3 to D&D 5e.

Handles:
- Renamed spells (Bone Chill → Chill Touch)
- Mechanic differences (Haste, Polymorph, etc.)
- BG3-unique spells
"""

from dataclasses import dataclass, field

from ..core.character import ConversionWarning, Spell
from ..data import load_game_data


@dataclass
class SpellMapping:
    """Mapping for a spell."""
    bg3_name: str
    dnd5e_name: str
    level: int
    school: str | None = None
    mechanic_differences: list[str] = field(default_factory=list)
    notes: str | None = None


def _build_spell_mappings(section: str) -> dict[str, SpellMapping]:
    """Build SpellMapping objects from a JSON section."""
    data = load_game_data()
    result = {}
    for bg3_name, entry in data["spells"][section].items():
        result[bg3_name] = SpellMapping(
            bg3_name=bg3_name,
            dnd5e_name=entry["dnd5e_name"],
            level=entry["level"],
            school=entry.get("school"),
            mechanic_differences=entry.get("mechanic_differences", []),
            notes=entry.get("notes"),
        )
    return result


# Spells that have different names in BG3 vs 5e
RENAMED_SPELLS: dict[str, SpellMapping] = _build_spell_mappings("renamed")

# Spells with significant mechanic differences
MECHANIC_DIFFERENCES: dict[str, SpellMapping] = _build_spell_mappings("mechanic_differences")

# BG3-unique spells with no 5e equivalent
BG3_UNIQUE_SPELLS: dict[str, SpellMapping] = _build_spell_mappings("bg3_unique")

# Standard spell list (level -> spells at that level)
_std_raw = load_game_data()["spells"]["standard_spells"]
STANDARD_SPELLS: dict[int, list[str]] = {int(k): v for k, v in _std_raw.items()}

_data = load_game_data()

# BG3 base actions that are NOT spells (filter these out)
BG3_BASE_ACTIONS: set[str] = set(_data["filters"]["base_actions"])

# BG3 class ability names that are NOT spells
BG3_CLASS_ACTIONS: set[str] = set(_data["filters"]["class_actions"])

# Prefixes to strip from BG3 spell names
_BG3_SPELL_PREFIXES = _data["filters"]["spell_prefixes"]


def convert_bg3_spell_name(raw_name: str) -> str | None:
    """Convert a raw BG3 spell name to a clean 5e spell name.

    Returns None if the name is a base action or class ability, not a spell.
    """
    import re

    # Strip prefixes
    name = raw_name
    for prefix in _BG3_SPELL_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    # Collapse companion/familiar variants (class features, not spells)
    if re.match(r'^Rangers ?Companion(_.*)?$', name):
        return None

    # Collapse "Find Familiar_Cat_Ritual" / "FindFamiliar_Cat_Ritual" → "Find Familiar"
    if re.match(r'^Find ?Familiar(_.*)?$', name):
        name = "FindFamiliar"

    # Strip _Ritual suffix (ritual cast = same spell)
    name = re.sub(r'_Ritual$', '', name)

    # Strip _Reapply / _FreeRecast / _Free Recast / numbered suffixes
    name = re.sub(r'_(Reapply|Free ?Recast)$', '', name)
    name = re.sub(r'_\d+$', '', name)

    # Collapse ability-suffixed variants: Hex_Strength → Hex, Animate Dead_Zombie → Animate Dead
    _ABILITY_SUFFIXES = tuple(_data["filters"]["ability_suffixes"])
    for suf in _ABILITY_SUFFIXES:
        if name.endswith(suf):
            name = name[:-len(suf)]
            break

    # Collapse summon/creature variants: AnimateDead_Skeleton → AnimateDead
    name = re.sub(r'^(Animate ?Dead)_(Skeleton|Zombie)$', r'\1', name)

    # Racial/item variant suffixes: MistyStep_Githyanki → MistyStep
    name = re.sub(r'_(Githyanki ?Psionics|Githyanki|Wizard)$', '', name)
    name = re.sub(r'^(Jump)_(Githyanki)$', r'\1', name)

    # "Healing Word_Mass" → remap to MassHealingWord
    if name in ("Healing Word_Mass", "HealingWord_Mass"):
        name = "MassHealingWord"

    # "Create Destroy Water" → direct map
    if name in ("CreateDestroyWater", "Create Destroy Water"):
        name = "CreateOrDestroyWater"

    # Filter out base actions and class actions
    if name in BG3_BASE_ACTIONS or name in BG3_CLASS_ACTIONS:
        return None
    if raw_name in BG3_BASE_ACTIONS or raw_name in BG3_CLASS_ACTIONS:
        return None

    # Filter out common non-spell patterns
    skip_patterns = _data["filters"]["skip_patterns"]
    for pat in skip_patterns:
        if pat in raw_name:
            return None

    # Known direct mappings from BG3 internal → 5e name
    DIRECT_MAP: dict[str, str] = _data["spells"]["direct_name_map"]

    if name in DIRECT_MAP:
        return DIRECT_MAP[name]

    # CamelCase to spaces: "HealingWord" → "Healing Word"
    import re
    spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
    spaced = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', spaced)

    # Clean up
    spaced = spaced.strip()
    if not spaced or len(spaced) < 2:
        return None

    return spaced


class SpellMapper:
    """Maps BG3 spells to D&D 5e equivalents."""

    def __init__(self):
        self.renamed = RENAMED_SPELLS
        self.mechanic_diffs = MECHANIC_DIFFERENCES
        self.bg3_unique = BG3_UNIQUE_SPELLS

    def map_spell(self, bg3_spell: Spell) -> tuple[Spell, list[ConversionWarning]]:
        """Map a BG3 spell to D&D 5e equivalent."""
        warnings: list[ConversionWarning] = []
        spell_name = bg3_spell.name

        # Check for renamed spells
        if spell_name in self.renamed:
            mapping = self.renamed[spell_name]
            mapped_spell = Spell(
                name=mapping.dnd5e_name,
                level=mapping.level,
                school=mapping.school,
                prepared=bg3_spell.prepared,
                bg3_name=spell_name,
            )
            if mapping.mechanic_differences:
                for diff in mapping.mechanic_differences:
                    warnings.append(ConversionWarning(
                        category="spell",
                        item_name=spell_name,
                        message=diff,
                        severity="info",
                    ))
            return mapped_spell, warnings

        # Check for mechanic differences
        if spell_name in self.mechanic_diffs:
            mapping = self.mechanic_diffs[spell_name]
            mapped_spell = Spell(
                name=mapping.dnd5e_name,
                level=mapping.level,
                school=mapping.school,
                prepared=bg3_spell.prepared,
                bg3_name=spell_name,
                mechanic_differences=mapping.mechanic_differences,
            )
            for diff in mapping.mechanic_differences:
                warnings.append(ConversionWarning(
                    category="spell_mechanics",
                    item_name=spell_name,
                    message=diff,
                    severity="warning",
                ))
            if mapping.notes:
                warnings.append(ConversionWarning(
                    category="spell",
                    item_name=spell_name,
                    message=mapping.notes,
                    severity="info",
                ))
            return mapped_spell, warnings

        # Check for BG3-unique spells
        if spell_name in self.bg3_unique:
            mapping = self.bg3_unique[spell_name]
            warnings.append(ConversionWarning(
                category="spell",
                item_name=spell_name,
                message=f"BG3-only spell. {mapping.notes or 'No 5e equivalent.'}",
                severity="warning",
            ))
            mapped_spell = Spell(
                name=mapping.dnd5e_name,
                level=mapping.level,
                school=mapping.school,
                prepared=bg3_spell.prepared,
                bg3_name=spell_name,
            )
            return mapped_spell, warnings

        # Standard spell - return as-is
        return Spell(
            name=spell_name,
            level=bg3_spell.level,
            school=bg3_spell.school,
            prepared=bg3_spell.prepared,
            bg3_name=spell_name,
        ), warnings

    def is_illithid_power(self, spell_name: str) -> bool:
        """Check if a spell is an Illithid power."""
        illithid_powers = set(_data["spells"]["illithid_powers"])
        name_lower = spell_name.lower()
        if name_lower in illithid_powers:
            return True
        return name_lower.startswith("illithid") or name_lower.startswith("tadpole")

    def get_spell_slots_for_level(self, class_name: str, class_level: int) -> dict[int, int]:
        """Get spell slots for a class at a given level."""
        spell_data = _data["spells"]
        slot_tables = spell_data["spell_slots"]
        caster_types = spell_data["caster_types"]

        if class_name in caster_types["full"]:
            raw = slot_tables["full_caster"].get(str(class_level), {})
        elif class_name in caster_types["half"]:
            raw = slot_tables["half_caster"].get(str(class_level), {})
        elif class_name in caster_types["warlock"]:
            raw = slot_tables["warlock"].get(str(class_level), {})
        else:
            return {}

        return {int(k): v for k, v in raw.items()}
