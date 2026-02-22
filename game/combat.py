"""Utilitários de combate."""


def build_scaled_regular_monster(monster_template, player_level, map_data=None):
    """Cria monstro regular com escala de mapa e ajuste por nível do jogador."""
    regular_scaling = (map_data or {}).get("regular_scaling", {})
    hp_scale = regular_scaling.get("hp", 1.0)
    atk_scale = regular_scaling.get("atk", 1.0)
    gold_scale = regular_scaling.get("gold", 1.0)

    base_hp = monster_template["hp"] + (player_level - monster_template["level"]) * 10
    base_atk = monster_template["atk"] + (player_level - monster_template["level"]) * 2

    scaled_hp = max(1, int(base_hp * hp_scale))
    scaled_atk = max(1, int(base_atk * atk_scale))
    scaled_gold = max(1, int(monster_template["gold"] * gold_scale))

    return {
        "name": monster_template["name"],
        "hp": scaled_hp,
        "max_hp": scaled_hp,
        "atk": scaled_atk,
        "xp": monster_template["xp"],
        "gold": scaled_gold,
        "level": monster_template["level"],
        "drops": monster_template["drops"],
        "effects": monster_template.get("effects", [])
    }
