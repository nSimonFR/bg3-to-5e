"""Tests for character models."""

import pytest

from bg3_to_5e.core.character import (
    AbilityName,
    AbilityScores,
    BG3Character,
    CharacterClass,
    DnD5eCharacter,
    Equipment,
    Feature,
    SavingThrowProficiencies,
    SkillProficiencies,
    Spell,
    SpellSlots,
)


class TestAbilityScores:
    """Tests for AbilityScores model."""

    def test_default_scores(self):
        """Test default ability scores are 10."""
        scores = AbilityScores()
        assert scores.strength == 10
        assert scores.dexterity == 10
        assert scores.constitution == 10
        assert scores.intelligence == 10
        assert scores.wisdom == 10
        assert scores.charisma == 10

    def test_custom_scores(self):
        """Test setting custom ability scores."""
        scores = AbilityScores(
            strength=18,
            dexterity=14,
            constitution=16,
            intelligence=8,
            wisdom=12,
            charisma=10,
        )
        assert scores.strength == 18
        assert scores.dexterity == 14
        assert scores.constitution == 16
        assert scores.intelligence == 8
        assert scores.wisdom == 12
        assert scores.charisma == 10

    def test_modifier_calculation(self):
        """Test ability modifier calculation."""
        scores = AbilityScores(
            strength=18,  # +4
            dexterity=14,  # +2
            constitution=10,  # +0
            intelligence=8,  # -1
            wisdom=1,  # -5
            charisma=20,  # +5
        )
        assert scores.get_modifier(AbilityName.STRENGTH) == 4
        assert scores.get_modifier(AbilityName.DEXTERITY) == 2
        assert scores.get_modifier(AbilityName.CONSTITUTION) == 0
        assert scores.get_modifier(AbilityName.INTELLIGENCE) == -1
        assert scores.get_modifier(AbilityName.WISDOM) == -5
        assert scores.get_modifier(AbilityName.CHARISMA) == 5

    def test_score_bounds(self):
        """Test ability score bounds validation."""
        with pytest.raises(ValueError):
            AbilityScores(strength=0)  # Below minimum

        with pytest.raises(ValueError):
            AbilityScores(dexterity=31)  # Above maximum


class TestCharacterClass:
    """Tests for CharacterClass model."""

    def test_basic_class(self):
        """Test creating a basic class."""
        cls = CharacterClass(name="Fighter", level=5)
        assert cls.name == "Fighter"
        assert cls.level == 5
        assert cls.subclass is None

    def test_class_with_subclass(self):
        """Test creating a class with subclass."""
        cls = CharacterClass(
            name="Rogue",
            level=7,
            subclass="Assassin",
        )
        assert cls.name == "Rogue"
        assert cls.level == 7
        assert cls.subclass == "Assassin"

    def test_level_bounds(self):
        """Test level bounds validation."""
        with pytest.raises(ValueError):
            CharacterClass(name="Fighter", level=0)

        with pytest.raises(ValueError):
            CharacterClass(name="Fighter", level=21)


class TestBG3Character:
    """Tests for BG3Character model."""

    def test_basic_character(self):
        """Test creating a basic character."""
        char = BG3Character(
            name="Wycia",
            race="Half-Elf",
            classes=[
                CharacterClass(name="Sorcerer", level=10, subclass="Draconic Bloodline"),
            ],
        )
        assert char.name == "Wycia"
        assert char.race == "Half-Elf"
        assert len(char.classes) == 1
        assert char.total_level == 10

    def test_multiclass_character(self):
        """Test creating a multiclass character."""
        char = BG3Character(
            name="Lilith",
            race="Tiefling",
            classes=[
                CharacterClass(name="Warlock", level=5, subclass="The Fiend"),
                CharacterClass(name="Sorcerer", level=7, subclass="Draconic Bloodline"),
            ],
        )
        assert char.total_level == 12
        assert len(char.classes) == 2

    def test_character_with_equipment(self):
        """Test character with equipment."""
        char = BG3Character(
            name="Test",
            race="Human",
            equipment=[
                Equipment(name="Longsword", type="weapon", equipped=True),
                Equipment(name="Chain Mail", type="armor", equipped=True),
            ],
        )
        assert len(char.equipment) == 2

    def test_character_with_spells(self):
        """Test character with spells."""
        char = BG3Character(
            name="Test",
            race="Human",
            spells=[
                Spell(name="Fire Bolt", level=0, prepared=True),
                Spell(name="Fireball", level=3, prepared=True),
            ],
        )
        assert len(char.spells) == 2


class TestDnD5eCharacter:
    """Tests for DnD5eCharacter model."""

    def test_primary_class(self):
        """Test primary class detection."""
        char = DnD5eCharacter(
            name="Test",
            race="Human",
            background="Soldier",
            classes=[
                CharacterClass(name="Fighter", level=3),
                CharacterClass(name="Rogue", level=5),
            ],
        )
        assert char.primary_class == "Rogue"  # Highest level

    def test_single_class_primary(self):
        """Test primary class with single class."""
        char = DnD5eCharacter(
            name="Test",
            race="Human",
            background="Soldier",
            classes=[
                CharacterClass(name="Paladin", level=8),
            ],
        )
        assert char.primary_class == "Paladin"

    def test_empty_classes(self):
        """Test primary class with no classes."""
        char = DnD5eCharacter(
            name="Test",
            race="Human",
            background="Soldier",
        )
        assert char.primary_class == "Unknown"


class TestSpell:
    """Tests for Spell model."""

    def test_cantrip(self):
        """Test creating a cantrip."""
        spell = Spell(name="Fire Bolt", level=0, school="Evocation")
        assert spell.level == 0
        assert spell.school == "Evocation"

    def test_leveled_spell(self):
        """Test creating a leveled spell."""
        spell = Spell(
            name="Fireball",
            level=3,
            school="Evocation",
            prepared=True,
        )
        assert spell.level == 3
        assert spell.prepared is True

    def test_spell_with_differences(self):
        """Test spell with mechanic differences."""
        spell = Spell(
            name="Haste",
            level=3,
            bg3_name="Haste",
            mechanic_differences=["BG3: Extra action can be any action"],
        )
        assert len(spell.mechanic_differences) == 1


class TestEquipment:
    """Tests for Equipment model."""

    def test_basic_item(self):
        """Test creating a basic item."""
        item = Equipment(name="Longsword", type="weapon")
        assert item.name == "Longsword"
        assert item.magical is False
        assert item.quantity == 1

    def test_magical_item(self):
        """Test creating a magical item."""
        item = Equipment(
            name="+2 Longsword",
            type="weapon",
            magical=True,
            attunement_required=True,
        )
        assert item.magical is True
        assert item.attunement_required is True

    def test_bg3_unique_item(self):
        """Test marking BG3-unique item."""
        item = Equipment(
            name="Mourning Frost",
            type="weapon",
            magical=True,
            bg3_unique=True,
            conversion_notes="BG3-unique staff",
        )
        assert item.bg3_unique is True
        assert item.conversion_notes is not None
