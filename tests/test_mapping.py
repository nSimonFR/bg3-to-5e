"""Tests for BG3 to 5e mapping engine."""

import pytest

from bg3_to_5e.core.character import (
    AbilityName,
    AbilityScores,
    BG3Character,
    CharacterClass,
    Equipment,
    Feature,
    SavingThrowProficiencies,
    SkillProficiencies,
    Spell,
)
from bg3_to_5e.mapping.classes import ClassMapper
from bg3_to_5e.mapping.converter import BG3To5eConverter
from bg3_to_5e.mapping.equipment import EquipmentMapper
from bg3_to_5e.mapping.races import RaceMapper
from bg3_to_5e.mapping.spells import SpellMapper


class TestClassMapper:
    """Tests for class mapping."""

    def test_standard_class_mapping(self):
        """Test mapping a standard class."""
        mapper = ClassMapper()
        bg3_class = CharacterClass(name="Fighter", level=5)
        mapped, warnings = mapper.map_class(bg3_class)

        assert mapped.name == "Fighter"
        assert mapped.level == 5
        assert len(warnings) == 0

    def test_subclass_mapping(self):
        """Test mapping a subclass."""
        mapper = ClassMapper()
        bg3_class = CharacterClass(name="Fighter", level=5, subclass="Battle Master")
        mapped, warnings = mapper.map_class(bg3_class)

        assert mapped.name == "Fighter"
        assert mapped.subclass == "Battle Master"
        # Should have mechanic difference warning
        assert any("maneuver" in w.message.lower() for w in warnings)

    def test_unknown_class(self):
        """Test mapping an unknown class."""
        mapper = ClassMapper()
        bg3_class = CharacterClass(name="UnknownClass", level=3)
        mapped, warnings = mapper.map_class(bg3_class)

        assert mapped.name == "UnknownClass"
        assert len(warnings) > 0
        assert warnings[0].severity == "warning"

    def test_hit_die_lookup(self):
        """Test hit die lookup."""
        mapper = ClassMapper()
        assert mapper.get_hit_die("Barbarian") == "d12"
        assert mapper.get_hit_die("Wizard") == "d6"
        assert mapper.get_hit_die("Fighter") == "d10"
        assert mapper.get_hit_die("Unknown") == "d8"

    def test_saving_throw_proficiencies(self):
        """Test saving throw proficiency lookup."""
        mapper = ClassMapper()
        saves = mapper.get_saving_throw_proficiencies("Wizard")
        assert "intelligence" in saves
        assert "wisdom" in saves


class TestSpellMapper:
    """Tests for spell mapping."""

    def test_renamed_spell(self):
        """Test mapping a renamed spell."""
        mapper = SpellMapper()
        spell = Spell(name="Bone Chill", level=0)
        mapped, warnings = mapper.map_spell(spell)

        assert mapped.name == "Chill Touch"
        assert mapped.bg3_name == "Bone Chill"

    def test_spell_with_mechanic_differences(self):
        """Test spell with mechanic differences."""
        mapper = SpellMapper()
        spell = Spell(name="Haste", level=3)
        mapped, warnings = mapper.map_spell(spell)

        assert mapped.name == "Haste"
        assert len(warnings) > 0
        assert any("action" in w.message.lower() for w in warnings)

    def test_standard_spell(self):
        """Test standard spell without changes."""
        mapper = SpellMapper()
        spell = Spell(name="Shield", level=1, prepared=True)
        mapped, warnings = mapper.map_spell(spell)

        assert mapped.name == "Shield"
        assert mapped.prepared is True
        # Shield has notes but no major mechanic differences
        assert len([w for w in warnings if w.severity == "warning"]) == 0

    def test_illithid_power_detection(self):
        """Test Illithid power detection."""
        mapper = SpellMapper()
        assert mapper.is_illithid_power("Illithid Persuasion") is True
        assert mapper.is_illithid_power("Black Hole") is True
        assert mapper.is_illithid_power("Fireball") is False


class TestEquipmentMapper:
    """Tests for equipment mapping."""

    def test_standard_weapon(self):
        """Test mapping a standard weapon."""
        mapper = EquipmentMapper()
        item = Equipment(name="Longsword", type="weapon")
        mapped, warnings = mapper.map_equipment(item)

        assert mapped.name == "Longsword"
        assert len(warnings) == 0

    def test_standard_armor(self):
        """Test mapping standard armor."""
        mapper = EquipmentMapper()
        item = Equipment(name="Chain Mail", type="armor")
        mapped, warnings = mapper.map_equipment(item)

        assert mapped.name == "Chain Mail"

    def test_bg3_unique_item(self):
        """Test mapping a BG3-unique item."""
        mapper = EquipmentMapper()
        item = Equipment(name="Mourning Frost", type="weapon", magical=True)
        mapped, warnings = mapper.map_equipment(item)

        assert "Staff of Frost" in mapped.name
        assert len(warnings) > 0
        assert any("BG3-unique" in w.message for w in warnings)

    def test_plus_weapon_pattern(self):
        """Test mapping +X weapon patterns."""
        mapper = EquipmentMapper()
        item = Equipment(name="+1 Longsword", type="weapon", magical=True)
        mapped, warnings = mapper.map_equipment(item)

        assert "+1" in mapped.name
        assert "Longsword" in mapped.name
        assert mapped.magical is True

    def test_ac_lookup(self):
        """Test armor class lookup."""
        mapper = EquipmentMapper()
        assert mapper.get_armor_class("Plate") == 18
        assert mapper.get_armor_class("Leather") == 11
        assert mapper.get_armor_class("Shield") == 2


class TestRaceMapper:
    """Tests for race mapping."""

    def test_standard_race(self):
        """Test mapping a standard race."""
        mapper = RaceMapper()
        race, subrace, warnings = mapper.map_race("Human")

        assert race == "Human"
        assert len(warnings) == 0

    def test_internal_race_name(self):
        """Test mapping internal race names."""
        mapper = RaceMapper()
        race, subrace, warnings = mapper.map_race("Elf_High")

        assert race == "Elf"
        assert subrace == "High Elf"

    def test_tiefling_subrace(self):
        """Test mapping Tiefling subraces."""
        mapper = RaceMapper()
        race, subrace, warnings = mapper.map_race("Tiefling_Asmodeus")

        assert race == "Tiefling"
        assert subrace == "Asmodeus"

    def test_background_mapping(self):
        """Test background mapping."""
        mapper = RaceMapper()
        bg, warnings = mapper.map_background("Soldier")

        assert bg == "Soldier"
        assert len(warnings) == 0

    def test_dark_urge_background(self):
        """Test Dark Urge background mapping."""
        mapper = RaceMapper()
        bg, warnings = mapper.map_background("Dark Urge")

        assert bg == "Custom"


class TestBG3To5eConverter:
    """Tests for the full converter."""

    def test_basic_conversion(self):
        """Test basic character conversion."""
        converter = BG3To5eConverter()
        bg3_char = BG3Character(
            name="Test Character",
            race="Human",
            background="Soldier",
            classes=[CharacterClass(name="Fighter", level=5)],
            ability_scores=AbilityScores(
                strength=16,
                dexterity=14,
                constitution=14,
                intelligence=10,
                wisdom=12,
                charisma=8,
            ),
            max_hp=44,
            current_hp=44,
            armor_class=18,
        )

        result = converter.convert(bg3_char)

        assert result.name == "Test Character"
        assert result.race == "Human"
        assert result.background == "Soldier"
        assert len(result.classes) == 1
        assert result.classes[0].name == "Fighter"
        assert result.max_hp == 44
        assert result.proficiency_bonus == 3  # Level 5

    def test_multiclass_conversion(self):
        """Test multiclass character conversion."""
        converter = BG3To5eConverter()
        bg3_char = BG3Character(
            name="Multiclass",
            race="Half-Elf",
            classes=[
                CharacterClass(name="Warlock", level=5, subclass="The Fiend"),
                CharacterClass(name="Sorcerer", level=5, subclass="Draconic Bloodline"),
            ],
        )

        result = converter.convert(bg3_char)

        assert result.total_level == 10
        assert len(result.classes) == 2
        assert result.proficiency_bonus == 4  # Level 10

    def test_illithid_powers_excluded(self):
        """Test that Illithid powers generate warnings."""
        converter = BG3To5eConverter()
        bg3_char = BG3Character(
            name="Test",
            race="Human",
            tadpole_powers=[
                Feature(name="Illithid Persuasion", source="illithid", is_illithid_power=True),
                Feature(name="Black Hole", source="illithid", is_illithid_power=True),
            ],
        )

        result = converter.convert(bg3_char)

        # Should have a warning about Illithid powers
        assert any(
            w.category == "illithid"
            for w in result.conversion_warnings
        )

    def test_spell_conversion(self):
        """Test spell conversion."""
        converter = BG3To5eConverter()
        bg3_char = BG3Character(
            name="Spellcaster",
            race="Human",
            spellcasting_ability=AbilityName.INTELLIGENCE,
            spells=[
                Spell(name="Bone Chill", level=0),  # Should be renamed
                Spell(name="Haste", level=3),  # Should have warning
                Spell(name="Shield", level=1),  # Standard
            ],
        )

        result = converter.convert(bg3_char)

        # Check renamed spell
        spell_names = [s.name for s in result.spells]
        assert "Chill Touch" in spell_names
        assert "Bone Chill" not in spell_names

        # Check warnings for mechanic differences
        assert any(
            w.category == "spell_mechanics" and "Haste" in w.item_name
            for w in result.conversion_warnings
        )

    def test_proficiency_bonus_calculation(self):
        """Test proficiency bonus calculation by level."""
        converter = BG3To5eConverter()

        test_cases = [
            (1, 2), (4, 2), (5, 3), (8, 3),
            (9, 4), (12, 4), (13, 5), (16, 5),
            (17, 6), (20, 6),
        ]

        for level, expected_prof in test_cases:
            assert converter._calculate_proficiency_bonus(level) == expected_prof
