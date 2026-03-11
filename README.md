# BG3 to D&D 5e Character Sheet Converter

Convert Baldur's Gate 3 save files to standard D&D 5e character sheets in various formats.

## Features

- **Multiple Output Formats**: JSON, HTML, PDF, Foundry VTT, Roll20
- **Full Mapping Engine**: Handles BG3-specific classes, spells, items, and races
- **Conversion Warnings**: Flags mechanic differences between BG3 and tabletop 5e
- **Split-Screen / Co-op Support**: Correctly identifies and names custom characters in multiplayer saves
- **Save File Parsing**: Extracts character names, ability scores, classes, spells, equipment, and gold directly from `.lsv` save files

## Installation

<!-- TODO: publish to PyPI -->
Install from source:

```bash
git clone https://github.com/nSimonFR/bg3-to-5e.git
cd bg3-to-5e
pip install -e .
```

## Quick Start

```bash
# List available saves
bg3-to-5e list-saves

# Convert a save file to HTML
bg3-to-5e convert path/to/QuickSave.lsv -f html

# Convert to all formats including PDF
bg3-to-5e convert path/to/QuickSave.lsv -f all --pdf-template templates/DnD_5E_CharacterSheet_FormFillable.pdf
```

## Output Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| `json` | dnd5e_json_schema format | Interoperability, backups |
| `html` | Printable web page | Quick reference, printing |
| `pdf` | Filled WotC 5e character sheet | Official character sheets |
| `foundry` | Foundry VTT actor JSON | Import into Foundry VTT |
| `roll20` | Roll20 character format | Import into Roll20 |
| `all` | All of the above | Complete export |

### PDF Export

PDF export fills the official [WotC 2022 fillable character sheet](https://media.wizards.com/2022/dnd/downloads/DnD_5E_CharacterSheet_FormFillable.pdf). A copy is included in `templates/`.

```bash
# Using the bundled template
bg3-to-5e convert save.lsv -f pdf --pdf-template templates/DnD_5E_CharacterSheet_FormFillable.pdf

# Using your own template
bg3-to-5e convert save.lsv -f pdf --pdf-template path/to/your/sheet.pdf
```

All three pages are filled: ability scores, skills, saves, combat stats, equipment, features (page 1), personality and appearance (page 2), spellcasting, spell slots, and spell lists (page 3).

## BG3 vs 5e Differences

The converter flags notable differences between BG3 and tabletop 5e:

### Spells
- **Haste**: BG3 allows any action; 5e restricts to Attack (one weapon attack), Dash, Disengage, Hide, or Use an Object
- **Dissonant Whispers**: BG3 causes Frightened; 5e does damage + flee
- **Bone Chill** → **Chill Touch**: Renamed in 5e
- **Counterspell**: BG3 reaction is automatic; 5e requires choosing to react
- **Magic Missile**: BG3 rolls damage per missile; 5e RAW rolls once for all

### Classes
- **Barbarian Rage**: BG3 applies to DEX attacks; 5e STR only
- **Battle Master**: BG3 chooses maneuver before attack; 5e on hit
- **Divine Smite**: BG3 is a bonus action; 5e decided after hitting

### BG3-Specific Content
- Illithid/Tadpole powers (no 5e equivalent)
- Unique items (Markoheshkir, Mourning Frost, etc.) mapped to closest 5e equivalents
- Some subclasses (Bounty Hunter)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## AI-Generated Project

This project was fully generated using [Claude Code](https://claude.com/claude-code) (Opus 4.6) through approximately 10 planning sessions and ~$30 of API tokens for complete implementation, including binary format reverse-engineering, mapping engine, all exporters, and test suite.

## License

MIT — see [LICENSE](LICENSE).
