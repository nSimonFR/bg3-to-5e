"""Parser for the LSMF (NewAge) ECS binary blob in BG3 save files.

The NewAge blob is embedded as a ScratchBuffer attribute within the "NewAge"
node of Globals.lsf. It contains the Entity Component System (ECS) data with
all character stats, HP, levels, etc.

Format reverse-engineered from:
- LSLib: https://github.com/Norbyte/lslib
- bg3se: https://github.com/Norbyte/bg3se
- LennardF1989's ImHex patterns
"""

import struct
from dataclasses import dataclass, field

from ..data import load_game_data as _load_game_data

# LSMF header is 48 bytes; all component offsets are relative to this base
_BASE_OFFSET = 48

# BG3 AbilityId enum: None=0, STR=1, DEX=2, CON=3, INT=4, WIS=5, CHA=6
_ABILITY_NAMES = _load_game_data()["extractor"]["ability_names"]

# BG3 SkillId enum (BG3 order, not alphabetical)
_SKILL_NAMES = _load_game_data()["extractor"]["skill_names"]

# Component names we care about
_STATS_COMPONENT = "game.stats.v3.StatsComponent"
_HEALTH_COMPONENT = "game.stats.v0.HealthComponent"
_LEVEL_COMPONENT = "game.stats.v0.LevelComponent"
_EXPERIENCE_COMPONENT = "game.experience.v0.ExperienceComponent"
_SPELLBOOK_PREPARES = "game.spell.v0.SpellBookPrepares"
_SPELLID_COMPONENT = "game.spell.v0.SpellId"
_BACKGROUND_COMPONENT = "game.character_creation.v0.BackgroundComponent"
_CORE_LEVEL = "core.v0.Level"
_ENTITY_ID = "core.v0.EntityId"

# New component names for extended extraction
_GOD_COMPONENT = "game.god.v0.GodComponent"
_ACTION_RESOURCES_COMPONENT = "game.action_resources.v1.Component"
_PROGRESSION_LEVELUP = "game.progression.v3.LevelUpComponent"
_CC_LEVELUP = "game.character_creation.v3.LevelUpComponent"
_CC_LEVELUP_DATA = "game.character_creation.v3.LevelUpComponentData"
_CC_LEVELUP_SELECTORS = "game.character_creation.v2.LevelUpComponentSelectors"
_CC_SKILL_SELECTOR = "game.character_creation.v2.SkillSelector"
_CC_SKILL_ADD_SLOT = "game.character_creation.v1.SkillAddSlot"
_CC_SKILL_EXPERTISE = "game.character_creation.v2.SkillExpertiseSelector"
_CC_ESKILL = "game.character_creation.v1.ESkill"
_DISPLAY_NAME_TS = "game.display_names.v0.DisplayNameTS"
_INV_WIELDED = "game.inventory.v0.WieldedComponent"
_INV_WIELDING = "game.inventory.v0.WieldingComponent"
_INV_CONTAINER = "game.inventory.v1.ContainerComponent"
_INV_MEMBER = "game.inventory.v0.MemberComponent"
_INV_MEMBER_DATA = "game.inventory.v0.MemberData"
_TOGGLED_PASSIVES = "game.passives.v0.ToggledPassivesComponent"
_SCRIPT_PASSIVES = "game.passives.v0.ScriptPassivesComponent"
_TEMPLATE_COMPONENT = "game.templates.v0.TemplateComponent"
_INV_STACK = "game.inventory.v0.NewStackComponent"
_INV_STACK_DATA = "game.inventory.v0.Stack"
_INV_STACK_ENTRY = "game.inventory.v0.StackEntry"
_OWNEE_CURRENT = "game.v0.OwneeCurrentComponent"
_CC_STATS_COMPONENT = "game.character_creation.v1.CharacterCreationStatsComponent"
_IS_CUSTOM_COMPONENT = "game.character_creation.v0.IsCustomComponent"
_GOLD_TEMPLATE_UUID = _load_game_data()["uuids"]["templates"]["gold"]


@dataclass
class LevelUpEntry:
    """A single level-up record from progression data."""
    class_uuid: str
    subclass_uuid: str | None = None


@dataclass
class ActionResource:
    """An action resource (bardic inspiration, ki, rage, etc.)."""
    uuid: str
    current: float = 0.0
    max_value: float = 0.0
    level: int = 0  # Resource sub-level (e.g., spell slot level)


@dataclass
class NewAgeCharacterStats:
    """Extracted character stats from the LSMF blob."""
    entity_uuid: str
    name: str | None = None
    is_custom: bool = False
    abilities: dict[str, int] = field(default_factory=dict)
    hp: int = 0
    max_hp: int = 0
    temp_hp: int = 0
    max_temp_hp: int = 0
    level: int = 0
    proficiency_bonus: int = 2
    xp_total: int = 0
    spells: list[str] = field(default_factory=list)
    background: str | None = None
    # New fields
    deity: str | None = None
    level_ups: list[LevelUpEntry] = field(default_factory=list)
    action_resources: list[ActionResource] = field(default_factory=list)
    skill_proficiencies: dict[str, int] = field(default_factory=dict)
    passives: list[str] = field(default_factory=list)
    inventory: list[dict] = field(default_factory=list)
    gold: int = 0


@dataclass
class _ComponentInfo:
    """Parsed component table entry."""
    name: str
    index: int
    elem_size: int
    elem_count: int
    data_offset: int  # Absolute offset within LSMF blob


class NewAgeParser:
    """Parser for LSMF (NewAge) ECS binary blob."""

    MAGIC = b"LSMF"

    def __init__(self, data: bytes):
        if data[:4] != self.MAGIC:
            raise ValueError(f"Invalid LSMF magic: {data[:4]!r}")
        self._data = data
        self._components: dict[str, _ComponentInfo] = {}
        self._entity_guids: list[str] = []
        self._owner_lists: list[tuple[int, int, int]] = []  # (start, end, comp_idx)

    def parse(self) -> list[NewAgeCharacterStats]:
        """Parse LSMF blob and return stats for party members."""
        self._parse_header()
        self._parse_entity_index()

        party_entities = self._find_party_entities()
        if not party_entities:
            return []

        return self._extract_party_stats(party_entities)

    def _parse_header(self) -> None:
        """Parse LSMF header and component table."""
        d = self._data

        # Header: 48 bytes
        # magic(4) + version(4) + hash(8) + info_offset(8) + index_size(8)
        # + name_size(4) + component_count(2) + unknown1(2) + unknown2(8)
        info_offset = struct.unpack_from("<Q", d, 16)[0]
        name_size = struct.unpack_from("<I", d, 32)[0]
        component_count = struct.unpack_from("<H", d, 36)[0]

        name_table_abs = info_offset + _BASE_OFFSET
        comp_table_abs = info_offset + name_size + _BASE_OFFSET

        # Parse component entries (48 bytes each)
        for i in range(component_count):
            off = comp_table_abs + i * 48
            name_off = struct.unpack_from("<Q", d, off)[0]
            name_sz = struct.unpack_from("<I", d, off + 8)[0]
            elem_size = struct.unpack_from("<I", d, off + 24)[0]
            elem_count = struct.unpack_from("<Q", d, off + 32)[0]
            comp_offset = struct.unpack_from("<Q", d, off + 40)[0]

            name_abs = name_table_abs + name_off
            name = d[name_abs:name_abs + name_sz].decode("utf-8", errors="replace").rstrip("\x00")

            self._components[name] = _ComponentInfo(
                name=name,
                index=i,
                elem_size=elem_size,
                elem_count=elem_count,
                data_offset=comp_offset + _BASE_OFFSET,
            )

    def _parse_entity_index(self) -> None:
        """Parse entity GUID table and OwnerLists from core.v0.Level."""
        level_comp = self._components.get(_CORE_LEVEL)
        if not level_comp:
            return

        d = self._data
        off = level_comp.data_offset

        # core.v0.Level data (32 bytes):
        # entity_start(8) + entity_end(8) + owners_start(8) + owners_end(8)
        entity_start = struct.unpack_from("<Q", d, off)[0]
        entity_end = struct.unpack_from("<Q", d, off + 8)[0]
        owners_start = struct.unpack_from("<Q", d, off + 16)[0]
        owners_end = struct.unpack_from("<Q", d, off + 24)[0]

        # Parse entity GUIDs (16 bytes each)
        entity_abs = entity_start + _BASE_OFFSET
        entity_count = (entity_end - entity_start) // 16

        self._entity_guids = []
        for i in range(entity_count):
            guid_off = entity_abs + i * 16
            uuid_bytes = d[guid_off:guid_off + 16]
            self._entity_guids.append(self._format_uuid(uuid_bytes))

        # Parse OwnerLists (32 bytes each)
        owners_abs = owners_start + _BASE_OFFSET
        owner_list_count = (owners_end - owners_start) // 32

        self._owner_lists = []
        for i in range(owner_list_count):
            ol_off = owners_abs + i * 32
            ol_start = struct.unpack_from("<Q", d, ol_off)[0]
            ol_end = struct.unpack_from("<Q", d, ol_off + 8)[0]
            comp_idx = struct.unpack_from("<Q", d, ol_off + 16)[0]
            self._owner_lists.append((ol_start, ol_end, comp_idx))

    def _get_owner_indices(self, comp_name: str) -> list[int] | None:
        """Get owner indices (entity GUID table indices) for a component's elements."""
        comp = self._components.get(comp_name)
        if not comp:
            return None

        # Find the OwnerList entry for this component
        for ol_start, ol_end, comp_idx in self._owner_lists:
            if comp_idx == comp.index:
                if ol_start == 0xFFFFFFFFFFFFFFFF:
                    return None
                abs_start = ol_start + _BASE_OFFSET
                count = (ol_end - ol_start) // 4
                indices = []
                for i in range(count):
                    idx = struct.unpack_from("<I", self._data, abs_start + i * 4)[0]
                    indices.append(idx)
                return indices

        return None

    def _build_entity_to_elem_map(self, comp_name: str) -> dict[int, int]:
        """Build reverse mapping: entity_guid_idx -> elem_idx for a component."""
        indices = self._get_owner_indices(comp_name)
        if not indices:
            return {}
        return {entity_idx: elem_idx for elem_idx, entity_idx in enumerate(indices)}

    def _build_entity_to_elems_map(self, comp_name: str) -> dict[int, list[int]]:
        """Build mapping: entity_guid_idx -> list[elem_idx] for many-to-one components."""
        indices = self._get_owner_indices(comp_name)
        if not indices:
            return {}
        result: dict[int, list[int]] = {}
        for elem_idx, entity_idx in enumerate(indices):
            result.setdefault(entity_idx, []).append(elem_idx)
        return result

    def _find_party_entities(self) -> list[int]:
        """Find entity GUID indices for party members using ExperienceComponent."""
        exp_indices = self._get_owner_indices(_EXPERIENCE_COMPONENT)
        if exp_indices:
            return exp_indices

        # Fallback: if no ExperienceComponent, try to find party members
        # by looking for entities that have both StatsComponent and LevelComponent
        # with level > 0
        stats_indices = self._get_owner_indices(_STATS_COMPONENT)
        level_indices = self._get_owner_indices(_LEVEL_COMPONENT)
        if not stats_indices or not level_indices:
            return []

        stats_entities = set(stats_indices)
        level_comp = self._components.get(_LEVEL_COMPONENT)
        if not level_comp:
            return []

        # Find entities with level > 0 that also have stats
        result = []
        for elem_idx, entity_idx in enumerate(level_indices):
            if entity_idx in stats_entities:
                level = self._read_level(elem_idx)
                if level > 0:
                    result.append(entity_idx)

        return result[:20]  # Limit to prevent returning all NPCs

    def _extract_party_stats(self, party_entity_indices: list[int]) -> list[NewAgeCharacterStats]:
        """Extract stats for party member entities."""
        stats_map = self._build_entity_to_elem_map(_STATS_COMPONENT)
        health_map = self._build_entity_to_elem_map(_HEALTH_COMPONENT)
        level_map = self._build_entity_to_elem_map(_LEVEL_COMPONENT)
        exp_map = self._build_entity_to_elem_map(_EXPERIENCE_COMPONENT)
        spellbook_map = self._build_entity_to_elem_map(_SPELLBOOK_PREPARES)
        background_map = self._build_entity_to_elem_map(_BACKGROUND_COMPONENT)
        god_map = self._build_entity_to_elem_map(_GOD_COMPONENT)
        action_res_map = self._build_entity_to_elem_map(_ACTION_RESOURCES_COMPONENT)
        progression_map = self._build_entity_to_elem_map(_PROGRESSION_LEVELUP)
        cc_levelup_map = self._build_entity_to_elem_map(_CC_LEVELUP)
        toggled_map = self._build_entity_to_elem_map(_TOGGLED_PASSIVES)
        script_passives_map = self._build_entity_to_elem_map(_SCRIPT_PASSIVES)
        wielding_map = self._build_entity_to_elem_map(_INV_WIELDING)
        member_map = self._build_entity_to_elems_map(_INV_MEMBER)
        cc_stats_map = self._build_entity_to_elem_map(_CC_STATS_COMPONENT)
        custom_entities = set(self._get_owner_indices(_IS_CUSTOM_COMPONENT) or [])

        # Gold per party member (computed once for all)
        party_gold = self._read_gold_for_party(party_entity_indices)

        results = []
        for entity_idx in party_entity_indices:
            if entity_idx >= len(self._entity_guids):
                continue

            stats = NewAgeCharacterStats(
                entity_uuid=self._entity_guids[entity_idx],
                gold=party_gold.get(entity_idx, 0),
                is_custom=entity_idx in custom_entities,
            )

            # Character name from CharacterCreationStatsComponent
            if entity_idx in cc_stats_map:
                stats.name = self._read_cc_name(cc_stats_map[entity_idx])

            # Abilities from StatsComponent
            if entity_idx in stats_map:
                self._read_stats(stats, stats_map[entity_idx])

            # HP from HealthComponent
            if entity_idx in health_map:
                self._read_health(stats, health_map[entity_idx])

            # Level from LevelComponent
            if entity_idx in level_map:
                stats.level = self._read_level(level_map[entity_idx])

            # XP from ExperienceComponent
            if entity_idx in exp_map:
                self._read_experience(stats, exp_map[entity_idx])

            # Spells from SpellBookPrepares → SpellId
            if entity_idx in spellbook_map:
                stats.spells = self._read_spells(spellbook_map[entity_idx])

            # Background from BackgroundComponent
            if entity_idx in background_map:
                stats.background = self._read_background(background_map[entity_idx])

            # Deity from GodComponent
            if entity_idx in god_map:
                stats.deity = self._read_deity(god_map[entity_idx])

            # Action resources
            if entity_idx in action_res_map:
                stats.action_resources = self._read_action_resources(
                    action_res_map[entity_idx]
                )

            # Level-up progression (exact multiclass splits)
            if entity_idx in progression_map:
                stats.level_ups = self._read_progression(
                    progression_map[entity_idx]
                )

            # Skills from character creation hierarchy
            if entity_idx in cc_levelup_map:
                stats.skill_proficiencies = self._read_skills_from_cc(
                    cc_levelup_map[entity_idx]
                )

            # Passives from ToggledPassives + ScriptPassives
            passives: list[str] = []
            if entity_idx in toggled_map:
                passives.extend(self._read_toggled_passives(
                    toggled_map[entity_idx]
                ))
            if entity_idx in script_passives_map:
                passives.extend(self._read_script_passives(
                    script_passives_map[entity_idx]
                ))
            if passives:
                stats.passives = passives

            # Equipment from inventory components
            inv = self._read_inventory(entity_idx, wielding_map, member_map)
            if inv:
                stats.inventory = inv

            results.append(stats)

        return results

    def _read_stats(self, stats: NewAgeCharacterStats, elem_idx: int) -> None:
        """Read ability scores from StatsComponent element.

        StatsComponent layout (36 bytes per element):
        - Bytes 0-3: Header/handle (4 bytes)
        - Bytes 4-31: Abilities[7] as int32 array (28 bytes)
          Index 0=None, 1=STR, 2=DEX, 3=CON, 4=INT, 5=WIS, 6=CHA
        - Bytes 32-35: ProficiencyBonus (4 bytes)
        """
        comp = self._components.get(_STATS_COMPONENT)
        if not comp or elem_idx >= comp.elem_count:
            return

        off = comp.data_offset + elem_idx * comp.elem_size

        # Read abilities (7 int32s starting at offset 4)
        abilities = struct.unpack_from("<7i", self._data, off + 4)
        for i in range(1, 7):  # Skip index 0 (None)
            stats.abilities[_ABILITY_NAMES[i]] = abilities[i]

        # Read proficiency bonus (int32 at offset 32)
        stats.proficiency_bonus = struct.unpack_from("<i", self._data, off + 32)[0]

    def _read_health(self, stats: NewAgeCharacterStats, elem_idx: int) -> None:
        """Read HP from HealthComponent element.

        HealthComponent layout (32 bytes per element):
        - Bytes 0-3: HP (int32)
        - Bytes 4-7: MaxHP (int32)
        - Bytes 8-11: TempHP (int32)
        - Bytes 12-15: MaxTempHP (int32)
        - Bytes 16-31: Additional data (GUID, flags)
        """
        comp = self._components.get(_HEALTH_COMPONENT)
        if not comp or elem_idx >= comp.elem_count:
            return

        off = comp.data_offset + elem_idx * comp.elem_size
        hp, max_hp, temp_hp, max_temp_hp = struct.unpack_from("<4i", self._data, off)
        stats.hp = hp
        stats.max_hp = max_hp
        stats.temp_hp = temp_hp
        stats.max_temp_hp = max_temp_hp

    def _read_level(self, elem_idx: int) -> int:
        """Read level from LevelComponent element (4 bytes = int32)."""
        comp = self._components.get(_LEVEL_COMPONENT)
        if not comp or elem_idx >= comp.elem_count:
            return 0

        off = comp.data_offset + elem_idx * comp.elem_size
        return struct.unpack_from("<i", self._data, off)[0]

    def _read_experience(self, stats: NewAgeCharacterStats, elem_idx: int) -> None:
        """Read XP from ExperienceComponent element.

        ExperienceComponent layout (12 bytes per element):
        - Bytes 0-3: TotalXP (int32)
        - Bytes 4-7: TotalXP duplicate (int32)
        - Bytes 8-11: Unknown (int32)
        """
        comp = self._components.get(_EXPERIENCE_COMPONENT)
        if not comp or elem_idx >= comp.elem_count:
            return

        off = comp.data_offset + elem_idx * comp.elem_size
        stats.xp_total = struct.unpack_from("<I", self._data, off)[0]

    def _read_cc_name(self, elem_idx: int) -> str | None:
        """Read character name from CharacterCreationStatsComponent.

        Layout (88 bytes per element):
        - Bytes 0-31:  Two UUIDs (race, subrace)
        - Bytes 32-55: Various fields
        - Bytes 56-63: Name pointer (u64 raw offset into aux pool)
        - Bytes 64-67: Name length (u32)
        - Bytes 68-87: Remaining fields
        """
        comp = self._components.get(_CC_STATS_COMPONENT)
        if not comp or elem_idx >= comp.elem_count:
            return None

        d = self._data
        off = comp.data_offset + elem_idx * comp.elem_size

        name_ptr = struct.unpack_from("<Q", d, off + 56)[0]
        name_len = struct.unpack_from("<I", d, off + 64)[0]

        if name_len == 0 or name_len > 50 or name_ptr == 0xFFFFFFFFFFFFFFFF:
            return None

        name_abs = name_ptr + _BASE_OFFSET
        if name_abs + name_len > len(d):
            return None

        raw = d[name_abs:name_abs + name_len]
        try:
            name = raw.decode("utf-8", errors="replace").rstrip("\x00")
            if name and len(name) >= 1:
                return name
        except (UnicodeDecodeError, ValueError):
            pass

        return None

    def _read_spells(self, elem_idx: int) -> list[str]:
        """Read spell names from SpellBookPrepares → SpellId.

        SpellBookPrepares element: two u64 offsets (start, end) into the SpellId array.
        SpellId entry (24 bytes): string_offset(u64) + string_length(u32) + hash(u32) + ref(u64)
        The string_offset points into the SpellId component's data block.
        """
        prepares_comp = self._components.get(_SPELLBOOK_PREPARES)
        spellid_comp = self._components.get(_SPELLID_COMPONENT)
        if not prepares_comp or not spellid_comp or elem_idx >= prepares_comp.elem_count:
            return []

        d = self._data
        off = prepares_comp.data_offset + elem_idx * prepares_comp.elem_size

        # Read offset range into SpellId array
        spell_start = struct.unpack_from("<Q", d, off)[0]
        spell_end = struct.unpack_from("<Q", d, off + 8)[0]

        if spell_start == 0xFFFFFFFFFFFFFFFF or spell_end <= spell_start:
            return []

        # SpellId entries start at spellid_comp.data_offset
        # spell_start/spell_end are byte offsets relative to component data start
        spellid_base = spellid_comp.data_offset
        entry_size = spellid_comp.elem_size if spellid_comp.elem_size > 0 else 24

        spells = []
        pos = spell_start + _BASE_OFFSET
        end = spell_end + _BASE_OFFSET

        while pos + entry_size <= end:
            try:
                str_off = struct.unpack_from("<Q", d, pos)[0]
                str_len = struct.unpack_from("<I", d, pos + 8)[0]

                if str_off != 0xFFFFFFFFFFFFFFFF and str_len > 0 and str_len < 256:
                    str_abs = str_off + _BASE_OFFSET
                    if str_abs + str_len <= len(d):
                        name = d[str_abs:str_abs + str_len].decode("utf-8", errors="replace").rstrip("\x00")
                        if name and len(name) > 1:
                            spells.append(name)
            except (struct.error, IndexError):
                break
            pos += entry_size

        return spells

    def _read_background(self, elem_idx: int) -> str | None:
        """Read background UUID from BackgroundComponent element (16 bytes = UUID)."""
        comp = self._components.get(_BACKGROUND_COMPONENT)
        if not comp or elem_idx >= comp.elem_count:
            return None

        off = comp.data_offset + elem_idx * comp.elem_size
        uuid_bytes = self._data[off:off + 16]
        return self._format_uuid(uuid_bytes)

    def _read_deity(self, elem_idx: int) -> str | None:
        """Read deity UUID from GodComponent element.

        GodComponent layout (40 bytes per element):
        - Bytes 0-15: Deity UUID (16 bytes)
        - Bytes 16-39: Additional data (position, flags)
        """
        comp = self._components.get(_GOD_COMPONENT)
        if not comp or elem_idx >= comp.elem_count:
            return None

        off = comp.data_offset + elem_idx * comp.elem_size
        uuid_bytes = self._data[off:off + 16]
        uuid_str = self._format_uuid(uuid_bytes)

        # Skip null UUIDs (no deity set)
        if uuid_str == "00000000-0000-0000-0000-000000000000":
            return None

        return uuid_str

    def _read_action_resources(self, elem_idx: int) -> list[ActionResource]:
        """Read action resources from action_resources.v1.Component.

        The component element (16 bytes) is a range pointer [start, end] into
        a flat array of 64-byte action resource entries:
        - Bytes 0-15:  Resource UUID
        - Bytes 16-23: Minimum value (f64, typically 0.0)
        - Bytes 24-31: Current value (f64)
        - Bytes 32-39: Max value (f64)
        - Bytes 40-43: Sub-level (u32, e.g., spell slot level)
        - Bytes 44-47: Padding
        - Bytes 48-63: Sentinel (0xFFFFFFFF...)
        """
        comp = self._components.get(_ACTION_RESOURCES_COMPONENT)
        if not comp or elem_idx >= comp.elem_count:
            return []

        d = self._data
        off = comp.data_offset + elem_idx * comp.elem_size
        start_off, end_off = struct.unpack_from("<QQ", d, off)

        if start_off == 0xFFFFFFFFFFFFFFFF or end_off <= start_off:
            return []

        entry_size = 64
        resources = []
        pos = start_off + _BASE_OFFSET
        end = end_off + _BASE_OFFSET

        while pos + entry_size <= end:
            try:
                uuid_bytes = d[pos:pos + 16]
                uuid_str = self._format_uuid(uuid_bytes)

                # Skip null UUIDs
                if uuid_str == "00000000-0000-0000-0000-000000000000":
                    pos += entry_size
                    continue

                current = struct.unpack_from("<d", d, pos + 24)[0]
                max_val = struct.unpack_from("<d", d, pos + 32)[0]
                level = struct.unpack_from("<I", d, pos + 40)[0]

                resources.append(ActionResource(
                    uuid=uuid_str,
                    current=current,
                    max_value=max_val,
                    level=level,
                ))
            except (struct.error, IndexError):
                break
            pos += entry_size

        return resources

    def _read_progression(self, elem_idx: int) -> list[LevelUpEntry]:
        """Read level-up progression from progression.v3.LevelUpComponent.

        The component element (16 bytes) is a range pointer [start, end] into
        an array of u64 offsets, each pointing to a 96-byte progression record:
        - Bytes 0-15:  Class UUID
        - Bytes 16-31: Subclass UUID (zero if not chosen at this level)
        - Bytes 32-95: Additional data (race, selectors, etc.)
        """
        comp = self._components.get(_PROGRESSION_LEVELUP)
        if not comp or elem_idx >= comp.elem_count:
            return []

        d = self._data
        off = comp.data_offset + elem_idx * comp.elem_size
        start_off, end_off = struct.unpack_from("<QQ", d, off)

        if start_off == 0xFFFFFFFFFFFFFFFF or end_off <= start_off:
            return []

        entries = []
        pos = start_off + _BASE_OFFSET
        end = end_off + _BASE_OFFSET

        while pos + 8 <= end:
            try:
                # Each entry is a u64 offset pointing to a 96-byte record
                record_off = struct.unpack_from("<Q", d, pos)[0]
                abs_off = record_off + _BASE_OFFSET

                if abs_off + 32 > len(d):
                    break

                class_uuid = self._format_uuid(d[abs_off:abs_off + 16])
                sub_uuid = self._format_uuid(d[abs_off + 16:abs_off + 32])

                # Skip null class UUIDs
                if class_uuid == "00000000-0000-0000-0000-000000000000":
                    pos += 8
                    continue

                sub = sub_uuid if sub_uuid != "00000000-0000-0000-0000-000000000000" else None
                entries.append(LevelUpEntry(class_uuid=class_uuid, subclass_uuid=sub))
            except (struct.error, IndexError):
                break
            pos += 8

        return entries

    def _read_skills_from_cc(self, elem_idx: int) -> dict[str, int]:
        """Read skill proficiencies from character creation level-up hierarchy.

        Chain: CC LevelUpComponent → LevelUpComponentData →
        LevelUpComponentSelectors → SkillSelector → SkillAddSlot → ESkill

        The LevelUpComponentSelectors entry has 7 range pairs (each 16 bytes):
        - Pair[2] (offsets 32,40): SkillSelector entries (proficiencies)
        - Pair[3] (offsets 48,56): SkillExpertiseSelector entries (expertise)

        Each range pair holds raw offsets into an auxiliary pool of u64
        pointers. Each pointer (+ _BASE_OFFSET) resolves to a typed selector
        entry. The typed selector's offsets 24-32 are a range into
        SkillAddSlot, and each SkillAddSlot entry points to an ESkill value.
        """
        cc_lu = self._components.get(_CC_LEVELUP)
        lu_data_comp = self._components.get(_CC_LEVELUP_DATA)
        lu_sel_comp = self._components.get(_CC_LEVELUP_SELECTORS)
        ss_comp = self._components.get(_CC_SKILL_SELECTOR)
        sas_comp = self._components.get(_CC_SKILL_ADD_SLOT)
        eskill_comp = self._components.get(_CC_ESKILL)
        se_comp = self._components.get(_CC_SKILL_EXPERTISE)

        if not all([cc_lu, lu_data_comp, lu_sel_comp, ss_comp, sas_comp, eskill_comp]):
            return {}

        if elem_idx >= cc_lu.elem_count:
            return {}

        d = self._data
        skills: dict[str, int] = {}

        # Step 1: Read CC LevelUpComponent range → pointers to LUData records
        off = cc_lu.data_offset + elem_idx * cc_lu.elem_size
        start_raw, end_raw = struct.unpack_from("<QQ", d, off)

        if start_raw == 0xFFFFFFFFFFFFFFFF or end_raw <= start_raw:
            return {}

        n_pointers = (end_raw - start_raw) // 8

        for ptr_idx in range(n_pointers):
            # Read u64 pointer from auxiliary pool → LevelUpComponentData record
            ptr_abs = start_raw + _BASE_OFFSET + ptr_idx * 8
            if ptr_abs + 8 > len(d):
                break
            lu_data_raw = struct.unpack_from("<Q", d, ptr_abs)[0]
            lu_data_abs = lu_data_raw + _BASE_OFFSET

            # Step 2: Get LevelUpComponentSelectors pointer (offset 72 in LUData)
            if lu_data_abs + 80 > len(d):
                continue
            sel_raw = struct.unpack_from("<Q", d, lu_data_abs + 72)[0]
            sel_abs = sel_raw + _BASE_OFFSET
            sel_idx = (sel_abs - lu_sel_comp.data_offset) // lu_sel_comp.elem_size

            if sel_idx < 0 or sel_idx >= lu_sel_comp.elem_count:
                continue

            sel_off = lu_sel_comp.data_offset + sel_idx * lu_sel_comp.elem_size

            # Step 3: Read skill proficiencies from pair[2] (offsets 32, 40)
            self._read_skills_from_selector_pair(
                sel_off + 32, ss_comp, sas_comp, eskill_comp, skills, 1
            )

            # Step 4: Read skill expertise from pair[3] (offsets 48, 56)
            if se_comp:
                self._read_skills_from_selector_pair(
                    sel_off + 48, se_comp, sas_comp, eskill_comp, skills, 2
                )

        return skills

    def _read_skills_from_selector_pair(
        self,
        pair_offset: int,
        typed_comp: _ComponentInfo,
        sas_comp: _ComponentInfo,
        eskill_comp: _ComponentInfo,
        skills: dict[str, int],
        proficiency_level: int,
    ) -> None:
        """Read skills from one Selectors range pair → typed selector → ESkill."""
        d = self._data
        p_start = struct.unpack_from("<Q", d, pair_offset)[0]
        p_end = struct.unpack_from("<Q", d, pair_offset + 8)[0]

        if p_start == 0xFFFFFFFFFFFFFFFF or p_end <= p_start:
            return

        typed_end = typed_comp.data_offset + typed_comp.elem_count * typed_comp.elem_size

        n_entries = (p_end - p_start) // 8
        for i in range(n_entries):
            entry_abs = p_start + _BASE_OFFSET + i * 8
            if entry_abs + 8 > len(d):
                break
            sel_raw = struct.unpack_from("<Q", d, entry_abs)[0]
            sel_abs = sel_raw + _BASE_OFFSET

            # Verify address falls within the typed selector component
            if sel_abs < typed_comp.data_offset or sel_abs >= typed_end:
                continue

            # Read SkillAddSlot range from typed selector (offsets 24, 32)
            if sel_abs + 40 > len(d):
                continue
            sas_start = struct.unpack_from("<Q", d, sel_abs + 24)[0]
            sas_end = struct.unpack_from("<Q", d, sel_abs + 32)[0]

            if sas_start == 0xFFFFFFFFFFFFFFFF or sas_end <= sas_start:
                continue

            n_skills = (sas_end - sas_start) // sas_comp.elem_size
            for si in range(n_skills):
                sas_off = sas_start + _BASE_OFFSET + si * sas_comp.elem_size
                if sas_off + 4 > len(d):
                    break
                es_raw = struct.unpack_from("<I", d, sas_off)[0]
                es_abs = es_raw + _BASE_OFFSET
                es_idx = (es_abs - eskill_comp.data_offset) // eskill_comp.elem_size

                if 0 <= es_idx < eskill_comp.elem_count:
                    skill_val = struct.unpack_from("<I", d, eskill_comp.data_offset + es_idx * eskill_comp.elem_size)[0]
                    if skill_val < len(_SKILL_NAMES):
                        skill_name = _SKILL_NAMES[skill_val]
                        skills[skill_name] = max(skills.get(skill_name, 0), proficiency_level)

    def _read_string_range(self, start_raw: int, end_raw: int) -> list[str]:
        """Read a list of string refs from an aux pool range.

        Each entry is 16 bytes: str_offset(u64) + str_len(u32) + padding(u32).
        str_offset is a raw offset; absolute address = str_offset + _BASE_OFFSET.
        """
        if start_raw == 0xFFFFFFFFFFFFFFFF or end_raw <= start_raw:
            return []
        d = self._data
        results: list[str] = []
        pos = start_raw + _BASE_OFFSET
        end = end_raw + _BASE_OFFSET
        while pos + 16 <= end:
            str_raw = struct.unpack_from("<Q", d, pos)[0]
            str_len = struct.unpack_from("<I", d, pos + 8)[0]
            if 0 < str_len < 256:
                str_abs = str_raw + _BASE_OFFSET
                if str_abs + str_len <= len(d):
                    try:
                        s = d[str_abs:str_abs + str_len].decode("utf-8").rstrip("\x00")
                        if s:
                            results.append(s)
                    except UnicodeDecodeError:
                        pass
            pos += 16
        return results

    def _read_toggled_passives(self, elem_idx: int) -> list[str]:
        """Read enabled passive names from ToggledPassivesComponent.

        Layout (32 bytes per element):
          Bytes 0-15:  "on" range [start(u64), end(u64)] → 16-byte string entries
          Bytes 16-31: "off" flags range (bool bytes, one per passive)

        Returns names of passives that are toggled ON and not marked OFF.
        """
        comp = self._components.get(_TOGGLED_PASSIVES)
        if not comp or elem_idx >= comp.elem_count:
            return []
        d = self._data
        off = comp.data_offset + elem_idx * comp.elem_size
        on_start, on_end, off_start, off_end = struct.unpack_from("<QQQQ", d, off)

        passives = self._read_string_range(on_start, on_end)

        # Filter out any passives flagged as currently OFF
        if off_start != 0xFFFFFFFFFFFFFFFF and off_end > off_start:
            off_flags_abs = off_start + _BASE_OFFSET
            result: list[str] = []
            for i, name in enumerate(passives):
                flag_abs = off_flags_abs + i
                if flag_abs < len(d) and d[flag_abs] == 0:
                    result.append(name)
            return result

        return passives

    def _read_script_passives(self, elem_idx: int) -> list[str]:
        """Read passive names from ScriptPassivesComponent.

        Layout (16 bytes per element):
          Bytes 0-7:  range start (u64) → aux pool of 16-byte string entries
          Bytes 8-15: range end (u64)
        """
        comp = self._components.get(_SCRIPT_PASSIVES)
        if not comp or elem_idx >= comp.elem_count:
            return []
        off = comp.data_offset + elem_idx * comp.elem_size
        start_raw, end_raw = struct.unpack_from("<QQ", self._data, off)
        return self._read_string_range(start_raw, end_raw)

    def _read_gold_for_party(
        self,
        party_entity_indices: list[int],
    ) -> dict[int, int]:
        """Read gold amounts owned by party members.

        Returns {entity_idx: gold_amount} for party members who have gold.

        Chain: TemplateComponent (find gold entities) → NewStackComponent →
               Stack → StackEntry (amount) + OwneeCurrentComponent (ownership).
        """
        d = self._data
        template_comp = self._components.get(_TEMPLATE_COMPONENT)
        stack_comp = self._components.get(_INV_STACK)
        stack_data = self._components.get(_INV_STACK_DATA)
        stack_entry = self._components.get(_INV_STACK_ENTRY)
        ownee_comp = self._components.get(_OWNEE_CURRENT)

        if not all([template_comp, stack_comp, stack_data, stack_entry, ownee_comp]):
            return {}

        # Build entity→template UUID map (only check for gold template)
        template_owners = self._get_owner_indices(_TEMPLATE_COMPONENT)
        gold_entities: set[int] = set()
        for i in range(template_comp.elem_count):
            off = template_comp.data_offset + i * template_comp.elem_size
            # TemplateComponent: str_offset(u64), str_len(u64), type_ptr(u64)
            str_raw = struct.unpack_from("<Q", d, off)[0]
            str_len_raw = struct.unpack_from("<Q", d, off + 8)[0]
            str_len = str_len_raw & 0xFFFFFFFF  # Lower 32 bits
            if str_len == 36:  # UUID string length
                str_abs = str_raw + _BASE_OFFSET
                if str_abs + 36 <= len(d):
                    try:
                        tmpl_uuid = d[str_abs:str_abs + 36].decode("ascii")
                        if tmpl_uuid == _GOLD_TEMPLATE_UUID:
                            entity_idx = template_owners[i] if template_owners and i < len(template_owners) else -1
                            if entity_idx >= 0:
                                gold_entities.add(entity_idx)
                    except (UnicodeDecodeError, ValueError):
                        pass

        if not gold_entities:
            return {}

        # Build entity→stack amount map for gold entities
        stack_owners = self._get_owner_indices(_INV_STACK)
        entity_gold: dict[int, int] = {}
        for i in range(stack_comp.elem_count):
            entity_idx = stack_owners[i] if stack_owners and i < len(stack_owners) else -1
            if entity_idx not in gold_entities:
                continue
            off = stack_comp.data_offset + i * stack_comp.elem_size
            stack_ptr = struct.unpack_from("<Q", d, off)[0]
            stack_abs = stack_ptr + _BASE_OFFSET
            # Stack: ptr0(u64), ptr1(u64), se_begin(u64), se_end(u64)
            if stack_abs + 32 > len(d):
                continue
            se_begin = struct.unpack_from("<Q", d, stack_abs + 16)[0]
            se_end = struct.unpack_from("<Q", d, stack_abs + 24)[0]
            if se_begin == 0xFFFFFFFFFFFFFFFF or se_end <= se_begin:
                continue
            # Read stack entries (8 bytes each: handle(u32) + amount(u32))
            total = 0
            pos = se_begin + _BASE_OFFSET
            end = se_end + _BASE_OFFSET
            while pos + 8 <= end and pos + 8 <= len(d):
                amount = struct.unpack_from("<I", d, pos + 4)[0]
                total += amount
                pos += 8
            entity_gold[entity_idx] = total

        if not entity_gold:
            return {}

        # Resolve ownership: gold entity → parent entity (via OwneeCurrentComponent)
        ownee_owners = self._get_owner_indices(_OWNEE_CURRENT)
        party_set = set(party_entity_indices)
        party_gold: dict[int, int] = {}

        # Build GUID string → entity_idx lookup from entity index
        guid_str_to_idx: dict[str, int] = {}
        for idx, guid_str in enumerate(self._entity_guids):
            guid_str_to_idx[guid_str] = idx

        # Build entity_idx → parent_entity_idx from OwneeCurrentComponent
        ownee_map: dict[int, int] = {}
        for i in range(ownee_comp.elem_count):
            entity_idx = ownee_owners[i] if ownee_owners and i < len(ownee_owners) else -1
            if entity_idx < 0:
                continue
            off = ownee_comp.data_offset + i * ownee_comp.elem_size
            parent_raw = struct.unpack_from("<Q", d, off)[0]
            parent_abs = parent_raw + _BASE_OFFSET
            if parent_abs + 16 > len(d):
                continue
            parent_guid_str = self._format_uuid(d[parent_abs:parent_abs + 16])
            parent_idx = guid_str_to_idx.get(parent_guid_str, -1)
            if parent_idx >= 0:
                ownee_map[entity_idx] = parent_idx

        # Walk ownership chain for each gold entity to find party owner
        for gold_entity, amount in entity_gold.items():
            current = gold_entity
            visited: set[int] = set()
            while current >= 0 and current not in party_set:
                if current in visited:
                    break
                visited.add(current)
                current = ownee_map.get(current, -1)
            if current in party_set:
                party_gold[current] = party_gold.get(current, 0) + amount

        return party_gold

    def _read_inventory(
        self,
        entity_idx: int,
        wielding_map: dict[int, int],
        member_map: dict[int, list[int]],
    ) -> list[dict]:
        """Read equipped/inventory items for a party entity.

        Not yet fully implemented: requires a template-UUID→item-name lookup
        table that is not embedded in save files. Returns empty list.
        """
        return []

    @staticmethod
    def _format_uuid(uuid_bytes: bytes) -> str:
        """Format 16-byte UUID as string (little-endian fields)."""
        a = struct.unpack_from("<I", uuid_bytes, 0)[0]
        b = struct.unpack_from("<H", uuid_bytes, 4)[0]
        c = struct.unpack_from("<H", uuid_bytes, 6)[0]
        d = uuid_bytes[8:10].hex()
        e = uuid_bytes[10:16].hex()
        return f"{a:08x}-{b:04x}-{c:04x}-{d}-{e}"
