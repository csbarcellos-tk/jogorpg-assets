"""Conteúdo base do jogo: classes, armas e armaduras."""

classes = {
    "Guerreiro": {
        "hp_bonus": 40,
        "damage_bonus": 4,
        "defense_bonus": 5,
        "description": "Especialista em combate corpo a corpo com alta resistência",
        "emoji": "⚔️"
    },
    "Mago": {
        "hp_bonus": 15,
        "damage_bonus": 12,
        "defense_bonus": 0,
        "description": "Poderoso em dano mágico mas extremamente frágil",
        "emoji": "🔮"
    },
    "Arqueiro": {
        "hp_bonus": 20,
        "damage_bonus": 8,
        "defense_bonus": 2,
        "description": "Ataques precisos à distância com dano consistente",
        "emoji": "🏹"
    },
    "Lutador": {
        "hp_bonus": 25,
        "damage_bonus": 6,
        "defense_bonus": 3,
        "description": "Golpes rápidos e versáteis, bom equilíbrio",
        "emoji": "👊"
    },
    "Desempregado": {
        "hp_bonus": 0,
        "damage_bonus": 0,
        "defense_bonus": 0,
        "description": "Começa fraco mas tem potencial... talvez",
        "emoji": "😰"
    }
}

starting_weapons = {
    "Mago": "Graveto encantado",
    "Guerreiro": "Espada de madeira",
    "Arqueiro": "Estilingue",
    "Desempregado": "Punhos",
    "Lutador": "Bastão de madeira"
}

common_weapons = {
    "Espada de madeira": {"damage": 3, "price": 60, "level_req": 1, "category": "guerreiro", "emoji": "⚔️", "effect": None},
    "Machado de pedra": {"damage": 4, "price": 75, "level_req": 1, "category": "guerreiro", "emoji": "🪓", "effect": None},
    "Martelo de madeira": {"damage": 3, "price": 67, "level_req": 1, "category": "guerreiro", "emoji": "🔨", "effect": None},
    "Graveto encantado": {"damage": 2, "price": 52, "level_req": 1, "category": "mago", "emoji": "🪄", "effect": None},
    "Varinha de madeira": {"damage": 3, "price": 67, "level_req": 1, "category": "mago", "emoji": "✨", "effect": None},
    "Grimório básico": {"damage": 2, "price": 60, "level_req": 1, "category": "mago", "emoji": "📖", "effect": None},
    "Arco curto": {"damage": 3, "price": 67, "level_req": 1, "category": "arqueiro", "emoji": "🏹", "effect": None},
    "Adaga enferrujada": {"damage": 2, "price": 45, "level_req": 1, "category": "arqueiro", "emoji": "🔪", "effect": None},
    "Estilingue": {"damage": 2, "price": 37, "level_req": 1, "category": "arqueiro", "emoji": "⚡", "effect": None},
    "Manopla de couro": {"damage": 3, "price": 60, "level_req": 1, "category": "lutador", "emoji": "👊", "effect": None},
    "Soco inglês": {"damage": 4, "price": 75, "level_req": 1, "category": "lutador", "emoji": "🥊", "effect": None},
    "Bastão de madeira": {"damage": 3, "price": 52, "level_req": 1, "category": "lutador", "emoji": "🪵", "effect": None},
    "Punhos": {"damage": 0, "price": 0, "level_req": 1, "category": "geral", "emoji": "👊", "effect": None}
}

rare_weapons = {
    "Espada longa": {"damage": 12, "price": 600, "level_req": 3, "category": "guerreiro", "emoji": "⚔️", "effect": None},
    "Machado de guerra": {"damage": 14, "price": 680, "level_req": 4, "category": "guerreiro", "emoji": "🪓", "effect": "sangramento"},
    "Martelo de ferro": {"damage": 13, "price": 650, "level_req": 3, "category": "guerreiro", "emoji": "🔨", "effect": "atordoamento"},
    "Lança de cavaleiro": {"damage": 15, "price": 760, "level_req": 5, "category": "guerreiro", "emoji": "🏹", "effect": "perfurante"},
    "Cajado elemental": {"damage": 11, "price": 680, "level_req": 4, "category": "mago", "emoji": "🪄", "effect": "fogo"},
    "Varinha de cristal": {"damage": 10, "price": 650, "level_req": 3, "category": "mago", "emoji": "✨", "effect": "gelo"},
    "Grimório arcano": {"damage": 12, "price": 710, "level_req": 4, "category": "mago", "emoji": "📖", "effect": "eletrico"},
    "Orbe de vidro": {"damage": 9, "price": 600, "level_req": 3, "category": "mago", "emoji": "🔮", "effect": "veneno"},
    "Arco longo": {"damage": 13, "price": 650, "level_req": 4, "category": "arqueiro", "emoji": "🏹", "effect": "perfurante"},
    "Besta leve": {"damage": 14, "price": 680, "level_req": 4, "category": "arqueiro", "emoji": "🎯", "effect": None},
    "Adaga de prata": {"damage": 10, "price": 540, "level_req": 3, "category": "arqueiro", "emoji": "🔪", "effect": "sangramento"},
    "Shuriken de aço": {"damage": 8, "price": 475, "level_req": 3, "category": "arqueiro", "emoji": "⭐", "effect": "veneno"},
    "Manopla de ferro": {"damage": 12, "price": 610, "level_req": 3, "category": "lutador", "emoji": "👊", "effect": None},
    "Katar": {"damage": 13, "price": 660, "level_req": 4, "category": "lutador", "emoji": "⚔️", "effect": "sangramento"},
    "Nunchaku": {"damage": 10, "price": 540, "level_req": 3, "category": "lutador", "emoji": "🌀", "effect": "atordoamento"},
    "Soco de pedra": {"damage": 11, "price": 580, "level_req": 3, "category": "lutador", "emoji": "👊", "effect": None}
}

epic_weapons = {
    "Espada de prata": {"damage": 25, "price": 2000, "level_req": 7, "category": "guerreiro", "emoji": "⚔️", "effect": "sagrado"},
    "Machado duplo": {"damage": 28, "price": 2250, "level_req": 8, "category": "guerreiro", "emoji": "🪓", "effect": "sangramento"},
    "Martelo de guerra": {"damage": 26, "price": 2080, "level_req": 7, "category": "guerreiro", "emoji": "🔨", "effect": "atordoamento"},
    "Lança dragão": {"damage": 30, "price": 2340, "level_req": 8, "category": "guerreiro", "emoji": "🏹", "effect": "perfurante"},
    "Cajado arcano": {"damage": 24, "price": 2170, "level_req": 7, "category": "mago", "emoji": "🪄", "effect": "eletrico"},
    "Varinha élfica": {"damage": 22, "price": 1920, "level_req": 6, "category": "mago", "emoji": "✨", "effect": "gelo"},
    "Grimório antigo": {"damage": 26, "price": 2340, "level_req": 8, "category": "mago", "emoji": "📖", "effect": "fogo"},
    "Orbe cristalino": {"damage": 20, "price": 1670, "level_req": 6, "category": "mago", "emoji": "🔮", "effect": "veneno"},
    "Arco élfico": {"damage": 25, "price": 2080, "level_req": 7, "category": "arqueiro", "emoji": "🏹", "effect": "gelo"},
    "Besta pesada": {"damage": 28, "price": 2250, "level_req": 8, "category": "arqueiro", "emoji": "🎯", "effect": "perfurante"},
    "Adaga élfica": {"damage": 22, "price": 1840, "level_req": 6, "category": "arqueiro", "emoji": "🔪", "effect": "sangramento"},
    "Shuriken elemental": {"damage": 20, "price": 1670, "level_req": 6, "category": "arqueiro", "emoji": "⭐", "effect": "eletrico"},
    "Manopla de prata": {"damage": 24, "price": 2000, "level_req": 7, "category": "lutador", "emoji": "👊", "effect": "sagrado"},
    "Katar flamejante": {"damage": 27, "price": 2170, "level_req": 8, "category": "lutador", "emoji": "⚔️", "effect": "fogo"},
    "Nunchaku de aço": {"damage": 22, "price": 1750, "level_req": 6, "category": "lutador", "emoji": "🌀", "effect": "atordoamento"},
    "Soco de trovão": {"damage": 25, "price": 1920, "level_req": 7, "category": "lutador", "emoji": "👊", "effect": "eletrico"}
}

legendary_weapons = {
    "Espada flamejante": {"damage": 48, "price": 6800, "level_req": 11, "category": "guerreiro", "emoji": "⚔️", "effect": "fogo"},
    "Machado do trovão": {"damage": 52, "price": 7650, "level_req": 12, "category": "guerreiro", "emoji": "🪓", "effect": "eletrico"},
    "Martelo de gelo": {"damage": 45, "price": 6460, "level_req": 10, "category": "guerreiro", "emoji": "🔨", "effect": "gelo"},
    "Lança divina": {"damage": 55, "price": 8160, "level_req": 12, "category": "guerreiro", "emoji": "🏹", "effect": "sagrado"},
    "Cajado ancião": {"damage": 50, "price": 7140, "level_req": 11, "category": "mago", "emoji": "🪄", "effect": "eletrico"},
    "Varinha celestial": {"damage": 45, "price": 6460, "level_req": 10, "category": "mago", "emoji": "✨", "effect": "sagrado"},
    "Grimório das trevas": {"damage": 52, "price": 7480, "level_req": 11, "category": "mago", "emoji": "📖", "effect": "veneno"},
    "Orbe profético": {"damage": 42, "price": 6120, "level_req": 10, "category": "mago", "emoji": "🔮", "effect": "gelo"},
    "Arco celestial": {"damage": 48, "price": 6800, "level_req": 11, "category": "arqueiro", "emoji": "🏹", "effect": "sagrado"},
    "Besta do caçador": {"damage": 52, "price": 7310, "level_req": 12, "category": "arqueiro", "emoji": "🎯", "effect": "perfurante"},
    "Adaga sombria": {"damage": 44, "price": 6290, "level_req": 10, "category": "arqueiro", "emoji": "🔪", "effect": "sangramento"},
    "Shuriken divina": {"damage": 40, "price": 5950, "level_req": 10, "category": "arqueiro", "emoji": "⭐", "effect": "eletrico"},
    "Manopla divina": {"damage": 46, "price": 6630, "level_req": 11, "category": "lutador", "emoji": "👊", "effect": "sagrado"},
    "Katar do vento": {"damage": 50, "price": 6970, "level_req": 11, "category": "lutador", "emoji": "⚔️", "effect": "perfurante"},
    "Nunchaku elemental": {"damage": 42, "price": 6120, "level_req": 10, "category": "lutador", "emoji": "🌀", "effect": "eletrico"},
    "Soco do dragão": {"damage": 48, "price": 6800, "level_req": 11, "category": "lutador", "emoji": "👊", "effect": "fogo"}
}

mythic_weapons = {
    "Excalibur": {"damage": 100, "price": 20400, "level_req": 18, "category": "guerreiro", "emoji": "⚔️", "effect": "sagrado"},
    "Mjolnir": {"damage": 110, "price": 22950, "level_req": 20, "category": "guerreiro", "emoji": "🔨", "effect": "eletrico"},
    "Gungnir": {"damage": 105, "price": 21250, "level_req": 19, "category": "guerreiro", "emoji": "🏹", "effect": "perfurante"},
    "Espada do amanhã": {"damage": 95, "price": 18700, "level_req": 17, "category": "guerreiro", "emoji": "⚔️", "effect": "fogo"},
    "Cajado de Merlin": {"damage": 108, "price": 22100, "level_req": 20, "category": "mago", "emoji": "🪄", "effect": "eletrico"},
    "Varinha da realidade": {"damage": 98, "price": 19550, "level_req": 18, "category": "mago", "emoji": "✨", "effect": "sagrado"},
    "Grimório infinito": {"damage": 102, "price": 21250, "level_req": 19, "category": "mago", "emoji": "📖", "effect": "veneno"},
    "Orbe do tempo": {"damage": 92, "price": 17850, "level_req": 17, "category": "mago", "emoji": "🔮", "effect": "gelo"},
    "Arco de Ártemis": {"damage": 98, "price": 20060, "level_req": 18, "category": "arqueiro", "emoji": "🏹", "effect": "gelo"},
    "Besta do apocalipse": {"damage": 112, "price": 23800, "level_req": 20, "category": "arqueiro", "emoji": "🎯", "effect": "fogo"},
    "Besta do destino": {"damage": 88, "price": 17000, "level_req": 16, "category": "arqueiro", "emoji": "🔪", "effect": "sangramento"},
    "Shuriken celestial": {"damage": 85, "price": 16150, "level_req": 15, "category": "arqueiro", "emoji": "⭐", "effect": "eletrico"},
    "Manopla do infinito": {"damage": 95, "price": 18700, "level_req": 17, "category": "lutador", "emoji": "👊", "effect": "sagrado"},
    "Katar do caos": {"damage": 105, "price": 21760, "level_req": 19, "category": "lutador", "emoji": "⚔️", "effect": "fogo"},
    "Nunchaku da tempestade": {"damage": 90, "price": 17850, "level_req": 16, "category": "lutador", "emoji": "🌀", "effect": "eletrico"},
    "Soco primordial": {"damage": 100, "price": 20400, "level_req": 18, "category": "lutador", "emoji": "👊", "effect": "perfurante"}
}


def get_all_weapons():
    def add_with_rarity(target, source, rarity):
        for name, data in source.items():
            if "rarity" not in data:
                data = data.copy()
                data["rarity"] = rarity
            target[name] = data

    merged = {}
    add_with_rarity(merged, common_weapons, "comum")
    add_with_rarity(merged, rare_weapons, "rara")
    add_with_rarity(merged, epic_weapons, "épica")
    add_with_rarity(merged, legendary_weapons, "lendária")
    add_with_rarity(merged, mythic_weapons, "mítica")
    return merged


def add_weapon_level_variants(base_weapons):
    expanded_weapons = dict(base_weapons)

    source_items = list(base_weapons.items())
    for weapon_name, weapon_data in source_items:
        if weapon_data.get("price", 0) <= 0:
            continue

        category = weapon_data.get("category")
        if category not in {"guerreiro", "mago", "arqueiro", "lutador", "geral"}:
            continue

        base_level = weapon_data["level_req"]
        base_damage = weapon_data["damage"]
        base_price = weapon_data["price"]

        for level_step in range(1, 6):
            target_level = min(25, base_level + level_step)
            if target_level == base_level:
                continue

            variant_name = f"{weapon_name} Lv {target_level}"
            if variant_name in expanded_weapons:
                continue

            damage_scale = 1.0 + (0.08 * level_step)
            price_scale = 1.0 + (0.12 * level_step)

            scaled_damage = max(base_damage + level_step, int(round(base_damage * damage_scale)))
            scaled_price = max(base_price + (10 * level_step), int(round((base_price * price_scale) / 10)) * 10)

            variant_data = weapon_data.copy()
            variant_data["damage"] = scaled_damage
            variant_data["price"] = scaled_price
            variant_data["level_req"] = target_level
            variant_data["base_weapon"] = weapon_name
            variant_data["is_level_variant"] = True

            expanded_weapons[variant_name] = variant_data

    return expanded_weapons


weapons = add_weapon_level_variants(get_all_weapons())

weapons_by_category = {
    "guerreiro": {k: v for k, v in weapons.items() if v.get("category") == "guerreiro"},
    "mago": {k: v for k, v in weapons.items() if v.get("category") == "mago"},
    "arqueiro": {k: v for k, v in weapons.items() if v.get("category") == "arqueiro"},
    "lutador": {k: v for k, v in weapons.items() if v.get("category") == "lutador"},
    "geral": {k: v for k, v in weapons.items() if v.get("category") == "geral"}
}

armors = {
    "Roupas velhas": {"defense": 1, "price": 0, "level_req": 1, "rarity": "comum", "emoji": "👕"},
    "Armadura de couro": {"defense": 3, "price": 100, "level_req": 1, "rarity": "comum", "emoji": "🛡️"},
    "Gibão de pele": {"defense": 4, "price": 135, "level_req": 2, "rarity": "comum", "emoji": "🧥"},
    "Cota de malha": {"defense": 6, "price": 200, "level_req": 3, "rarity": "comum", "emoji": "🛡️"},
    "Armadura de placas": {"defense": 10, "price": 500, "level_req": 4, "rarity": "rara", "emoji": "🛡️"},
    "Armadura de escamas": {"defense": 12, "price": 670, "level_req": 5, "rarity": "rara", "emoji": "🐉"},
    "Couraça de ferro": {"defense": 15, "price": 835, "level_req": 6, "rarity": "rara", "emoji": "🛡️"},
    "Armadura élfica": {"defense": 14, "price": 1340, "level_req": 7, "rarity": "épica", "emoji": "🧝"},
    "Armadura anã": {"defense": 16, "price": 1670, "level_req": 8, "rarity": "épica", "emoji": "⛰️"},
    "Armadura de dragão": {"defense": 18, "price": 2170, "level_req": 9, "rarity": "épica", "emoji": "🐲"},
    "Armadura divina": {"defense": 24, "price": 4170, "level_req": 10, "rarity": "lendária", "emoji": "👼"},
    "Armadura demoníaca": {"defense": 26, "price": 5010, "level_req": 11, "rarity": "lendária", "emoji": "👿"},
    "Armadura celestial": {"defense": 28, "price": 5840, "level_req": 12, "rarity": "lendária", "emoji": "✨"},
    "Armadura de Ainz": {"defense": 35, "price": 13360, "level_req": 15, "rarity": "mítica", "emoji": "👑"},
    "Armadura do vazio": {"defense": 40, "price": 20040, "level_req": 18, "rarity": "mítica", "emoji": "🌌"}
}


def add_armor_level_variants(base_armors):
    expanded_armors = dict(base_armors)

    source_items = list(base_armors.items())
    for armor_name, armor_data in source_items:
        if armor_data.get("price", 0) <= 0:
            continue

        base_level = armor_data["level_req"]
        base_defense = armor_data["defense"]
        base_price = armor_data["price"]

        for level_step in range(1, 6):
            target_level = min(25, base_level + level_step)
            if target_level == base_level:
                continue

            variant_name = f"{armor_name} Lv {target_level}"
            if variant_name in expanded_armors:
                continue

            defense_scale = 1.0 + (0.07 * level_step)
            price_scale = 1.0 + (0.12 * level_step)

            scaled_defense = max(base_defense + level_step, int(round(base_defense * defense_scale)))
            scaled_price = max(base_price + (10 * level_step), int(round((base_price * price_scale) / 10)) * 10)

            variant_data = armor_data.copy()
            variant_data["defense"] = scaled_defense
            variant_data["price"] = scaled_price
            variant_data["level_req"] = target_level
            variant_data["base_armor"] = armor_name
            variant_data["is_level_variant"] = True

            expanded_armors[variant_name] = variant_data

    return expanded_armors


armors = add_armor_level_variants(armors)
