"""Class and subclass mapping from BG3 to D&D 5e."""

from dataclasses import dataclass

from ..core.character import CharacterClass, ConversionWarning
from ..data import load_game_data


@dataclass
class ClassMapping:
    """Mapping for a class or subclass."""
    bg3_name: str
    dnd5e_name: str
    notes: str | None = None
    mechanic_differences: list[str] | None = None


def _build_class_mappings() -> dict[str, ClassMapping]:
    """Build ClassMapping objects for main classes from JSON data."""
    data = load_game_data()
    result = {}
    for name in data["classes"]["names"]:
        result[name] = ClassMapping(name, name)
    return result


def _build_subclass_mappings() -> dict[str, ClassMapping]:
    """Build ClassMapping objects for subclasses from JSON data."""
    data = load_game_data()
    result = {}
    for bg3_name, entry in data["classes"]["subclass_mappings"].items():
        result[bg3_name] = ClassMapping(
            bg3_name=bg3_name,
            dnd5e_name=entry["dnd5e_name"],
            notes=entry.get("notes"),
            mechanic_differences=entry.get("mechanic_differences"),
        )
    return result


def _build_unique_subclasses() -> dict[str, ClassMapping]:
    """Build ClassMapping objects for BG3-unique subclasses from JSON data."""
    data = load_game_data()
    result = {}
    for bg3_name, entry in data["classes"]["bg3_unique_subclasses"].items():
        result[bg3_name] = ClassMapping(
            bg3_name=bg3_name,
            dnd5e_name=entry["dnd5e_name"],
            notes=entry.get("notes"),
        )
    return result


# Main class mappings (most are 1:1)
CLASS_MAPPINGS: dict[str, ClassMapping] = _build_class_mappings()

# Subclass mappings - includes BG3-specific subclasses
SUBCLASS_MAPPINGS: dict[str, ClassMapping] = _build_subclass_mappings()

# BG3-specific subclasses with no direct 5e equivalent
BG3_UNIQUE_SUBCLASSES: dict[str, ClassMapping] = _build_unique_subclasses()

# Class feature differences between BG3 and 5e
CLASS_MECHANIC_DIFFERENCES: dict[str, list[str]] = load_game_data()["classes"]["mechanic_differences"]


class ClassMapper:
    """Maps BG3 classes/subclasses to D&D 5e equivalents."""

    def __init__(self):
        self.class_mappings = CLASS_MAPPINGS
        self.subclass_mappings = SUBCLASS_MAPPINGS
        self.unique_subclasses = BG3_UNIQUE_SUBCLASSES
        self.mechanic_differences = CLASS_MECHANIC_DIFFERENCES

    def map_class(self, bg3_class: CharacterClass) -> tuple[CharacterClass, list[ConversionWarning]]:
        """Map a BG3 class to D&D 5e equivalent."""
        warnings: list[ConversionWarning] = []

        # Map the main class
        class_name = bg3_class.name
        if class_name in self.class_mappings:
            mapped_name = self.class_mappings[class_name].dnd5e_name
        else:
            mapped_name = class_name
            warnings.append(ConversionWarning(
                category="class",
                item_name=class_name,
                message=f"Unknown class '{class_name}', using as-is",
                severity="warning",
            ))

        # Map the subclass
        mapped_subclass = None
        if bg3_class.subclass:
            subclass_name = bg3_class.subclass
            if subclass_name in self.subclass_mappings:
                mapping = self.subclass_mappings[subclass_name]
                mapped_subclass = mapping.dnd5e_name
                if mapping.notes:
                    warnings.append(ConversionWarning(
                        category="subclass",
                        item_name=subclass_name,
                        message=mapping.notes,
                        severity="info",
                    ))
                if mapping.mechanic_differences:
                    for diff in mapping.mechanic_differences:
                        warnings.append(ConversionWarning(
                            category="subclass",
                            item_name=subclass_name,
                            message=diff,
                            severity="warning",
                        ))
            elif subclass_name in self.unique_subclasses:
                mapping = self.unique_subclasses[subclass_name]
                mapped_subclass = mapping.dnd5e_name
                warnings.append(ConversionWarning(
                    category="subclass",
                    item_name=subclass_name,
                    message=f"BG3-specific subclass. {mapping.notes}",
                    severity="warning",
                ))
            else:
                mapped_subclass = subclass_name
                warnings.append(ConversionWarning(
                    category="subclass",
                    item_name=subclass_name,
                    message=f"Unknown subclass '{subclass_name}', using as-is",
                    severity="warning",
                ))

        # Check for class-level mechanic differences
        if class_name in self.mechanic_differences:
            for diff in self.mechanic_differences[class_name]:
                warnings.append(ConversionWarning(
                    category="class_mechanics",
                    item_name=class_name,
                    message=diff,
                    severity="info",
                ))

        if mapped_subclass and mapped_subclass in self.mechanic_differences:
            for diff in self.mechanic_differences[mapped_subclass]:
                warnings.append(ConversionWarning(
                    category="class_mechanics",
                    item_name=mapped_subclass,
                    message=diff,
                    severity="info",
                ))

        result = CharacterClass(
            name=mapped_name,
            level=bg3_class.level,
            subclass=mapped_subclass,
            bg3_name=bg3_class.name,
            bg3_subclass=bg3_class.subclass,
        )

        return result, warnings

    def get_hit_die(self, class_name: str) -> str:
        """Get the hit die for a class."""
        hit_dice = load_game_data()["classes"]["hit_dice"]
        return hit_dice.get(class_name, "d8")

    def get_saving_throw_proficiencies(self, class_name: str) -> tuple[str, str]:
        """Get the saving throw proficiencies for a class."""
        saves = load_game_data()["classes"]["saving_throws"]
        pair = saves.get(class_name, ["strength", "constitution"])
        return (pair[0], pair[1])
