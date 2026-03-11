"""Export to Roll20 character format.

Generates JSON compatible with Roll20's D&D 5e by Roll20 character sheet.
Can be imported via Character Vault or API.
"""

import json
from pathlib import Path
from typing import Any

from ..core.character import AbilityName, DnD5eCharacter


class Roll20Exporter:
    """Export character to Roll20 format."""

    def export(self, character: DnD5eCharacter, output_path: Path | str | None = None) -> dict[str, Any]:
        """Export character to Roll20 format."""
        data = self._build_character(character)

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

        return data

    def _build_character(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build Roll20 character data."""
        return {
            "schema_version": 3,
            "character": {
                "name": char.name,
                "avatar": "",
                "bio": char.backstory or f"Converted from Baldur's Gate 3",
                "attribs": self._build_attributes(char),
                "abilities": self._build_abilities_list(char),
            },
        }

    def _build_attributes(self, char: DnD5eCharacter) -> list[dict[str, Any]]:
        """Build Roll20 attribute list."""
        attrs = []

        # Helper to add attribute
        def add(name: str, current: Any, max_val: Any = None):
            attr = {"name": name, "current": str(current)}
            if max_val is not None:
                attr["max"] = str(max_val)
            attrs.append(attr)

        # Character info
        add("character_name", char.name)
        add("base_level", char.total_level)
        add("level", char.total_level)
        add("experience", 0)
        add("race", char.subrace or char.race)
        add("background", char.background)
        add("alignment", char.alignment)
        add("player_name", char.player_name)

        # Build class string
        class_parts = []
        for cls in char.classes:
            part = f"{cls.name} {cls.level}"
            class_parts.append(part)
        add("class", " / ".join(class_parts))

        # For multiclass display
        for i, cls in enumerate(char.classes):
            add(f"multiclass{i+1}_flag", 1 if i > 0 else 0)
            if i > 0:
                add(f"multiclass{i}_lvl", cls.level)
                add(f"multiclass{i}", cls.name)
                if cls.subclass:
                    add(f"multiclass{i}_subclass", cls.subclass)

        # Primary class
        if char.classes:
            add("class", char.classes[0].name)
            add("subclass", char.classes[0].subclass or "")
            add("hitdietype", self._get_hit_die_num(char.classes[0].name))

        # Ability scores
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            score = getattr(char.ability_scores, ability)
            ability_enum = AbilityName(ability)
            mod = char.ability_scores.get_modifier(ability_enum)

            add(ability, score)
            add(f"{ability}_base", score)
            add(f"{ability}_mod", mod)

        # Saving throws
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            ability_enum = AbilityName(ability)
            base_mod = char.ability_scores.get_modifier(ability_enum)
            prof = getattr(char.saving_throws, ability, False)
            total = base_mod + (char.proficiency_bonus if prof else 0)

            add(f"{ability}_save_bonus", total)
            add(f"{ability}_save_prof", "@{pb}" if prof else "0")

        # Combat stats
        add("hp", char.current_hp, char.max_hp)
        add("hp_temp", char.temp_hp)
        add("ac", char.armor_class)
        add("initiative_bonus", char.initiative)
        add("speed", char.speed)
        add("hitdietype", self._get_hit_die_num(char.primary_class))
        add("hitdie", char.total_level, char.total_level)
        add("pb", char.proficiency_bonus)

        # Death saves
        add("deathsave_succ1", 1 if char.death_saves_successes >= 1 else 0)
        add("deathsave_succ2", 1 if char.death_saves_successes >= 2 else 0)
        add("deathsave_succ3", 1 if char.death_saves_successes >= 3 else 0)
        add("deathsave_fail1", 1 if char.death_saves_failures >= 1 else 0)
        add("deathsave_fail2", 1 if char.death_saves_failures >= 2 else 0)
        add("deathsave_fail3", 1 if char.death_saves_failures >= 3 else 0)

        # Skills
        skill_attrs = {
            "acrobatics": ("dexterity", "acrobatics"),
            "animal_handling": ("wisdom", "animal_handling"),
            "arcana": ("intelligence", "arcana"),
            "athletics": ("strength", "athletics"),
            "deception": ("charisma", "deception"),
            "history": ("intelligence", "history"),
            "insight": ("wisdom", "insight"),
            "intimidation": ("charisma", "intimidation"),
            "investigation": ("intelligence", "investigation"),
            "medicine": ("wisdom", "medicine"),
            "nature": ("intelligence", "nature"),
            "perception": ("wisdom", "perception"),
            "performance": ("charisma", "performance"),
            "persuasion": ("charisma", "persuasion"),
            "religion": ("intelligence", "religion"),
            "sleight_of_hand": ("dexterity", "sleight_of_hand"),
            "stealth": ("dexterity", "stealth"),
            "survival": ("wisdom", "survival"),
        }

        for skill, (ability, skill_name) in skill_attrs.items():
            ability_enum = AbilityName(ability)
            base_mod = char.ability_scores.get_modifier(ability_enum)
            prof_level = getattr(char.skills, skill, 0)

            if prof_level == 2:
                total = base_mod + char.proficiency_bonus * 2
                prof_val = "(@{pb}*2)"
            elif prof_level == 1:
                total = base_mod + char.proficiency_bonus
                prof_val = "@{pb}"
            else:
                total = base_mod
                prof_val = "0"

            roll20_skill = skill_name.replace("_", "")
            add(f"{roll20_skill}_bonus", total)
            add(f"{roll20_skill}_prof", prof_val)
            add(f"{roll20_skill}_type", prof_level)

        # Passive perception
        perception_mod = char.ability_scores.get_modifier(AbilityName.WISDOM)
        perception_prof = char.skills.perception
        if perception_prof == 2:
            passive = 10 + perception_mod + char.proficiency_bonus * 2
        elif perception_prof == 1:
            passive = 10 + perception_mod + char.proficiency_bonus
        else:
            passive = 10 + perception_mod
        add("passive_wisdom", passive)

        # Spellcasting
        if char.spellcasting_ability:
            add("spellcasting_ability", f"@{{{char.spellcasting_ability.value}_mod}}+")
            add("spell_save_dc", char.spell_save_dc)
            add("spell_attack_bonus", char.spell_attack_bonus)

        # Spell slots
        add("lvl1_slots_total", char.spell_slots.level_1)
        add("lvl1_slots_expended", 0)
        add("lvl2_slots_total", char.spell_slots.level_2)
        add("lvl2_slots_expended", 0)
        add("lvl3_slots_total", char.spell_slots.level_3)
        add("lvl3_slots_expended", 0)
        add("lvl4_slots_total", char.spell_slots.level_4)
        add("lvl4_slots_expended", 0)
        add("lvl5_slots_total", char.spell_slots.level_5)
        add("lvl5_slots_expended", 0)
        add("lvl6_slots_total", char.spell_slots.level_6)
        add("lvl6_slots_expended", 0)
        add("lvl7_slots_total", char.spell_slots.level_7)
        add("lvl7_slots_expended", 0)
        add("lvl8_slots_total", char.spell_slots.level_8)
        add("lvl8_slots_expended", 0)
        add("lvl9_slots_total", char.spell_slots.level_9)
        add("lvl9_slots_expended", 0)

        # Currency
        add("cp", char.copper)
        add("sp", char.silver)
        add("ep", char.electrum)
        add("gp", char.gold)
        add("pp", char.platinum)

        # Personality
        add("personality_traits", char.personality_traits)
        add("ideals", char.ideals)
        add("bonds", char.bonds)
        add("flaws", char.flaws)

        # Features and traits as text block
        features_text = "\n\n".join(
            f"**{f.name}** ({f.source})\n{f.description or ''}"
            for f in char.features
        )
        add("features_and_traits", features_text)

        # Equipment as text
        equipment_text = "\n".join(
            f"{'[E] ' if e.equipped else ''}{e.name}{' (x' + str(e.quantity) + ')' if e.quantity > 1 else ''}"
            for e in char.equipment
        )
        add("equipment", equipment_text)

        return attrs

    def _build_abilities_list(self, char: DnD5eCharacter) -> list[dict[str, Any]]:
        """Build Roll20 abilities (macros) list."""
        abilities = []

        # Initiative macro
        abilities.append({
            "name": "Initiative",
            "action": "/roll 1d20+@{initiative_bonus} &{tracker}",
            "istokenaction": True,
        })

        # Saving throw macros
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            abilities.append({
                "name": f"{ability.title()} Save",
                "action": f"/roll 1d20+@{{{ability}_save_bonus}}",
                "istokenaction": False,
            })

        # Add spell macros for known spells
        for spell in char.spells[:10]:  # Limit to avoid too many
            abilities.append({
                "name": spell.name,
                "action": f"&{{template:spell}} {{{{name={spell.name}}}}} {{{{level={spell.level}}}}}",
                "istokenaction": False,
            })

        return abilities

    def _get_hit_die_num(self, class_name: str) -> int:
        """Get hit die number for a class."""
        hit_dice = {
            "Barbarian": 12,
            "Bard": 8,
            "Cleric": 8,
            "Druid": 8,
            "Fighter": 10,
            "Monk": 8,
            "Paladin": 10,
            "Ranger": 10,
            "Rogue": 8,
            "Sorcerer": 6,
            "Warlock": 8,
            "Wizard": 6,
        }
        return hit_dice.get(class_name, 8)
