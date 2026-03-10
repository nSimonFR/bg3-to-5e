"""Export to Foundry VTT actor format.

Generates JSON compatible with Foundry VTT's dnd5e system (v3.x+).
Can be imported via Actor → Import Data or using modules like ddb-importer.
"""

import json
import uuid
from pathlib import Path
from typing import Any

from ..core.character import AbilityName, DnD5eCharacter


class FoundryVTTExporter:
    """Export character to Foundry VTT dnd5e actor format."""

    def export(self, character: DnD5eCharacter, output_path: Path | str | None = None) -> dict[str, Any]:
        """Export character to Foundry VTT format."""
        data = self._build_actor(character)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

        return data

    def _build_actor(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build Foundry VTT actor document."""
        actor_id = str(uuid.uuid4())[:16]

        return {
            "_id": actor_id,
            "name": char.name,
            "type": "character",
            "img": "icons/svg/mystery-man.svg",
            "system": self._build_system_data(char),
            "items": self._build_items(char),
            "effects": [],
            "flags": {
                "bg3-to-5e": {
                    "source": "bg3",
                    "originalName": char.source_character,
                    "conversionWarnings": len(char.conversion_warnings),
                }
            },
            "prototypeToken": {
                "name": char.name,
                "displayName": 20,
                "actorLink": True,
                "disposition": 1,
            },
        }

    def _build_system_data(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build the system data section."""
        return {
            "abilities": self._build_abilities(char),
            "attributes": self._build_attributes(char),
            "details": self._build_details(char),
            "traits": self._build_traits(char),
            "currency": {
                "cp": char.copper,
                "sp": char.silver,
                "ep": char.electrum,
                "gp": char.gold,
                "pp": char.platinum,
            },
            "skills": self._build_skills(char),
            "spells": self._build_spellcasting_data(char),
            "bonuses": {
                "mwak": {"attack": "", "damage": ""},
                "rwak": {"attack": "", "damage": ""},
                "msak": {"attack": "", "damage": ""},
                "rsak": {"attack": "", "damage": ""},
                "abilities": {"check": "", "save": "", "skill": ""},
                "spell": {"dc": ""},
            },
        }

    def _build_abilities(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build abilities section."""
        abilities = {}
        for ability in ["str", "dex", "con", "int", "wis", "cha"]:
            full_name = {
                "str": "strength", "dex": "dexterity", "con": "constitution",
                "int": "intelligence", "wis": "wisdom", "cha": "charisma"
            }[ability]

            score = getattr(char.ability_scores, full_name)
            prof = getattr(char.saving_throws, full_name, False)

            abilities[ability] = {
                "value": score,
                "proficient": 1 if prof else 0,
                "bonuses": {"check": "", "save": ""},
            }

        return abilities

    def _build_attributes(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build attributes section."""
        # Calculate hit dice
        hd = {}
        for cls in char.classes:
            die = self._get_hit_die(cls.name)
            if die not in hd:
                hd[die] = {"value": 0, "max": 0}
            hd[die]["value"] += cls.level
            hd[die]["max"] += cls.level

        return {
            "ac": {
                "flat": char.armor_class,
                "calc": "flat",
                "formula": "",
            },
            "hp": {
                "value": char.current_hp,
                "max": char.max_hp,
                "temp": char.temp_hp,
                "tempmax": 0,
            },
            "init": {
                "ability": "dex",
                "bonus": "",
            },
            "movement": {
                "walk": char.speed,
                "swim": 0,
                "fly": 0,
                "climb": 0,
                "burrow": 0,
                "hover": False,
                "units": "ft",
            },
            "attunement": {
                "max": 3,
            },
            "senses": {
                "darkvision": 0,
                "blindsight": 0,
                "tremorsense": 0,
                "truesight": 0,
                "units": "ft",
            },
            "spellcasting": char.spellcasting_ability.value[:3] if char.spellcasting_ability else "",
            "exhaustion": 0,
            "hd": hd,
            "death": {
                "success": char.death_saves_successes,
                "failure": char.death_saves_failures,
            },
            "inspiration": False,
            "prof": char.proficiency_bonus,
        }

    def _build_details(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build details section."""
        return {
            "biography": {
                "value": char.backstory or f"<p>Converted from Baldur's Gate 3</p>",
                "public": "",
            },
            "alignment": char.alignment,
            "race": char.subrace or char.race,
            "background": char.background,
            "originalClass": char.primary_class,
            "xp": {"value": 0},
            "appearance": char.age or "",
            "trait": char.personality_traits,
            "ideal": char.ideals,
            "bond": char.bonds,
            "flaw": char.flaws,
            "level": char.total_level,
        }

    def _build_traits(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build traits section."""
        return {
            "size": "med",
            "di": {"value": [], "custom": ""},
            "dr": {"value": [], "custom": ""},
            "dv": {"value": [], "custom": ""},
            "ci": {"value": [], "custom": ""},
            "languages": {"value": ["common"], "custom": ""},
            "weaponProf": {"value": [], "custom": ""},
            "armorProf": {"value": [], "custom": ""},
        }

    def _build_skills(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build skills section."""
        skill_map = {
            "acr": "acrobatics",
            "ani": "animal_handling",
            "arc": "arcana",
            "ath": "athletics",
            "dec": "deception",
            "his": "history",
            "ins": "insight",
            "itm": "intimidation",
            "inv": "investigation",
            "med": "medicine",
            "nat": "nature",
            "prc": "perception",
            "prf": "performance",
            "per": "persuasion",
            "rel": "religion",
            "slt": "sleight_of_hand",
            "ste": "stealth",
            "sur": "survival",
        }

        skill_abilities = {
            "acr": "dex", "ani": "wis", "arc": "int", "ath": "str",
            "dec": "cha", "his": "int", "ins": "wis", "itm": "cha",
            "inv": "int", "med": "wis", "nat": "int", "prc": "wis",
            "prf": "cha", "per": "cha", "rel": "int", "slt": "dex",
            "ste": "dex", "sur": "wis",
        }

        skills = {}
        for short, full in skill_map.items():
            prof_level = getattr(char.skills, full, 0)
            skills[short] = {
                "value": prof_level,  # 0 = none, 1 = proficient, 2 = expertise
                "ability": skill_abilities[short],
                "bonuses": {"check": "", "passive": ""},
            }

        return skills

    def _build_spellcasting_data(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build spell slot data."""
        return {
            "spell1": {"value": char.spell_slots.level_1, "max": char.spell_slots.level_1, "override": None},
            "spell2": {"value": char.spell_slots.level_2, "max": char.spell_slots.level_2, "override": None},
            "spell3": {"value": char.spell_slots.level_3, "max": char.spell_slots.level_3, "override": None},
            "spell4": {"value": char.spell_slots.level_4, "max": char.spell_slots.level_4, "override": None},
            "spell5": {"value": char.spell_slots.level_5, "max": char.spell_slots.level_5, "override": None},
            "spell6": {"value": char.spell_slots.level_6, "max": char.spell_slots.level_6, "override": None},
            "spell7": {"value": char.spell_slots.level_7, "max": char.spell_slots.level_7, "override": None},
            "spell8": {"value": char.spell_slots.level_8, "max": char.spell_slots.level_8, "override": None},
            "spell9": {"value": char.spell_slots.level_9, "max": char.spell_slots.level_9, "override": None},
            "pact": {"value": 0, "max": 0, "override": None},
        }

    def _build_items(self, char: DnD5eCharacter) -> list[dict[str, Any]]:
        """Build items array (classes, features, spells, equipment)."""
        items = []

        # Add classes
        for cls in char.classes:
            items.append(self._build_class_item(cls))

        # Add features
        for feature in char.features:
            items.append(self._build_feature_item(feature))

        # Add spells
        for spell in char.spells:
            items.append(self._build_spell_item(spell))

        # Add equipment
        for equip in char.equipment:
            items.append(self._build_equipment_item(equip))

        return items

    def _build_class_item(self, cls) -> dict[str, Any]:
        """Build a class item."""
        return {
            "_id": str(uuid.uuid4())[:16],
            "name": cls.name,
            "type": "class",
            "img": "icons/svg/book.svg",
            "system": {
                "identifier": cls.name.lower(),
                "levels": cls.level,
                "subclass": cls.subclass or "",
                "hitDice": self._get_hit_die(cls.name),
                "hitDiceUsed": 0,
            },
        }

    def _build_feature_item(self, feature) -> dict[str, Any]:
        """Build a feature item."""
        return {
            "_id": str(uuid.uuid4())[:16],
            "name": feature.name,
            "type": "feat",
            "img": "icons/svg/upgrade.svg",
            "system": {
                "description": {"value": feature.description or ""},
                "source": feature.source,
                "type": {
                    "value": "class" if feature.source in ["class", "subclass"] else "race",
                    "subtype": "",
                },
            },
        }

    def _build_spell_item(self, spell) -> dict[str, Any]:
        """Build a spell item."""
        return {
            "_id": str(uuid.uuid4())[:16],
            "name": spell.name,
            "type": "spell",
            "img": "icons/svg/lightning.svg",
            "system": {
                "description": {"value": ""},
                "source": "BG3",
                "level": spell.level,
                "school": self._map_school(spell.school),
                "preparation": {
                    "mode": "prepared",
                    "prepared": spell.prepared,
                },
            },
        }

    def _build_equipment_item(self, equip) -> dict[str, Any]:
        """Build an equipment item."""
        item_type = self._map_equipment_type(equip.type)

        item = {
            "_id": str(uuid.uuid4())[:16],
            "name": equip.name,
            "type": item_type,
            "img": self._get_equipment_icon(item_type),
            "system": {
                "description": {"value": equip.conversion_notes or ""},
                "source": "BG3",
                "quantity": equip.quantity,
                "equipped": equip.equipped,
                "rarity": "uncommon" if equip.magical else "common",
                "attunement": "required" if equip.attunement_required else "",
                "attuned": equip.attuned,
            },
        }

        return item

    def _get_hit_die(self, class_name: str) -> str:
        """Get hit die for a class."""
        hit_dice = {
            "Barbarian": "d12",
            "Bard": "d8",
            "Cleric": "d8",
            "Druid": "d8",
            "Fighter": "d10",
            "Monk": "d8",
            "Paladin": "d10",
            "Ranger": "d10",
            "Rogue": "d8",
            "Sorcerer": "d6",
            "Warlock": "d8",
            "Wizard": "d6",
        }
        return hit_dice.get(class_name, "d8")

    def _map_school(self, school: str | None) -> str:
        """Map spell school to Foundry abbreviation."""
        if not school:
            return "evoc"

        school_map = {
            "Abjuration": "abj",
            "Conjuration": "con",
            "Divination": "div",
            "Enchantment": "enc",
            "Evocation": "evo",
            "Illusion": "ill",
            "Necromancy": "nec",
            "Transmutation": "trs",
        }
        return school_map.get(school, "evo")

    def _map_equipment_type(self, equip_type: str) -> str:
        """Map equipment type to Foundry item type."""
        type_map = {
            "weapon": "weapon",
            "armor": "equipment",
            "shield": "equipment",
            "wondrous": "equipment",
            "consumable": "consumable",
            "misc": "loot",
        }
        return type_map.get(equip_type, "loot")

    def _get_equipment_icon(self, item_type: str) -> str:
        """Get icon path for equipment type."""
        icons = {
            "weapon": "icons/svg/sword.svg",
            "equipment": "icons/svg/shield.svg",
            "consumable": "icons/svg/potion.svg",
            "loot": "icons/svg/chest.svg",
        }
        return icons.get(item_type, "icons/svg/item-bag.svg")
