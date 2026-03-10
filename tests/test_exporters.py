"""Tests for output exporters."""

import json
import tempfile
from pathlib import Path

import pytest

from bg3_to_5e.core.character import (
    AbilityName,
    AbilityScores,
    CharacterClass,
    DnD5eCharacter,
    Equipment,
    SavingThrowProficiencies,
    SkillProficiencies,
    Spell,
    SpellSlots,
)
from bg3_to_5e.output.dnd5e_json import DnD5eJsonExporter
from bg3_to_5e.output.foundry_vtt import FoundryVTTExporter
from bg3_to_5e.output.html_sheet import HTMLSheetExporter
from bg3_to_5e.output.roll20 import Roll20Exporter


@pytest.fixture
def sample_character():
    """Create a sample D&D 5e character for testing."""
    return DnD5eCharacter(
        name="Test Hero",
        player_name="Test Player",
        race="Half-Elf",
        subrace="High Half-Elf",
        background="Noble",
        alignment="Neutral Good",
        classes=[
            CharacterClass(name="Wizard", level=8, subclass="School of Evocation"),
        ],
        ability_scores=AbilityScores(
            strength=8,
            dexterity=14,
            constitution=14,
            intelligence=18,
            wisdom=12,
            charisma=10,
        ),
        max_hp=50,
        current_hp=45,
        temp_hp=5,
        armor_class=15,
        initiative=2,
        speed=30,
        hit_dice="8d6",
        proficiency_bonus=3,
        saving_throws=SavingThrowProficiencies(
            intelligence=True,
            wisdom=True,
        ),
        skills=SkillProficiencies(
            arcana=2,  # Expertise
            history=1,  # Proficient
            investigation=1,
        ),
        spellcasting_ability=AbilityName.INTELLIGENCE,
        spell_save_dc=15,
        spell_attack_bonus=7,
        spell_slots=SpellSlots(level_1=4, level_2=3, level_3=3, level_4=2),
        spells=[
            Spell(name="Fire Bolt", level=0, prepared=True),
            Spell(name="Mage Hand", level=0, prepared=True),
            Spell(name="Shield", level=1, prepared=True),
            Spell(name="Magic Missile", level=1, prepared=True),
            Spell(name="Fireball", level=3, prepared=True),
        ],
        equipment=[
            Equipment(name="Staff of Power", type="weapon", magical=True, equipped=True),
            Equipment(name="Robe of the Archmagi", type="armor", magical=True, equipped=True),
        ],
        gold=500,
    )


class TestDnD5eJsonExporter:
    """Tests for JSON exporter."""

    def test_export_to_dict(self, sample_character):
        """Test exporting character to dictionary."""
        exporter = DnD5eJsonExporter()
        data = exporter.export(sample_character)

        assert data["name"] == "Test Hero"
        assert data["player_name"] == "Test Player"
        assert data["race"] == "Half-Elf"
        assert data["level"] == 8
        assert len(data["classes"]) == 1
        assert data["classes"][0]["name"] == "Wizard"

    def test_export_abilities(self, sample_character):
        """Test ability score export."""
        exporter = DnD5eJsonExporter()
        data = exporter.export(sample_character)

        assert data["ability_scores"]["intelligence"] == 18
        assert data["ability_modifiers"]["intelligence"] == 4
        assert data["ability_modifiers"]["strength"] == -1

    def test_export_spellcasting(self, sample_character):
        """Test spellcasting data export."""
        exporter = DnD5eJsonExporter()
        data = exporter.export(sample_character)

        assert data["spellcasting"]["spell_save_dc"] == 15
        assert data["spellcasting"]["spell_attack_bonus"] == 7
        assert data["spellcasting"]["spell_slots"]["1st"] == 4

    def test_export_to_file(self, sample_character):
        """Test exporting to file."""
        exporter = DnD5eJsonExporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_char.json"
            data = exporter.export(sample_character, output_path)

            assert output_path.exists()

            with open(output_path) as f:
                loaded = json.load(f)
                assert loaded["name"] == "Test Hero"


class TestHTMLSheetExporter:
    """Tests for HTML exporter."""

    def test_export_to_string(self, sample_character):
        """Test exporting character to HTML string."""
        exporter = HTMLSheetExporter()
        html = exporter.export(sample_character)

        assert "Test Hero" in html
        assert "Half-Elf" in html
        assert "Wizard" in html
        assert "Level 8" in html or "level 8" in html.lower()

    def test_export_abilities_in_html(self, sample_character):
        """Test ability scores appear in HTML."""
        exporter = HTMLSheetExporter()
        html = exporter.export(sample_character)

        assert "18" in html  # Intelligence score
        assert "+4" in html  # Intelligence modifier

    def test_export_spells_in_html(self, sample_character):
        """Test spells appear in HTML."""
        exporter = HTMLSheetExporter()
        html = exporter.export(sample_character)

        assert "Fire Bolt" in html
        assert "Fireball" in html
        assert "Shield" in html

    def test_export_to_file(self, sample_character):
        """Test exporting to file."""
        exporter = HTMLSheetExporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_char.html"
            exporter.export(sample_character, output_path)

            assert output_path.exists()

            content = output_path.read_text()
            assert "Test Hero" in content


class TestFoundryVTTExporter:
    """Tests for Foundry VTT exporter."""

    def test_export_actor(self, sample_character):
        """Test exporting character as Foundry actor."""
        exporter = FoundryVTTExporter()
        data = exporter.export(sample_character)

        assert data["name"] == "Test Hero"
        assert data["type"] == "character"
        assert "_id" in data

    def test_export_system_data(self, sample_character):
        """Test system data section."""
        exporter = FoundryVTTExporter()
        data = exporter.export(sample_character)

        system = data["system"]
        assert "abilities" in system
        assert "attributes" in system
        assert "skills" in system

        # Check ability format
        assert system["abilities"]["int"]["value"] == 18
        assert system["abilities"]["int"]["proficient"] == 1  # Save proficient

    def test_export_items(self, sample_character):
        """Test items array."""
        exporter = FoundryVTTExporter()
        data = exporter.export(sample_character)

        items = data["items"]
        assert len(items) > 0

        # Should have class item
        class_items = [i for i in items if i["type"] == "class"]
        assert len(class_items) == 1
        assert class_items[0]["name"] == "Wizard"

        # Should have spell items
        spell_items = [i for i in items if i["type"] == "spell"]
        assert len(spell_items) == 5

    def test_export_to_file(self, sample_character):
        """Test exporting to file."""
        exporter = FoundryVTTExporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_foundry.json"
            exporter.export(sample_character, output_path)

            assert output_path.exists()

            with open(output_path) as f:
                loaded = json.load(f)
                assert loaded["name"] == "Test Hero"


class TestRoll20Exporter:
    """Tests for Roll20 exporter."""

    def test_export_character(self, sample_character):
        """Test exporting character for Roll20."""
        exporter = Roll20Exporter()
        data = exporter.export(sample_character)

        assert "character" in data
        assert data["character"]["name"] == "Test Hero"
        assert "attribs" in data["character"]

    def test_export_attributes(self, sample_character):
        """Test attribute export."""
        exporter = Roll20Exporter()
        data = exporter.export(sample_character)

        attribs = {a["name"]: a["current"] for a in data["character"]["attribs"]}

        assert attribs["character_name"] == "Test Hero"
        assert attribs["intelligence"] == "18"
        assert attribs["intelligence_mod"] == "4"

    def test_export_skills(self, sample_character):
        """Test skill export."""
        exporter = Roll20Exporter()
        data = exporter.export(sample_character)

        attribs = {a["name"]: a["current"] for a in data["character"]["attribs"]}

        # Arcana should have expertise bonus
        arcana_bonus = int(attribs.get("arcana_bonus", "0"))
        # Base INT mod (4) + prof * 2 (6) = 10
        assert arcana_bonus == 10

    def test_export_abilities_macros(self, sample_character):
        """Test macro generation."""
        exporter = Roll20Exporter()
        data = exporter.export(sample_character)

        abilities = data["character"]["abilities"]
        ability_names = [a["name"] for a in abilities]

        assert "Initiative" in ability_names
        # Should have saving throw macros
        assert any("Save" in name for name in ability_names)

    def test_export_to_file(self, sample_character):
        """Test exporting to file."""
        exporter = Roll20Exporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_roll20.json"
            exporter.export(sample_character, output_path)

            assert output_path.exists()

            with open(output_path) as f:
                loaded = json.load(f)
                assert loaded["character"]["name"] == "Test Hero"
