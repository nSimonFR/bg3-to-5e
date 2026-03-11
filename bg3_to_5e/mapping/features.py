"""Class features, racial traits, and background skills for 5e inference.

When the save file doesn't contain explicit feature data, these tables
let us infer features from class/level/subclass/race.
"""

from ..data import load_game_data

_data = load_game_data()

# Class → level → features gained at that level (string keys → int)
CLASS_FEATURES: dict[str, dict[int, list[str]]] = {
    cls: {int(lvl): feats for lvl, feats in levels.items()}
    for cls, levels in _data["features"]["class_features"].items()
}

# Subclass → level → features gained at that level (string keys → int)
SUBCLASS_FEATURES: dict[str, dict[int, list[str]]] = {
    sub: {int(lvl): feats for lvl, feats in levels.items()}
    for sub, levels in _data["features"]["subclass_features"].items()
}

# Racial traits
RACIAL_TRAITS: dict[str, list[str]] = _data["races"]["racial_traits"]

# Racial skill proficiencies (deterministic ones only)
RACIAL_SKILLS: dict[str, list[str]] = _data["races"]["racial_skills"]

# Background → 2 skill proficiencies
BACKGROUND_SKILLS: dict[str, list[str]] = _data["backgrounds"]["skills"]


def get_features_for_class(
    class_name: str,
    level: int,
    subclass: str | None = None,
) -> list[tuple[str, str]]:
    """Get features for a class at a given level.

    Returns list of (feature_name, source) tuples.
    Accumulates features from level 1 through the given level.
    """
    features = []

    # Class features
    class_feats = CLASS_FEATURES.get(class_name, {})
    for lvl in range(1, level + 1):
        for feat in class_feats.get(lvl, []):
            features.append((feat, class_name))

    # Subclass features
    if subclass:
        sub_feats = SUBCLASS_FEATURES.get(subclass, {})
        for lvl in range(1, level + 1):
            for feat in sub_feats.get(lvl, []):
                features.append((feat, subclass))

    return features


def get_racial_features(race: str, subrace: str | None = None) -> list[tuple[str, str]]:
    """Get racial traits.

    Returns list of (trait_name, source) tuples.
    """
    key = subrace if subrace and subrace in RACIAL_TRAITS else race
    traits = RACIAL_TRAITS.get(key, [])
    source = subrace or race
    return [(t, source) for t in traits]
