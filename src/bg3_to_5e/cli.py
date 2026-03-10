"""Command-line interface for BG3 to D&D 5e converter."""

from pathlib import Path
from typing import Literal

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .core.character import AbilityName, AbilityScores, BG3Character, CharacterClass, DnD5eCharacter
from .extractors.lsv_parser import LSVParser, SavePartyMember, list_saves
from .extractors.se_import import ScriptExtenderImport
from .mapping.converter import BG3To5eConverter
from .output.dnd5e_json import DnD5eJsonExporter
from .output.foundry_vtt import FoundryVTTExporter
from .output.html_sheet import HTMLSheetExporter
from .output.pdf_sheet import PDFSheetExporter
from .output.roll20 import Roll20Exporter

console = Console()

# Default save directory
DEFAULT_SAVE_DIR = Path.home() / ".local/share/Larian Studios/Baldur's Gate 3/PlayerProfiles/Public/Savegames/Story"


OutputFormat = Literal["json", "html", "pdf", "foundry", "roll20", "all"]


@click.group()
@click.version_option()
def main():
    """BG3 to D&D 5e Character Sheet Converter.

    Convert Baldur's Gate 3 save files to standard D&D 5e character sheets
    in various formats (JSON, HTML, PDF, Foundry VTT, Roll20).
    """
    pass


@main.command("list-saves")
@click.option(
    "-d", "--directory",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Save directory to scan (default: BG3 save location)"
)
@click.option(
    "-l", "--limit",
    type=int,
    default=20,
    help="Maximum number of saves to show"
)
def list_saves_cmd(directory: Path | None, limit: int):
    """List available BG3 save files."""
    save_dir = directory or DEFAULT_SAVE_DIR

    if not save_dir.exists():
        console.print(f"[red]Save directory not found:[/red] {save_dir}")
        console.print("\nUse --directory to specify a custom location.")
        raise SystemExit(1)

    console.print(f"[dim]Scanning:[/dim] {save_dir}\n")

    saves = list_saves(save_dir)

    if not saves:
        console.print("[yellow]No save files found.[/yellow]")
        return

    # Group by character
    by_char: dict[str, list] = {}
    for save in saves:
        char_name = save.character_name or "Unknown"
        if char_name not in by_char:
            by_char[char_name] = []
        by_char[char_name].append(save)

    # Display summary
    table = Table(title=f"BG3 Save Files ({len(saves)} total)")
    table.add_column("Character", style="cyan")
    table.add_column("Saves", justify="right")
    table.add_column("Latest Save", style="dim")

    for char_name, char_saves in sorted(by_char.items()):
        latest = char_saves[-1]
        table.add_row(
            char_name,
            str(len(char_saves)),
            latest.save_name or latest.path.stem,
        )

    console.print(table)

    # Show recent saves
    console.print(f"\n[bold]Recent Saves (showing {min(limit, len(saves))}):[/bold]")

    recent_table = Table()
    recent_table.add_column("#", style="dim", width=4)
    recent_table.add_column("Character", style="cyan")
    recent_table.add_column("Save Name")
    recent_table.add_column("Party", style="dim")
    recent_table.add_column("Path", style="dim", max_width=50)

    for i, save in enumerate(saves[-limit:][::-1], 1):
        # Build party summary
        party_str = ""
        if save.party:
            parts = []
            for m in save.party:
                cls = m.classes[0]["Main"] if m.classes else "?"
                parts.append(f"{'*' if m.is_player else ''}{m.name[:3]} L{m.level} {cls}")
            party_str = ", ".join(parts)

        recent_table.add_row(
            str(i),
            save.character_name or "Unknown",
            save.save_name or save.path.stem,
            party_str or str(len(save.files)) + " files",
            str(save.path.name),
        )

    console.print(recent_table)


@main.command("convert")
@click.argument("save_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "-f", "--format",
    type=click.Choice(["json", "html", "pdf", "foundry", "roll20", "all"]),
    default="all",
    help="Output format(s)"
)
@click.option(
    "-o", "--output",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("./output"),
    help="Output directory"
)
@click.option(
    "--pdf-template",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="PDF template file for filling"
)
@click.option(
    "--show-warnings/--no-warnings",
    default=True,
    help="Show conversion warnings"
)
def convert_cmd(
    save_file: Path,
    format: OutputFormat,
    output: Path,
    pdf_template: Path | None,
    show_warnings: bool,
):
    """Convert a BG3 save file to D&D 5e character sheet(s).

    Extracts class, level, and race data from SaveInfo.json in the save file.
    Ability scores, spells, and equipment require Script Extender for full fidelity.
    """
    console.print(f"[bold]Converting:[/bold] {save_file.name}")

    try:
        with LSVParser(save_file) as parser:
            save_info = parser.get_save_info()
            console.print(f"[dim]Character:[/dim] {save_info.character_name or 'Unknown'}")
            console.print(f"[dim]Files in save:[/dim] {len(save_info.files)}")

            if save_info.party:
                console.print(f"[green]Found {len(save_info.party)} party member(s) in SaveInfo.json[/green]")
            else:
                console.print("[yellow]No SaveInfo.json found - limited extraction.[/yellow]")

            # Try to extract real stats from the NewAge blob
            newage_stats = parser.extract_newage_stats()
            if newage_stats:
                console.print(f"[green]Extracted real stats for {len(newage_stats)} character(s) from save data[/green]")
                _apply_newage_stats(save_info, newage_stats)
            else:
                console.print("[dim]Could not extract stats from save data - using defaults.[/dim]")

            # Extract character data for all party members
            bg3_chars = _extract_characters_from_lsv(save_info)

    except Exception as e:
        console.print(f"[red]Error parsing save file:[/red] {e}")
        raise SystemExit(1)

    converter = BG3To5eConverter()

    for bg3_char in bg3_chars:
        console.print(Panel(f"[bold cyan]{bg3_char.name}[/bold cyan]"))

        dnd5e_char = converter.convert(bg3_char)
        _display_character_summary(dnd5e_char)

        if show_warnings and dnd5e_char.conversion_warnings:
            _display_warnings(dnd5e_char)

        char_output = output / _sanitize_filename(bg3_char.name) if len(bg3_chars) > 1 else output
        _export_character(dnd5e_char, char_output, format, pdf_template)
        console.print(f"[green]✓[/green] Saved to: {char_output}\n")

    console.print(f"[green bold]Conversion complete![/green bold]")


@main.command("import-se")
@click.argument("json_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "-f", "--format",
    type=click.Choice(["json", "html", "pdf", "foundry", "roll20", "all"]),
    default="all",
    help="Output format(s)"
)
@click.option(
    "-o", "--output",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("./output"),
    help="Output directory"
)
@click.option(
    "--pdf-template",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="PDF template file for filling"
)
@click.option(
    "--show-warnings/--no-warnings",
    default=True,
    help="Show conversion warnings"
)
def import_se_cmd(
    json_file: Path,
    format: OutputFormat,
    output: Path,
    pdf_template: Path | None,
    show_warnings: bool,
):
    """Import character data from BG3 Script Extender JSON export.

    This is the recommended method for full-fidelity character extraction.
    Use the bg3_export.lua script in BG3's Script Extender console.
    """
    console.print(f"[bold]Importing:[/bold] {json_file.name}")

    try:
        importer = ScriptExtenderImport(json_path=json_file)
        bg3_chars = importer.import_all()
    except Exception as e:
        console.print(f"[red]Error parsing JSON:[/red] {e}")
        raise SystemExit(1)

    console.print(f"[green]Found {len(bg3_chars)} character(s)[/green]\n")

    converter = BG3To5eConverter()

    for bg3_char in bg3_chars:
        console.print(Panel(f"[bold cyan]{bg3_char.name}[/bold cyan]"))

        # Convert to 5e
        dnd5e_char = converter.convert(bg3_char)

        # Show character summary
        _display_character_summary(dnd5e_char)

        # Show warnings
        if show_warnings and dnd5e_char.conversion_warnings:
            _display_warnings(dnd5e_char)

        # Export
        char_output = output / _sanitize_filename(bg3_char.name)
        _export_character(dnd5e_char, char_output, format, pdf_template)

        console.print(f"[green]✓[/green] Saved to: {char_output}\n")

    console.print(f"\n[green bold]Conversion complete![/green bold]")


@main.command("se-setup")
def se_setup_cmd():
    """Show instructions for setting up BG3 Script Extender."""
    instructions = """
[bold cyan]BG3 Script Extender Setup[/bold cyan]

The Script Extender allows exporting full character data from a running game.
This bypasses the undocumented "NewAge" binary format in save files.

[bold]One-time setup (~2 minutes):[/bold]

1. [yellow]Download BG3 Script Extender[/yellow]
   https://github.com/Norbyte/bg3se/releases

2. [yellow]Extract to your BG3 installation[/yellow]
   Linux (Steam): ~/.steam/steam/steamapps/common/Baldurs Gate 3/bin/
   Windows: C:\\Program Files (x86)\\Steam\\steamapps\\common\\Baldurs Gate 3\\bin\\

3. [yellow]Copy the export script[/yellow]
   Copy lua/bg3_export.lua to:
   Linux: ~/.local/share/Larian Studios/Baldur's Gate 3/Script Extender/
   Windows: %LOCALAPPDATA%\\Larian Studios\\Baldur's Gate 3\\Script Extender\\

4. [yellow]Launch the game and open the console[/yellow]
   Press ~ (tilde) to open the Script Extender console

5. [yellow]Run the export[/yellow]
   In the console, type:
   [green]Ext.Require("bg3_export.lua")[/green]
   [green]export5e()[/green]

6. [yellow]Find your export[/yellow]
   The JSON file will be saved to:
   Linux: ~/.local/share/Larian Studios/Baldur's Gate 3/Script Extender/party_export.json
   Windows: %LOCALAPPDATA%\\Larian Studios\\Baldur's Gate 3\\Script Extender\\party_export.json

[bold]Then run:[/bold]
[green]bg3-to-5e import-se party_export.json[/green]
"""
    console.print(Panel(instructions, title="Script Extender Setup"))


def _apply_newage_stats(save_info, newage_stats) -> None:
    """Match NewAge stats to SaveInfo party members and populate their stats.

    Matching strategy:
    1. Match by unique XP+level combination
    2. Match by unique level
    3. Match by class primary ability score (highest stat matches class)
    4. Remaining unmatched are assigned by order
    """
    if not save_info.party or not newage_stats:
        return

    from .extractors.newage_parser import NewAgeCharacterStats

    # Class → primary ability mapping
    CLASS_PRIMARY_ABILITY: dict[str, str] = {
        "Bard": "charisma", "Cleric": "wisdom", "Druid": "wisdom",
        "Paladin": "charisma", "Ranger": "dexterity", "Sorcerer": "charisma",
        "Warlock": "charisma", "Wizard": "intelligence", "Rogue": "dexterity",
        "Fighter": "strength", "Barbarian": "strength", "Monk": "dexterity",
    }

    unmatched_members = list(enumerate(save_info.party))
    unmatched_stats = list(newage_stats)
    matched: dict[int, NewAgeCharacterStats] = {}

    def _match(member_idx, member, stats):
        matched[member_idx] = stats
        unmatched_members.remove((member_idx, member))
        unmatched_stats.remove(stats)

    # Pass 1: Match by unique XP+level combination
    for member_idx, member in list(unmatched_members):
        for stats in list(unmatched_stats):
            if stats.xp_total == member.xp_total and stats.level == member.level:
                xp_level_count = sum(
                    1 for s in unmatched_stats
                    if s.xp_total == member.xp_total and s.level == member.level
                )
                member_count = sum(
                    1 for _, m in unmatched_members
                    if m.xp_total == member.xp_total and m.level == member.level
                )
                if xp_level_count == 1 and member_count == 1:
                    _match(member_idx, member, stats)
                    break

    # Pass 2: Match by unique level
    for member_idx, member in list(unmatched_members):
        level_matches = [s for s in unmatched_stats if s.level == member.level]
        member_at_level = [(i, m) for i, m in unmatched_members if m.level == member.level]
        if len(level_matches) == 1 and len(member_at_level) == 1:
            _match(member_idx, member, level_matches[0])

    # Pass 3: Match by class primary ability (highest ability matches class)
    for member_idx, member in list(unmatched_members):
        main_class = member.classes[0]["Main"] if member.classes else None
        if not main_class:
            continue
        primary_ability = CLASS_PRIMARY_ABILITY.get(main_class)
        if not primary_ability:
            continue

        # Find unmatched stats at same level where primary ability is the highest
        best_match = None
        best_score = -1
        for stats in unmatched_stats:
            if stats.level != member.level or not stats.abilities:
                continue
            primary_val = stats.abilities.get(primary_ability, 0)
            max_val = max(stats.abilities.values()) if stats.abilities else 0
            if primary_val == max_val and primary_val > best_score:
                best_match = stats
                best_score = primary_val

        if best_match:
            _match(member_idx, member, best_match)

    # Pass 4: Assign remaining by order (same level)
    for member_idx, member in list(unmatched_members):
        for stats in list(unmatched_stats):
            if stats.level == member.level:
                _match(member_idx, member, stats)
                break

    # Pass 5: Assign any remaining stats by order
    for (member_idx, member), stats in zip(list(unmatched_members), list(unmatched_stats)):
        matched[member_idx] = stats

    # Apply matched stats to party members
    for member_idx, stats in matched.items():
        member = save_info.party[member_idx]
        member.ability_scores = stats.abilities
        member.hp = stats.hp
        member.max_hp = stats.max_hp
        member.proficiency_bonus = stats.proficiency_bonus
        if stats.name and member.is_player:
            member.name = stats.name
        if stats.spells:
            member.spells = stats.spells
        if stats.background:
            member.background = stats.background
        if stats.deity:
            member.deity = stats.deity
        if stats.level_ups:
            member.level_ups = [
                {"class_uuid": lu.class_uuid, "subclass_uuid": lu.subclass_uuid}
                for lu in stats.level_ups
            ]
        if stats.action_resources:
            member.action_resources = [
                {"uuid": r.uuid, "current": r.current, "max": r.max_value, "level": r.level}
                for r in stats.action_resources
            ]
        if stats.skill_proficiencies:
            member.skill_proficiencies = stats.skill_proficiencies
        if stats.passives:
            member.passives = stats.passives
        if stats.gold:
            member.gold = stats.gold


def _extract_characters_from_lsv(save_info) -> list[BG3Character]:
    """Extract character data from LSV save info.

    Uses SaveInfo.json for class, level, and race data.
    Uses NewAge stats (if populated) for ability scores, HP, level-ups,
    deity, skills, and action resources.
    """
    from .core.character import Feature, SkillProficiencies
    from .mapping.resources import (
        ACTION_RESOURCE_UUIDS,
        CLASS_UUID_MAPPINGS,
        DEITY_UUID_MAPPINGS,
        SUBCLASS_UUID_MAPPINGS,
        _FILTERED_RESOURCE_NAMES,
    )

    char_name = save_info.character_name or "Unknown"
    characters = []

    # Class → spellcasting ability mapping
    from .data import load_game_data as _load
    CLASS_SPELLCASTING: dict[str, AbilityName] = {
        k: AbilityName[v] for k, v in _load()["classes"]["spellcasting_ability"].items()
    }

    # Patterns indicating summons/companions rather than real party members
    SUMMON_PATTERNS = _load()["filters"]["summon_patterns"]

    if save_info.party:
        for member in save_info.party:
            # Skip summons and companions
            if any(p in member.origin for p in SUMMON_PATTERNS):
                continue

            # Use extracted name if available, fall back to save character name for players
            if member.is_player and member.name != "Player":
                name = member.name
            elif member.is_player:
                name = char_name
            else:
                name = member.name

            # Build class list — prefer exact level-up data from NewAge blob
            classes = _build_classes_from_member(member, CLASS_UUID_MAPPINGS, SUBCLASS_UUID_MAPPINGS)

            # Build ability scores from NewAge data (if available)
            ability_scores = AbilityScores()
            if member.ability_scores:
                ability_scores = AbilityScores(
                    strength=member.ability_scores.get("strength", 10),
                    dexterity=member.ability_scores.get("dexterity", 10),
                    constitution=member.ability_scores.get("constitution", 10),
                    intelligence=member.ability_scores.get("intelligence", 10),
                    wisdom=member.ability_scores.get("wisdom", 10),
                    charisma=member.ability_scores.get("charisma", 10),
                )

            max_hp = member.max_hp if member.max_hp is not None else 0
            current_hp = member.hp if member.hp is not None else max_hp
            prof_bonus = member.proficiency_bonus if member.proficiency_bonus is not None else 2

            # Determine spellcasting ability from primary class
            spellcasting_ability = None
            if classes:
                primary_class = max(classes, key=lambda c: c.level)
                spellcasting_ability = CLASS_SPELLCASTING.get(primary_class.name)

            # Calculate unarmored AC (10 + DEX mod, class-specific variants)
            dex_mod = (ability_scores.dexterity - 10) // 2
            armor_class = 10 + dex_mod
            if classes:
                primary_name = max(classes, key=lambda c: c.level).name
                con_mod = (ability_scores.constitution - 10) // 2
                wis_mod = (ability_scores.wisdom - 10) // 2
                if primary_name == "Barbarian":
                    armor_class = 10 + dex_mod + con_mod
                elif primary_name == "Monk":
                    armor_class = 10 + dex_mod + wis_mod

            # Resolve background from NewAge data if available
            background = getattr(member, "background", None)

            # Resolve deity from NewAge data if available
            deity = None
            if member.deity:
                deity = _lookup_uuid(member.deity, DEITY_UUID_MAPPINGS) or member.deity

            # Build skill proficiencies from NewAge data
            skills = SkillProficiencies()
            if member.skill_proficiencies:
                skills = SkillProficiencies(**member.skill_proficiencies)

            # Collect spells from NewAge data if available
            raw_spells = getattr(member, "spells", None) or []
            spells = _convert_raw_spells(raw_spells) if raw_spells else []

            # Build features from action resources
            features: list[Feature] = []
            if member.action_resources:
                for res in member.action_resources:
                    res_name = _lookup_uuid(res["uuid"], ACTION_RESOURCE_UUIDS)
                    if res_name and res_name not in _FILTERED_RESOURCE_NAMES:
                        max_val = int(res["max"])
                        if max_val > 0:
                            features.append(Feature(
                                name=f"{res_name} ({max_val}/rest)",
                                source="class",
                                bg3_name=res["uuid"],
                            ))

            characters.append(BG3Character(
                name=name,
                race=member.race,
                classes=classes if classes else [],
                ability_scores=ability_scores,
                max_hp=max_hp,
                current_hp=current_hp,
                proficiency_bonus=prof_bonus,
                armor_class=armor_class,
                spellcasting_ability=spellcasting_ability,
                background=background,
                deity=deity,
                skills=skills,
                spells=spells,
                features=features,
                gold=member.gold or 0,
            ))
    else:
        # No SaveInfo.json available - minimal extraction
        characters.append(BG3Character(
            name=char_name,
            race="Unknown",
            classes=[],
            max_hp=0,
            current_hp=0,
            armor_class=10,
        ))

    return characters


def _lookup_uuid(uuid: str, mapping: dict[str, str]) -> str | None:
    """Look up a UUID in a mapping dict, with prefix fallback.

    BG3 class/subclass UUIDs can vary across saves (same first 8 hex chars,
    different remainder). Try exact match first, then fall back to matching
    on just the data1 field (first 8 hex chars before the first dash).
    """
    # Exact match
    result = mapping.get(uuid)
    if result:
        return result

    # Prefix fallback: match on first segment (data1 field)
    prefix = uuid.split("-")[0] if "-" in uuid else uuid[:8]
    for key, value in mapping.items():
        if key.startswith(prefix + "-") or key.startswith(prefix):
            return value

    return None


def _build_classes_from_member(
    member,
    class_uuids: dict[str, str],
    subclass_uuids: dict[str, str],
) -> list[CharacterClass]:
    """Build class list from a SavePartyMember.

    Prefers exact level-up data from the NewAge blob when available,
    falling back to the approximate split from SaveInfo.json.
    """
    # Try exact level-up data first
    if member.level_ups:
        # Count levels per class UUID, track last subclass per class
        class_levels: dict[str, int] = {}
        class_subclasses: dict[str, str | None] = {}
        for lu in member.level_ups:
            cls_uuid = lu["class_uuid"]
            class_levels[cls_uuid] = class_levels.get(cls_uuid, 0) + 1
            if lu.get("subclass_uuid"):
                class_subclasses[cls_uuid] = lu["subclass_uuid"]

        classes = []
        for cls_uuid, level in class_levels.items():
            cls_name = _lookup_uuid(cls_uuid, class_uuids) or cls_uuid[:8]
            sub_uuid = class_subclasses.get(cls_uuid)
            sub_name = (_lookup_uuid(sub_uuid, subclass_uuids) or sub_uuid[:8]) if sub_uuid else None

            # Also try to match subclass from SaveInfo.json for better naming
            si_sub = None
            for si_cls in member.classes:
                if si_cls.get("Main") == cls_name and si_cls.get("Sub"):
                    si_sub = si_cls["Sub"]
                    break

            classes.append(CharacterClass(
                name=cls_name,
                level=max(1, min(20, level)),
                subclass=si_sub or sub_name,
                bg3_name=cls_name,
                bg3_subclass=si_sub or sub_name,
            ))
        return classes

    # Fallback: approximate split from SaveInfo.json
    valid_classes = [c for c in member.classes if c.get("Main")]
    if not valid_classes:
        return []

    num_classes = len(valid_classes)
    base_level = max(1, member.level // num_classes)
    remainder = member.level - base_level * num_classes

    classes = []
    for i, cls in enumerate(valid_classes):
        main_class = cls.get("Main", "")
        sub_class = cls.get("Sub", "") or None
        cls_level = base_level + (1 if i == 0 and remainder > 0 else 0)
        cls_level = max(1, min(20, cls_level))
        classes.append(CharacterClass(
            name=main_class,
            level=cls_level,
            subclass=sub_class,
            bg3_name=main_class,
            bg3_subclass=sub_class,
        ))
    return classes


def _convert_raw_spells(raw_spells: list[str]) -> list["Spell"]:
    """Convert raw BG3 spell name strings to Spell objects."""
    from .core.character import Spell
    from .mapping.spells import convert_bg3_spell_name, STANDARD_SPELLS

    # Build reverse lookup: spell name → level
    spell_level_lookup: dict[str, int] = {}
    for level, names in STANDARD_SPELLS.items():
        for name in names:
            spell_level_lookup[name.lower()] = level

    spells = []
    seen = set()
    for raw_name in raw_spells:
        clean_name = convert_bg3_spell_name(raw_name)
        if not clean_name or clean_name.lower() in seen:
            continue
        seen.add(clean_name.lower())
        level = spell_level_lookup.get(clean_name.lower(), 0)
        spells.append(Spell(name=clean_name, level=level, prepared=True, bg3_name=raw_name))

    return spells


def _display_character_summary(char: DnD5eCharacter):
    """Display a summary of the converted character."""
    table = Table(show_header=False, box=None)
    table.add_column("", style="dim", width=15)
    table.add_column("")

    # Class string
    class_str = " / ".join(
        f"{c.name} {c.level}" + (f" ({c.subclass})" if c.subclass else "")
        for c in char.classes
    )

    table.add_row("Race", f"{char.subrace or ''} {char.race}".strip())
    table.add_row("Class", class_str or "Unknown")
    table.add_row("Background", char.background)
    if char.deity:
        table.add_row("Deity", char.deity)
    table.add_row("Level", str(char.total_level))

    # Ability scores
    ab = char.ability_scores
    abilities_str = (f"STR {ab.strength}  DEX {ab.dexterity}  CON {ab.constitution}  "
                     f"INT {ab.intelligence}  WIS {ab.wisdom}  CHA {ab.charisma}")
    table.add_row("Abilities", abilities_str)

    table.add_row("HP", f"{char.current_hp}/{char.max_hp}")
    table.add_row("AC", str(char.armor_class))

    if char.spells:
        table.add_row("Spells", str(len(char.spells)))
    if char.equipment:
        table.add_row("Items", str(len(char.equipment)))

    console.print(table)


def _display_warnings(char: DnD5eCharacter):
    """Display conversion warnings."""
    if not char.conversion_warnings:
        return

    console.print("\n[yellow bold]Conversion Warnings:[/yellow bold]")

    # Group by category
    by_category: dict[str, list] = {}
    for w in char.conversion_warnings:
        if w.category not in by_category:
            by_category[w.category] = []
        by_category[w.category].append(w)

    for category, warnings in by_category.items():
        console.print(f"\n  [dim]{category.title()}:[/dim]")
        for w in warnings[:5]:  # Limit per category
            severity_color = {"info": "blue", "warning": "yellow", "error": "red"}.get(w.severity, "white")
            console.print(f"    [{severity_color}]•[/{severity_color}] {w.item_name}: {w.message}")
        if len(warnings) > 5:
            console.print(f"    [dim]... and {len(warnings) - 5} more[/dim]")


def _export_character(
    char: DnD5eCharacter,
    output_dir: Path,
    format: OutputFormat,
    pdf_template: Path | None,
):
    """Export character to specified format(s)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    name = _sanitize_filename(char.name)

    formats_to_export = []
    if format == "all":
        formats_to_export = ["json", "html", "pdf", "foundry", "roll20"]
    else:
        formats_to_export = [format]

    for fmt in formats_to_export:
        if fmt == "json":
            exporter = DnD5eJsonExporter()
            exporter.export(char, output_dir / f"{name}.json")
            console.print(f"  [dim]→[/dim] {name}.json")

        elif fmt == "html":
            exporter = HTMLSheetExporter()
            exporter.export(char, output_dir / f"{name}.html")
            console.print(f"  [dim]→[/dim] {name}.html")

        elif fmt == "pdf":
            exporter = PDFSheetExporter(template_path=pdf_template)
            exporter.export(char, output_dir / f"{name}.pdf")
            if pdf_template:
                console.print(f"  [dim]→[/dim] {name}.pdf")
            else:
                console.print(f"  [dim]→[/dim] {name}.pdf [yellow](template needed for proper PDF)[/yellow]")

        elif fmt == "foundry":
            exporter = FoundryVTTExporter()
            exporter.export(char, output_dir / f"{name}_foundry.json")
            console.print(f"  [dim]→[/dim] {name}_foundry.json")

        elif fmt == "roll20":
            exporter = Roll20Exporter()
            exporter.export(char, output_dir / f"{name}_roll20.json")
            console.print(f"  [dim]→[/dim] {name}_roll20.json")


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.strip()


if __name__ == "__main__":
    main()
