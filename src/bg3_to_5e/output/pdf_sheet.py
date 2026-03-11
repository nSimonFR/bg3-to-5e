"""Export to PDF character sheet.

Uses pypdf to fill in the WotC 2022 D&D 5e fillable character sheet PDF template.
Falls back to generating an HTML sheet if no template is available.
"""

from pathlib import Path
from typing import Any

from ..core.character import AbilityName, DnD5eCharacter


class PDFSheetExporter:
    """Export character to PDF format using the WotC 2022 fillable template."""

    # WotC 2022 PDF field names for skills.
    # NOTE: Several field names have trailing spaces — this is intentional,
    # matching the actual field names in the official WotC PDF template.
    SKILL_FIELD_NAMES: dict[str, str] = {
        "acrobatics": "Acrobatics",
        "animal_handling": "Animal",
        "arcana": "Arcana",
        "athletics": "Athletics",
        "deception": "Deception ",       # trailing space
        "history": "History ",            # trailing space
        "insight": "Insight",
        "intimidation": "Intimidation",
        "investigation": "Investigation ",  # trailing space
        "medicine": "Medicine",
        "nature": "Nature",
        "perception": "Perception ",      # trailing space
        "performance": "Performance",
        "persuasion": "Persuasion",
        "religion": "Religion",
        "sleight_of_hand": "SleightofHand",
        "stealth": "Stealth ",            # trailing space
        "survival": "Survival",
    }

    SKILL_ABILITIES: dict[str, str] = {
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

    # WotC 2022 PDF modifier field names.
    # NOTE: "CHamod" and "DEXmod " are not typos — they match the actual
    # field names in the official WotC PDF (lowercase 'a', trailing space).
    ABILITY_MOD_FIELDS: dict[str, str] = {
        "strength": "STRmod",
        "dexterity": "DEXmod ",     # trailing space
        "constitution": "CONmod",
        "intelligence": "INTmod",
        "wisdom": "WISmod",
        "charisma": "CHamod",       # lowercase 'a' — WotC typo
    }

    # WotC 2022 PDF: proficiency checkbox field names.
    # Saving throw proficiency checkboxes (Check Box 11-16)
    ST_CHECKBOX_FIELDS: dict[str, str] = {
        "strength": "Check Box 11",
        "dexterity": "Check Box 18",
        "constitution": "Check Box 19",
        "intelligence": "Check Box 20",
        "wisdom": "Check Box 21",
        "charisma": "Check Box 22",
    }

    # Skill proficiency checkboxes (Check Box 23-40)
    SKILL_CHECKBOX_FIELDS: dict[str, str] = {
        "acrobatics": "Check Box 23",
        "animal_handling": "Check Box 24",
        "arcana": "Check Box 25",
        "athletics": "Check Box 26",
        "deception": "Check Box 27",
        "history": "Check Box 28",
        "insight": "Check Box 29",
        "intimidation": "Check Box 30",
        "investigation": "Check Box 31",
        "medicine": "Check Box 32",
        "nature": "Check Box 33",
        "perception": "Check Box 34",
        "performance": "Check Box 35",
        "persuasion": "Check Box 36",
        "religion": "Check Box 37",
        "sleight_of_hand": "Check Box 38",
        "stealth": "Check Box 39",
        "survival": "Check Box 40",
    }

    # Spell slot fields: SlotsTotal 19 = 1st level, ..., SlotsTotal 27 = 9th level
    SLOT_TOTAL_FIELDS: dict[int, str] = {
        1: "SlotsTotal 19",
        2: "SlotsTotal 20",
        3: "SlotsTotal 21",
        4: "SlotsTotal 22",
        5: "SlotsTotal 23",
        6: "SlotsTotal 24",
        7: "SlotsTotal 25",
        8: "SlotsTotal 26",
        9: "SlotsTotal 27",
    }

    def __init__(self, template_path: Path | str | None = None):
        """Initialize with optional PDF template path."""
        self.template_path = Path(template_path) if template_path else None

    def export(self, character: DnD5eCharacter, output_path: Path | str) -> None:
        """Export character to PDF."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        if self.template_path and self.template_path.exists():
            self._fill_template(character, output)
        else:
            self._generate_simple_pdf(character, output)

    def _fill_template(self, char: DnD5eCharacter, output: Path) -> None:
        """Fill a PDF template with character data using pypdf."""
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(str(self.template_path))
        writer = PdfWriter()
        writer.append(reader)

        values = self._build_field_values(char)

        for page in writer.pages:
            writer.update_page_form_field_values(page, values)

        with open(output, "wb") as f:
            writer.write(f)

    def _build_field_values(self, char: DnD5eCharacter) -> dict[str, Any]:
        """Build field values matching WotC 2022 fillable PDF field names."""
        values: dict[str, Any] = {}

        # Basic info
        values["CharacterName"] = char.name
        values["CharacterName 2"] = char.name
        values["Background"] = char.background
        values["Alignment"] = char.alignment
        values["PlayerName"] = char.player_name

        # Class/Level string
        class_parts = []
        for cls in char.classes:
            part = f"{cls.name} {cls.level}"
            if cls.subclass:
                part = f"{cls.name} ({cls.subclass}) {cls.level}"
            class_parts.append(part)
        values["ClassLevel"] = " / ".join(class_parts)

        # Race (field has trailing space in WotC PDF)
        race_full = char.race
        if char.subrace:
            race_full = f"{char.subrace} {char.race}"
        values["Race "] = race_full

        # Ability scores and modifiers
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            score = getattr(char.ability_scores, ability)
            ability_enum = AbilityName(ability)
            mod = char.ability_scores.get_modifier(ability_enum)

            values[ability[:3].upper()] = str(score)
            values[self.ABILITY_MOD_FIELDS[ability]] = self._format_modifier(mod)

        # Combat stats
        values["AC"] = str(char.armor_class)
        values["Initiative"] = self._format_modifier(char.initiative)
        values["Speed"] = str(char.speed)
        values["HPMax"] = str(char.max_hp)
        values["HPCurrent"] = str(char.current_hp)
        values["HPTemp"] = str(char.temp_hp) if char.temp_hp else ""
        values["HDTotal"] = char.hit_dice
        values["ProfBonus"] = self._format_modifier(char.proficiency_bonus)

        # Passive perception
        perception_mod = self._get_skill_modifier(char, "perception")
        values["Passive"] = str(10 + perception_mod)

        # Saving throws
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            ability_enum = AbilityName(ability)
            base_mod = char.ability_scores.get_modifier(ability_enum)
            prof = getattr(char.saving_throws, ability, False)
            total = base_mod + (char.proficiency_bonus if prof else 0)
            values[f"ST {ability.title()}"] = self._format_modifier(total)
            if prof:
                values[self.ST_CHECKBOX_FIELDS[ability]] = "/Yes"

        # Skills
        for skill, ability in self.SKILL_ABILITIES.items():
            mod = self._get_skill_modifier(char, skill)
            field_name = self.SKILL_FIELD_NAMES[skill]
            values[field_name] = self._format_modifier(mod)

            prof_level = getattr(char.skills, skill, 0)
            if prof_level >= 1:
                values[self.SKILL_CHECKBOX_FIELDS[skill]] = "/Yes"

        # Spellcasting (page 3 fields have " 2" suffix in WotC PDF)
        if char.spellcasting_ability:
            values["SpellcastingAbility 2"] = char.spellcasting_ability.value.upper()[:3]
            values["SpellSaveDC  2"] = str(char.spell_save_dc)
            values["SpellAtkBonus 2"] = self._format_modifier(char.spell_attack_bonus)
            # Spellcasting class
            if char.classes:
                values["Spellcasting Class 2"] = char.classes[0].name

        # Spell slots
        for level in range(1, 10):
            count = getattr(char.spell_slots, f"level_{level}", 0)
            if count > 0:
                values[self.SLOT_TOTAL_FIELDS[level]] = str(count)

        # Spells — cantrips start at Spells 1014, then leveled spells follow
        spell_idx = 1014
        spells_by_level: dict[int, list[str]] = {}
        for spell in char.spells:
            spells_by_level.setdefault(spell.level, []).append(spell.name)

        for level in range(0, 10):
            for name in spells_by_level.get(level, []):
                values[f"Spells {spell_idx}"] = name
                spell_idx += 1

        # Currency
        values["CP"] = str(char.copper)
        values["SP"] = str(char.silver)
        values["EP"] = str(char.electrum)
        values["GP"] = str(char.gold)
        values["PP"] = str(char.platinum)

        # Equipment (as text block)
        equipment_lines = []
        for item in char.equipment[:20]:
            line = item.name
            if item.quantity > 1:
                line += f" (x{item.quantity})"
            if item.equipped:
                line += " [E]"
            if item.magical:
                line += " *"
            equipment_lines.append(line)
        values["Equipment"] = "\n".join(equipment_lines)

        # Features (as text block)
        feature_lines = []
        for feat in char.features[:15]:
            line = f"• {feat.name}"
            if feat.source:
                line += f" ({feat.source})"
            feature_lines.append(line)
        values["Features and Traits"] = "\n".join(feature_lines)

        # Personality (page 2)
        if char.personality_traits:
            values["PersonalityTraits "] = char.personality_traits
        if char.ideals:
            values["Ideals"] = char.ideals
        if char.bonds:
            values["Bonds"] = char.bonds
        if char.flaws:
            values["Flaws"] = char.flaws

        # Appearance (page 2)
        if char.age:
            values["Age"] = char.age
        if char.height:
            values["Height"] = char.height
        if char.weight:
            values["Weight"] = char.weight
        if char.eyes:
            values["Eyes"] = char.eyes
        if char.skin:
            values["Skin"] = char.skin
        if char.hair:
            values["Hair"] = char.hair
        if char.backstory:
            values["Backstory"] = char.backstory
        if char.allies_and_organizations:
            values["Allies"] = char.allies_and_organizations
        if char.treasure:
            values["Treasure"] = char.treasure

        return values

    def _get_skill_modifier(self, char: DnD5eCharacter, skill: str) -> int:
        """Calculate the total modifier for a skill."""
        ability = self.SKILL_ABILITIES[skill]
        ability_enum = AbilityName(ability)
        base_mod = char.ability_scores.get_modifier(ability_enum)
        prof_level = getattr(char.skills, skill, 0)

        if prof_level == 2:
            return base_mod + char.proficiency_bonus * 2
        elif prof_level == 1:
            return base_mod + char.proficiency_bonus
        return base_mod

    def _generate_simple_pdf(self, char: DnD5eCharacter, output: Path) -> None:
        """Generate a simple text-based PDF without a template."""
        from .html_sheet import HTMLSheetExporter

        html_exporter = HTMLSheetExporter()
        html_content = html_exporter.export(char)

        html_path = output.with_suffix(".html")
        with open(html_path, "w") as f:
            f.write(html_content)

        with open(output, "w") as f:
            f.write(f"PDF generation requires a template.\n")
            f.write(f"HTML version saved to: {html_path}\n\n")
            f.write(f"To use PDF export:\n")
            f.write(f"1. Download a fillable D&D 5e character sheet PDF\n")
            f.write(f"2. Run with: --pdf-template path/to/template.pdf\n")

    def _format_modifier(self, value: int) -> str:
        """Format a modifier with + or - sign."""
        if value >= 0:
            return f"+{value}"
        return str(value)
