"""Main BG3 to D&D 5e conversion engine."""

from ..core.character import (
    AbilityName,
    BG3Character,
    CharacterClass,
    ConversionWarning,
    DnD5eCharacter,
    Equipment,
    Feature,
    SavingThrowProficiencies,
    SkillProficiencies,
    Spell,
    SpellSlots,
)
from ..data import load_game_data
from .classes import ClassMapper
from .equipment import EquipmentMapper
from .features import (
    BACKGROUND_SKILLS,
    RACIAL_SKILLS,
    get_features_for_class,
    get_racial_features,
)
from .races import RaceMapper
from .spells import SpellMapper


class BG3To5eConverter:
    """Converts BG3 characters to D&D 5e format."""

    def __init__(self):
        self.class_mapper = ClassMapper()
        self.spell_mapper = SpellMapper()
        self.equipment_mapper = EquipmentMapper()
        self.race_mapper = RaceMapper()

    def convert(self, bg3_char: BG3Character) -> DnD5eCharacter:
        """Convert a BG3 character to D&D 5e format."""
        warnings: list[ConversionWarning] = []

        # Map race
        race_5e, subrace_5e, race_warnings = self.race_mapper.map_race(
            bg3_char.race, bg3_char.subrace
        )
        warnings.extend(race_warnings)

        # Map background
        background_5e, bg_warnings = self.race_mapper.map_background(bg3_char.background)
        warnings.extend(bg_warnings)

        # Map classes
        classes_5e = []
        for bg3_class in bg3_char.classes:
            mapped_class, class_warnings = self.class_mapper.map_class(bg3_class)
            classes_5e.append(mapped_class)
            warnings.extend(class_warnings)

        # Map spells (excluding illithid powers)
        spells_5e = []
        for spell in bg3_char.spells:
            if not self.spell_mapper.is_illithid_power(spell.name):
                mapped_spell, spell_warnings = self.spell_mapper.map_spell(spell)
                spells_5e.append(mapped_spell)
                warnings.extend(spell_warnings)

        # Map equipment
        equipment_5e = []
        for item in bg3_char.equipment:
            mapped_item, item_warnings = self.equipment_mapper.map_equipment(item)
            equipment_5e.append(mapped_item)
            warnings.extend(item_warnings)

        # Infer features from class/level/subclass/race
        features_5e = self._infer_features(bg3_char, classes_5e, race_5e, subrace_5e)

        # Merge in action resource features (from save data)
        # These provide uses/rest info not available from inference
        if bg3_char.features:
            import re
            def _norm(name: str) -> str:
                return re.sub(r'\s*\([^)]*\)$', '', name).strip().lower()
            inferred_names = {_norm(f.name) for f in features_5e}
            for feature in bg3_char.features:
                if _norm(feature.name) not in inferred_names:
                    features_5e.append(feature)

        if not bg3_char.features:
            warnings.append(ConversionWarning(
                category="features",
                item_name="All Features",
                message="Features inferred from class/level, not extracted from save",
                severity="info",
            ))

        # Infer skill proficiencies from background and race
        skills = self._infer_skills(bg3_char, background_5e, race_5e, subrace_5e, classes_5e, warnings)

        # Handle tadpole powers - add warning but don't include
        if bg3_char.tadpole_powers:
            warnings.append(ConversionWarning(
                category="illithid",
                item_name="Tadpole Powers",
                message=f"Character has {len(bg3_char.tadpole_powers)} Illithid powers. These have no 5e equivalent.",
                severity="warning",
            ))

        # Calculate race-based speed (override default 30 if race has different speed)
        race_mapping = self.race_mapper.get_race_mapping(
            bg3_char.race, bg3_char.subrace
        )
        speed = bg3_char.speed
        if race_mapping and bg3_char.speed == 30:
            speed = race_mapping.speed
        # Barbarian Fast Movement: +10 ft at level 5+
        for cls in classes_5e:
            if cls.name == "Barbarian" and cls.level >= 5:
                speed += 10
                break

        # Calculate 5e-specific values
        proficiency_bonus = self._calculate_proficiency_bonus(bg3_char.total_level)
        spell_save_dc, spell_attack = self._calculate_spellcasting(
            bg3_char.ability_scores,
            bg3_char.spellcasting_ability,
            proficiency_bonus
        )
        hit_dice = self._calculate_hit_dice(classes_5e)
        saving_throws = self._infer_saving_throws(classes_5e, bg3_char.saving_throws)

        return DnD5eCharacter(
            name=bg3_char.name,
            race=race_5e,
            subrace=subrace_5e,
            background=background_5e,
            deity=bg3_char.deity,
            classes=classes_5e,
            ability_scores=bg3_char.ability_scores,
            max_hp=bg3_char.max_hp,
            current_hp=bg3_char.current_hp,
            temp_hp=bg3_char.temp_hp,
            armor_class=bg3_char.armor_class,
            initiative=bg3_char.ability_scores.get_modifier(AbilityName.DEXTERITY),
            speed=speed,
            hit_dice=hit_dice,
            proficiency_bonus=proficiency_bonus,
            saving_throws=saving_throws,
            skills=skills,
            spells=spells_5e,
            spell_slots=self._calculate_spell_slots(classes_5e),
            spellcasting_ability=bg3_char.spellcasting_ability,
            spell_save_dc=spell_save_dc,
            spell_attack_bonus=spell_attack,
            equipment=equipment_5e,
            gold=bg3_char.gold,
            features=features_5e,
            source_character=bg3_char.name,
            conversion_warnings=warnings,
        )

    # Tiered features where only the highest tier should appear
    _SUPERSEDED_FEATURES: dict[str, list[str]] = load_game_data()["features"]["superseded_features"]

    def _infer_features(
        self,
        bg3_char: BG3Character,
        classes: list[CharacterClass],
        race: str,
        subrace: str | None,
    ) -> list[Feature]:
        """Infer features from class/level/subclass/race."""
        features = []

        # Class and subclass features
        for cls in classes:
            for feat_name, source in get_features_for_class(
                cls.name, cls.level, cls.subclass
            ):
                features.append(Feature(name=feat_name, source=source))

        # Racial features
        for feat_name, source in get_racial_features(race, subrace):
            features.append(Feature(name=feat_name, source=source))

        # Remove superseded tiered features (keep only highest tier)
        for _group, tiers in self._SUPERSEDED_FEATURES.items():
            present = [f.name for f in features if f.name in tiers]
            if len(present) > 1:
                # Keep only the highest tier (last in the ordered list)
                highest = max(present, key=lambda n: tiers.index(n))
                features = [
                    f for f in features
                    if f.name not in tiers or f.name == highest
                ]

        return features

    def _infer_skills(
        self,
        bg3_char: BG3Character,
        background: str,
        race: str,
        subrace: str | None,
        classes: list[CharacterClass],
        warnings: list[ConversionWarning],
    ) -> "SkillProficiencies":
        """Infer skill proficiencies from background and race."""
        # Start with existing skills if any are set
        skills = bg3_char.skills
        has_any = any(
            getattr(skills, field) > 0
            for field in SkillProficiencies.model_fields
        )
        if has_any:
            return skills

        # Build new skill proficiencies
        skill_dict: dict[str, int] = {}

        # Background skills
        bg_skills = BACKGROUND_SKILLS.get(background, [])
        for skill in bg_skills:
            skill_dict[skill] = 1

        # Racial skills
        key = subrace if subrace and subrace in RACIAL_SKILLS else race
        for skill in RACIAL_SKILLS.get(key, []):
            skill_dict[skill] = max(skill_dict.get(skill, 0), 1)

        # Add warning about missing class skills
        if classes:
            primary = max(classes, key=lambda c: c.level)
            class_skill_counts = load_game_data()["classes"]["skill_count"]
            count = class_skill_counts.get(primary.name, 2)
            warnings.append(ConversionWarning(
                category="skills",
                item_name=primary.name,
                message=f"{count} additional skill proficiencies from class not determined (player choice)",
                severity="info",
            ))

        return SkillProficiencies(**skill_dict)

    def _calculate_proficiency_bonus(self, total_level: int) -> int:
        """Calculate proficiency bonus based on total level."""
        if total_level < 1:
            return 2
        return (total_level - 1) // 4 + 2

    def _calculate_spellcasting(
        self,
        abilities: "AbilityScores",
        spellcasting_ability: AbilityName | None,
        proficiency: int
    ) -> tuple[int, int]:
        """Calculate spell save DC and spell attack bonus."""
        if not spellcasting_ability:
            return 0, 0

        ability_mod = abilities.get_modifier(spellcasting_ability)
        spell_save_dc = 8 + proficiency + ability_mod
        spell_attack = proficiency + ability_mod

        return spell_save_dc, spell_attack

    def _calculate_hit_dice(self, classes: list[CharacterClass]) -> str:
        """Calculate hit dice string from classes."""
        if not classes:
            return ""

        dice_counts: dict[str, int] = {}
        for char_class in classes:
            die = self.class_mapper.get_hit_die(char_class.name)
            dice_counts[die] = dice_counts.get(die, 0) + char_class.level

        parts = [f"{count}{die}" for die, count in sorted(dice_counts.items(), reverse=True)]
        return " + ".join(parts)

    def _infer_saving_throws(
        self,
        classes: list[CharacterClass],
        existing: SavingThrowProficiencies
    ) -> SavingThrowProficiencies:
        """Infer saving throw proficiencies from primary class."""
        # If we already have save data, use it
        if any([
            existing.strength, existing.dexterity, existing.constitution,
            existing.intelligence, existing.wisdom, existing.charisma
        ]):
            return existing

        # Otherwise infer from primary class
        if not classes:
            return existing

        primary_class = max(classes, key=lambda c: c.level)
        save1, save2 = self.class_mapper.get_saving_throw_proficiencies(primary_class.name)

        return SavingThrowProficiencies(
            strength=(save1 == "strength" or save2 == "strength"),
            dexterity=(save1 == "dexterity" or save2 == "dexterity"),
            constitution=(save1 == "constitution" or save2 == "constitution"),
            intelligence=(save1 == "intelligence" or save2 == "intelligence"),
            wisdom=(save1 == "wisdom" or save2 == "wisdom"),
            charisma=(save1 == "charisma" or save2 == "charisma"),
        )

    def _calculate_spell_slots(self, classes: list[CharacterClass]) -> SpellSlots:
        """Calculate spell slots based on class levels."""
        # Find primary spellcasting class
        spellcasters = ["Bard", "Cleric", "Druid", "Sorcerer", "Wizard", "Warlock",
                        "Paladin", "Ranger", "Eldritch Knight", "Arcane Trickster"]

        caster_levels = {}
        for char_class in classes:
            if char_class.name in spellcasters:
                caster_levels[char_class.name] = char_class.level
            elif char_class.subclass in ["Eldritch Knight", "Arcane Trickster"]:
                caster_levels[char_class.subclass] = char_class.level

        if not caster_levels:
            return SpellSlots()

        # For simplicity, use single-class spell slot calculation
        # Multiclass spellcasting is more complex
        primary_caster = max(caster_levels.items(), key=lambda x: x[1])
        caster_name, caster_level = primary_caster

        slots = self.spell_mapper.get_spell_slots_for_level(caster_name, caster_level)

        return SpellSlots(
            level_1=slots.get(1, 0),
            level_2=slots.get(2, 0),
            level_3=slots.get(3, 0),
            level_4=slots.get(4, 0),
            level_5=slots.get(5, 0),
            level_6=slots.get(6, 0),
            level_7=slots.get(7, 0),
            level_8=slots.get(8, 0),
            level_9=slots.get(9, 0),
        )

    def get_warnings_summary(self, warnings: list[ConversionWarning]) -> dict[str, list[ConversionWarning]]:
        """Group warnings by category."""
        grouped: dict[str, list[ConversionWarning]] = {}
        for warning in warnings:
            if warning.category not in grouped:
                grouped[warning.category] = []
            grouped[warning.category].append(warning)
        return grouped
