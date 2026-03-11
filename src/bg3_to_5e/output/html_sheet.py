"""Export to HTML character sheet."""

from pathlib import Path

from jinja2 import Environment, BaseLoader, select_autoescape

from ..core.character import AbilityName, DnD5eCharacter


class HTMLSheetExporter:
    """Export character to HTML format."""

    def __init__(self):
        self.env = Environment(
            loader=BaseLoader(),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.env.filters["modifier"] = self._format_modifier
        self.env.filters["calc_save"] = self._calc_save_filter
        self.env.filters["calc_skill"] = self._calc_skill_filter

    def export(self, character: DnD5eCharacter, output_path: Path | str | None = None) -> str:
        """Export character to HTML."""
        template = self.env.from_string(self._get_default_template())

        html = template.render(
            char=character,
            AbilityName=AbilityName,
        )

        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write(html)

        return html

    def _format_modifier(self, value: int) -> str:
        """Format a modifier with + or - sign."""
        if value >= 0:
            return f"+{value}"
        return str(value)

    def _calc_save_filter(self, char: DnD5eCharacter, ability: str) -> int:
        """Calculate saving throw modifier for template."""
        ability_enum = AbilityName(ability)
        base_mod = char.ability_scores.get_modifier(ability_enum)
        prof = getattr(char.saving_throws, ability, False)
        return base_mod + (char.proficiency_bonus if prof else 0)

    def _calc_skill_filter(self, char: DnD5eCharacter, skill: str, ability: str) -> int:
        """Calculate skill modifier for template."""
        ability_enum = AbilityName(ability)
        base_mod = char.ability_scores.get_modifier(ability_enum)
        prof_level = getattr(char.skills, skill, 0)

        if prof_level == 2:
            return base_mod + char.proficiency_bonus * 2
        elif prof_level == 1:
            return base_mod + char.proficiency_bonus
        return base_mod

    def _get_default_template(self) -> str:
        """Return the default HTML template."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ char.name }} - D&D 5e Character Sheet</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f5f5f5; color: #333; line-height: 1.4; }
        .sheet { max-width: 900px; margin: 20px auto; background: white; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        header { border-bottom: 3px solid #8b0000; padding-bottom: 15px; margin-bottom: 20px; }
        h1 { font-size: 2.5em; color: #8b0000; }
        .subtitle { font-size: 1.1em; color: #666; }
        .grid { display: grid; gap: 20px; }
        .grid-2 { grid-template-columns: 1fr 1fr; }
        .grid-3 { grid-template-columns: 1fr 1fr 1fr; }
        .grid-6 { grid-template-columns: repeat(6, 1fr); }
        section { margin-bottom: 25px; }
        h2 { font-size: 1.3em; color: #8b0000; border-bottom: 2px solid #ddd; padding-bottom: 5px; margin-bottom: 15px; }
        h3 { font-size: 1.1em; color: #555; margin-bottom: 10px; }
        .stat-box { text-align: center; padding: 15px 10px; border: 2px solid #8b0000; border-radius: 8px; background: #fafafa; }
        .stat-box .label { font-size: 0.75em; text-transform: uppercase; color: #666; font-weight: bold; }
        .stat-box .value { font-size: 2em; font-weight: bold; color: #8b0000; }
        .stat-box .modifier { font-size: 1.2em; color: #333; }
        .combat-stats { display: flex; gap: 30px; justify-content: center; flex-wrap: wrap; }
        .combat-stat { text-align: center; min-width: 80px; }
        .combat-stat .value { font-size: 2em; font-weight: bold; color: #8b0000; }
        .combat-stat .label { font-size: 0.8em; text-transform: uppercase; color: #666; }
        .save-list, .skill-list { list-style: none; }
        .save-list li, .skill-list li { padding: 5px 0; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; }
        .proficient { font-weight: bold; }
        .expertise { font-weight: bold; color: #8b0000; }
        .spell-section { margin-top: 15px; }
        .spell-level { background: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
        .spell-level h4 { margin-bottom: 8px; color: #8b0000; }
        .spell-list { display: flex; flex-wrap: wrap; gap: 8px; }
        .spell { background: white; padding: 5px 10px; border: 1px solid #ddd; border-radius: 3px; font-size: 0.9em; }
        .spell.prepared { border-color: #8b0000; background: #fff5f5; }
        .equipment-list { list-style: none; }
        .equipment-list li { padding: 8px 0; border-bottom: 1px solid #eee; }
        .equipped { font-weight: bold; }
        .magical { color: #8b0000; }
        .features-list { list-style: none; }
        .features-list li { padding: 10px 0; border-bottom: 1px solid #eee; }
        .feature-source { font-size: 0.8em; color: #666; }
        .warnings { background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin-top: 20px; }
        .warnings h3 { color: #856404; margin-bottom: 10px; }
        .warnings ul { margin-left: 20px; }
        .warnings li { margin-bottom: 5px; }
        .warning-info { color: #0c5460; }
        .warning-warning { color: #856404; }
        footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; text-align: center; color: #666; font-size: 0.9em; }
        @media print {
            body { background: white; }
            .sheet { box-shadow: none; margin: 0; max-width: 100%; }
        }
        @media (max-width: 768px) {
            .grid-2, .grid-3 { grid-template-columns: 1fr; }
            .grid-6 { grid-template-columns: repeat(3, 1fr); }
        }
    </style>
</head>
<body>
    <div class="sheet">
        <header>
            <h1>{{ char.name }}</h1>
            <p class="subtitle">
                Level {{ char.total_level }}
                {% for cls in char.classes %}
                    {{ cls.name }}{% if cls.subclass %} ({{ cls.subclass }}){% endif %}{% if not loop.last %} / {% endif %}
                {% endfor %}
                &bull; {{ char.race }}{% if char.subrace %} ({{ char.subrace }}){% endif %}
                &bull; {{ char.background }}
                {% if char.deity %}&bull; {{ char.deity }}{% endif %}
            </p>
        </header>

        <section>
            <div class="grid grid-6">
                {% for ability in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'] %}
                <div class="stat-box">
                    <div class="label">{{ ability[:3]|upper }}</div>
                    <div class="value">{{ char.ability_scores[ability] }}</div>
                    <div class="modifier">{{ char.ability_scores.get_modifier(AbilityName(ability))|modifier }}</div>
                </div>
                {% endfor %}
            </div>
        </section>

        <section>
            <div class="combat-stats">
                <div class="combat-stat">
                    <div class="value">{{ char.armor_class }}</div>
                    <div class="label">Armor Class</div>
                </div>
                <div class="combat-stat">
                    <div class="value">{{ char.initiative|modifier }}</div>
                    <div class="label">Initiative</div>
                </div>
                <div class="combat-stat">
                    <div class="value">{{ char.speed }} ft</div>
                    <div class="label">Speed</div>
                </div>
                <div class="combat-stat">
                    <div class="value">{{ char.current_hp }}/{{ char.max_hp }}</div>
                    <div class="label">Hit Points</div>
                </div>
                <div class="combat-stat">
                    <div class="value">{{ char.hit_dice }}</div>
                    <div class="label">Hit Dice</div>
                </div>
                <div class="combat-stat">
                    <div class="value">+{{ char.proficiency_bonus }}</div>
                    <div class="label">Proficiency</div>
                </div>
            </div>
        </section>

        <div class="grid grid-2">
            <section>
                <h2>Saving Throws</h2>
                <ul class="save-list">
                    {% for ability in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'] %}
                    <li class="{% if char.saving_throws[ability] %}proficient{% endif %}">
                        <span>{{ ability|title }}</span>
                        <span>{{ char|calc_save(ability)|modifier }}</span>
                    </li>
                    {% endfor %}
                </ul>
            </section>

            <section>
                <h2>Skills</h2>
                <ul class="skill-list">
                    {% set skills = [
                        ('acrobatics', 'dexterity'),
                        ('animal_handling', 'wisdom'),
                        ('arcana', 'intelligence'),
                        ('athletics', 'strength'),
                        ('deception', 'charisma'),
                        ('history', 'intelligence'),
                        ('insight', 'wisdom'),
                        ('intimidation', 'charisma'),
                        ('investigation', 'intelligence'),
                        ('medicine', 'wisdom'),
                        ('nature', 'intelligence'),
                        ('perception', 'wisdom'),
                        ('performance', 'charisma'),
                        ('persuasion', 'charisma'),
                        ('religion', 'intelligence'),
                        ('sleight_of_hand', 'dexterity'),
                        ('stealth', 'dexterity'),
                        ('survival', 'wisdom')
                    ] %}
                    {% for skill, ability in skills %}
                    {% set prof = char.skills[skill] %}
                    <li class="{% if prof == 2 %}expertise{% elif prof == 1 %}proficient{% endif %}">
                        <span>{{ skill|replace('_', ' ')|title }} ({{ ability[:3]|upper }})</span>
                        <span>{{ char|calc_skill(skill, ability)|modifier }}</span>
                    </li>
                    {% endfor %}
                </ul>
            </section>
        </div>

        {% if char.spells %}
        <section>
            <h2>Spellcasting</h2>
            {% if char.spellcasting_ability %}
            <p>
                <strong>Spellcasting Ability:</strong> {{ char.spellcasting_ability.value|title }} &bull;
                <strong>Spell Save DC:</strong> {{ char.spell_save_dc }} &bull;
                <strong>Spell Attack:</strong> {{ char.spell_attack_bonus|modifier }}
            </p>
            {% endif %}
            <p>
                <strong>Spell Slots:</strong>
                1st: {{ char.spell_slots.level_1 }} |
                2nd: {{ char.spell_slots.level_2 }} |
                3rd: {{ char.spell_slots.level_3 }} |
                4th: {{ char.spell_slots.level_4 }} |
                5th: {{ char.spell_slots.level_5 }}
                {% if char.spell_slots.level_6 %} | 6th: {{ char.spell_slots.level_6 }}{% endif %}
                {% if char.spell_slots.level_7 %} | 7th: {{ char.spell_slots.level_7 }}{% endif %}
                {% if char.spell_slots.level_8 %} | 8th: {{ char.spell_slots.level_8 }}{% endif %}
                {% if char.spell_slots.level_9 %} | 9th: {{ char.spell_slots.level_9 }}{% endif %}
            </p>
            <div class="spell-section">
                {% for level in range(10) %}
                {% set level_spells = char.spells|selectattr('level', 'equalto', level)|list %}
                {% if level_spells %}
                <div class="spell-level">
                    <h4>{% if level == 0 %}Cantrips{% else %}Level {{ level }}{% endif %}</h4>
                    <div class="spell-list">
                        {% for spell in level_spells %}
                        <span class="spell {% if spell.prepared %}prepared{% endif %}">{{ spell.name }}</span>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}
                {% endfor %}
            </div>
        </section>
        {% endif %}

        {% if char.equipment %}
        <section>
            <h2>Equipment</h2>
            <p><strong>Currency:</strong> {{ char.gold }} gp</p>
            <ul class="equipment-list">
                {% for item in char.equipment %}
                <li class="{% if item.equipped %}equipped{% endif %} {% if item.magical %}magical{% endif %}">
                    {{ item.name }}
                    {% if item.quantity > 1 %}(x{{ item.quantity }}){% endif %}
                    {% if item.magical %}✦{% endif %}
                    {% if item.attuned %}(attuned){% endif %}
                </li>
                {% endfor %}
            </ul>
        </section>
        {% endif %}

        {% if char.features %}
        <section>
            <h2>Features & Traits</h2>
            <ul class="features-list">
                {% for feature in char.features %}
                <li>
                    <strong>{{ feature.name }}</strong>
                    <span class="feature-source">({{ feature.source }})</span>
                    {% if feature.description %}<p>{{ feature.description }}</p>{% endif %}
                </li>
                {% endfor %}
            </ul>
        </section>
        {% endif %}

        {% if char.conversion_warnings %}
        <section class="warnings">
            <h3>Conversion Notes</h3>
            <ul>
                {% for warning in char.conversion_warnings %}
                <li class="warning-{{ warning.severity }}">
                    <strong>{{ warning.item_name }}:</strong> {{ warning.message }}
                </li>
                {% endfor %}
            </ul>
        </section>
        {% endif %}

        <footer>
            <p>Converted from Baldur\'s Gate 3 &bull; Generated by bg3-to-5e</p>
        </footer>
    </div>
</body>
</html>'''
