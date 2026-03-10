"""Tests for Script Extender JSON import."""

import json
import tempfile
from pathlib import Path

import pytest

from bg3_to_5e.core.character import AbilityName
from bg3_to_5e.extractors.se_import import ScriptExtenderImport, import_from_se_json


@pytest.fixture
def sample_se_export():
    """Sample Script Extender export data."""
    return {
        "exportVersion": "1.0",
        "exportDate": "2024-01-15 10:30:00",
        "party": [
            {
                "name": "Wycia",
                "uuid": "12345-abcde",
                "race": "HalfElf_High",
                "subrace": None,
                "background": "Noble",
                "classes": [
                    {
                        "name": "Sorcerer",
                        "level": 10,
                        "subclass": "Draconic Bloodline",
                        "internalName": "Sorcerer",
                    }
                ],
                "abilities": {
                    "Strength": 8,
                    "Dexterity": 14,
                    "Constitution": 14,
                    "Intelligence": 10,
                    "Wisdom": 12,
                    "Charisma": 18,
                },
                "maxHp": 72,
                "currentHp": 72,
                "tempHp": 0,
                "armorClass": 15,
                "speed": 30,
                "proficiencyBonus": 4,
                "savingThrows": {
                    "Strength": False,
                    "Dexterity": False,
                    "Constitution": True,
                    "Intelligence": False,
                    "Wisdom": False,
                    "Charisma": True,
                },
                "skills": {
                    "Arcana": {"proficient": True, "expertise": False},
                    "Persuasion": {"proficient": True, "expertise": False},
                    "Deception": {"proficient": False, "expertise": False},
                },
                "spells": [
                    {"name": "Fire Bolt", "level": 0, "prepared": True},
                    {"name": "Mage Hand", "level": 0, "prepared": True},
                    {"name": "Fireball", "level": 3, "prepared": True},
                    {"name": "Haste", "level": 3, "prepared": True},
                ],
                "spellSlots": {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
                "equipment": [
                    {"name": "Staff of Fire", "type": "weapon", "equipped": True, "magical": True},
                    {"name": "Robe", "type": "armor", "equipped": True},
                ],
                "gold": 1500,
                "features": [
                    {"name": "Draconic Resilience", "source": "class"},
                    {"name": "Metamagic", "source": "class"},
                ],
                "tadpolePowers": [
                    {"name": "Illithid Persuasion", "internalName": "TAD_IllithidPersuasion"},
                ],
            },
            {
                "name": "Shadowheart",
                "uuid": "67890-fghij",
                "race": "Elf_Drow",
                "background": "Acolyte",
                "classes": [
                    {"name": "Cleric", "level": 10, "subclass": "Trickery Domain"}
                ],
                "abilities": {
                    "Strength": 12,
                    "Dexterity": 14,
                    "Constitution": 14,
                    "Intelligence": 10,
                    "Wisdom": 17,
                    "Charisma": 10,
                },
                "maxHp": 68,
                "currentHp": 68,
            },
        ],
    }


class TestScriptExtenderImport:
    """Tests for SE JSON import."""

    def test_import_party(self, sample_se_export):
        """Test importing a party export."""
        importer = ScriptExtenderImport(json_data=sample_se_export)
        characters = importer.import_all()

        assert len(characters) == 2
        assert characters[0].name == "Wycia"
        assert characters[1].name == "Shadowheart"

    def test_import_character_details(self, sample_se_export):
        """Test character detail import."""
        importer = ScriptExtenderImport(json_data=sample_se_export)
        characters = importer.import_all()

        wycia = characters[0]
        assert wycia.race == "Half-Elf"  # Cleaned up from HalfElf_High
        assert wycia.background == "Noble"
        assert len(wycia.classes) == 1
        assert wycia.classes[0].name == "Sorcerer"
        assert wycia.classes[0].level == 10

    def test_import_abilities(self, sample_se_export):
        """Test ability score import."""
        importer = ScriptExtenderImport(json_data=sample_se_export)
        characters = importer.import_all()

        wycia = characters[0]
        assert wycia.ability_scores.charisma == 18
        assert wycia.ability_scores.strength == 8

    def test_import_saving_throws(self, sample_se_export):
        """Test saving throw import."""
        importer = ScriptExtenderImport(json_data=sample_se_export)
        characters = importer.import_all()

        wycia = characters[0]
        assert wycia.saving_throws.constitution is True
        assert wycia.saving_throws.charisma is True
        assert wycia.saving_throws.strength is False

    def test_import_skills(self, sample_se_export):
        """Test skill import."""
        importer = ScriptExtenderImport(json_data=sample_se_export)
        characters = importer.import_all()

        wycia = characters[0]
        assert wycia.skills.arcana == 1  # Proficient
        assert wycia.skills.persuasion == 1  # Proficient
        assert wycia.skills.deception == 0  # Not proficient

    def test_import_spells(self, sample_se_export):
        """Test spell import."""
        importer = ScriptExtenderImport(json_data=sample_se_export)
        characters = importer.import_all()

        wycia = characters[0]
        assert len(wycia.spells) == 4
        spell_names = [s.name for s in wycia.spells]
        assert "Fire Bolt" in spell_names
        assert "Fireball" in spell_names

    def test_import_tadpole_powers(self, sample_se_export):
        """Test tadpole power import."""
        importer = ScriptExtenderImport(json_data=sample_se_export)
        characters = importer.import_all()

        wycia = characters[0]
        assert len(wycia.tadpole_powers) == 1
        assert wycia.tadpole_powers[0].name == "Illithid Persuasion"
        assert wycia.tadpole_powers[0].is_illithid_power is True

    def test_import_equipment(self, sample_se_export):
        """Test equipment import."""
        importer = ScriptExtenderImport(json_data=sample_se_export)
        characters = importer.import_all()

        wycia = characters[0]
        assert len(wycia.equipment) == 2
        staff = next(e for e in wycia.equipment if "Staff" in e.name)
        assert staff.magical is True
        assert staff.equipped is True

    def test_import_from_file(self, sample_se_export):
        """Test importing from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_se_export, f)
            temp_path = f.name

        try:
            characters = import_from_se_json(temp_path)
            assert len(characters) == 2
        finally:
            Path(temp_path).unlink()

    def test_import_single_character(self):
        """Test importing a single character export."""
        single_char = {
            "name": "Solo Hero",
            "race": "Human",
            "classes": [{"name": "Fighter", "level": 5}],
            "abilities": {
                "Strength": 16,
                "Dexterity": 12,
                "Constitution": 14,
                "Intelligence": 10,
                "Wisdom": 10,
                "Charisma": 8,
            },
        }

        importer = ScriptExtenderImport(json_data=single_char)
        characters = importer.import_all()

        assert len(characters) == 1
        assert characters[0].name == "Solo Hero"

    def test_race_cleanup(self):
        """Test that internal race names are cleaned up."""
        data = {
            "name": "Test",
            "race": "Tiefling_Asmodeus",
        }

        importer = ScriptExtenderImport(json_data=data)
        characters = importer.import_all()

        assert characters[0].race == "Tiefling"

    def test_minimal_character(self):
        """Test importing character with minimal data."""
        minimal = {
            "name": "Minimal",
            "race": "Human",
        }

        importer = ScriptExtenderImport(json_data=minimal)
        characters = importer.import_all()

        char = characters[0]
        assert char.name == "Minimal"
        assert char.race == "Human"
        assert char.max_hp == 0  # Default
        assert len(char.classes) == 0

    def test_error_on_no_input(self):
        """Test error when no input provided."""
        with pytest.raises(ValueError):
            ScriptExtenderImport()
