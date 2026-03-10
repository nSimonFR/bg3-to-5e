"""Import character data exported from BG3 Script Extender.

This module handles JSON data exported by the bg3_export.lua script
running in the BG3 Script Extender console.
"""

import json
from pathlib import Path
from typing import Any

from ..core.character import (
    AbilityName,
    AbilityScores,
    BG3Character,
    CharacterClass,
    Equipment,
    Feature,
    SavingThrowProficiencies,
    SkillProficiencies,
    Spell,
    SpellSlots,
)


class ScriptExtenderImport:
    """Import character data from BG3 Script Extender JSON export."""

    # Mapping from BG3 ability names to our enum
    ABILITY_MAP = {
        "Strength": AbilityName.STRENGTH,
        "Dexterity": AbilityName.DEXTERITY,
        "Constitution": AbilityName.CONSTITUTION,
        "Intelligence": AbilityName.INTELLIGENCE,
        "Wisdom": AbilityName.WISDOM,
        "Charisma": AbilityName.CHARISMA,
    }

    # Skill name normalization
    SKILL_MAP = {
        "Acrobatics": "acrobatics",
        "AnimalHandling": "animal_handling",
        "Animal Handling": "animal_handling",
        "Arcana": "arcana",
        "Athletics": "athletics",
        "Deception": "deception",
        "History": "history",
        "Insight": "insight",
        "Intimidation": "intimidation",
        "Investigation": "investigation",
        "Medicine": "medicine",
        "Nature": "nature",
        "Perception": "perception",
        "Performance": "performance",
        "Persuasion": "persuasion",
        "SleightOfHand": "sleight_of_hand",
        "Sleight of Hand": "sleight_of_hand",
        "Stealth": "stealth",
        "Survival": "survival",
    }

    def __init__(self, json_path: Path | str | None = None, json_data: dict | None = None):
        """Initialize with either a file path or raw JSON data."""
        if json_path:
            self.data = self._load_json(Path(json_path))
        elif json_data:
            self.data = json_data
        else:
            raise ValueError("Must provide either json_path or json_data")

    def _load_json(self, path: Path) -> dict:
        """Load JSON from file."""
        with open(path) as f:
            return json.load(f)

    def import_all(self) -> list[BG3Character]:
        """Import all characters from the export."""
        characters = []

        # Handle both single character and party exports
        if "party" in self.data:
            for char_data in self.data["party"]:
                characters.append(self._parse_character(char_data))
        elif "characters" in self.data:
            for char_data in self.data["characters"]:
                characters.append(self._parse_character(char_data))
        else:
            # Single character export
            characters.append(self._parse_character(self.data))

        return characters

    def _parse_character(self, data: dict) -> BG3Character:
        """Parse a single character from export data."""
        return BG3Character(
            name=data.get("name", "Unknown"),
            uuid=data.get("uuid"),
            race=self._parse_race(data),
            subrace=data.get("subrace"),
            background=data.get("background"),
            classes=self._parse_classes(data),
            ability_scores=self._parse_abilities(data),
            max_hp=data.get("maxHp", 0),
            current_hp=data.get("currentHp", 0),
            temp_hp=data.get("tempHp", 0),
            armor_class=data.get("armorClass", 10),
            initiative_bonus=data.get("initiative", 0),
            speed=data.get("speed", 30),
            proficiency_bonus=data.get("proficiencyBonus", 2),
            saving_throws=self._parse_saving_throws(data),
            skills=self._parse_skills(data),
            spells=self._parse_spells(data),
            spell_slots=self._parse_spell_slots(data),
            spellcasting_ability=self._parse_spellcasting_ability(data),
            equipment=self._parse_equipment(data),
            gold=data.get("gold", 0),
            features=self._parse_features(data),
            tadpole_powers=self._parse_tadpole_powers(data),
            inspiration_points=data.get("inspiration", 0),
            raw_data=data,
        )

    def _parse_race(self, data: dict) -> str:
        """Parse race from character data."""
        race = data.get("race", "Unknown")
        # BG3 uses internal names sometimes
        race_cleanup = {
            "Tiefling_Asmodeus": "Tiefling",
            "Tiefling_Mephistopheles": "Tiefling",
            "Tiefling_Zariel": "Tiefling",
            "Elf_High": "High Elf",
            "Elf_Wood": "Wood Elf",
            "Elf_Drow": "Drow",
            "Dwarf_Gold": "Hill Dwarf",
            "Dwarf_Shield": "Mountain Dwarf",
            "Halfling_Lightfoot": "Lightfoot Halfling",
            "Halfling_Strongheart": "Strongheart Halfling",
            "Gnome_Rock": "Rock Gnome",
            "Gnome_Forest": "Forest Gnome",
            "Gnome_Deep": "Deep Gnome",
            "HalfElf_High": "Half-Elf",
            "HalfElf_Wood": "Half-Elf",
            "HalfElf_Drow": "Half-Elf",
            "Dragonborn_Black": "Dragonborn",
            "Dragonborn_Blue": "Dragonborn",
            "Dragonborn_Brass": "Dragonborn",
            "Dragonborn_Bronze": "Dragonborn",
            "Dragonborn_Copper": "Dragonborn",
            "Dragonborn_Gold": "Dragonborn",
            "Dragonborn_Green": "Dragonborn",
            "Dragonborn_Red": "Dragonborn",
            "Dragonborn_Silver": "Dragonborn",
            "Dragonborn_White": "Dragonborn",
            "Githyanki": "Githyanki",
        }
        return race_cleanup.get(race, race)

    def _parse_classes(self, data: dict) -> list[CharacterClass]:
        """Parse class levels from character data."""
        classes = []
        class_data = data.get("classes", [])

        if isinstance(class_data, list):
            for cls in class_data:
                classes.append(CharacterClass(
                    name=cls.get("name", "Unknown"),
                    level=cls.get("level", 1),
                    subclass=cls.get("subclass"),
                    bg3_name=cls.get("internalName"),
                    bg3_subclass=cls.get("internalSubclass"),
                ))
        elif isinstance(class_data, dict):
            # Single class format
            classes.append(CharacterClass(
                name=class_data.get("name", data.get("class", "Unknown")),
                level=class_data.get("level", data.get("level", 1)),
                subclass=class_data.get("subclass"),
            ))

        # Fallback if no class data
        if not classes and "class" in data:
            classes.append(CharacterClass(
                name=data["class"],
                level=data.get("level", 1),
                subclass=data.get("subclass"),
            ))

        return classes

    def _parse_abilities(self, data: dict) -> AbilityScores:
        """Parse ability scores."""
        abilities = data.get("abilities", {})
        stats = data.get("stats", {})

        # Try multiple data formats
        return AbilityScores(
            strength=abilities.get("Strength", stats.get("str", 10)),
            dexterity=abilities.get("Dexterity", stats.get("dex", 10)),
            constitution=abilities.get("Constitution", stats.get("con", 10)),
            intelligence=abilities.get("Intelligence", stats.get("int", 10)),
            wisdom=abilities.get("Wisdom", stats.get("wis", 10)),
            charisma=abilities.get("Charisma", stats.get("cha", 10)),
        )

    def _parse_saving_throws(self, data: dict) -> SavingThrowProficiencies:
        """Parse saving throw proficiencies."""
        saves = data.get("savingThrows", data.get("saves", {}))
        return SavingThrowProficiencies(
            strength=saves.get("Strength", False),
            dexterity=saves.get("Dexterity", False),
            constitution=saves.get("Constitution", False),
            intelligence=saves.get("Intelligence", False),
            wisdom=saves.get("Wisdom", False),
            charisma=saves.get("Charisma", False),
        )

    def _parse_skills(self, data: dict) -> SkillProficiencies:
        """Parse skill proficiencies."""
        skills = data.get("skills", {})
        result = SkillProficiencies()

        for bg3_name, our_name in self.SKILL_MAP.items():
            skill_data = skills.get(bg3_name, {})
            if isinstance(skill_data, dict):
                # Format: {"proficient": true, "expertise": false}
                prof = skill_data.get("proficient", False)
                exp = skill_data.get("expertise", False)
                value = 2 if exp else (1 if prof else 0)
            elif isinstance(skill_data, bool):
                value = 1 if skill_data else 0
            elif isinstance(skill_data, int):
                value = min(skill_data, 2)
            else:
                value = 0
            setattr(result, our_name, value)

        return result

    def _parse_spells(self, data: dict) -> list[Spell]:
        """Parse known/prepared spells."""
        spells = []
        spell_data = data.get("spells", [])

        for spell in spell_data:
            if isinstance(spell, str):
                spells.append(Spell(name=spell, level=0))
            elif isinstance(spell, dict):
                spells.append(Spell(
                    name=spell.get("name", "Unknown"),
                    level=spell.get("level", 0),
                    school=spell.get("school"),
                    prepared=spell.get("prepared", False),
                    bg3_name=spell.get("internalName"),
                ))

        return spells

    def _parse_spell_slots(self, data: dict) -> SpellSlots:
        """Parse spell slot information."""
        slots = data.get("spellSlots", {})
        return SpellSlots(
            level_1=slots.get("1", 0),
            level_2=slots.get("2", 0),
            level_3=slots.get("3", 0),
            level_4=slots.get("4", 0),
            level_5=slots.get("5", 0),
            level_6=slots.get("6", 0),
            level_7=slots.get("7", 0),
            level_8=slots.get("8", 0),
            level_9=slots.get("9", 0),
        )

    def _parse_spellcasting_ability(self, data: dict) -> AbilityName | None:
        """Parse spellcasting ability."""
        ability = data.get("spellcastingAbility")
        if ability:
            return self.ABILITY_MAP.get(ability)
        return None

    def _parse_equipment(self, data: dict) -> list[Equipment]:
        """Parse equipment list."""
        equipment = []
        equip_data = data.get("equipment", data.get("inventory", []))

        for item in equip_data:
            if isinstance(item, str):
                equipment.append(Equipment(name=item, type="misc"))
            elif isinstance(item, dict):
                equipment.append(Equipment(
                    name=item.get("name", "Unknown"),
                    type=item.get("type", "misc"),
                    equipped=item.get("equipped", False),
                    quantity=item.get("quantity", 1),
                    magical=item.get("magical", False),
                    attunement_required=item.get("requiresAttunement", False),
                    attuned=item.get("attuned", False),
                    bg3_name=item.get("internalName"),
                    bg3_unique=item.get("unique", False),
                ))

        return equipment

    def _parse_features(self, data: dict) -> list[Feature]:
        """Parse class/race features."""
        features = []
        feature_data = data.get("features", [])

        for feat in feature_data:
            if isinstance(feat, str):
                features.append(Feature(name=feat, source="unknown"))
            elif isinstance(feat, dict):
                features.append(Feature(
                    name=feat.get("name", "Unknown"),
                    source=feat.get("source", "unknown"),
                    description=feat.get("description"),
                    bg3_name=feat.get("internalName"),
                ))

        return features

    def _parse_tadpole_powers(self, data: dict) -> list[Feature]:
        """Parse Illithid/tadpole powers."""
        powers = []
        power_data = data.get("tadpolePowers", data.get("illithidPowers", []))

        for power in power_data:
            if isinstance(power, str):
                powers.append(Feature(
                    name=power,
                    source="illithid",
                    is_illithid_power=True,
                ))
            elif isinstance(power, dict):
                powers.append(Feature(
                    name=power.get("name", "Unknown"),
                    source="illithid",
                    description=power.get("description"),
                    is_illithid_power=True,
                    bg3_name=power.get("internalName"),
                ))

        return powers


def import_from_se_json(path: Path | str) -> list[BG3Character]:
    """Convenience function to import characters from SE JSON export."""
    importer = ScriptExtenderImport(json_path=path)
    return importer.import_all()
