from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
import random
import json
import logging
from datetime import datetime, timedelta
import time
import math
import asyncio
import threading
import os

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Arquivo de save
SAVE_FILE = "players.json"

# Lock para sincronizar saves em background - evita race conditions
save_lock = threading.Lock()

# Locks por usuário para evitar múltiplos cliques simultâneos (debounce)
user_action_locks = {}
user_action_timeout = {}

# Banco de dados em memória
players = {}

# Constantes do jogo
XP_BASE = 50
HP_BASE = 50  # Começa com menos vida (modo hardcore)
HP_PER_LEVEL = 20
DAMAGE_RANGE = (2, 5)  # Dano base reduzido (hardcore)
MONSTER_DAMAGE_RANGE = (5, 10)  # Dano base dos monstros aumentado
REST_HEAL = 8
REST_INTERVAL_SECONDS = 10 * 60
RANDOM_ENCOUNTER_CHANCE = 0.15  # 15% de chance de encontro
MERCHANT_POTION_NAME = "Poção pequena"
MERCHANT_DISCOUNT = 0.6

# Sistema de economia dinâmica da loja
DAILY_OFFERS = [
    {"type": "sell_bonus", "category": "misc", "bonus": 0.4, "text": "💰 Pagando 40% a mais por drops raros!"},
    {"type": "sell_bonus", "category": "weapon", "bonus": 0.3, "text": "⚔️ Comprando armas usadas por 30% a mais!"},
    {"type": "sell_bonus", "category": "armor", "bonus": 0.3, "text": "🛡️ Armaduras velhas valem 30% extra hoje!"},
    {"type": "buy_discount", "category": "potions", "bonus": 0.2, "text": "🧪 20% de desconto em todas as poções!"},
    {"type": "buy_discount", "category": "weapons", "bonus": 0.15, "text": "⚔️ 15% OFF em armas!"},
    {"type": "buy_discount", "category": "armors", "bonus": 0.15, "text": "🛡️ 15% OFF em armaduras!"},
]

# Cores e emojis
EMOJIS = {
    "comum": "⚪",
    "rara": "🔵",
    "épica": "🟣",
    "lendária": "🟡",
    "mítica": "🔴",
    "vida": "❤️",
    "vida_extra": "💚",
    "dano": "⚔️",
    "defesa": "🛡️",
    "ouro": "💰",
    "xp": "⭐",
    "veneno": "💚",  # Verde escuro para veneno
    "fogo": "🔥",
    "gelo": "❄️",
    "eletrico": "⚡"
}

# Classes do jogo
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

# Armas iniciais por classe
starting_weapons = {
    "Mago": "Graveto encantado",
    "Guerreiro": "Adaga enferrujada",
    "Arqueiro": "Estilingue",
    "Desempregado": "Punhos",
    "Lutador": "Bastão de madeira"
}

# ========== SISTEMA DE ARMAS REBALANCEADO ==========
# Agora com progressao mais lenta e precos mais realistas

# Constantes de balanceamento
PRICE_MULTIPLIER = {
    "comum": 1,
    "rara": 3,
    "épica": 8,
    "lendária": 20,
    "mítica": 50
}

DAMAGE_PER_LEVEL = {
    "comum": 2,
    "rara": 4,
    "épica": 7,
    "lendária": 12,
    "mítica": 20
}

# Categorias de armas por classe
weapon_categories = {
    "guerreiro": ["Espada", "Machado", "Martelo", "Lança"],
    "mago": ["Cajado", "Varinha", "Grimório", "Orbe"],
    "arqueiro": ["Arco", "Besta", "Adaga", "Shuriken"],
    "lutador": ["Manopla", "Soco", "Katar", "Nunchaku"],
    "geral": ["Punhos", "Adaga", "Bastão"]
}

# ===== ARMAS COMUNS (Nível 1-2) =====
# Preco: 40-75 gold | Dano: 2-5
common_weapons = {
    # Categoria Guerreiro
    "Espada de madeira": {"damage": 3, "price": 60, "level_req": 1, "category": "guerreiro", "emoji": "⚔️", "effect": None},
    "Machado de pedra": {"damage": 4, "price": 75, "level_req": 1, "category": "guerreiro", "emoji": "🪓", "effect": None},
    "Martelo de madeira": {"damage": 3, "price": 67, "level_req": 1, "category": "guerreiro", "emoji": "🔨", "effect": None},
    
    # Categoria Mago
    "Graveto encantado": {"damage": 2, "price": 52, "level_req": 1, "category": "mago", "emoji": "🪄", "effect": None},
    "Varinha de madeira": {"damage": 3, "price": 67, "level_req": 1, "category": "mago", "emoji": "✨", "effect": None},
    "Grimório básico": {"damage": 2, "price": 60, "level_req": 1, "category": "mago", "emoji": "📖", "effect": None},
    
    # Categoria Arqueiro
    "Arco curto": {"damage": 3, "price": 67, "level_req": 1, "category": "arqueiro", "emoji": "🏹", "effect": None},
    "Adaga enferrujada": {"damage": 2, "price": 45, "level_req": 1, "category": "arqueiro", "emoji": "🔪", "effect": None},
    "Estilingue": {"damage": 2, "price": 37, "level_req": 1, "category": "arqueiro", "emoji": "⚡", "effect": None},
    
    # Categoria Lutador
    "Manopla de couro": {"damage": 3, "price": 60, "level_req": 1, "category": "lutador", "emoji": "👊", "effect": None},
    "Soco inglês": {"damage": 4, "price": 75, "level_req": 1, "category": "lutador", "emoji": "🥊", "effect": None},
    "Bastão de madeira": {"damage": 3, "price": 52, "level_req": 1, "category": "lutador", "emoji": "🪵", "effect": None},
    
    # Categoria Geral (Disponível para todas as classes)
    "Punhos": {"damage": 0, "price": 0, "level_req": 1, "category": "geral", "emoji": "👊", "effect": None}
}

# ===== ARMAS RARAS (Nível 3-5) =====
# Preco: 450-800 gold | Dano: 8-15
rare_weapons = {
    # Categoria Guerreiro
    "Espada longa": {"damage": 12, "price": 600, "level_req": 3, "category": "guerreiro", "emoji": "⚔️", "effect": None},
    "Machado de guerra": {"damage": 14, "price": 680, "level_req": 4, "category": "guerreiro", "emoji": "🪓", "effect": "sangramento"},
    "Martelo de ferro": {"damage": 13, "price": 650, "level_req": 3, "category": "guerreiro", "emoji": "🔨", "effect": "atordoamento"},
    "Lança de cavaleiro": {"damage": 15, "price": 760, "level_req": 5, "category": "guerreiro", "emoji": "🏹", "effect": "perfurante"},
    
    # Categoria Mago
    "Cajado elemental": {"damage": 11, "price": 680, "level_req": 4, "category": "mago", "emoji": "🪄", "effect": "fogo"},
    "Varinha de cristal": {"damage": 10, "price": 650, "level_req": 3, "category": "mago", "emoji": "✨", "effect": "gelo"},
    "Grimório arcano": {"damage": 12, "price": 710, "level_req": 4, "category": "mago", "emoji": "📖", "effect": "eletrico"},
    "Orbe de vidro": {"damage": 9, "price": 600, "level_req": 3, "category": "mago", "emoji": "🔮", "effect": "veneno"},
    
    # Categoria Arqueiro
    "Arco longo": {"damage": 13, "price": 650, "level_req": 4, "category": "arqueiro", "emoji": "🏹", "effect": "perfurante"},
    "Besta leve": {"damage": 14, "price": 680, "level_req": 4, "category": "arqueiro", "emoji": "🎯", "effect": None},
    "Adaga de prata": {"damage": 10, "price": 540, "level_req": 3, "category": "arqueiro", "emoji": "🔪", "effect": "sangramento"},
    "Shuriken de aço": {"damage": 8, "price": 475, "level_req": 3, "category": "arqueiro", "emoji": "⭐", "effect": "veneno"},
    
    # Categoria Lutador
    "Manopla de ferro": {"damage": 12, "price": 610, "level_req": 3, "category": "lutador", "emoji": "👊", "effect": None},
    "Katar": {"damage": 13, "price": 660, "level_req": 4, "category": "lutador", "emoji": "⚔️", "effect": "sangramento"},
    "Nunchaku": {"damage": 10, "price": 540, "level_req": 3, "category": "lutador", "emoji": "🌀", "effect": "atordoamento"},
    "Soco de pedra": {"damage": 11, "price": 580, "level_req": 3, "category": "lutador", "emoji": "👊", "effect": None}
}

# ===== ARMAS ÉPICAS (Nível 6-8) =====
# Preco: 1600-2400 gold | Dano: 20-30
epic_weapons = {
    # Categoria Guerreiro
    "Espada de prata": {"damage": 25, "price": 2000, "level_req": 7, "category": "guerreiro", "emoji": "⚔️", "effect": "sagrado"},
    "Machado duplo": {"damage": 28, "price": 2250, "level_req": 8, "category": "guerreiro", "emoji": "🪓", "effect": "sangramento"},
    "Martelo de guerra": {"damage": 26, "price": 2080, "level_req": 7, "category": "guerreiro", "emoji": "🔨", "effect": "atordoamento"},
    "Lança dragão": {"damage": 30, "price": 2340, "level_req": 8, "category": "guerreiro", "emoji": "🏹", "effect": "perfurante"},
    
    # Categoria Mago
    "Cajado arcano": {"damage": 24, "price": 2170, "level_req": 7, "category": "mago", "emoji": "🪄", "effect": "eletrico"},
    "Varinha élfica": {"damage": 22, "price": 1920, "level_req": 6, "category": "mago", "emoji": "✨", "effect": "gelo"},
    "Grimório antigo": {"damage": 26, "price": 2340, "level_req": 8, "category": "mago", "emoji": "📖", "effect": "fogo"},
    "Orbe cristalino": {"damage": 20, "price": 1670, "level_req": 6, "category": "mago", "emoji": "🔮", "effect": "veneno"},
    
    # Categoria Arqueiro
    "Arco élfico": {"damage": 25, "price": 2080, "level_req": 7, "category": "arqueiro", "emoji": "🏹", "effect": "gelo"},
    "Besta pesada": {"damage": 28, "price": 2250, "level_req": 8, "category": "arqueiro", "emoji": "🎯", "effect": "perfurante"},
    "Adaga élfica": {"damage": 22, "price": 1840, "level_req": 6, "category": "arqueiro", "emoji": "🔪", "effect": "sangramento"},
    "Shuriken elemental": {"damage": 20, "price": 1670, "level_req": 6, "category": "arqueiro", "emoji": "⭐", "effect": "eletrico"},
    
    # Categoria Lutador
    "Manopla de prata": {"damage": 24, "price": 2000, "level_req": 7, "category": "lutador", "emoji": "👊", "effect": "sagrado"},
    "Katar flamejante": {"damage": 27, "price": 2170, "level_req": 8, "category": "lutador", "emoji": "⚔️", "effect": "fogo"},
    "Nunchaku de aço": {"damage": 22, "price": 1750, "level_req": 6, "category": "lutador", "emoji": "🌀", "effect": "atordoamento"},
    "Soco de trovão": {"damage": 25, "price": 1920, "level_req": 7, "category": "lutador", "emoji": "👊", "effect": "eletrico"}
}

# ===== ARMAS LENDÁRIAS (Nível 10-12) =====
# Preco: 5000-8500 gold | Dano: 40-60
legendary_weapons = {
    # Categoria Guerreiro
    "Espada flamejante": {"damage": 48, "price": 6800, "level_req": 11, "category": "guerreiro", "emoji": "⚔️", "effect": "fogo"},
    "Machado do trovão": {"damage": 52, "price": 7650, "level_req": 12, "category": "guerreiro", "emoji": "🪓", "effect": "eletrico"},
    "Martelo de gelo": {"damage": 45, "price": 6460, "level_req": 10, "category": "guerreiro", "emoji": "🔨", "effect": "gelo"},
    "Lança divina": {"damage": 55, "price": 8160, "level_req": 12, "category": "guerreiro", "emoji": "🏹", "effect": "sagrado"},
    
    # Categoria Mago
    "Cajado ancião": {"damage": 50, "price": 7140, "level_req": 11, "category": "mago", "emoji": "🪄", "effect": "eletrico"},
    "Varinha celestial": {"damage": 45, "price": 6460, "level_req": 10, "category": "mago", "emoji": "✨", "effect": "sagrado"},
    "Grimório das trevas": {"damage": 52, "price": 7480, "level_req": 11, "category": "mago", "emoji": "📖", "effect": "veneno"},
    "Orbe profético": {"damage": 42, "price": 6120, "level_req": 10, "category": "mago", "emoji": "🔮", "effect": "gelo"},
    
    # Categoria Arqueiro
    "Arco celestial": {"damage": 48, "price": 6800, "level_req": 11, "category": "arqueiro", "emoji": "🏹", "effect": "sagrado"},
    "Besta do caçador": {"damage": 52, "price": 7310, "level_req": 12, "category": "arqueiro", "emoji": "🎯", "effect": "perfurante"},
    "Adaga sombria": {"damage": 44, "price": 6290, "level_req": 10, "category": "arqueiro", "emoji": "🔪", "effect": "sangramento"},
    "Shuriken divina": {"damage": 40, "price": 5950, "level_req": 10, "category": "arqueiro", "emoji": "⭐", "effect": "eletrico"},
    
    # Categoria Lutador
    "Manopla divina": {"damage": 46, "price": 6630, "level_req": 11, "category": "lutador", "emoji": "👊", "effect": "sagrado"},
    "Katar do vento": {"damage": 50, "price": 6970, "level_req": 11, "category": "lutador", "emoji": "⚔️", "effect": "perfurante"},
    "Nunchaku elemental": {"damage": 42, "price": 6120, "level_req": 10, "category": "lutador", "emoji": "🌀", "effect": "eletrico"},
    "Soco do dragão": {"damage": 48, "price": 6800, "level_req": 11, "category": "lutador", "emoji": "👊", "effect": "fogo"}
}

# ===== ARMAS MÍTICAS (Nível 15+) =====
# Preco: 14000-24000 gold | Dano: 80-120
mythic_weapons = {
    # Categoria Guerreiro
    "Excalibur": {"damage": 100, "price": 20400, "level_req": 18, "category": "guerreiro", "emoji": "⚔️", "effect": "sagrado"},
    "Mjolnir": {"damage": 110, "price": 22950, "level_req": 20, "category": "guerreiro", "emoji": "🔨", "effect": "eletrico"},
    "Gungnir": {"damage": 105, "price": 21250, "level_req": 19, "category": "guerreiro", "emoji": "🏹", "effect": "perfurante"},
    "Espada do amanhã": {"damage": 95, "price": 18700, "level_req": 17, "category": "guerreiro", "emoji": "⚔️", "effect": "fogo"},
    
    # Categoria Mago
    "Cajado de Merlin": {"damage": 108, "price": 22100, "level_req": 20, "category": "mago", "emoji": "🪄", "effect": "eletrico"},
    "Varinha da realidade": {"damage": 98, "price": 19550, "level_req": 18, "category": "mago", "emoji": "✨", "effect": "sagrado"},
    "Grimório infinito": {"damage": 102, "price": 21250, "level_req": 19, "category": "mago", "emoji": "📖", "effect": "veneno"},
    "Orbe do tempo": {"damage": 92, "price": 17850, "level_req": 17, "category": "mago", "emoji": "🔮", "effect": "gelo"},
    
    # Categoria Arqueiro
    "Arco de Ártemis": {"damage": 98, "price": 20060, "level_req": 18, "category": "arqueiro", "emoji": "🏹", "effect": "gelo"},
    "Besta do apocalipse": {"damage": 112, "price": 23800, "level_req": 20, "category": "arqueiro", "emoji": "🎯", "effect": "fogo"},
    "Besta do destino": {"damage": 88, "price": 17000, "level_req": 16, "category": "arqueiro", "emoji": "🔪", "effect": "sangramento"},
    "Shuriken celestial": {"damage": 85, "price": 16150, "level_req": 15, "category": "arqueiro", "emoji": "⭐", "effect": "eletrico"},
    
    # Categoria Lutador
    "Manopla do infinito": {"damage": 95, "price": 18700, "level_req": 17, "category": "lutador", "emoji": "👊", "effect": "sagrado"},
    "Katar do caos": {"damage": 105, "price": 21760, "level_req": 19, "category": "lutador", "emoji": "⚔️", "effect": "fogo"},
    "Nunchaku da tempestade": {"damage": 90, "price": 17850, "level_req": 16, "category": "lutador", "emoji": "🌀", "effect": "eletrico"},
    "Soco primordial": {"damage": 100, "price": 20400, "level_req": 18, "category": "lutador", "emoji": "👊", "effect": "perfurante"}
}

# ===== FUNCAO PARA COMBINAR TODAS AS ARMAS =====
def get_all_weapons():
    """Combina todos os dicionarios de armas em um so"""
    def add_with_rarity(target, source, rarity):
        for name, data in source.items():
            if "rarity" not in data:
                data = data.copy()
                data["rarity"] = rarity
            target[name] = data

    weapons = {}
    add_with_rarity(weapons, common_weapons, "comum")
    add_with_rarity(weapons, rare_weapons, "rara")
    add_with_rarity(weapons, epic_weapons, "épica")
    add_with_rarity(weapons, legendary_weapons, "lendária")
    add_with_rarity(weapons, mythic_weapons, "mítica")
    return weapons

# Armas combinadas (use esta variavel no resto do codigo)
weapons = get_all_weapons()

# ===== ARMAS POR CATEGORIA (para facilitar a loja) =====
weapons_by_category = {
    "guerreiro": {k: v for k, v in weapons.items() if v.get("category") == "guerreiro"},
    "mago": {k: v for k, v in weapons.items() if v.get("category") == "mago"},
    "arqueiro": {k: v for k, v in weapons.items() if v.get("category") == "arqueiro"},
    "lutador": {k: v for k, v in weapons.items() if v.get("category") == "lutador"},
    "geral": {k: v for k, v in weapons.items() if v.get("category") == "geral"}
}

# ===== ARMAS POR RARIDADE (para facilitar drops) =====
weapons_by_rarity = {
    "comum": {k: v for k, v in weapons.items() if v.get("rarity") == "comum"},
    "rara": {k: v for k, v in weapons.items() if v.get("rarity") == "rara"},
    "épica": {k: v for k, v in weapons.items() if v.get("rarity") == "épica"},
    "lendária": {k: v for k, v in weapons.items() if v.get("rarity") == "lendária"},
    "mítica": {k: v for k, v in weapons.items() if v.get("rarity") == "mítica"}
}

# ===== ARMADURAS REBALANCEADAS =====
armors = {
    # Iniciais (nível 1)
    "Roupas velhas": {"defense": 1, "price": 0, "level_req": 1, "rarity": "comum", "emoji": "👕"},
    
    # Comuns (nível 1-3)
    "Armadura de couro": {"defense": 3, "price": 100, "level_req": 1, "rarity": "comum", "emoji": "🛡️"},
    "Gibão de pele": {"defense": 4, "price": 135, "level_req": 2, "rarity": "comum", "emoji": "🧥"},
    "Cota de malha": {"defense": 6, "price": 200, "level_req": 3, "rarity": "comum", "emoji": "🛡️"},
    
    # Raras (nível 4-6)
    "Armadura de placas": {"defense": 10, "price": 500, "level_req": 4, "rarity": "rara", "emoji": "🛡️"},
    "Armadura de escamas": {"defense": 12, "price": 670, "level_req": 5, "rarity": "rara", "emoji": "🐉"},
    "Couraça de ferro": {"defense": 15, "price": 835, "level_req": 6, "rarity": "rara", "emoji": "🛡️"},
    
    # Épicas (nível 7-9)
    "Armadura élfica": {"defense": 14, "price": 1340, "level_req": 7, "rarity": "épica", "emoji": "🧝"},
    "Armadura anã": {"defense": 16, "price": 1670, "level_req": 8, "rarity": "épica", "emoji": "⛰️"},
    "Armadura de dragão": {"defense": 18, "price": 2170, "level_req": 9, "rarity": "épica", "emoji": "🐲"},
    
    # Lendárias (nível 10-12)
    "Armadura divina": {"defense": 24, "price": 4170, "level_req": 10, "rarity": "lendária", "emoji": "👼"},
    "Armadura demoníaca": {"defense": 26, "price": 5010, "level_req": 11, "rarity": "lendária", "emoji": "👿"},
    "Armadura celestial": {"defense": 28, "price": 5840, "level_req": 12, "rarity": "lendária", "emoji": "✨"},
    
    # Míticas (nível 15+)
    "Armadura de Ainz": {"defense": 35, "price": 13360, "level_req": 15, "rarity": "mítica", "emoji": "👑"},
    "Armadura do vazio": {"defense": 40, "price": 20040, "level_req": 18, "rarity": "mítica", "emoji": "🌌"}
}

# ===== FUNCOES DE UTILIDADE PARA ARMAS =====
def get_weapons_by_level(level):
    """Retorna armas disponiveis para um determinado nivel"""
    available = {}
    for name, data in weapons.items():
        if data["level_req"] <= level:
            available[name] = data
    return available

def get_weapons_by_class(class_name, level):
    """Retorna armas disponiveis para uma classe especifica"""
    available = {}
    class_lower = class_name.lower()
    
    for name, data in weapons.items():
        if data["level_req"] <= level:
            if data["category"] == class_lower or data["category"] == "geral":
                available[name] = data
    
    return available

def get_random_weapon_drop(player_level, monster_level=1):
    """Gera um drop aleatorio de arma baseado no nivel do jogador E do monstro"""
    # Usa o menor level para determinar raridade máxima
    effective_level = min(player_level, monster_level)
    possible_rarities = []
    
    if effective_level <= 3:
        possible_rarities = ["comum"]
    elif effective_level <= 6:
        possible_rarities = ["comum", "rara"]
    elif effective_level <= 10:
        possible_rarities = ["comum", "rara", "épica"]
    elif effective_level <= 15:
        possible_rarities = ["rara", "épica", "lendária"]
    else:
        possible_rarities = ["épica", "lendária", "mítica"]
    
    # Escolhe raridade com pesos (mais comum tem mais chance)
    weights = []
    for rarity in possible_rarities:
        if rarity == "comum":
            weights.append(5)
        elif rarity == "rara":
            weights.append(3)
        elif rarity == "épica":
            weights.append(2)
        else:  # lendária, mítica
            weights.append(1)
    
    chosen_rarity = random.choices(possible_rarities, weights=weights)[0]
    
    # Filtra armas da raridade que o jogador pode usar
    rarity_weapons = {k: v for k, v in weapons.items() 
                      if v["rarity"] == chosen_rarity and v["level_req"] <= player_level and v["price"] > 0}
    
    if rarity_weapons:
        return random.choice(list(rarity_weapons.items()))
    return None

def get_random_armor_drop(player_level, monster_level=1):
    """Gera um drop aleatorio de armadura baseado no nivel do jogador E do monstro"""
    # Usa o menor level para determinar raridade máxima
    effective_level = min(player_level, monster_level)
    possible_rarities = []
    
    if effective_level <= 3:
        possible_rarities = ["comum"]
    elif effective_level <= 6:
        possible_rarities = ["comum", "rara"]
    elif effective_level <= 10:
        possible_rarities = ["comum", "rara", "épica"]
    elif effective_level <= 15:
        possible_rarities = ["rara", "épica", "lendária"]
    else:
        possible_rarities = ["épica", "lendária", "mítica"]
    
    # Escolhe raridade com pesos (mais comum tem mais chance)
    weights = []
    for rarity in possible_rarities:
        if rarity == "comum":
            weights.append(5)
        elif rarity == "rara":
            weights.append(3)
        elif rarity == "épica":
            weights.append(2)
        else:  # lendária, mítica
            weights.append(1)
    
    chosen_rarity = random.choices(possible_rarities, weights=weights)[0]
    
    # Filtra armaduras da raridade que o jogador pode usar
    rarity_armors = {k: v for k, v in armors.items() 
                     if v["rarity"] == chosen_rarity and v["level_req"] <= player_level and v["price"] > 0}
    
    if rarity_armors:
        return random.choice(list(rarity_armors.items()))
    return None

def get_random_common_armor_drop(player_level):
    """Gera um drop aleatorio de armadura comum (simples)"""
    common_armors = {k: v for k, v in armors.items()
                     if v["rarity"] == "comum" and v["level_req"] <= player_level and v["price"] > 0}

    if common_armors:
        return random.choice(list(common_armors.items()))
    return None

# Monstros com drops
monsters = [
    # ===== INICIANTES (Nível 1-3) =====
    {
        "name": "Slime", "hp": 40, "atk": 5, "xp": 15, "level": 1, "gold": 3,
        "drops": [
            {"item": "Poção pequena", "chance": 0.2},
            {"item": "Gosma de slime", "chance": 0.8}
        ],
        "effects": ["veneno"]
    },
    {
        "name": "Goblin", "hp": 70, "atk": 8, "xp": 25, "level": 2, "gold": 8,
        "drops": [
            {"item": "Poção pequena", "chance": 0.15},
            {"item": "Adaga", "chance": 0.1},
            {"item": "Ouro", "chance": 0.3}
        ],
        "effects": None
    },
    {
        "name": "Orc", "hp": 120, "atk": 14, "xp": 50, "level": 3, "gold": 15,
        "drops": [
            {"item": "Poção média", "chance": 0.15},
            {"item": "Espada enferrujada", "chance": 0.15},
            {"item": "Armadura de couro", "chance": 0.1}
        ],
        "effects": ["fogo"]
    },
    
    # ===== INTERMEDIÁRIOS (Nível 4-6) =====
    {
        "name": "Esqueleto", "hp": 160, "atk": 15, "xp": 80, "level": 4, "gold": 25,
        "drops": [
            {"item": "Poção média", "chance": 0.2},
            {"item": "Espada longa", "chance": 0.12},
            {"item": "Cota de malha", "chance": 0.1}
        ],
        "effects": ["gelo"]
    },
    {
        "name": "Ciclope", "hp": 240, "atk": 20, "xp": 120, "level": 5, "gold": 40,
        "drops": [
            {"item": "Poção grande", "chance": 0.2},
            {"item": "Espada de prata", "chance": 0.1},
            {"item": "Armadura de placas", "chance": 0.1}
        ],
        "effects": ["eletrico"]
    },
    {
        "name": "Troll", "hp": 300, "atk": 22, "xp": 150, "level": 6, "gold": 50,
        "drops": [
            {"item": "Poção grande", "chance": 0.2},
            {"item": "Martelo de guerra", "chance": 0.1},
            {"item": "Armadura de escamas", "chance": 0.1}
        ],
        "effects": ["sangramento"]
    },
    
    # ===== AVANÇADOS (Nível 7-10) =====
    {
        "name": "Dragão jovem", "hp": 360, "atk": 30, "xp": 200, "level": 7, "gold": 80,
        "drops": [
            {"item": "Poção grande", "chance": 0.25},
            {"item": "Espada flamejante", "chance": 0.08},
            {"item": "Armadura divina", "chance": 0.06}
        ],
        "effects": ["fogo", "veneno"]
    },
    {
        "name": "Basilisco", "hp": 400, "atk": 35, "xp": 220, "level": 8, "gold": 100,
        "drops": [
            {"item": "Poção grande", "chance": 0.25},
            {"item": "Machado do trovão", "chance": 0.1},
            {"item": "Armadura anã", "chance": 0.08}
        ],
        "effects": ["veneno", "gelo"]
    },
    {
        "name": "Espectro", "hp": 320, "atk": 38, "xp": 240, "level": 9, "gold": 120,
        "drops": [
            {"item": "Poção grande", "chance": 0.2},
            {"item": "Varinha de cristal", "chance": 0.1},
            {"item": "Couraça de ferro", "chance": 0.08}
        ],
        "effects": ["eletrico", "sangramento"]
    },
    {
        "name": "Quimera", "hp": 480, "atk": 42, "xp": 300, "level": 10, "gold": 150,
        "drops": [
            {"item": "Poção grande", "chance": 0.25},
            {"item": "Espada de prata", "chance": 0.12},
            {"item": "Armadura de dragão", "chance": 0.1}
        ],
        "effects": ["fogo", "gelo", "eletrico"]
    },
    
    # ===== EXPERTS (Nível 11-15) =====
    {
        "name": "Lich", "hp": 280, "atk": 48, "xp": 300, "level": 11, "gold": 220,
        "drops": [
            {"item": "Poção grande", "chance": 0.45},
            {"item": "Grimório antigo", "chance": 0.15},
            {"item": "Armadura élfica", "chance": 0.12}
        ],
        "effects": ["veneno", "eletrico"]
    },
    {
        "name": "Cerberus", "hp": 320, "atk": 52, "xp": 350, "level": 12, "gold": 260,
        "drops": [
            {"item": "Poção grande", "chance": 0.45},
            {"item": "Machado duplo", "chance": 0.15},
            {"item": "Armadura celestial", "chance": 0.12}
        ],
        "effects": ["fogo", "sangramento"]
    },
    {
        "name": "Fênix", "hp": 300, "atk": 55, "xp": 400, "level": 13, "gold": 300,
        "drops": [
            {"item": "Poção grande", "chance": 0.5},
            {"item": "Cajado arcano", "chance": 0.15},
            {"item": "Armadura divina", "chance": 0.12}
        ],
        "effects": ["fogo", "fogo"]
    },
    {
        "name": "Leviatã", "hp": 360, "atk": 60, "xp": 450, "level": 14, "gold": 350,
        "drops": [
            {"item": "Poção grande", "chance": 0.5},
            {"item": "Lança dragão", "chance": 0.15},
            {"item": "Armadura demoníaca", "chance": 0.12}
        ],
        "effects": ["gelo", "eletrico"]
    },
    {
        "name": "Titã da Floresta", "hp": 400, "atk": 65, "xp": 500, "level": 15, "gold": 400,
        "drops": [
            {"item": "Poção grande", "chance": 0.5},
            {"item": "Katar flamejante", "chance": 0.15},
            {"item": "Armadura ancião", "chance": 0.12}
        ],
        "effects": ["fogo", "gelo", "eletrico"]
    },
    
    # ===== HERÓICOS (Nível 16-20) =====
    {
        "name": "Demônio das Chamas", "hp": 450, "atk": 72, "xp": 600, "level": 16, "gold": 500,
        "drops": [
            {"item": "Poção grande", "chance": 0.55},
            {"item": "Espada flamejante", "chance": 0.15},
            {"item": "Armadura demoníaca", "chance": 0.15}
        ],
        "effects": ["fogo", "fogo", "fogo"]
    },
    {
        "name": "Gólem de Gelo", "hp": 420, "atk": 68, "xp": 550, "level": 17, "gold": 480,
        "drops": [
            {"item": "Poção grande", "chance": 0.55},
            {"item": "Martelo de gelo", "chance": 0.15},
            {"item": "Armadura celestial", "chance": 0.15}
        ],
        "effects": ["gelo", "gelo"]
    },
    {
        "name": "Dragão Antigo", "hp": 500, "atk": 78, "xp": 700, "level": 18, "gold": 600,
        "drops": [
            {"item": "Poção grande", "chance": 0.6},
            {"item": "Grimore infinito", "chance": 0.18},
            {"item": "Armadura de Ainz", "chance": 0.15}
        ],
        "effects": ["fogo", "veneno", "sangramento"]
    },
    {
        "name": "Senhor da Noite", "hp": 520, "atk": 82, "xp": 750, "level": 19, "gold": 650,
        "drops": [
            {"item": "Poção grande", "chance": 0.6},
            {"item": "Varinha celestial", "chance": 0.18},
            {"item": "Armadura do vazio", "chance": 0.15}
        ],
        "effects": ["eletrico", "sangramento", "gelo"]
    },
    {
        "name": "Rei Esqueleto", "hp": 550, "atk": 88, "xp": 800, "level": 20, "gold": 700,
        "drops": [
            {"item": "Poção grande", "chance": 0.6},
            {"item": "Soco do dragão", "chance": 0.18},
            {"item": "Armadura ancião", "chance": 0.15}
        ],
        "effects": ["veneno", "fogo", "eletrico"]
    },
    
    # ===== LENDÁRIOS (Nível 21+) =====
    {
        "name": "Rei Demônio", "hp": 600, "atk": 95, "xp": 900, "level": 21, "gold": 800,
        "drops": [
            {"item": "Poção grande", "chance": 0.65},
            {"item": "Excalibur", "chance": 0.2},
            {"item": "Armadura de Ainz", "chance": 0.18}
        ],
        "effects": ["fogo", "veneno", "eletrico", "gelo"]
    },
    {
        "name": "Divindade Caída", "hp": 650, "atk": 100, "xp": 1000, "level": 22, "gold": 900,
        "drops": [
            {"item": "Poção grande", "chance": 0.65},
            {"item": "Mjolnir", "chance": 0.2},
            {"item": "Armadura do vazio", "chance": 0.18}
        ],
        "effects": ["eletrico", "sagrado"]
    },
    {
        "name": "Entidade Ancestral", "hp": 700, "atk": 105, "xp": 1100, "level": 23, "gold": 1000,
        "drops": [
            {"item": "Poção grande", "chance": 0.7},
            {"item": "Gungnir", "chance": 0.22},
            {"item": "Armadura divina", "chance": 0.2}
        ],
        "effects": ["fogo", "gelo", "eletrico", "veneno"]
    },
    {
        "name": "Abissal", "hp": 750, "atk": 110, "xp": 1200, "level": 24, "gold": 1100,
        "drops": [
            {"item": "Poção grande", "chance": 0.7},
            {"item": "Cajado de Merlin", "chance": 0.22},
            {"item": "Armadura de Ainz", "chance": 0.2}
        ],
        "effects": ["veneno", "sangramento", "sagrado"]
    },
    {
        "name": "Titã Eterno", "hp": 800, "atk": 120, "xp": 1500, "level": 25, "gold": 1300,
        "drops": [
            {"item": "Poção grande", "chance": 0.75},
            {"item": "Varinha da realidade", "chance": 0.25},
            {"item": "Armadura do vazio", "chance": 0.22}
        ],
        "effects": ["fogo", "gelo", "eletrico", "veneno", "sangramento"]
    }
]

# ===== MAPEAMENTO DE IMAGENS DOS MONSTROS =====
# Base URL para as imagens no GitHub
BASE_IMAGE_URL = "https://raw.githubusercontent.com/csbarcellos-tk/jogorpg-assets/main/images"

MONSTER_IMAGES = {
    # Bosses Finais
    "Leviatã": f"{BASE_IMAGE_URL}/leviatan.png",
    "Fênix": f"{BASE_IMAGE_URL}/fenix.png",
    "Lich": f"{BASE_IMAGE_URL}/lich.png",
    
    # Dragões
    "Dragão Jovem": f"{BASE_IMAGE_URL}/dragao_jovem.png",
    
    # Clássicos
    "Slime": f"{BASE_IMAGE_URL}/Slime.png",
    "Goblin": f"{BASE_IMAGE_URL}/goblin.png",
    "Orc": f"{BASE_IMAGE_URL}/orc.png",
    "Esqueleto": f"{BASE_IMAGE_URL}/esqueleto.png",
    "Troll": f"{BASE_IMAGE_URL}/troll.png",
    
    # Lendários
    "Basilisco": f"{BASE_IMAGE_URL}/basilisco.png",
    "Quimera": f"{BASE_IMAGE_URL}/quimera.png",
    "Ciclope": f"{BASE_IMAGE_URL}/ciclope.png",
    
    # Elementais e Gigantes
    "Golem de Gelo": f"{BASE_IMAGE_URL}/golem_de_gelo.png",
    "Abissal": f"{BASE_IMAGE_URL}/abissal.png",
    "Cerberus": f"{BASE_IMAGE_URL}/cerberus.png",
    "Demonio das Chamas": f"{BASE_IMAGE_URL}/demonio_das_chamas.png",
    "Divindade Caída": f"{BASE_IMAGE_URL}/divindade_caida.png",
    "Dragão Antigo": f"{BASE_IMAGE_URL}/dragao_antigo.png",
    "Entidade Ancestral": f"{BASE_IMAGE_URL}/entidade_ancestral.png",
    "Espectro": f"{BASE_IMAGE_URL}/espectro.png",
    "Fênix": f"{BASE_IMAGE_URL}/fenix.png",
    "Rei Demonio": f"{BASE_IMAGE_URL}/rei_demonio.png",
    "Rei Esqueleto": f"{BASE_IMAGE_URL}/rei_esqueleto.png",
    "Senhor da Noite": f"{BASE_IMAGE_URL}/senhor_da_noite.png",
    "Titã da Floresta": f"{BASE_IMAGE_URL}/tita_da_floresta.png",
    "Titã Eterno": f"{BASE_IMAGE_URL}/tita_eterno.png",
}

# ===== MAPEAMENTO DE IMAGENS DAS CLASSES =====
CLASS_IMAGES = {
    "Guerreiro": f"{BASE_IMAGE_URL}/classe_guerreiro.png",
    "Mago": f"{BASE_IMAGE_URL}/classe_mago.png",
    "Arqueiro": f"{BASE_IMAGE_URL}/classe_arqueiro.png",
    "Lutador": f"{BASE_IMAGE_URL}/classe_lutador.png",
    "Desempregado": f"{BASE_IMAGE_URL}/classe_desempregado.png",
}

# ===== IMAGENS DA LOJA E VENDEDOR AMBULANTE =====
SHOP_IMAGE = f"{BASE_IMAGE_URL}/loja.png"
MERCHANT_IMAGES = [
    f"{BASE_IMAGE_URL}/vendedor_ambulante.png",
    f"{BASE_IMAGE_URL}/vendedor_ambulante2.png"
]

# Itens consumíveis
consumables = {
    "Poção pequena": {"heal": 20, "price": 40, "emoji": "🧪", "effect": None},
    "Poção média": {"heal": 40, "price": 90, "emoji": "🧪", "effect": None},
    "Poção grande": {"heal": 80, "price": 180, "emoji": "🧪", "effect": None},
    "Antídoto": {"heal": 10, "price": 50, "emoji": "💊", "effect": "cura_veneno"},
    "Poção de vida extra": {"heal": 30, "price": 120, "emoji": "💚", "effect": "vida_extra"},
    "Elixir de força": {"damage_bonus": 5, "duration": 3, "price": 150, "emoji": "💪", "effect": "buff"},
    "Elixir de defesa": {"defense_bonus": 3, "duration": 3, "price": 150, "emoji": "🛡️", "effect": "buff"}
}

# Itens diversos (drops)
misc_items = {
    "Gosma de slime": {"price": 5, "emoji": "💧", "description": "Restos de slime"},
    "Ouro": {"price": 1, "emoji": "💰", "description": "Moedas de ouro"},
    "Osso": {"price": 3, "emoji": "🦴", "description": "Osso de esqueleto"},
    "Pele de orc": {"price": 8, "emoji": "🧶", "description": "Pele grossa de orc"},
    "Olho de ciclope": {"price": 15, "emoji": "👁️", "description": "Olho mágico"},
    "Escama de dragão": {"price": 50, "emoji": "🐉", "description": "Escama rara"}
}

def _save_players_sync():
    """Função síncrona que realiza a gravação de arquivo (thread-safe com lock)"""
    with save_lock:  # Lock evita múltiplas threads escrevendo simultaneamente
        try:
            # Converte objetos não serializáveis
            players_serializable = {}
            for user_id, player_data in players.items():
                players_serializable[user_id] = player_data.copy()
                
                # Converte datetime para string
                for key in ["created_at", "last_daily", "last_hunt", "last_rest"]:
                    if key in player_data and player_data[key]:
                        if isinstance(player_data[key], datetime):
                            players_serializable[user_id][key] = player_data[key].isoformat()
                        else:
                            players_serializable[user_id][key] = str(player_data[key]) if player_data[key] else None
            
            with open(SAVE_FILE, "w", encoding='utf-8') as f:
                json.dump(players_serializable, f, ensure_ascii=False, indent=2)
            logging.debug(f"Jogadores salvos com sucesso! Total: {len(players)}")
        except Exception as e:
            logging.error(f"Erro ao salvar jogadores: {e}")

async def _save_players_async():
    """Função assíncrona real que executa em thread"""
    await asyncio.to_thread(_save_players_sync)

def save_players_background(context: ContextTypes.DEFAULT_TYPE = None):
    """Salva jogadores em background sem bloquear - fire-and-forget
    Thread-safe com lock para evitar race conditions."""
    # Executa em thread de I/O separada
    threading.Thread(target=_save_players_sync, daemon=True).start()

async def save_players():
    """Salva os dados dos jogadores em arquivo de forma assíncrona (compatibilidade)"""
    await _save_players_async()

def check_user_action_cooldown(user_id: str, cooldown_seconds: float = 0.5) -> bool:
    """Verifica se o usuário está em cooldown de ações (debounce para múltiplos cliques)
    Retorna True se OK, False se ainda em cooldown"""
    global user_action_timeout
    
    now = time.time()
    last_action = user_action_timeout.get(user_id, 0)
    
    if now - last_action < cooldown_seconds:
        return False  # Ainda em cooldown
    
    user_action_timeout[user_id] = now
    return True  # OK - pode executar ação

def load_players():
    """Carrega os dados dos jogadores do arquivo"""
    global players
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, "r", encoding='utf-8') as f:
                players_loaded = json.load(f)
            
            # Converte strings de volta para datetime
            players = {}
            for user_id, player_data in players_loaded.items():
                players[user_id] = player_data
                for key in ["created_at", "last_daily", "last_hunt", "last_rest"]:
                    if key in player_data and player_data[key]:
                        try:
                            players[user_id][key] = datetime.fromisoformat(player_data[key])
                        except:
                            players[user_id][key] = None
            
            logging.info(f"Jogadores carregados! Total: {len(players)}")
    except Exception as e:
        logging.error(f"Erro ao carregar jogadores: {e}")
        players = {}

def xp_needed(level):
    """Calcula XP necessário para o próximo nível"""
    return XP_BASE * level * 2

def total_xp_for_level(level):
    """Calcula o XP total acumulado até o nível atual"""
    total = 0
    for lv in range(1, level):
        total += xp_needed(lv)
    return total

def get_total_xp(level, current_xp):
    """Retorna o XP total do jogador (acumulado + atual)"""
    return total_xp_for_level(level) + current_xp

def get_rank(level):
    """Retorna o rank (patente) do jogador baseado no nível"""
    ranks = [
        (1, 3, "Desocupado", "😴"),
        (4, 7, "Aprendiz", "🔰"),
        (8, 12, "Aventureiro", "🎖️"),
        (13, 18, "Guerreiro", "⚔️"),
        (19, 25, "Herói", "👑"),
        (26, 32, "Lendário", "✨"),
        (33, 40, "Mestre", "🔱"),
        (41, 50, "Divino", "⚡"),
        (51, float('inf'), "Imortal", "👹")
    ]
    
    for min_level, max_level, rank_name, emoji in ranks:
        if min_level <= level <= max_level:
            return f"{emoji} {rank_name}"
    
    return "😴 Desconhecido"

def format_rest_time(seconds_left):
    """Formata o tempo restante do descanso"""
    seconds_left = max(0, int(seconds_left))
    minutes = seconds_left // 60
    seconds = seconds_left % 60
    return f"{minutes}m {seconds}s"

def rest_progress_bar(current_seconds, total_seconds=REST_INTERVAL_SECONDS, length=10):
    """Cria barra de progresso do descanso"""
    if total_seconds <= 0:
        return "⬜️" * length
    filled = int((current_seconds / total_seconds) * length)
    filled = min(length, max(0, filled))
    return "🟩" * filled + "⬜️" * (length - filled)

def get_rarity_emoji(rarity):
    """Retorna emoji baseado na raridade"""
    emojis = {
        "comum": "⚪",
        "rara": "🔵",
        "épica": "🟣",
        "lendária": "🟡",
        "mítica": "🔴"
    }
    return emojis.get(rarity, "⚪")

def get_class_damage_bonus(class_name, level):
    """Escala o bonus de dano da classe pelo nivel"""
    base_bonus = classes[class_name]["damage_bonus"]
    scaled = math.floor(base_bonus * (max(1, level) / 10))
    return max(0, scaled)

def get_class_crit_chance(class_name, level):
    """Calcula chance de crítico da classe baseado no level"""
    base_level = max(1, level - 1)  # Começa no level 0 para level 1
    
    if class_name == "Arqueiro":
        # 15% base + 1% por level
        return 0.15 + (base_level * 0.01)
    elif class_name == "Mago":
        # 10% base + 2% por level
        return 0.10 + (base_level * 0.02)
    elif class_name == "Lutador" or class_name == "Guerreiro" or class_name == "Desempregado":
        # 5% base (igual para todos)
        return 0.05
    
    return 0.05

def get_class_defense_bonus(class_name, level):
    """Calcula bônus de defesa da classe baseado no level"""
    base_level = max(1, level - 1)  # Começa no level 0 para level 1
    
    if class_name == "Guerreiro":
        # 5 defesa base + 2 por level
        return 5 + (base_level * 2)
    
    return 0

def get_class_damage_scaling(class_name, level):
    """Calcula bônus de dano por percentual para classes específicas"""
    base_level = max(1, level - 1)  # Começa no level 0 para level 1
    
    if class_name == "Lutador":
        # 5 dano base + 2% por level (multiplicador: 1.05 + 0.02*level)
        return 1.0 + 0.05 + (base_level * 0.02)
    
    return 1.0

def hp_bar(current, maximum, effects=None):
    """Cria uma barra de vida visual com efeitos"""
    bar_length = 15
    filled = int((current / maximum) * bar_length)
    
    # Define a cor baseada nos efeitos
    if effects:
        if "veneno" in effects:
            bar_char = "💚"  # Verde para veneno
        elif "fogo" in effects:
            bar_char = "🔥"  # Fogo
        elif "gelo" in effects:
            bar_char = "❄️"  # Gelo
        elif "eletrico" in effects:
            bar_char = "⚡"  # Elétrico
        else:
            bar_char = "❤️"
    else:
        bar_char = "❤️"
    
    # Se tiver vida extra, mostra em verde diferente
    extra_healing = False
    if current > maximum:
        bar_char = "💚"
        extra_healing = True
    
    bar = bar_char * filled + "🖤" * (bar_length - filled)
    
    if extra_healing:
        return f"💚 Vida: {bar} {current}/{maximum} (Vida extra!)"
    else:
        return f"{bar_char} Vida: {bar} {current}/{maximum}"

def hp_bar_blocks(current, maximum, length=8):
    """Cria uma barra de vida em blocos para o combate"""
    if maximum <= 0:
        filled = 0
    else:
        filled = int((current / maximum) * length)
        if current > 0:
            filled = max(1, filled)
    filled = min(length, max(0, filled))
    return "🟥" * filled + "⬜️" * (length - filled)

def format_combat_status(header, monster, player, turn, show_monster_icon=True):
    """Monta o layout do combate em texto"""
    monster_name = f"👹 {monster['name']}" if show_monster_icon else monster["name"]
    monster_bar = hp_bar_blocks(monster["hp"], monster["max_hp"])
    player_bar = hp_bar_blocks(player["hp"], player["max_hp"])
    monster_effects_text = ""
    if player.get("monster_effects"):
        monster_effects_text = f"\n⚠️ Efeitos no monstro: {', '.join(player['monster_effects'])}"
    player_effects_text = ""
    active_buffs = [buff["name"] for buff in player.get("buffs", []) if buff.get("duration", 0) > 0]
    if active_buffs:
        player_effects_text = f"\n⚠️ Seus efeitos: {', '.join(active_buffs)}"
    return (
        f"{header}\n"
        f"{monster_name}\n"
        f"❤️ HP: {monster['hp']}/{monster['max_hp']}\n"
        f"{monster_bar}"
        f"{monster_effects_text}\n\n"
        f"👤 Você\n"
        f"❤️ HP: {player['hp']}/{player['max_hp']}\n"
        f"{player_bar}\n"
        f"🎯 Turno: {turn}"
        f"{player_effects_text}"
    )

def get_daily_offer():
    """Retorna a oferta do dia baseada na data atual"""
    # Usa o dia do ano para determinar a oferta (muda todo dia)
    day_of_year = datetime.now().timetuple().tm_yday
    offer_index = day_of_year % len(DAILY_OFFERS)
    return DAILY_OFFERS[offer_index]

def calculate_sell_price(item_name, base_price, item_type):
    """Calcula o preço de venda com base na oferta do dia"""
    offer = get_daily_offer()
    sell_price = int(base_price * 0.4)  # Base: 40% do preço original
    
    # Aplica bônus se for oferta de venda para essa categoria
    if offer["type"] == "sell_bonus":
        if (offer["category"] == "misc" and item_type == "misc") or \
           (offer["category"] == "weapon" and item_type == "weapon") or \
           (offer["category"] == "armor" and item_type == "armor"):
            bonus = int(sell_price * offer["bonus"])
            sell_price += bonus
    
    return sell_price

def calculate_buy_price(item_price, category):
    """Calcula o preço de compra com base na oferta do dia"""
    offer = get_daily_offer()
    buy_price = item_price
    
    # Aplica desconto se for oferta de compra para essa categoria
    if offer["type"] == "buy_discount" and offer["category"] == category:
        discount = int(buy_price * offer["bonus"])
        buy_price -= discount
    
    return buy_price

async def clean_chat(context, chat_id, message_id):
    """Apaga mensagem anterior para não poluir o chat"""
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia um novo personagem - AGORA SEM DINHEIRO E SEM ITENS"""
    user_id = str(update.effective_user.id)
    
    # Limpa chat anterior se existir
    if "last_message" in context.user_data:
        await clean_chat(context, update.effective_chat.id, context.user_data["last_message"])
    
    # Menu de escolha de classe (agora com descrição completa)
    keyboard = []
    for class_name, class_data in classes.items():
        # Descrição completa sem cortes
        desc = class_data['description']
        keyboard.append([
            InlineKeyboardButton(
                f"{class_data['emoji']} {class_name} - {desc}",
                callback_data=f"class_{class_name}"
            )
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = await update.message.reply_text(
        f"🎮 **Bem-vindo ao RPG Adventure HARDCORE!**\n\n"
        f"Comece sua jornada do zero:\n"
        f"❌ Sem dinheiro\n"
        f"❌ Sem poções\n"
        f"❌ Sem XP\n"
        f"❌ Sem equipamentos\n\n"
        f"**Escolha sua classe:**\n"
        f"(O Desempregado é o modo hardcore - sem bônus!)",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    context.user_data["last_message"] = msg.message_id

async def class_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a escolha da classe"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    class_name = query.data.replace("class_", "")
    class_data = classes[class_name]
    starting_weapon = starting_weapons.get(class_name, "Punhos")
    
    # Cria personagem SEM NADA (modo hardcore)
    players[user_id] = {
        "name": None,  # Nome será escolhido depois
        "class": class_name,
        "hp": HP_BASE + class_data["hp_bonus"],
        "max_hp": HP_BASE + class_data["hp_bonus"],
        "base_hp": HP_BASE + class_data["hp_bonus"],  # HP base sem buffs
        "xp": 0,  # Começa sem XP
        "level": 1,
        "weapon": starting_weapon,
        "armor": "Roupas velhas",
        "inventory": {},  # Inventário vazio
        "equipped_weapons": [starting_weapon],  # Armas que possui
        "equipped_armors": ["Roupas velhas"],  # Armaduras que possui
        "gold": 0,  # Começa sem dinheiro
        "monster": None,
        "buffs": [],
        "effects": [],  # Efeitos atuais (veneno, fogo, etc)
        "created_at": datetime.now(),
        "last_daily": None,
        "last_hunt": None,
        "last_rest": None,
        "current_map": "Floresta da Perdição",
        "monster_effects": []  # Efeitos do monstro no jogador
    }
    
    await save_players()
    
    # Agora pede o nome do personagem
    keyboard = [[InlineKeyboardButton("🎲 Nome aleatorio", callback_data="random_name")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    class_image = CLASS_IMAGES.get(class_name)
    message_text = (
        f"✅ Classe escolhida: {class_name} {class_data['emoji']}\n\n"
        f"📝 **Digite o nome do seu personagem:**\n"
        f"(Envie uma mensagem com o nome desejado)"
    )

    if class_image:
        try:
            await query.message.reply_photo(
                photo=class_image,
                caption=message_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            await query.delete_message()
        except Exception:
            await query.edit_message_text(
                message_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    else:
        await query.edit_message_text(
            message_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    # Guarda que está aguardando nome
    context.user_data["awaiting_name"] = True

def generate_random_name():
    """Gera um nome aleatorio simples"""
    prefixes = ["Astra", "Brasa", "Cifra", "Duna", "Eter", "Ferro", "Gelo", "Luz", "Nexo", "Sombra"]
    suffixes = ["dorn", "fire", "grim", "lume", "mora", "nox", "rune", "vale", "ward", "zen"]
    return f"{random.choice(prefixes)}{random.choice(suffixes)}"

async def complete_character_creation(user_id, name, update, context):
    """Finaliza criacao do personagem com nome definido"""
    players[user_id]["name"] = name
    context.user_data["awaiting_name"] = False

    # Limpa mensagem anterior
    if "last_message" in context.user_data:
        await clean_chat(context, update.effective_chat.id, context.user_data["last_message"])

    keyboard = [
        [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
        [InlineKeyboardButton("🏪 Loja", callback_data="shop")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        f"🎉 **Personagem criado com sucesso!**\n\n"
        f"👤 **Nome:** {name}\n"
        f"📚 **Classe:** {players[user_id]['class']}\n"
        f"❤️ **HP:** {players[user_id]['hp']}\n"
        f"⚔️ **Arma:** {players[user_id]['weapon']}\n"
        f"🛡️ **Armadura:** Roupas velhas\n"
        f"💰 **Gold:** 0\n\n"
        f"**Agora você começa do zero! Boa sorte!** 🍀"
    )

    class_image = CLASS_IMAGES.get(players[user_id]["class"])
    if class_image:
        try:
            msg = await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=class_image,
                caption=message_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception:
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
    else:
        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    context.user_data["last_message"] = msg.message_id
    await save_players()

async def set_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Define o nome do personagem"""
    user_id = str(update.effective_user.id)

    if user_id not in players or not context.user_data.get("awaiting_name"):
        return

    name = update.message.text[:20]  # Limita tamanho do nome
    await complete_character_creation(user_id, name, update, context)

async def random_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Define um nome aleatorio para o personagem"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)

    if user_id not in players or not context.user_data.get("awaiting_name"):
        return

    name = generate_random_name()
    await complete_character_creation(user_id, name, update, context)

async def merchant_buy_potion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compra com desconto no vendedor ambulante"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return

    player = players[user_id]
    base_price = consumables[MERCHANT_POTION_NAME]["price"]
    discount_price = max(1, int(base_price * MERCHANT_DISCOUNT))

    if player["gold"] < discount_price:
        keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, 
            "❌ Gold insuficiente para comprar com o vendedor.",
            reply_markup=reply_markup
        )
        return

    player["gold"] -= discount_price
    player["inventory"][MERCHANT_POTION_NAME] = player["inventory"].get(MERCHANT_POTION_NAME, 0) + 1
    await save_players()

    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await edit_callback_message(query, f"✅ Comprou {MERCHANT_POTION_NAME} por {discount_price}💰.",
        reply_markup=reply_markup
    )

async def merchant_duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia duelo hardcore com o vendedor ambulante"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return

    player = players[user_id]
    if player.get("monster"):
        await edit_callback_message(query, "❌ Você já está em combate!")
        return

    merchant = {
        "name": "Vendedor ambulante",
        "hp": 800,
        "max_hp": 800,
        "atk": 90,
        "xp": 0,
        "gold": 0,
        "level": 20,
        "drops": [],
        "effects": []
    }

    player["monster"] = merchant
    player["monster_effects"] = []
    player["combat_turn"] = 1
    await save_players()

    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data="attack")],
        [InlineKeyboardButton("🎒 Usar item", callback_data="use_item_menu")],
        [InlineKeyboardButton("🏃 Fugir", callback_data="flee")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await edit_callback_message(query, 
        format_combat_status(
            "⚔️ DUELO INSANO",
            merchant,
            player,
            player["combat_turn"],
            show_monster_icon=True
        ),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def send_combat_message(query, monster, player, header, turn):
    """Envia mensagem de combate com foto se existir"""
    combat_text = format_combat_status(header, monster, player, turn, show_monster_icon=True)
    monster_image = MONSTER_IMAGES.get(monster["name"])
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data="attack")],
        [InlineKeyboardButton("🎒 Usar item", callback_data="use_item_menu")],
        [InlineKeyboardButton("🏃 Fugir", callback_data="flee")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if monster_image:
        try:
            has_photo = getattr(query.message, "photo", None)
            
            # Primeira vez de combate: deleta msg anterior e envia nova (mudança de contexto)
            if turn == 1 and has_photo:
                try:
                    await query.delete_message()
                except:
                    pass
                # Envia nova mensagem com imagem do monstro
                await query.message.reply_photo(
                    photo=monster_image,
                    caption=combat_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            elif has_photo:
                # Já em combate: apenas edita texto (mantém imagem)
                try:
                    await query.edit_message_caption(
                        caption=combat_text,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                except:
                    # Se falhar edit_caption, tenta text
                    await query.edit_message_text(combat_text, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                # Sem foto: envia nova com foto
                await query.message.reply_photo(
                    photo=monster_image,
                    caption=combat_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                await query.delete_message()
        except Exception as e:
            # Último fallback: apenas texto
            logging.warning(f"Erro ao enviar mensagem de combate: {e}")
            try:
                await query.edit_message_text(combat_text, parse_mode='Markdown', reply_markup=reply_markup)
            except:
                pass
    else:
        # Sem imagem do monstro: enviar apenas texto
        try:
            await query.edit_message_text(combat_text, parse_mode='Markdown', reply_markup=reply_markup)
        except:
            pass

async def edit_callback_message(query, text, reply_markup=None, parse_mode=None):
    """Edita mensagem de callback, respeitando fotos com legenda."""
    if query.message and getattr(query.message, "photo", None):
        await query.edit_message_caption(
            caption=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    else:
        await query.edit_message_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )

async def send_player_message(query, player, text, keyboard=None):
    """Envia mensagem com foto da classe do personagem"""
    class_image = CLASS_IMAGES.get(player["class"])
    
    if keyboard is None:
        keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if class_image and query.message:
        try:
            await query.edit_message_caption(
                caption=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception:
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    elif class_image:
        try:
            await query.message.reply_photo(
                photo=class_image,
                caption=text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            await query.delete_message()
        except Exception:
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def start_hunt_combat(query, player):
    """Inicia combate com um monstro aleatorio"""
    # Escolhe monstro baseado no nível com variedade maior
    min_level = max(1, player["level"] - 1)  # Permite monstros 1 nível abaixo
    max_level = player["level"] + 4  # Permite monstros até 4 níveis acima
    
    available_monsters = [m for m in monsters if min_level <= m["level"] <= max_level]
    
    if not available_monsters:
        available_monsters = monsters[:5]  # Pelo menos os 5 primeiros monstros
    
    # Sistema de peso: monstros próximos do nível do jogador têm mais chance
    weights = []
    for m in available_monsters:
        level_diff = abs(m["level"] - player["level"])
        if level_diff == 0:
            weights.append(5)  # Mesmo nível: peso 5
        elif level_diff == 1:
            weights.append(4)  # 1 nível de diferença: peso 4
        elif level_diff == 2:
            weights.append(3)  # 2 níveis: peso 3
        else:
            weights.append(1)  # 3+ níveis: peso 1
    
    monster_template = random.choices(available_monsters, weights=weights)[0].copy()

    # Cria monstro com stats ajustados
    monster = {
        "name": monster_template["name"],
        "hp": monster_template["hp"] + (player["level"] - monster_template["level"]) * 10,
        "max_hp": monster_template["hp"] + (player["level"] - monster_template["level"]) * 10,
        "atk": monster_template["atk"] + (player["level"] - monster_template["level"]) * 2,
        "xp": monster_template["xp"],
        "gold": monster_template["gold"],
        "level": monster_template["level"],
        "drops": monster_template["drops"],
        "effects": monster_template.get("effects", [])
    }

    player["monster"] = monster
    player["monster_effects"] = []
    player["combat_turn"] = 1
    await save_players()

    await send_combat_message(query, monster, player, "⚔️ COMBATE INICIADO", player["combat_turn"])

async def hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia uma caçada com cooldown"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return
    
    player = players[user_id]
    
    # Verifica cooldown de 5 segundos
    last_hunt = player.get("last_hunt")
    if last_hunt:
        if isinstance(last_hunt, str):
            try:
                last_hunt = datetime.fromisoformat(last_hunt)
            except:
                last_hunt = None
        if last_hunt:
            time_diff = (datetime.now() - last_hunt).total_seconds()
            if time_diff < 5:
                keyboard = [
                    [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="back_to_main")],
                    [InlineKeyboardButton("⚔️ Caçar novamente", callback_data="hunt")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await edit_callback_message(query, f"⏳ Aguarde {5 - int(time_diff)} segundos para caçar novamente!",
                    reply_markup=reply_markup
                )
                return
    
    # Verifica se já está em combate
    if player.get("monster"):
        keyboard = [
            [InlineKeyboardButton("⚔️ Atacar", callback_data="attack")],
            [InlineKeyboardButton("🎒 Usar item", callback_data="use_item_menu")],
            [InlineKeyboardButton("🏃 Fugir", callback_data="flee")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        combat_turn = player.get("combat_turn", 1)
        await edit_callback_message(query, 
            format_combat_status(
                "⚔️ COMBATE EM ANDAMENTO",
                player["monster"],
                player,
                combat_turn,
                show_monster_icon=True
            ),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Marca caçada para evitar spam
    player["last_hunt"] = datetime.now()
    await save_players()

    # Encontro aleatorio
    if random.random() < RANDOM_ENCOUNTER_CHANCE:
        encounter = random.choices(
            ["merchant", "camp", "treasure", "potion_small", "potion_medium", "potion_large", "gold_small", "gold_medium", "gold_large", "gold_huge", "nothing"],
            weights=[100, 20, 20, 80, 30, 5, 100, 50, 10, 5, 50]
        )[0]

        if encounter == "merchant":
            merchant_narration = random.choice([
                "📖 *Você se depara com um homem estranho perto da trilha, usando roupas gastas. Ele sorri de forma misteriosa e abre sua bolsa repleta de potions. É um vendedor ambulante!*",
                "📖 *Uma figura encapuzada surge da neblina. Ele revela ser um vendedor ambulante com poções mágicas para vender.*",
                "📖 *Um comerciante viajante bloqueia seu caminho. Seus olhos brilham enquanto ele oferece suspeitos frascos de poções.*",
                "📖 *No meio da floresta, você encontra um velho senhor com uma mochila repleta de frascos e garrafas misteriosas.*",
                "📖 *Uma voz rouca chama sua atenção. Um vendedor ambulante emerge entre as árvores, oferecendo seus produtos curiosos.*"
            ])
            base_price = consumables[MERCHANT_POTION_NAME]["price"]
            discount_price = max(1, int(base_price * MERCHANT_DISCOUNT))
            keyboard = [
                [InlineKeyboardButton(f"🧪 Comprar ({discount_price}💰)", callback_data="merchant_buy_potion")],
                [InlineKeyboardButton("⚔️ Duelar (hardcore)", callback_data="merchant_duel")],
                [InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Escolhe imagem aleatória do vendedor
            merchant_image = random.choice(MERCHANT_IMAGES)
            merchant_text = f"{merchant_narration}\n\n" \
                           f"🧳 **Vendedor ambulante**\n\n" \
                           f"Ele oferece {MERCHANT_POTION_NAME} por um preco mais barato.\n" \
                           f"_Cuidado: se decidir duelar, ele é brutal._"
            
            # Envia mensagem com imagem do vendedor
            try:
                # Deleta mensagem anterior
                try:
                    await query.delete_message()
                except:
                    pass
                
                # Envia nova mensagem com imagem do vendedor
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=merchant_image,
                    caption=merchant_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                print(f"✅ Imagem do vendedor enviada: {merchant_image}")
            except Exception as e:
                print(f"❌ Erro ao enviar imagem do vendedor: {e}")
                # Fallback: apenas texto
                await edit_callback_message(query, merchant_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            return

        if encounter == "camp":
            narration = random.choice([
                "📖 *Enquanto caminha pela floresta, você encontra uma fogueira ainda acesa. Alguém esteve aqui recentemente...*",
                "📖 *Uma fogueira abandonada brilha no escuro da noite. Você sente o calor reconfortante das chamas.*",
                "📖 *Ao seguir pela trilha, você descobre um acampamento velho com uma fogueira tocando. O ar quente alivia seu cansaço.*",
                "📖 *Resquícios de um acampamento aparecem à noite. A fogueira ainda queima, trazendo aquele conforto que você precisava.*",
                "📖 *Você encontra um refúgio improvisado com uma fogueira crepitante. Decide ficar um pouco e se aquecer.*",
                "📖 *Entre as árvores, você descobre um fogo de acampamento ainda vivo. O calor das chamas restaura suas forças.*"
            ])
            heal = 10
            player["hp"] = min(player["max_hp"], player["hp"] + heal)
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"{narration}\n\n"
                f"🔥 **Fogueira abandonada**\n\n"
                f"Você descansou e recuperou {heal} HP.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        if encounter == "treasure":
            narration = random.choice([
                "📖 *Ao passar por um arbusto, algo brilha na grama. Uma bolsa de couro antiga, perdida há tempos.*",
                "📖 *Você pisa em algo macio e descobre uma bolsa esquecida sob folhas secas.*",
                "📖 *Um reflexo metálico chama sua atenção. Escavando um pouco, você encontra uma bolsa com moedas de ouro.*",
                "📖 *Um viajante esqueceu sua bolsa nas proximidades. Que sorte a sua em encontrá-la!*",
                "📖 *Entre galhos e raízes, você descobre uma bolsa antiga repleta de tesouro perdido.*"
            ])
            gold_found = random.randint(8, 20)
            player["gold"] += gold_found
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"{narration}\n\n"
                f"🪙 **Bolsa esquecida**\n\n"
                f"Você encontrou {gold_found} gold.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        if encounter == "gold_small":
            narration = random.choice([
                "📖 *Moedas de ouro brilham no chão perto da trilha. Sorte sua!*",
                "📖 *Algumas moedas caem de uma árvore, como se alguém as tivesse perdido.*",
                "📖 *Você encontra moedas de ouro espalhadas na trilha. Um achado valioso!*",
                "📖 *Brilhos dourados chamam sua atenção no chão. Moedas antigas, ainda em bom estado.*"
            ])
            gold_found = 10
            player["gold"] += gold_found
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"{narration}\n\n"
                f"💰 Você encontrou {gold_found} gold.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        if encounter == "gold_medium":
            narration = random.choice([
                "📖 *Uma bolsa pequena com moedas está pendurada em um galho. Parece ter caído de alguém.*",
                "📖 *Você encontra uma bolsinha de couro presa em um galho baixo, cheia de moedas de ouro.*",
                "📖 *Uma bolsa esquecida em uma árvore revela um tesouro valioso em seu interior.*",
                "📖 *Você consegue alcançar uma bolsa presa nos arbustos. Dentro dela, moedas brilhantes o recompensam.*"
            ])
            gold_found = 30
            player["gold"] += gold_found
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"{narration}\n\n"
                f"💰 Você encontrou {gold_found} gold.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        if encounter == "gold_large":
            narration = random.choice([
                "📖 *Um cofre velho está meio enterrado na terra. Você consegue abri-lo com dificuldade.*",
                "📖 *Você descobre uma caixa de madeira enferrujada. Dentro dela, um tesouro considerável!*",
                "📖 *Os restos de um antigo baú aparecem entre as raízes. Você consegue abri-lo e encontra riquezas.*",
                "📖 *Uma caixa secreta estava escondida na caverna. Você a força aberta e descobre moedas de ouro.*"
            ])
            gold_found = 70
            player["gold"] += gold_found
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"{narration}\n\n"
                f"💰 Você encontrou {gold_found} gold!",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        if encounter == "gold_huge":
            narration = random.choice([
                "📖 *Uma tumba esquecida revela um tesouro antigo! Moedas de ouro reluzem ao escuro.*",
                "📖 *Você encontra uma câmara secreta cheia de ouro! Um verdadeiro tesouro de reis!*",
                "📖 *Uma estrutura antiga emerge do solo. Dentro dela, uma fortuna em moedas antigas!*",
                "📖 *Um túmulo sagrado revela seus segredos. Riquezas incalculáveis aguardam você!*",
                "📖 *Você descobre um tesouro lendário escondido há séculos. Uma fortuna para uma vida de luxo!*"
            ])
            gold_found = 120
            player["gold"] += gold_found
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"{narration}\n\n"
                f"💰💰 Você encontrou {gold_found} gold!!!",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        if encounter == "potion_small":
            narration = random.choice([
                "📖 *Uma poção pequena está abandonada na grama. Ainda parece estar em bom estado.*",
                "📖 *Um frasco brilhante com líquido vermelho repousa no chão. Uma poção de cura!*",
                "📖 *Você encontra uma garrafinha mágica entre as pedras da trilha.*",
                "📖 *Um frasco de poção foi deixado para trás por algum viajante. Que sorte!*"
            ])
            potion_name = "Poção pequena"
            player["inventory"][potion_name] = player["inventory"].get(potion_name, 0) + 1
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"{narration}\n\n"
                f"🧪 Você encontrou {potion_name}!",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        if encounter == "potion_medium":
            narration = random.choice([
                "📖 *Uma poção média brilha com uma cor estranha em galho. Você a coleta com cuidado.*",
                "📖 *Um frasco maior com brilho azulado está preso em um galho. Uma poção rara!*",
                "📖 *Você descobre uma poção de cura mais potente escondida entre as folhas.*",
                "📖 *Uma garrafa mágica de tamanho considerável brilha na penumbra da floresta.*"
            ])
            potion_name = "Poção média"
            player["inventory"][potion_name] = player["inventory"].get(potion_name, 0) + 1
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"{narration}\n\n"
                f"🧪 Você encontrou {potion_name}!",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        if encounter == "potion_large":
            narration = random.choice([
                "📖 *Uma poção grande, radiante com magia antiga, descansa em uma caverna próxima. Um verdadeiro tesouro!*",
                "📖 *Um caldeirão mágico repleto de poção brilhante aparece diante de você. Riqueza alquímica!*",
                "📖 *Você encontra uma adega secreta com uma grande poção de poder antigamente perdido.*",
                "📖 *Uma garrafa enorme, com brilho mágico incomparável, emerge da escuridão. Um artefato lendário!*",
                "📖 *Você descobre um baú antigo com uma poção mestre de cura suprema no seu interior.*"
            ])
            potion_name = "Poção grande"
            player["inventory"][potion_name] = player["inventory"].get(potion_name, 0) + 1
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"{narration}\n\n"
                f"🧪 Você encontrou {potion_name}!!!",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        nothing_narration = random.choice([
            "📖 *A trilha é longa e cansativa. Você caminha atento às sombras, sem avistar nada de interessante. O caminho segue tranquilo...*",
            "📖 *Você caminha pela floresta em silêncio. Nada de especial é encontrado, apenas a natureza ao seu redor.*",
            "📖 *A jornada continua sem eventos notáveis. A floresta segue seu curso natural e monótono.*",
            "📖 *Você prossegue pela trilha sem encontrar nada de valor. Apenas árvores, plantas e mais árvores.*",
            "📖 *O caminho parece interminável. Você segue adiante sem qualquer descoberta ou encontro especial.*"
        ])
        keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, f"{nothing_narration}\n\n"
            "🌫️ **Nada acontece**",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return

    await start_hunt_combat(query, player)

async def continue_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Continua a caçada apos um encontro"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return

    player = players[user_id]
    if player.get("monster"):
        await edit_callback_message(query, "❌ Você já está em combate!")
        return

    await start_hunt_combat(query, player)

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa ataques"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Debounce: evita múltiplos cliques rápidos processarem attack 2x
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.8):
        await query.answer("⏳ Aguarde um momento...")
        return
    
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return
    
    player = players[user_id]
    
    if not player.get("monster"):
        await edit_callback_message(query, "❌ Nenhum monstro para atacar! Use /hunt")
        return
    
    monster = player["monster"]
    
    # Calcula dano do jogador
    weapon_damage = weapons[player["weapon"]]["damage"]
    class_bonus = get_class_damage_bonus(player["class"], player["level"])
    
    # Efeito da arma
    weapon_effect = weapons[player["weapon"]].get("effect")
    
    # Chance de crítico baseada na classe
    crit_chance = get_class_crit_chance(player["class"], player["level"])
    is_critical = random.random() < crit_chance
    crit_multiplier = 2 if is_critical else 1
    
    # Aplica buffs
    buff_damage = 0
    active_buffs = []
    for buff in player.get("buffs", []):
        if buff["duration"] > 0:
            buff["duration"] -= 1
            if "damage_bonus" in buff:
                buff_damage += buff["damage_bonus"]
            if buff["duration"] > 0:
                active_buffs.append(buff)
    
    player["buffs"] = active_buffs
    
    # Dano base
    base_damage = random.randint(DAMAGE_RANGE[0], DAMAGE_RANGE[1]) + weapon_damage + class_bonus + buff_damage
    
    # Aplica multiplicador de dano da classe (Lutador)
    damage_multiplier = get_class_damage_scaling(player["class"], player["level"])
    damage = int(base_damage * damage_multiplier)
    damage *= crit_multiplier
    
    # Aplica efeito da arma
    effect_message = ""
    if weapon_effect and random.random() < 0.3:  # 30% de chance de aplicar efeito
        if weapon_effect not in player.get("monster_effects", []):
            player.setdefault("monster_effects", []).append(weapon_effect)
            effect_message = f"\n✨ Efeito {weapon_effect} aplicado!"
    
    monster["hp"] -= damage
    
    # Dano do monstro com redução de armadura (apenas 33% da defesa conta)
    armor_defense = armors[player["armor"]]["defense"]
    class_defense = get_class_defense_bonus(player["class"], player["level"])
    total_defense = (armor_defense + class_defense) // 3  # Usa apenas 1/3 da defesa
    monster_damage = max(3, random.randint(MONSTER_DAMAGE_RANGE[0], MONSTER_DAMAGE_RANGE[1]) + monster["atk"] - total_defense)
    
    # Aplica efeitos do monstro no jogador
    if monster.get("effects"):
        for effect in monster["effects"]:
            if effect not in player.get("effects", []) and random.random() < 0.2:
                player.setdefault("effects", []).append(effect)
    
    player["hp"] -= monster_damage
    player["hp"] = max(0, player["hp"])  # Garante que HP não fique negativo
    
    # Verifica se monstro morreu
    if monster["hp"] <= 0:
        # Recompensas
        xp_gain = monster["xp"]
        gold_gain = monster["gold"]
        
        player["xp"] += xp_gain
        player["gold"] += gold_gain
        
        # Processa drops
        drop_message = ""
        for drop in monster["drops"]:
            if random.random() < drop["chance"]:
                item = drop["item"]
                # Verifica se é arma
                if item in weapons:
                    if item not in player.get("equipped_weapons", []):
                        player.setdefault("equipped_weapons", []).append(item)
                        drop_message += f"\n🎁 Dropou arma: {get_rarity_emoji(weapons[item]['rarity'])} {item}!"
                # Verifica se é armadura
                elif item in armors:
                    if item not in player.get("equipped_armors", []):
                        player.setdefault("equipped_armors", []).append(item)
                        drop_message += f"\n🎁 Dropou armadura: {get_rarity_emoji(armors[item]['rarity'])} {item}!"
                # Item consumível
                elif item in consumables:
                    player["inventory"][item] = player["inventory"].get(item, 0) + 1
                    drop_message += f"\n🎁 Dropou poção: {consumables[item]['emoji']} {item}!"
                # Item misc
                elif item in misc_items:
                    player["inventory"][item] = player["inventory"].get(item, 0) + 1
                    drop_message += f"\n🎁 Dropou: {misc_items[item]['emoji']} {item}!"
        
        # Tentativa de drop aleatório de armadura comum (monstros simples)
        if monster.get("level", 1) <= 3 and random.random() < 0.3:
            common_armor_drop = get_random_common_armor_drop(player["level"])
            if common_armor_drop:
                armor_name, armor_data = common_armor_drop
                if armor_name not in player.get("equipped_armors", []):
                    player.setdefault("equipped_armors", []).append(armor_name)
                    drop_message += f"\n🎁 Dropou armadura: {get_rarity_emoji(armor_data['rarity'])} {armor_name}!"

        # Tentativa de drop aleatório de arma (chance extra)
        if random.random() < 0.25:
            weapon_drop = get_random_weapon_drop(player["level"], monster.get("level", 1))
            if weapon_drop:
                weapon_name, weapon_data = weapon_drop
                if weapon_name not in player.get("equipped_weapons", []):
                    player.setdefault("equipped_weapons", []).append(weapon_name)
                    drop_message += f"\n🎁 Dropou arma rara: {get_rarity_emoji(weapon_data['rarity'])} {weapon_name}!"
        
        # Tentativa de drop aleatório de armadura (chance extra)
        if random.random() < 0.2:
            armor_drop = get_random_armor_drop(player["level"], monster.get("level", 1))
            if armor_drop:
                armor_name, armor_data = armor_drop
                if armor_name not in player.get("equipped_armors", []):
                    player.setdefault("equipped_armors", []).append(armor_name)
                    drop_message += f"\n🎁 Dropou armadura rara: {get_rarity_emoji(armor_data['rarity'])} {armor_name}!"
        
        xp_next = xp_needed(player["level"])
        message = f"⚔️ **Você derrotou {monster['name']}!**\n\n"
        message += f"⭐ +{xp_gain} XP\n"
        message += f"💰 +{gold_gain} gold"
        if is_critical:
            message += f"\n✨ **ACERTO CRÍTICO!**"
        if effect_message:
            message += effect_message
        message += drop_message
        
        # Verifica level up
        leveled_up = False
        while player["xp"] >= xp_needed(player["level"]):
            player["xp"] -= xp_needed(player["level"])
            player["level"] += 1
            player["max_hp"] += HP_PER_LEVEL
            player["hp"] = player["max_hp"]  # Só recupera HP ao upar
            leveled_up = True
            message += f"\n🔥 **LEVEL UP! Agora você é nível {player['level']}!**\n❤️ HP restaurado!"
        
        # Limpa efeitos
        player["monster"] = None
        player["effects"] = []
        player["monster_effects"] = []
        player.pop("combat_turn", None)
        save_players_background()
        
        keyboard = [
            [InlineKeyboardButton("🎯 Caçar novamente", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_callback_message(query, message, reply_markup=reply_markup)
        return
    
    # Verifica se jogador morreu
    if player["hp"] <= 0:
        # Penalidade por morte
        percent = random.randint(10, 35)
        xp_loss = math.ceil(player["xp"] * (percent / 100))
        gold_loss = math.ceil(player["gold"] * (percent / 100))
        player["hp"] = player["max_hp"] // 2
        player["gold"] = max(0, player["gold"] - gold_loss)
        player["xp"] = max(0, player["xp"] - xp_loss)
        player["monster"] = None
        player["effects"] = []
        player.pop("combat_turn", None)
        save_players_background()
        keyboard = [
            [InlineKeyboardButton("😢 Recomeçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, f"💀 **Você morreu!**\n\n"
            f"❤️ Reviveu com {player['hp']} HP\n"
            f"💰 Perdeu {gold_loss} gold ({percent}%)\n"
            f"⭐ Perdeu {xp_loss} XP ({percent}%)\n\n"
            f"**Continue sua jornada!**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Combate continua
    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data="attack")],
        [InlineKeyboardButton("🎒 Usar item", callback_data="use_item_menu")],
        [InlineKeyboardButton("🏃 Fugir", callback_data="flee")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    crit_text = " (CRÍTICO!)" if is_critical else ""
    current_turn = player.get("combat_turn", 1)
    next_turn = current_turn + 1
    player["combat_turn"] = next_turn
    save_players_background()
    
    await edit_callback_message(query, f"{format_combat_status('⚔️ SEU TURNO', monster, player, next_turn, show_monster_icon=False)}"
        f"\n\n📜 Você causou {damage} de dano{crit_text}{effect_message}"
        f"\n💔 {monster['name']} causou {monster_damage} de dano.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def flee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tenta fugir do combate"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Debounce: evita múltiplos cliques rápidos
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.8):
        return
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    if not player.get("monster"):
        await edit_callback_message(query, "❌ Nenhum combate ativo!")
        return
    
    if random.random() < 0.5:  # 50% chance de fugir
        player["monster"] = None
        player["effects"] = []
        player.pop("combat_turn", None)
        save_players_background()
        keyboard = [
            [InlineKeyboardButton("🎯 Caçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, 
            "🏃 Você conseguiu fugir!",
            reply_markup=reply_markup
        )
    else:
        monster = player["monster"]
        defense = armors[player["armor"]]["defense"] // 3  # Usa apenas 1/3 da defesa
        monster_damage = max(3, random.randint(MONSTER_DAMAGE_RANGE[0], MONSTER_DAMAGE_RANGE[1]) + monster["atk"] - defense)
        player["hp"] -= monster_damage
        player["hp"] = max(0, player["hp"])  # Garante que HP não fique negativo
        if player["hp"] <= 0:
            player["hp"] = player["max_hp"] // 2
            player["gold"] = max(0, player["gold"] - player["gold"] // 2)
            xp_loss = math.ceil(player["xp"] * 0.5)
            player["xp"] = max(0, player["xp"] - xp_loss)
            player["monster"] = None
            player.pop("combat_turn", None)
            save_players_background()
            keyboard = [
                [InlineKeyboardButton("🎯 Caçar", callback_data="hunt")],
                [InlineKeyboardButton("📊 Status", callback_data="status")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"💀 Não conseguiu fugir e morreu!\n"
                f"❤️ Reviveu com {player['hp']} HP\n"
                f"💰 Perdeu metade do gold\n"
                f"⭐ Perdeu {xp_loss} XP",
                reply_markup=reply_markup
            )
        else:
            save_players_background()
            keyboard = [
                [InlineKeyboardButton("🏃 Tentar fugir novamente", callback_data="flee")],
                [InlineKeyboardButton("⚔️ Atacar", callback_data="attack")],
                [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(query, f"❌ Não conseguiu fugir!\n"
                f"💥 Tomou {monster_damage} de dano\n"
                f"❤️ HP atual: {player['hp']}",
                reply_markup=reply_markup
            )

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra inventário"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    # Itens consumíveis
    consumable_text = "**🧪 Consumíveis:**\n"
    has_consumables = False
    for item, qty in player["inventory"].items():
        if item in consumables:
            consumable_text += f"  • {consumables[item]['emoji']} {item}: {qty}\n"
            has_consumables = True
    
    if not has_consumables:
        consumable_text += "  • Nenhum\n"
    
    # Armas
    weapon_text = "**⚔️ Armas:**\n"
    for weapon in player.get("equipped_weapons", ["Punhos"]):
        if weapon in weapons:
            rarity_emoji = get_rarity_emoji(weapons[weapon]["rarity"])
            equipped = " (Equipada)" if player["weapon"] == weapon else ""
            weapon_text += f"  • {rarity_emoji} {weapon}{equipped}\n"
    
    # Armaduras
    armor_text = "**🛡️ Armaduras:**\n"
    for armor in player.get("equipped_armors", ["Roupas velhas"]):
        if armor in armors:
            rarity_emoji = get_rarity_emoji(armors[armor]["rarity"])
            equipped = " (Equipada)" if player["armor"] == armor else ""
            armor_text += f"  • {rarity_emoji} {armor}{equipped}\n"
    
    # Itens diversos
    misc_text = "**📦 Outros itens:**\n"
    has_misc = False
    for item, qty in player["inventory"].items():
        if item in misc_items:
            misc_text += f"  • {misc_items[item]['emoji']} {item}: {qty}\n"
            has_misc = True
    
    if not has_misc:
        misc_text += "  • Nenhum\n"
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Equipar", callback_data="equip_menu")],
        [InlineKeyboardButton("💊 Usar item", callback_data="use_item_menu")],
        [InlineKeyboardButton("💰 Vender", callback_data="sell_items")],
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"🎒 **INVENTÁRIO**\n\n"
        f"{consumable_text}\n"
        f"{weapon_text}\n"
        f"{armor_text}\n"
        f"{misc_text}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def sell_drops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vende apenas items de drop (misc items)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Debounce: evita múltiplos cliques rápidos
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.5):
        return
    
    if user_id not in players:
        return
    
    player = players[user_id]
    offer = get_daily_offer()
    
    # Coleta apenas drops (misc_items)
    sellable_items = {}
    for item, qty in player["inventory"].items():
        if item in misc_items and qty > 0:
            base_price = misc_items[item]["price"]
            sell_price = calculate_sell_price(item, base_price, "misc")
            emoji = misc_items[item]["emoji"]
            sellable_items[item] = {
                "qty": qty,
                "emoji": emoji,
                "sell_price": sell_price,
                "type": "misc"
            }
    
    if not sellable_items:
        keyboard = [
            [InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
             InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_callback_message(query, 
            "📦 **VENDER DROPS** › Loja\n\n"
            "Você não tem drops para vender.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Monta mensagem e botões
    sell_text = "📦 **VENDER DROPS** › Loja\n\n"
    if offer["type"] == "sell_bonus" and offer["category"] == "misc":
        sell_text += f"⚡ {offer['text']}\n\n"
    sell_text += "Clique para vender:\n\n"
    
    keyboard = []
    for item_name, item_data in sellable_items.items():
        qty_text = f" x{item_data['qty']}" if item_data["qty"] > 1 else ""
        button_text = f"{item_data['emoji']} {item_name}{qty_text} → {item_data['sell_price']}💰"
        sell_text += f"{item_data['emoji']} **{item_name}**: x{item_data['qty']} ({item_data['sell_price']}💰 cada)\n"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sell_{item_name}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, 
        sell_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def sell_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vende armas e armaduras velhas"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Debounce: evita múltiplos cliques rápidos
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.5):
        return
    
    if user_id not in players:
        return
    
    player = players[user_id]
    offer = get_daily_offer()
    
    # Coleta armas e armaduras não equipadas
    sellable_items = {}
    
    # Armas
    for weapon in player.get("equipped_weapons", []):
        if weapon != player["weapon"] and weapon in weapons:
            base_price = weapons[weapon]["price"]
            sell_price = calculate_sell_price(weapon, base_price, "weapon")
            rarity_emoji = get_rarity_emoji(weapons[weapon]["rarity"])
            sellable_items[weapon] = {
                "emoji": rarity_emoji,
                "sell_price": sell_price,
                "type": "weapon"
            }
    
    # Armaduras
    for armor in player.get("equipped_armors", []):
        if armor != player["armor"] and armor in armors:
            base_price = armors[armor]["price"]
            sell_price = calculate_sell_price(armor, base_price, "armor")
            rarity_emoji = get_rarity_emoji(armors[armor]["rarity"])
            sellable_items[armor] = {
                "emoji": rarity_emoji,
                "sell_price": sell_price,
                "type": "armor"
            }
    
    if not sellable_items:
        keyboard = [
            [InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
             InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_callback_message(query, 
            "⚔️🛡️ **VENDER EQUIPAMENTOS** › Loja\n\n"
            "Você não tem equipamentos velhos para vender.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Monta mensagem e botões
    sell_text = "⚔️🛡️ **VENDER EQUIPAMENTOS** › Loja\n\n"
    if offer["type"] == "sell_bonus" and (offer["category"] == "weapon" or offer["category"] == "armor"):
        sell_text += f"⚡ {offer['text']}\n\n"
    sell_text += "Clique para vender:\n\n"
    
    keyboard = []
    for item_name, item_data in sellable_items.items():
        button_text = f"{item_data['emoji']} {item_name} → {item_data['sell_price']}💰"
        sell_text += f"{item_data['emoji']} **{item_name}**: {item_data['sell_price']}💰\n"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sell_{item_name}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, 
        sell_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def sell_all_quick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vende todos os items vendáveis de uma vez"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Debounce: evita múltiplos cliques rápidos (crítico - processa muitos items)
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.8):
        return
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    total_gold = 0
    items_sold = []
    
    # Vende todos os drops
    for item, qty in list(player["inventory"].items()):
        if item in misc_items and qty > 0:
            base_price = misc_items[item]["price"]
            sell_price = calculate_sell_price(item, base_price, "misc")
            total_gold += sell_price * qty
            items_sold.append(f"📦 {item} x{qty}")
            player["inventory"][item] = 0
    
    # Vende armas não equipadas
    for weapon in list(player.get("equipped_weapons", [])):
        if weapon != player["weapon"] and weapon in weapons:
            base_price = weapons[weapon]["price"]
            sell_price = calculate_sell_price(weapon, base_price, "weapon")
            total_gold += sell_price
            items_sold.append(f"⚔️ {weapon}")
            player["equipped_weapons"].remove(weapon)
    
    # Vende armaduras não equipadas
    for armor in list(player.get("equipped_armors", [])):
        if armor != player["armor"] and armor in armors:
            base_price = armors[armor]["price"]
            sell_price = calculate_sell_price(armor, base_price, "armor")
            total_gold += sell_price
            items_sold.append(f"🛡️ {armor}")
            player["equipped_armors"].remove(armor)
    
    if total_gold == 0:
        keyboard = [
            [InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
             InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_callback_message(query, 
            "💰 **VENDA RÁPIDA** › Loja\n\n"
            "Você não tem nada para vender!",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    player["gold"] += total_gold
    save_players_background()
    
    items_list = "\n".join(items_sold[:10])  # Mostra até 10 items
    if len(items_sold) > 10:
        items_list += f"\n... e mais {len(items_sold) - 10} items"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Voltar à loja", callback_data="shop")],
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, 
        f"💰 **VENDA RÁPIDA COMPLETA!**\n\n"
        f"Itens vendidos:\n{items_list}\n\n"
        f"💰 Total recebido: **{total_gold} gold**\n"
        f"💰 Seu gold: **{player['gold']}**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def sell_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu para vender items"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    # Coleta todos os items vendáveis em um dicionário
    sellable_items = {}
    
    # Adiciona consumables
    for item, qty in player["inventory"].items():
        if item in consumables and qty > 0:
            price = int(consumables[item]["price"] * 0.4)  # 40% do preço
            emoji = consumables[item]["emoji"]
            sellable_items[item] = {
                "qty": qty,
                "emoji": emoji,
                "sell_price": price,
                "type": "consumable"
            }
    
    # Adiciona armas (exceto a equipada)
    for weapon in player.get("equipped_weapons", []):
        if weapon != player["weapon"] and weapon in weapons and weapon != "Punhos":
            price = int(weapons[weapon]["price"] * 0.4)  # 40% do preço
            rarity_emoji = get_rarity_emoji(weapons[weapon]["rarity"])
            sellable_items[weapon] = {
                "qty": 1,
                "emoji": rarity_emoji,
                "sell_price": price,
                "type": "weapon"
            }
    
    # Adiciona armaduras (exceto a equipada)
    for armor in player.get("equipped_armors", []):
        if armor != player["armor"] and armor in armors and armor != "Roupas velhas":
            price = int(armors[armor]["price"] * 0.4)  # 40% do preço
            rarity_emoji = get_rarity_emoji(armors[armor]["rarity"])
            sellable_items[armor] = {
                "qty": 1,
                "emoji": rarity_emoji,
                "sell_price": price,
                "type": "armor"
            }
    
    # Adiciona itens diversos
    for item, qty in player["inventory"].items():
        if item in misc_items and qty > 0:
            price = int(misc_items[item]["price"] * 0.4)  # 40% do preço
            emoji = misc_items[item]["emoji"]
            sellable_items[item] = {
                "qty": qty,
                "emoji": emoji,
                "sell_price": price,
                "type": "misc"
            }
    
    if not sellable_items:
        keyboard = [
            [InlineKeyboardButton("🔙 Voltar", callback_data="inventory"),
             InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_callback_message(query, 
            "💰 **VENDER ITEMS** › Inventário\n\n"
            "Você não tem nenhum item para vender.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Monta mensagem e botões
    sell_text = "💰 **VENDER ITEMS** › Inventário\n\n"
    sell_text += "Clique em um item para vender:\n\n"
    
    keyboard = []
    for item_name, item_data in sellable_items.items():
        qty_text = f" x{item_data['qty']}" if item_data["qty"] > 1 else ""
        button_text = f"{item_data['emoji']} {item_name}{qty_text} → {item_data['sell_price']}💰"
        sell_text += f"{item_data['emoji']} **{item_name}**: x{item_data['qty']} ({item_data['sell_price']}💰 cada)\n"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sell_{item_name}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="inventory"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, 
        sell_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def sell_item_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a venda de um item"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Debounce: evita múltiplos cliques rápidos (crítico - envolve gold)
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.8):
        return
    
    if user_id not in players:
        return
    
    player = players[user_id]
    item_name = query.data.replace("sell_", "")
    
    # Determina tipo e preço do item
    sell_price = 0
    item_type = None
    
    if item_name in consumables and player["inventory"].get(item_name, 0) > 0:
        sell_price = int(consumables[item_name]["price"] * 0.4)
        item_type = "consumable"
    elif item_name in weapons and item_name in player.get("equipped_weapons", []) and item_name != player["weapon"]:
        sell_price = int(weapons[item_name]["price"] * 0.4)
        item_type = "weapon"
    elif item_name in armors and item_name in player.get("equipped_armors", []) and item_name != player["armor"]:
        sell_price = int(armors[item_name]["price"] * 0.4)
        item_type = "armor"
    elif item_name in misc_items and player["inventory"].get(item_name, 0) > 0:
        sell_price = int(misc_items[item_name]["price"] * 0.4)
        item_type = "misc"
    
    if not item_type:
        await edit_callback_message(query, "❌ Item não encontrado!")
        return
    
    # Processa venda
    if item_type == "consumable" or item_type == "misc":
        qty = player["inventory"].get(item_name, 0)
        total_price = sell_price * qty
        player["inventory"][item_name] = 0
        qty_text = f"x{qty} "
    else:  # weapon ou armor
        total_price = sell_price
        qty_text = ""
        if item_type == "weapon":
            player["equipped_weapons"].remove(item_name)
        else:
            player["equipped_armors"].remove(item_name)
    
    player["gold"] += total_price
    await save_players()
    
    keyboard = [
        [InlineKeyboardButton("💰 Vender mais", callback_data="sell_items")],
        [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
        [InlineKeyboardButton("🔙 Menu principal", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"✅ **VENDA CONCLUÍDA**\n\n"
        f"Você vendeu {qty_text}{item_name}\n"
        f"💰 Ganhou: +{total_price} gold\n\n"
        f"💵 Gold total: {player['gold']}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def equip_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de equipamento"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Equipar arma", callback_data="equip_weapon_menu")],
        [InlineKeyboardButton("🛡️ Equipar armadura", callback_data="equip_armor_menu")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="inventory"),
         InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"⚙️ **EQUIPAMENTOS** › Inventário\n\n"
        f"⚔️ **Arma atual:** {player['weapon']} (Dano: +{weapons[player['weapon']]['damage']})\n"
        f"🛡️ **Armadura atual:** {player['armor']} (Defesa: +{armors[player['armor']]['defense']})",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def equip_weapon_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu para equipar arma"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    keyboard = []
    for weapon in player.get("equipped_weapons", []):
        if weapon in weapons and weapon != player["weapon"]:
            weapon_data = weapons[weapon]
            rarity_emoji = get_rarity_emoji(weapon_data["rarity"])
            keyboard.append([
                InlineKeyboardButton(
                    f"{rarity_emoji} {weapon} (Dano: +{weapon_data['damage']})",
                    callback_data=f"equip_weapon_{weapon}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="equip_menu"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, 
        "⚔️ **EQUIPAR ARMA** › Equipamentos › Inventário\n\n**Escolha uma arma:**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def equip_armor_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu para equipar armadura"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    keyboard = []
    for armor in player.get("equipped_armors", []):
        if armor in armors and armor != player["armor"]:
            armor_data = armors[armor]
            rarity_emoji = get_rarity_emoji(armor_data["rarity"])
            keyboard.append([
                InlineKeyboardButton(
                    f"{rarity_emoji} {armor} (Defesa: +{armor_data['defense']})",
                    callback_data=f"equip_armor_{armor}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="equip_menu"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, 
        "🛡️ **EQUIPAR ARMADURA** › Equipamentos › Inventário\n\n**Escolha uma armadura:**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def equip_weapon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Equipa uma arma"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    weapon_name = query.data.replace("equip_weapon_", "")
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    if weapon_name in player.get("equipped_weapons", []):
        player["weapon"] = weapon_name
        await save_players()
        keyboard = [
            [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
            [InlineKeyboardButton("🏪 Loja", callback_data="shop")],
            [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_callback_message(query, f"✅ {weapons[weapon_name]['emoji']} **{weapon_name} equipada com sucesso!**",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await edit_callback_message(query, "❌ Você não possui esta arma!")

async def equip_armor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Equipa uma armadura"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    armor_name = query.data.replace("equip_armor_", "")
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    if armor_name in player.get("equipped_armors", []):
        player["armor"] = armor_name
        await save_players()
        keyboard = [
            [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
            [InlineKeyboardButton("🏪 Loja", callback_data="shop")],
            [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, f"✅ {armors[armor_name]['emoji']} **{armor_name} equipada com sucesso!**",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await edit_callback_message(query, "❌ Você não possui esta armadura!")

async def use_item_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu para usar itens"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    keyboard = []
    for item, qty in player["inventory"].items():
        if qty > 0 and item in consumables:
            consumable = consumables[item]
            keyboard.append([
                InlineKeyboardButton(
                    f"{consumable['emoji']} {item} ({qty})",
                    callback_data=f"use_item_{item}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="inventory"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, 
        "💊 **USAR ITEM** › Inventário\n\n**Escolha um item:**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def use_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usa um item"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    item_name = query.data.replace("use_item_", "")
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    if player["inventory"].get(item_name, 0) <= 0:
        await edit_callback_message(query, "❌ Você não tem este item!")
        return
    
    consumable = consumables[item_name]
    
    # Usa o item
    player["inventory"][item_name] -= 1
    
    message = f"✅ Usou: {consumable['emoji']} {item_name}!\n"
    
    # Aplica efeitos
    if "heal" in consumable:
        heal = consumable["heal"]
        old_hp = player["hp"]
        player["hp"] = min(player["max_hp"] + (30 if "vida extra" in item_name else 0), player["hp"] + heal)
        message += f"❤️ Cura: +{player['hp'] - old_hp} HP\n"
    
    if consumable.get("effect") == "buff":
        if "damage_bonus" in consumable:
            player.setdefault("buffs", []).append({
                "name": item_name,
                "damage_bonus": consumable["damage_bonus"],
                "duration": consumable["duration"]
            })
            message += f"⚔️ Bônus de dano: +{consumable['damage_bonus']} por {consumable['duration']} turnos\n"
        
        if "defense_bonus" in consumable:
            player.setdefault("buffs", []).append({
                "name": item_name,
                "defense_bonus": consumable["defense_bonus"],
                "duration": consumable["duration"]
            })
            message += f"🛡️ Bônus de defesa: +{consumable['defense_bonus']} por {consumable['duration']} turnos\n"
    
    if consumable.get("effect") == "cura_veneno":
        player["effects"] = [e for e in player.get("effects", []) if e != "veneno"]
        message += f"💊 Veneno curado!\n"
    
    save_players_background()
    
    # Se estiver em combate, mostra opções
    if player.get("monster"):
        keyboard = [
            [InlineKeyboardButton("⚔️ Atacar", callback_data="attack")],
            [InlineKeyboardButton("🏃 Fugir", callback_data="flee")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_callback_message(query, 
            message + "\nO que deseja fazer?",
            reply_markup=reply_markup
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🎯 Caçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_callback_message(query, 
            message + "\n" + hp_bar(player["hp"], player["max_hp"]),
            reply_markup=reply_markup
        )

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu principal da loja - Nova interface organizada"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Debounce: evita múltiplos cliques rápidos
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.5):
        return
    
    if user_id not in players:
        return
    
    player = players[user_id]
    offer = get_daily_offer()
    
    # Layout organizado em seções
    keyboard = [
        # SEÇÃO COMPRAR
        [InlineKeyboardButton("⚔️ Armas", callback_data="shop_weapons"),
         InlineKeyboardButton("🧪 Poções", callback_data="shop_potions")],
        [InlineKeyboardButton("🛡️ Armaduras", callback_data="shop_armors"),
         InlineKeyboardButton("✨ Buffs", callback_data="shop_buffs")],
        
        # SEÇÃO VENDER
        [InlineKeyboardButton("📦 Vender Drops", callback_data="sell_drops")],
        [InlineKeyboardButton("⚔️🛡️ Vender Equipamentos", callback_data="sell_equipment")],
        [InlineKeyboardButton("💰 Venda Rápida (Tudo)", callback_data="sell_all_quick")],
        
        # NAVEGAÇÃO
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    shop_text = (
        f"┌─────────────────────────────────┐\n"
        f"│   🏪 **LOJA DO MERCADOR**\n"
        f"│   💰 Seu gold: **{player['gold']}**\n"
        f"├─────────────────────────────────┤\n"
        f"│\n"
        f"│   ──── 🛒 **COMPRAR** ────\n"
        f"│\n"
        f"│   ──── 💰 **VENDER** ────\n"
        f"│\n"
        f"├─────────────────────────────────┤\n"
        f"│   ⚡ {offer['text']}\n"
        f"└─────────────────────────────────┘"
    )
    
    # Envia mensagem com imagem da loja
    try:
        # Sempre tenta deletar e enviar nova mensagem com foto
        try:
            await query.delete_message()
        except:
            pass
        
        # Envia foto da loja
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=SHOP_IMAGE,
            caption=shop_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        print(f"✅ Imagem da loja enviada: {SHOP_IMAGE}")
    except Exception as e:
        print(f"❌ Erro ao enviar imagem da loja: {e}")
        # Fallback: apenas texto
        await edit_callback_message(query, shop_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def shop_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de compra da loja"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🧪 Poções", callback_data="shop_potions")],
        [InlineKeyboardButton("⚔️ Armas", callback_data="shop_weapons")],
        [InlineKeyboardButton("🛡️ Armaduras", callback_data="shop_armors")],
        [InlineKeyboardButton("✨ Buffs", callback_data="shop_buffs")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
         InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"🛒 **COMPRAR ITEMS** › Loja\n\n"
        f"💰 Seu gold: {player['gold']}\n\n"
        f"Escolha uma categoria:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def shop_potions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra poções na loja"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    player = players[user_id]
    offer = get_daily_offer()
    
    shop_text = "🧪 **POÇÕES** › Comprar › Loja\n\n"
    if offer["type"] == "buy_discount" and offer["category"] == "potions":
        shop_text += f"⚡ {offer['text']}\n\n"
    shop_text += f"💰 Seu gold: {player['gold']}\n\n"
    
    keyboard = []
    for item_name, item_data in consumables.items():
        if "heal" in item_data:  # É poção
            base_price = item_data['price']
            final_price = calculate_buy_price(base_price, "potions")
            
            if final_price < base_price:
                price_display = f"~~{base_price}~~ {final_price}💰 🎉"
            else:
                price_display = f"{final_price}💰"
            
            heal_display = f"Cura: {item_data['heal']}"
            if "vida extra" in item_name.lower():
                heal_display += " (extra)"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{item_data['emoji']} {item_name} - {price_display} | {heal_display}",
                    callback_data=f"buy_potion_{item_name}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, shop_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def shop_weapons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra armas na loja filtradas pela classe do jogador"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    player = players[user_id]
    
    # Pega apenas armas da classe do jogador
    available_weapons = get_weapons_by_class(player["class"], player["level"])
    
    # Filtra armas com preco > 0 (mostra todas, mesmo acima do nivel)
    filtered = {}
    for name, data in available_weapons.items():
        if data["price"] > 0:
            filtered[name] = data
    
    # Organiza por raridade e dano
    rarity_order = ["comum", "rara", "épica", "lendária", "mítica"]
    organized = {rarity: [] for rarity in rarity_order}
    
    for name, data in filtered.items():
        rarity = data.get("rarity", "comum")
        if rarity in organized:
            organized[rarity].append((name, data))
    
    # Ordena por dano dentro de cada raridade
    for rarity in organized:
        organized[rarity].sort(key=lambda x: x[1]["damage"])
    
    # Monta keyboard com categorias
    keyboard = []
    for rarity in rarity_order:
        if organized[rarity]:
            rarity_emoji = get_rarity_emoji(rarity)
            for name, data in organized[rarity]:
                price_display = f"{data['price']}💰"
                damage_display = f"Dano: +{data['damage']}"
                level_display = f"Nv: {data['level_req']}"
                locked = player["level"] < data["level_req"]
                lock_display = " 🔒" if locked else ""
                level_req_display = f" | Req: {level_display}" if locked else ""

                keyboard.append([
                    InlineKeyboardButton(
                        f"{rarity_emoji}{lock_display} {name} - {price_display} | {damage_display}{level_req_display}",
                        callback_data=f"buy_weapon_{name}"
                    )
                ])
    
    if not keyboard:
        keyboard.append([InlineKeyboardButton("❌ Nenhuma arma disponível", callback_data="shop")])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"⚔️ **ARMAS** › Comprar › Loja\n\n"
        f"**{player['class'].upper()} {classes[player['class']]['emoji']}**\n\n"
        f"💰 Seu gold: {player['gold']}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def shop_armors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra armaduras na loja"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    player = players[user_id]
    
    keyboard = []
    for armor_name, armor_data in armors.items():
        if armor_data["price"] > 0:  # Não mostra Roupas velhas
            if armor_data["level_req"] <= player["level"]:
                rarity_emoji = get_rarity_emoji(armor_data["rarity"])
                price_display = f"{armor_data['price']}💰"
                defense_display = f"Defesa: +{armor_data['defense']}"
                level_display = f"Nv: {armor_data['level_req']}"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"{rarity_emoji} {armor_name} - {price_display} | {defense_display} | {level_display}",
                        callback_data=f"buy_armor_{armor_name}"
                    )
                ])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"🛡️ **ARMADURAS** › Comprar › Loja\n\n"
        f"💰 Seu gold: {player['gold']}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def shop_buffs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra buffs na loja"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    player = players[user_id]
    
    keyboard = []
    for item_name, item_data in consumables.items():
        if "buff" in item_data.get("effect", ""):
            price_display = f"{item_data['price']}💰"
            effect_display = ""
            if "damage_bonus" in item_data:
                effect_display = f"Dano: +{item_data['damage_bonus']}"
            if "defense_bonus" in item_data:
                effect_display = f"Defesa: +{item_data['defense_bonus']}"
            duration_display = f"{item_data['duration']} turnos"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{item_data['emoji']} {item_name} - {price_display} | {effect_display} | {duration_display}",
                    callback_data=f"buy_buff_{item_name}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"✨ **BUFFS** › Comprar › Loja\n\n"
        f"💰 Seu gold: {player['gold']}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa compra de itens"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    data = query.data
    
    # Debounce: evita múltiplos cliques rápidos (crítico - envolve gold)
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.8):
        return
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    # Determina tipo de compra
    if data.startswith("buy_potion_"):
        item_name = data.replace("buy_potion_", "")
        item_data = consumables[item_name]
        category = "potion"
        price_category = "potions"
    elif data.startswith("buy_weapon_"):
        item_name = data.replace("buy_weapon_", "")
        item_data = weapons[item_name]
        category = "weapon"
        price_category = "weapons"
    elif data.startswith("buy_armor_"):
        item_name = data.replace("buy_armor_", "")
        item_data = armors[item_name]
        category = "armor"
        price_category = "armors"
    elif data.startswith("buy_buff_"):
        item_name = data.replace("buy_buff_", "")
        item_data = consumables[item_name]
        category = "buff"
        price_category = "buffs"
    else:
        return
    
    # Calcula preço com desconto dinâmico
    base_price = item_data["price"]
    final_price = calculate_buy_price(base_price, price_category)
    
    # Verifica gold
    if player["gold"] < final_price:
        await edit_callback_message(query, "❌ Gold insuficiente!")
        return
    
    # Verifica level requerido
    if "level_req" in item_data and player["level"] < item_data["level_req"]:
        await edit_callback_message(query, f"❌ Necessário nível {item_data['level_req']}!")
        return
    
    # Processa compra
    player["gold"] -= final_price
    
    if category == "weapon":
        if item_name not in player.get("equipped_weapons", []):
            player.setdefault("equipped_weapons", []).append(item_name)
        rarity_emoji = get_rarity_emoji(item_data["rarity"])
        item_display = f"{rarity_emoji} {item_name}"
    
    elif category == "armor":
        if item_name not in player.get("equipped_armors", []):
            player.setdefault("equipped_armors", []).append(item_name)
        rarity_emoji = get_rarity_emoji(item_data["rarity"])
        item_display = f"{rarity_emoji} {item_name}"
    
    else:  # Poção ou buff
        player["inventory"][item_name] = player["inventory"].get(item_name, 0) + 1
        item_display = f"{item_data['emoji']} {item_name}"
    
    await save_players()
    
    # Mostra economia se houver desconto
    saved_text = ""
    if final_price < base_price:
        saved = base_price - final_price
        saved_text = f"\n🎉 Você economizou {saved}💰!"
    
    keyboard = [
        [InlineKeyboardButton("🛒 Comprar mais", callback_data="shop")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"✅ **Compra realizada!**\n\n"
        f"Item: {item_display}\n"
        f"💰 Custo: {final_price} gold{saved_text}\n"
        f"💰 Gold restante: {player['gold']}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra status do jogador"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    player = players[user_id]
    
    # Calcula dano total
    weapon_damage = weapons[player["weapon"]]["damage"]
    class_damage = get_class_damage_bonus(player["class"], player["level"])
    damage_multiplier = get_class_damage_scaling(player["class"], player["level"])
    total_damage = int((weapon_damage + class_damage) * damage_multiplier)
    
    # Calcula defesa total
    armor_defense = armors[player["armor"]]["defense"]
    class_defense = get_class_defense_bonus(player["class"], player["level"])
    total_defense = armor_defense + class_defense
    
    # Calcula crítico da classe
    crit_chance = get_class_crit_chance(player["class"], player["level"])
    crit_percentage = int(crit_chance * 100)
    
    # XP necessário
    xp_next = xp_needed(player["level"])
    xp_total = get_total_xp(player["level"], player["xp"])
    xp_remaining = max(0, xp_next - player["xp"])
    
    # Buffs ativos
    buffs_text = ""
    for buff in player.get("buffs", []):
        if buff["duration"] > 0:
            buffs_text += f"\n  • {buff['name']} ({buff['duration']} turnos)"
    
    # Efeitos ativos
    effects_text = ""
    if player.get("effects"):
        effects_text = f"\n⚠️ Efeitos: {', '.join(player['effects'])}"
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
        [InlineKeyboardButton("🛌 Descansar", callback_data="rest")],
        [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
        [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]
    ]
    status_text = (
        f"📊 **STATUS DO JOGADOR**\n\n"
        f"👤 {player['name']}\n"
        f"📚 Classe: {player['class']} {classes[player['class']]['emoji']}\n"
        f"{get_rank(player['level'])}\n"
        f"📈 Nível: {player['level']}\n"
        f"⭐ XP: {player['xp']}/{xp_next} (Total: {xp_total})\n"
        f"⏳ Proximo nivel: {xp_remaining} XP\n\n"
        f"❤️ HP: {player['hp']}/{player['max_hp']}\n"
        f"{hp_bar_blocks(player['hp'], player['max_hp'])}{effects_text}\n\n"
        f"⚔️ Dano total: {total_damage} ({weapons[player['weapon']]['emoji']} {player['weapon']} +{weapon_damage} | Classe +{class_damage})\n"
        f"🛡️ Defesa total: {total_defense} ({armors[player['armor']]['emoji']} {player['armor']} +{armor_defense} | Classe +{class_defense})\n"
        f"🎯 Crítico: {crit_percentage}% de chance\n"
        f"💰 Gold: {player['gold']}\n"
        f"{buffs_text}"
    )
    
    await send_player_message(query, player, status_text, keyboard)

async def rest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Descanso com cura gradual em tempo real"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    
    player = players[user_id]
    
    if player.get("monster"):
        keyboard = [[InlineKeyboardButton("🔙 Voltar ao menu", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, "❌ Você não pode descansar em combate!", reply_markup=reply_markup)
        return
    
    now = datetime.now()
    last_rest = player.get("last_rest")
    
    if player["hp"] >= player["max_hp"]:
        player["last_rest"] = now
        await save_players()
        keyboard = [
            [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
            [InlineKeyboardButton("🏪 Loja", callback_data="shop")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, "✅ HP cheio. Descanso reiniciado.", reply_markup=reply_markup)
        return
    
    if not last_rest:
        player["last_rest"] = now
        await save_players()
        keyboard = [
            [InlineKeyboardButton("🛌 Aguardando...", callback_data="rest")],
            [InlineKeyboardButton("🔙 Parar descanso", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, 
            "🛌 Descanso iniciado.\n"
            f"Recuperando {REST_HEAL} HP a cada {format_rest_time(REST_INTERVAL_SECONDS)}.\n\n"
            f"{rest_progress_bar(0)}\n"
            f"⏳ Proxima cura em {format_rest_time(REST_INTERVAL_SECONDS)}.",
            reply_markup=reply_markup
        )
        return
    
    elapsed = (now - last_rest).total_seconds()
    ticks = int(elapsed // REST_INTERVAL_SECONDS)
    if ticks <= 0:
        remaining = REST_INTERVAL_SECONDS - elapsed
        progress_percent = int((elapsed / REST_INTERVAL_SECONDS) * 100)
        keyboard = [
            [InlineKeyboardButton("🛌 Aguardando...", callback_data="rest")],
            [InlineKeyboardButton("🔙 Parar descanso", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, 
            "🛌 Você já está descansando.\n"
            f"{rest_progress_bar(elapsed)} {progress_percent}%\n"
            f"⏳ Proxima cura em {format_rest_time(remaining)}.",
            reply_markup=reply_markup
        )
        return
    
    heal_amount = ticks * REST_HEAL
    new_hp = min(player["max_hp"], player["hp"] + heal_amount)
    actual_heal = new_hp - player["hp"]
    player["hp"] = new_hp
    
    if player["hp"] >= player["max_hp"]:
        player["last_rest"] = now
    else:
        player["last_rest"] = last_rest + timedelta(seconds=ticks * REST_INTERVAL_SECONDS)
    
    await save_players()
    
    cures_text = f"Curado {ticks}x" if ticks > 1 else "Curado 1x"
    keyboard = [
        [InlineKeyboardButton("🛌 Continuar descansando", callback_data="rest")],
        [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
        [InlineKeyboardButton("🏪 Loja", callback_data="shop")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await edit_callback_message(query, f"🛌 Descanso concluido. {cures_text}\n"
        f"❤️ Recuperou {actual_heal} de vida.\n"
        f"❤️ HP: {player['hp']}/{player['max_hp']}\n"
        f"{hp_bar_blocks(player['hp'], player['max_hp'])}\n\n"
        f"{rest_progress_bar(0) if player['hp'] >= player['max_hp'] else rest_progress_bar(elapsed % REST_INTERVAL_SECONDS)}",
        reply_markup=reply_markup
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volta ao menu principal"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🛌 Descansar", callback_data="rest")],
        [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
        [InlineKeyboardButton("🏪 Loja", callback_data="shop")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"🏠 **MENU PRINCIPAL**\n\n"
        f"O que deseja fazer?",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens de texto"""
    if context.user_data.get("awaiting_name"):
        await set_name(update, context)

def main():
    """Função principal"""
    print("=" * 60)
    print("INICIANDO RPG ADVENTURE BOT - VERSÃO HARDCORE")
    print("=" * 60)
    
    # Carrega dados salvos
    load_players()
    
    # Debug: Mostra URLs das imagens
    print(f"\n🖼️ URL da imagem da loja: {SHOP_IMAGE}")
    print(f"🖼️ URLs das imagens do vendedor:")
    for i, img in enumerate(MERCHANT_IMAGES, 1):
        print(f"   {i}. {img}")
    print()
    
    # COLE SEU TOKEN AQUI
    TOKEN = "8377886070:AAEMTmoTwknuNBbH4D-n7jQgz675dRVseSI"
    
    print(f"Token: {TOKEN[:10]}...")
    print("✅ Dados carregados")
    
    # Criar aplicação
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers de comando
    app.add_handler(CommandHandler("start", start))
    
    # Handlers de callback (botões)
    app.add_handler(CallbackQueryHandler(class_selected, pattern="^class_"))
    app.add_handler(CallbackQueryHandler(random_name, pattern="^random_name$"))
    app.add_handler(CallbackQueryHandler(merchant_buy_potion, pattern="^merchant_buy_potion$"))
    app.add_handler(CallbackQueryHandler(merchant_duel, pattern="^merchant_duel$"))
    app.add_handler(CallbackQueryHandler(continue_hunt, pattern="^continue_hunt$"))
    app.add_handler(CallbackQueryHandler(hunt, pattern="^hunt$"))
    app.add_handler(CallbackQueryHandler(attack, pattern="^attack$"))
    app.add_handler(CallbackQueryHandler(flee, pattern="^flee$"))
    app.add_handler(CallbackQueryHandler(inventory, pattern="^inventory$"))
    app.add_handler(CallbackQueryHandler(equip_menu, pattern="^equip_menu$"))
    app.add_handler(CallbackQueryHandler(equip_weapon_menu, pattern="^equip_weapon_menu$"))
    app.add_handler(CallbackQueryHandler(equip_armor_menu, pattern="^equip_armor_menu$"))
    app.add_handler(CallbackQueryHandler(equip_weapon, pattern="^equip_weapon_"))
    app.add_handler(CallbackQueryHandler(equip_armor, pattern="^equip_armor_"))
    app.add_handler(CallbackQueryHandler(use_item_menu, pattern="^use_item_menu$"))
    app.add_handler(CallbackQueryHandler(use_item, pattern="^use_item_"))
    app.add_handler(CallbackQueryHandler(sell_items, pattern="^sell_items$"))
    app.add_handler(CallbackQueryHandler(sell_drops, pattern="^sell_drops$"))
    app.add_handler(CallbackQueryHandler(sell_equipment, pattern="^sell_equipment$"))
    app.add_handler(CallbackQueryHandler(sell_all_quick, pattern="^sell_all_quick$"))
    app.add_handler(CallbackQueryHandler(sell_item_confirm, pattern="^sell_"))
    app.add_handler(CallbackQueryHandler(shop, pattern="^shop$"))
    app.add_handler(CallbackQueryHandler(shop_buy, pattern="^shop_buy$"))
    app.add_handler(CallbackQueryHandler(shop_potions, pattern="^shop_potions$"))
    app.add_handler(CallbackQueryHandler(shop_weapons, pattern="^shop_weapons$"))
    app.add_handler(CallbackQueryHandler(shop_armors, pattern="^shop_armors$"))
    app.add_handler(CallbackQueryHandler(shop_buffs, pattern="^shop_buffs$"))
    app.add_handler(CallbackQueryHandler(buy_item, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(show_status, pattern="^status$"))
    app.add_handler(CallbackQueryHandler(rest, pattern="^rest$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    
    # Handler para mensagens de texto (nome do personagem)
    from telegram.ext import MessageHandler, filters
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_name))
    
    print("✅ Handlers registrados")
    print("🤖 Bot iniciado! Pressione Ctrl+C para parar")
    print("=" * 60)
    
    # Iniciar bot
    app.run_polling()

if __name__ == "__main__":
    main()