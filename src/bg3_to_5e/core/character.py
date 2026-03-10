"""Pydantic models for BG3 and D&D 5e characters."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AbilityName(str, Enum):
    """D&D ability score names."""
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    CONSTITUTION = "constitution"
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CHARISMA = "charisma"


class AbilityScores(BaseModel):
    """Character ability scores."""
    strength: int = Field(ge=1, le=30, default=10)
    dexterity: int = Field(ge=1, le=30, default=10)
    constitution: int = Field(ge=1, le=30, default=10)
    intelligence: int = Field(ge=1, le=30, default=10)
    wisdom: int = Field(ge=1, le=30, default=10)
    charisma: int = Field(ge=1, le=30, default=10)

    def get_modifier(self, ability: AbilityName) -> int:
        """Calculate ability modifier."""
        score = getattr(self, ability.value)
        return (score - 10) // 2


class CharacterClass(BaseModel):
    """Character class with level and subclass."""
    name: str
    level: int = Field(ge=1, le=20)
    subclass: str | None = None

    # BG3-specific fields for conversion tracking
    bg3_name: str | None = None
    bg3_subclass: str | None = None
    conversion_warnings: list[str] = Field(default_factory=list)


class Spell(BaseModel):
    """A spell known or prepared."""
    name: str
    level: int = Field(ge=0, le=9)  # 0 = cantrip
    school: str | None = None
    prepared: bool = False

    # BG3-specific
    bg3_name: str | None = None
    mechanic_differences: list[str] = Field(default_factory=list)


class SpellSlots(BaseModel):
    """Spell slots by level."""
    level_1: int = 0
    level_2: int = 0
    level_3: int = 0
    level_4: int = 0
    level_5: int = 0
    level_6: int = 0
    level_7: int = 0
    level_8: int = 0
    level_9: int = 0


class Equipment(BaseModel):
    """An equipment item."""
    name: str
    type: str  # weapon, armor, wondrous, etc.
    equipped: bool = False
    quantity: int = 1

    # Properties
    magical: bool = False
    attunement_required: bool = False
    attuned: bool = False

    # BG3-specific
    bg3_name: str | None = None
    bg3_unique: bool = False  # True if BG3-only item
    conversion_notes: str | None = None


class Feature(BaseModel):
    """A class, race, or background feature."""
    name: str
    source: str  # class, race, background, feat, etc.
    description: str | None = None

    # BG3-specific
    bg3_name: str | None = None
    is_illithid_power: bool = False
    homebrew_equivalent: bool = False


class SavingThrowProficiencies(BaseModel):
    """Saving throw proficiencies."""
    strength: bool = False
    dexterity: bool = False
    constitution: bool = False
    intelligence: bool = False
    wisdom: bool = False
    charisma: bool = False


class SkillProficiencies(BaseModel):
    """Skill proficiencies with expertise tracking."""
    # Each skill is: 0 = not proficient, 1 = proficient, 2 = expertise
    acrobatics: int = Field(ge=0, le=2, default=0)
    animal_handling: int = Field(ge=0, le=2, default=0)
    arcana: int = Field(ge=0, le=2, default=0)
    athletics: int = Field(ge=0, le=2, default=0)
    deception: int = Field(ge=0, le=2, default=0)
    history: int = Field(ge=0, le=2, default=0)
    insight: int = Field(ge=0, le=2, default=0)
    intimidation: int = Field(ge=0, le=2, default=0)
    investigation: int = Field(ge=0, le=2, default=0)
    medicine: int = Field(ge=0, le=2, default=0)
    nature: int = Field(ge=0, le=2, default=0)
    perception: int = Field(ge=0, le=2, default=0)
    performance: int = Field(ge=0, le=2, default=0)
    persuasion: int = Field(ge=0, le=2, default=0)
    religion: int = Field(ge=0, le=2, default=0)
    sleight_of_hand: int = Field(ge=0, le=2, default=0)
    stealth: int = Field(ge=0, le=2, default=0)
    survival: int = Field(ge=0, le=2, default=0)


class BG3Character(BaseModel):
    """Character data as extracted from BG3 save files."""
    # Core identity
    name: str
    uuid: str | None = None

    # Race/origin
    race: str
    subrace: str | None = None
    background: str | None = None
    deity: str | None = None

    # Classes (multiclass support)
    classes: list[CharacterClass] = Field(default_factory=list)

    # Abilities
    ability_scores: AbilityScores = Field(default_factory=AbilityScores)

    # Combat stats
    max_hp: int = 0
    current_hp: int = 0
    temp_hp: int = 0
    armor_class: int = 10
    initiative_bonus: int = 0
    speed: int = 30

    # Proficiencies
    proficiency_bonus: int = 2
    saving_throws: SavingThrowProficiencies = Field(default_factory=SavingThrowProficiencies)
    skills: SkillProficiencies = Field(default_factory=SkillProficiencies)

    # Spells
    spells: list[Spell] = Field(default_factory=list)
    spell_slots: SpellSlots = Field(default_factory=SpellSlots)
    spellcasting_ability: AbilityName | None = None

    # Equipment
    equipment: list[Equipment] = Field(default_factory=list)
    gold: int = 0

    # Features
    features: list[Feature] = Field(default_factory=list)

    # BG3-specific data
    tadpole_powers: list[Feature] = Field(default_factory=list)
    inspiration_points: int = 0

    # Raw data for debugging
    raw_data: dict[str, Any] | None = None

    @property
    def total_level(self) -> int:
        """Calculate total character level."""
        return sum(c.level for c in self.classes)


class ConversionWarning(BaseModel):
    """A warning about BG3 to 5e conversion differences."""
    category: str  # spell, class, item, feature
    item_name: str
    message: str
    severity: str = "info"  # info, warning, error


class DnD5eCharacter(BaseModel):
    """Standard D&D 5e character sheet data."""
    # Core identity
    name: str
    player_name: str = ""

    # Race/origin
    race: str
    subrace: str | None = None
    background: str
    deity: str | None = None
    alignment: str = "Neutral"

    # Classes
    classes: list[CharacterClass] = Field(default_factory=list)

    # Abilities
    ability_scores: AbilityScores = Field(default_factory=AbilityScores)

    # Combat
    max_hp: int = 0
    current_hp: int = 0
    temp_hp: int = 0
    armor_class: int = 10
    initiative: int = 0
    speed: int = 30
    hit_dice: str = ""
    death_saves_successes: int = 0
    death_saves_failures: int = 0

    # Proficiencies
    proficiency_bonus: int = 2
    saving_throws: SavingThrowProficiencies = Field(default_factory=SavingThrowProficiencies)
    skills: SkillProficiencies = Field(default_factory=SkillProficiencies)

    # Spells
    spells: list[Spell] = Field(default_factory=list)
    spell_slots: SpellSlots = Field(default_factory=SpellSlots)
    spellcasting_ability: AbilityName | None = None
    spell_save_dc: int = 0
    spell_attack_bonus: int = 0

    # Equipment
    equipment: list[Equipment] = Field(default_factory=list)
    copper: int = 0
    silver: int = 0
    electrum: int = 0
    gold: int = 0
    platinum: int = 0

    # Features
    features: list[Feature] = Field(default_factory=list)

    # Personality
    personality_traits: str = ""
    ideals: str = ""
    bonds: str = ""
    flaws: str = ""

    # Other
    age: str = ""
    height: str = ""
    weight: str = ""
    eyes: str = ""
    skin: str = ""
    hair: str = ""
    backstory: str = ""
    allies_and_organizations: str = ""
    treasure: str = ""

    # Conversion metadata
    source_character: str | None = None  # Original BG3 character name
    conversion_warnings: list[ConversionWarning] = Field(default_factory=list)

    @property
    def total_level(self) -> int:
        """Calculate total character level."""
        return sum(c.level for c in self.classes)

    @property
    def primary_class(self) -> str:
        """Get the primary (highest level) class name."""
        if not self.classes:
            return "Unknown"
        return max(self.classes, key=lambda c: c.level).name
