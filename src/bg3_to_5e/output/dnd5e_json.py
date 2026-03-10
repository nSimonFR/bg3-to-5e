"""Export to dnd5e_json_schema format.

Reference: https://github.com/BrianWendt/dnd5e_json_schema
"""

import json
from pathlib import Path
from typing import Any

from ..core.character import AbilityName, DnD5eCharacter


class DnD5eJsonExporter:
    """Export character to dnd5e_json_schema format."""

    SCHEMA_VERSION = "1.0"

    def export(self, character: DnD5eCharacter, output_path: Path | str | None = None) -> dict[str, Any]:
        """Export character to dnd5e_json format."""
        data = self._build_character_dict(character)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

        return data

    def _build_character_dict(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build the character dictionary."""
        return {
            "schema_version": self.SCHEMA_VERSION,
            "name": char.name,
            "player_name": char.player_name,
            "race": char.race,
            "subrace": char.subrace,
            "background": char.background,
            "deity": char.deity,
            "alignment": char.alignment,
            "level": char.total_level,
            "classes": [
                {
                    "name": c.name,
                    "level": c.level,
                    "subclass": c.subclass,
                }
                for c in char.classes
            ],
            "ability_scores": {
                "strength": char.ability_scores.strength,
                "dexterity": char.ability_scores.dexterity,
                "constitution": char.ability_scores.constitution,
                "intelligence": char.ability_scores.intelligence,
                "wisdom": char.ability_scores.wisdom,
                "charisma": char.ability_scores.charisma,
            },
            "ability_modifiers": {
                "strength": char.ability_scores.get_modifier(AbilityName.STRENGTH),
                "dexterity": char.ability_scores.get_modifier(AbilityName.DEXTERITY),
                "constitution": char.ability_scores.get_modifier(AbilityName.CONSTITUTION),
                "intelligence": char.ability_scores.get_modifier(AbilityName.INTELLIGENCE),
                "wisdom": char.ability_scores.get_modifier(AbilityName.WISDOM),
                "charisma": char.ability_scores.get_modifier(AbilityName.CHARISMA),
            },
            "hit_points": {
                "maximum": char.max_hp,
                "current": char.current_hp,
                "temporary": char.temp_hp,
            },
            "armor_class": char.armor_class,
            "initiative": char.initiative,
            "speed": char.speed,
            "hit_dice": char.hit_dice,
            "proficiency_bonus": char.proficiency_bonus,
            "saving_throws": {
                "strength": {
                    "proficient": char.saving_throws.strength,
                    "modifier": self._calc_save_mod(char, "strength"),
                },
                "dexterity": {
                    "proficient": char.saving_throws.dexterity,
                    "modifier": self._calc_save_mod(char, "dexterity"),
                },
                "constitution": {
                    "proficient": char.saving_throws.constitution,
                    "modifier": self._calc_save_mod(char, "constitution"),
                },
                "intelligence": {
                    "proficient": char.saving_throws.intelligence,
                    "modifier": self._calc_save_mod(char, "intelligence"),
                },
                "wisdom": {
                    "proficient": char.saving_throws.wisdom,
                    "modifier": self._calc_save_mod(char, "wisdom"),
                },
                "charisma": {
                    "proficient": char.saving_throws.charisma,
                    "modifier": self._calc_save_mod(char, "charisma"),
                },
            },
            "skills": self._build_skills(char),
            "spellcasting": self._build_spellcasting(char) if char.spellcasting_ability else None,
            "equipment": [
                {
                    "name": e.name,
                    "type": e.type,
                    "equipped": e.equipped,
                    "quantity": e.quantity,
                    "magical": e.magical,
                    "attunement_required": e.attunement_required,
                    "attuned": e.attuned,
                }
                for e in char.equipment
            ],
            "currency": {
                "copper": char.copper,
                "silver": char.silver,
                "electrum": char.electrum,
                "gold": char.gold,
                "platinum": char.platinum,
            },
            "features": [
                {
                    "name": f.name,
                    "source": f.source,
                    "description": f.description,
                }
                for f in char.features
            ],
            "personality": {
                "traits": char.personality_traits,
                "ideals": char.ideals,
                "bonds": char.bonds,
                "flaws": char.flaws,
            },
            "appearance": {
                "age": char.age,
                "height": char.height,
                "weight": char.weight,
                "eyes": char.eyes,
                "skin": char.skin,
                "hair": char.hair,
            },
            "backstory": char.backstory,
            "conversion_info": {
                "source": "BG3",
                "source_character": char.source_character,
                "warnings": [
                    {
                        "category": w.category,
                        "item": w.item_name,
                        "message": w.message,
                        "severity": w.severity,
                    }
                    for w in char.conversion_warnings
                ],
            },
        }

    def _calc_save_mod(self, char: DnD5eCharacter, ability: str) -> int:
        """Calculate saving throw modifier."""
        ability_enum = AbilityName(ability)
        base_mod = char.ability_scores.get_modifier(ability_enum)
        prof = getattr(char.saving_throws, ability, False)
        return base_mod + (char.proficiency_bonus if prof else 0)

    def _build_skills(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build skills section."""
        skill_abilities = {
            "acrobatics": "dexterity",
            "animal_handling": "wisdom",
            "arcana": "intelligence",
            "athletics": "strength",
            "deception": "charisma",
            "history": "intelligence",
            "insight": "wisdom",
            "intimidation": "charisma",
            "investigation": "intelligence",
            "medicine": "wisdom",
            "nature": "intelligence",
            "perception": "wisdom",
            "performance": "charisma",
            "persuasion": "charisma",
            "religion": "intelligence",
            "sleight_of_hand": "dexterity",
            "stealth": "dexterity",
            "survival": "wisdom",
        }

        skills = {}
        for skill_name, ability in skill_abilities.items():
            prof_level = getattr(char.skills, skill_name, 0)
            ability_enum = AbilityName(ability)
            base_mod = char.ability_scores.get_modifier(ability_enum)

            prof_bonus = 0
            if prof_level == 1:
                prof_bonus = char.proficiency_bonus
            elif prof_level == 2:
                prof_bonus = char.proficiency_bonus * 2  # Expertise

            skills[skill_name] = {
                "ability": ability,
                "proficient": prof_level >= 1,
                "expertise": prof_level >= 2,
                "modifier": base_mod + prof_bonus,
            }

        return skills

    def _build_spellcasting(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build spellcasting section."""
        spells_by_level: dict[int, list[dict]] = {}
        for spell in char.spells:
            level = spell.level
            if level not in spells_by_level:
                spells_by_level[level] = []
            spells_by_level[level].append({
                "name": spell.name,
                "prepared": spell.prepared,
                "school": spell.school,
            })

        return {
            "ability": char.spellcasting_ability.value if char.spellcasting_ability else None,
            "spell_save_dc": char.spell_save_dc,
            "spell_attack_bonus": char.spell_attack_bonus,
            "spell_slots": {
                "1st": char.spell_slots.level_1,
                "2nd": char.spell_slots.level_2,
                "3rd": char.spell_slots.level_3,
                "4th": char.spell_slots.level_4,
                "5th": char.spell_slots.level_5,
                "6th": char.spell_slots.level_6,
                "7th": char.spell_slots.level_7,
                "8th": char.spell_slots.level_8,
                "9th": char.spell_slots.level_9,
            },
            "spells": spells_by_level,
        }
