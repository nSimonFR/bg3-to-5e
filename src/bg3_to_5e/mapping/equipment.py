"""Equipment mapping from BG3 to D&D 5e.

Handles:
- Standard D&D items (weapons, armor, etc.)
- BG3-unique items (Mourning Frost, etc.)
- Magic item properties
"""

from dataclasses import dataclass, field

from ..core.character import ConversionWarning, Equipment
from ..data import load_game_data


@dataclass
class EquipmentMapping:
    """Mapping for equipment."""
    bg3_name: str
    dnd5e_name: str
    type: str
    rarity: str = "common"
    magical: bool = False
    attunement: bool = False
    notes: str | None = None
    properties: list[str] = field(default_factory=list)


def _build_simple_mappings(section: str) -> dict[str, EquipmentMapping]:
    """Build EquipmentMapping objects for standard weapons/armor from JSON."""
    data = load_game_data()
    result = {}
    for bg3_name, entry in data["equipment"][section].items():
        result[bg3_name] = EquipmentMapping(
            bg3_name=bg3_name,
            dnd5e_name=entry["dnd5e_name"],
            type=entry["type"],
        )
    return result


def _build_unique_items() -> dict[str, EquipmentMapping]:
    """Build EquipmentMapping objects for BG3-unique items from JSON."""
    data = load_game_data()
    result = {}
    for bg3_name, entry in data["equipment"]["bg3_unique_items"].items():
        result[bg3_name] = EquipmentMapping(
            bg3_name=bg3_name,
            dnd5e_name=entry["dnd5e_name"],
            type=entry["type"],
            rarity=entry.get("rarity", "common"),
            magical=entry.get("magical", False),
            attunement=entry.get("attunement", False),
            notes=entry.get("notes"),
        )
    return result


# Standard weapon mappings
WEAPON_MAPPINGS: dict[str, EquipmentMapping] = _build_simple_mappings("weapons")

# Standard armor mappings
ARMOR_MAPPINGS: dict[str, EquipmentMapping] = _build_simple_mappings("armor")

# BG3 unique items (no direct 5e equivalent)
BG3_UNIQUE_ITEMS: dict[str, EquipmentMapping] = _build_unique_items()


class EquipmentMapper:
    """Maps BG3 equipment to D&D 5e equivalents."""

    def __init__(self):
        self.weapons = WEAPON_MAPPINGS
        self.armor = ARMOR_MAPPINGS
        self.unique = BG3_UNIQUE_ITEMS

    def map_equipment(self, bg3_item: Equipment) -> tuple[Equipment, list[ConversionWarning]]:
        """Map a BG3 item to D&D 5e equivalent."""
        warnings: list[ConversionWarning] = []
        item_name = bg3_item.name

        # Check for standard weapons
        if item_name in self.weapons:
            mapping = self.weapons[item_name]
            return self._create_mapped_item(bg3_item, mapping), warnings

        # Check for standard armor
        if item_name in self.armor:
            mapping = self.armor[item_name]
            return self._create_mapped_item(bg3_item, mapping), warnings

        # Check for BG3-unique items
        if item_name in self.unique:
            mapping = self.unique[item_name]
            warnings.append(ConversionWarning(
                category="equipment",
                item_name=item_name,
                message=mapping.notes or f"BG3-unique item: {item_name}",
                severity="warning",
            ))
            return self._create_mapped_item(bg3_item, mapping), warnings

        # Check for +X weapons/armor patterns
        plus_pattern = self._check_plus_pattern(item_name)
        if plus_pattern:
            return plus_pattern, warnings

        # Unknown item - return as-is with warning
        warnings.append(ConversionWarning(
            category="equipment",
            item_name=item_name,
            message=f"Unknown item '{item_name}', using as-is. May be BG3-specific.",
            severity="info",
        ))

        return Equipment(
            name=item_name,
            type=bg3_item.type,
            equipped=bg3_item.equipped,
            quantity=bg3_item.quantity,
            magical=bg3_item.magical,
            attunement_required=bg3_item.attunement_required,
            attuned=bg3_item.attuned,
            bg3_name=item_name,
            bg3_unique=True,
        ), warnings

    def _create_mapped_item(self, bg3_item: Equipment, mapping: EquipmentMapping) -> Equipment:
        """Create a mapped equipment item."""
        return Equipment(
            name=mapping.dnd5e_name,
            type=mapping.type,
            equipped=bg3_item.equipped,
            quantity=bg3_item.quantity,
            magical=mapping.magical or bg3_item.magical,
            attunement_required=mapping.attunement or bg3_item.attunement_required,
            attuned=bg3_item.attuned,
            bg3_name=bg3_item.name,
            bg3_unique=False,
            conversion_notes=mapping.notes,
        )

    def _check_plus_pattern(self, name: str) -> Equipment | None:
        """Check for +1/+2/+3 weapon or armor patterns."""
        import re

        # Match patterns like "+1 Longsword", "Longsword +2", etc.
        plus_match = re.match(r"(\+[123])?\s*(.+?)(\s+\+[123])?$", name)
        if not plus_match:
            return None

        prefix_plus = plus_match.group(1)
        base_name = plus_match.group(2).strip()
        suffix_plus = plus_match.group(3)

        plus = prefix_plus or suffix_plus
        if not plus:
            return None

        plus = plus.strip()

        # Check if base is a known weapon or armor
        if base_name in self.weapons or base_name in self.armor:
            mapping = self.weapons.get(base_name) or self.armor.get(base_name)
            if mapping:
                return Equipment(
                    name=f"{plus} {mapping.dnd5e_name}",
                    type=mapping.type,
                    magical=True,
                    attunement_required=False,
                    bg3_name=name,
                )

        return None

    def get_armor_class(self, armor_name: str) -> int:
        """Get base AC for an armor type."""
        ac_values = load_game_data()["equipment"]["armor_class"]
        return ac_values.get(armor_name, 10)
