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
import sys
import traceback
from game.shop import build_showcase_items
from game.combat import build_scaled_regular_monster
from game.drops import level_requirement_warning
from game.content import classes, starting_weapons, weapons, weapons_by_category, armors

# ========== SISTEMA DE LOGGING MELHORADO ==========
# Cores ANSI para terminal
CORES = {
    'CRÍTICO': '\033[91m',      # Vermelho
    'ERRO': '\033[93m',          # Amarelo
    'AVISO': '\033[94m',         # Azul
    'INFO': '\033[92m',          # Verde
    'RESET': '\033[0m'           # Reset
}

# Arquivo de log
LOG_FILE = "error_logs.txt"
ERROR_STATS = {"total": 0, "crítico": 0, "erro": 0, "aviso": 0}

def format_timestamp():
    """Retorna timestamp formatado"""
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def log_customizado(mensagem, tipo="INFO", user_id=None, funcao=None, context=None):
    """
    Sistema de logging customizado com cores e arquivo
    
    Args:
        mensagem: Mensagem de log
        tipo: "CRÍTICO", "ERRO", "AVISO", "INFO"
        user_id: ID do usuário (opcional)
        funcao: Nome da função (opcional)
        context: Contexto adicional (opcional)
    """
    timestamp = format_timestamp()
    cor = CORES.get(tipo, CORES['INFO'])
    
    # Montar prefixo
    prefixo = f"{cor}[{timestamp}] [{tipo}]{CORES['RESET']}"
    
    # Montar mensagem completa
    msg_completa = f"{prefixo} {mensagem}"
    
    if user_id:
        msg_completa += f" | User: {user_id}"
    if funcao:
        msg_completa += f" | Func: {funcao}"
    if context:
        msg_completa += f" | Context: {context}"
    
    # Imprimir no terminal
    print(msg_completa)
    
    # Salvar em arquivo
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{tipo}] {mensagem}")
            if user_id:
                f.write(f" | User: {user_id}")
            if funcao:
                f.write(f" | Func: {funcao}")
            if context:
                f.write(f" | Context: {context}")
            f.write("\n")
    except:
        pass
    
    # Atualizar estatísticas
    ERROR_STATS["total"] += 1
    if tipo in ERROR_STATS:
        ERROR_STATS[tipo] += 1

def get_user_context(update):
    """Extrai contexto do usuário de um Update"""
    try:
        if update.callback_query:
            return str(update.callback_query.from_user.id)
        elif update.effective_user:
            return str(update.effective_user.id)
    except:
        pass
    return None

# Configuração básica de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING  # Reduzir verbosidade do logging padrão
)
# ================================================

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
MONSTER_DAMAGE_RANGE = (2, 5)  # Dano base dos monstros (rebalanceado)
MONSTER_ATK_MULTIPLIER = 0.45  # Aproveitamento do ATK bruto do monstro
PLAYER_DEFENSE_MULTIPLIER = 0.85  # Efetividade da defesa do jogador
MONSTER_MIN_DAMAGE = 1
REST_COOLDOWN_BASE = 5  # Cooldown base começa em 5 segundos
REST_HEAL_PERCENT = 0.5
MONSTER_GOLD_MULTIPLIER = 1.55  # +55% ouro ao derrotar monstros
RANDOM_ENCOUNTER_CHANCE = 0.15  # 15% de chance de encontro
MERCHANT_POTION_NAME = "Poção pequena"
MERCHANT_DISCOUNT = 0.6
POTION_PRICE_MULTIPLIER = 0.85  # 15% OFF base para poções

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

# Dados de classes/armas/armaduras foram extraídos para game/content.py

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
        if data["category"] == class_lower or data["category"] == "geral":
            available[name] = data
    
    return available

def get_random_weapon_drop(player_level, monster_level=1):
    """Gera um drop aleatorio de arma baseado no nivel do jogador E do monstro"""
    # Usa o nível do monstro para determinar raridade máxima
    effective_level = max(1, monster_level)
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
    
    # Filtra armas da raridade que podem cair para o tier do monstro
    max_drop_level = min(25, max(player_level, monster_level + 1))
    rarity_weapons = {k: v for k, v in weapons.items() 
                      if v["rarity"] == chosen_rarity and v["level_req"] <= max_drop_level and v["price"] > 0}
    
    if rarity_weapons:
        return random.choice(list(rarity_weapons.items()))
    return None

def get_random_armor_drop(player_level, monster_level=1):
    """Gera um drop aleatorio de armadura baseado no nivel do jogador E do monstro"""
    # Usa o nível do monstro para determinar raridade máxima
    effective_level = max(1, monster_level)
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
    
    # Filtra armaduras da raridade que podem cair para o tier do monstro
    max_drop_level = min(25, max(player_level, monster_level + 1))
    rarity_armors = {k: v for k, v in armors.items() 
                     if v["rarity"] == chosen_rarity and v["level_req"] <= max_drop_level and v["price"] > 0}
    
    if rarity_armors:
        return random.choice(list(rarity_armors.items()))
    return None

def get_random_common_armor_drop(player_level, monster_level=1):
    """Gera um drop aleatorio de armadura comum (simples)"""
    max_drop_level = min(25, max(player_level, monster_level + 1))
    common_armors = {k: v for k, v in armors.items()
                     if v["rarity"] == "comum" and v["level_req"] <= max_drop_level and v["price"] > 0}

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
        "name": "Goblin", "hp": 70, "atk": 11, "xp": 25, "level": 2, "gold": 8,
        "drops": [
            {"item": "Poção pequena", "chance": 0.15},
            {"item": "Adaga", "chance": 0.1},
            {"item": "Ouro", "chance": 0.45}
        ],
        "effects": None,
        "spawn_weight": 1.0
    },
    {
        "name": "Orc", "hp": 120, "atk": 14, "xp": 50, "level": 3, "gold": 15,
        "drops": [
            {"item": "Poção média", "chance": 0.15},
            {"item": "Poção de vida extra", "chance": 0.08},
            {"item": "Espada enferrujada", "chance": 0.15},
            {"item": "Armadura de couro", "chance": 0.1},
            {"item": "Ouro", "chance": 0.35}
        ],
        "effects": ["fogo"],
        "spawn_weight": 0.55
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

    # ===== NOVOS MONSTROS (Nível 1-8) =====
    {
        "name": "Rato Gigante", "hp": 50, "atk": 6, "xp": 18, "level": 1, "gold": 5,
        "drops": [
            {"item": "Poção pequena", "chance": 0.15},
            {"item": "Ouro", "chance": 0.45}
        ],
        "effects": None,
        "spawn_weight": 1.2
    },
    {
        "name": "Morcego Cavernoso", "hp": 65, "atk": 8, "xp": 22, "level": 2, "gold": 8,
        "drops": [
            {"item": "Poção pequena", "chance": 0.14},
            {"item": "Ouro", "chance": 0.42}
        ],
        "effects": ["sangramento"],
        "spawn_weight": 1.0
    },
    {
        "name": "Besouro de Lama", "hp": 80, "atk": 9, "xp": 26, "level": 2, "gold": 9,
        "drops": [
            {"item": "Poção pequena", "chance": 0.15},
            {"item": "Ouro", "chance": 0.4}
        ],
        "effects": ["veneno"],
        "spawn_weight": 0.95
    },
    {
        "name": "Lobo Jovem", "hp": 95, "atk": 11, "xp": 32, "level": 3, "gold": 12,
        "drops": [
            {"item": "Poção pequena", "chance": 0.12},
            {"item": "Poção média", "chance": 0.08},
            {"item": "Ouro", "chance": 0.4}
        ],
        "effects": ["sangramento"]
    },
    {
        "name": "Bandido Novato", "hp": 110, "atk": 12, "xp": 38, "level": 3, "gold": 14,
        "drops": [
            {"item": "Poção pequena", "chance": 0.12},
            {"item": "Adaga enferrujada", "chance": 0.08},
            {"item": "Ouro", "chance": 0.45}
        ],
        "effects": None
    },
    {
        "name": "Aranha do Mato", "hp": 140, "atk": 14, "xp": 65, "level": 4, "gold": 22,
        "drops": [
            {"item": "Poção média", "chance": 0.15},
            {"item": "Armadura de couro", "chance": 0.08},
            {"item": "Ouro", "chance": 0.38}
        ],
        "effects": ["veneno"]
    },
    {
        "name": "Kobold", "hp": 150, "atk": 15, "xp": 72, "level": 4, "gold": 24,
        "drops": [
            {"item": "Poção média", "chance": 0.16},
            {"item": "Espada de madeira", "chance": 0.08},
            {"item": "Ouro", "chance": 0.42}
        ],
        "effects": None
    },
    {
        "name": "Zumbi Lento", "hp": 220, "atk": 16, "xp": 92, "level": 5, "gold": 30,
        "drops": [
            {"item": "Poção média", "chance": 0.2},
            {"item": "Cota de malha", "chance": 0.08},
            {"item": "Ouro", "chance": 0.42}
        ],
        "effects": ["veneno"]
    },
    {
        "name": "Esqueleto Arqueiro", "hp": 170, "atk": 18, "xp": 100, "level": 5, "gold": 34,
        "drops": [
            {"item": "Poção média", "chance": 0.18},
            {"item": "Arco curto", "chance": 0.1},
            {"item": "Ouro", "chance": 0.42}
        ],
        "effects": ["gelo"]
    },
    {
        "name": "Xamã Goblin", "hp": 210, "atk": 20, "xp": 120, "level": 6, "gold": 40,
        "drops": [
            {"item": "Poção média", "chance": 0.2},
            {"item": "Varinha de madeira", "chance": 0.1},
            {"item": "Ouro", "chance": 0.45}
        ],
        "effects": ["fogo", "eletrico"]
    },
    {
        "name": "Gnoll Caçador", "hp": 240, "atk": 21, "xp": 135, "level": 6, "gold": 46,
        "drops": [
            {"item": "Poção grande", "chance": 0.16},
            {"item": "Arco longo", "chance": 0.08},
            {"item": "Ouro", "chance": 0.46}
        ],
        "effects": ["sangramento"]
    },
    {
        "name": "Aranha Sombria", "hp": 300, "atk": 26, "xp": 185, "level": 7, "gold": 72,
        "drops": [
            {"item": "Poção grande", "chance": 0.22},
            {"item": "Armadura de placas", "chance": 0.08},
            {"item": "Ouro", "chance": 0.45}
        ],
        "effects": ["veneno", "sangramento"]
    },
    {
        "name": "Ogro Brutamontes", "hp": 360, "atk": 30, "xp": 210, "level": 8, "gold": 95,
        "drops": [
            {"item": "Poção grande", "chance": 0.22},
            {"item": "Martelo de ferro", "chance": 0.1},
            {"item": "Ouro", "chance": 0.45}
        ],
        "effects": ["atordoamento"]
    },
    {
        "name": "Feiticeiro Renegado", "hp": 260, "atk": 34, "xp": 230, "level": 8, "gold": 105,
        "drops": [
            {"item": "Poção grande", "chance": 0.24},
            {"item": "Cajado elemental", "chance": 0.08},
            {"item": "Ouro", "chance": 0.46}
        ],
        "effects": ["fogo", "eletrico", "veneno"]
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
            {"item": "Armadura anã", "chance": 0.12}
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
            {"item": "Grimório infinito", "chance": 0.18},
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
            {"item": "Armadura anã", "chance": 0.15}
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

MONSTER_BY_NAME = {m["name"]: m for m in monsters}

MAPS = [
    # ===== MAPA 1: PLANÍCIE (Níveis 1-5) =====
    {
        "id": "planicie",
        "name": "🌾 Planície",
        "monster_names": [
            "Slime", "Rato Gigante", "Morcego Cavernoso", "Goblin", "Orc"
        ],
        "regular_scaling": {"hp": 1.0, "atk": 1.0, "gold": 1.0},
        "boss": {
            "name": "Javali errante",
            "chance": 0.08,
            "intro_text": "📖 *O mato se agita e passos pesados ecoam. Um olhar furioso surge entre a grama alta.*",
            "phase2_text": "📖 *O Javali cai... e de dentro das suas viceras surgem silhuetas menores, prontas para vingar a queda.*",
            "phases": [
                {
                    "name": "Javali errante",
                    "hp": 300,
                    "atk": 20,
                    "xp": 0,
                    "gold": 0,
                    "level": 5,
                    "crit_chance": 0.15,
                    "crit_damage": 28,
                    "drops": [
                        {"item": "Poção média", "chance": 0.25},
                        {"item": "Armadura de couro", "chance": 0.12},
                        {"item": "Ouro", "chance": 0.4}
                    ],
                    "effects": ["sangramento"]
                },
                {
                    "name": "Filhos do caido",
                    "hp": 300,
                    "atk": 14,
                    "xp": 205,
                    "gold": 160,
                    "level": 6,
                    "drops": [
                        {"item": "Poção média", "chance": 0.3},
                        {"item": "Cota de malha", "chance": 0.1},
                        {"item": "Ouro", "chance": 0.45}
                    ],
                    "effects": ["sangramento", "veneno"],
                    "double_attack": True,
                    "attack_names": ["Filho 1", "Filho 2"]
                }
            ]
        },
        "next_map_id": "floresta"
    },
    
    # ===== MAPA 2: FLORESTA SOMBRIA (Níveis 5-8) =====
    {
        "id": "floresta",
        "name": "🌲 Floresta Sombria",
        "monster_names": [
            "Lobo Jovem", "Bandido Novato", "Aranha do Mato", "Kobold", "Esqueleto"
        ],
        "regular_scaling": {"hp": 1.25, "atk": 1.2, "gold": 1.35},
        "boss": {
            "name": "Guardião da Floresta",
            "chance": 0.08,
            "intro_text": "📖 *As árvores tremem. Uma presença ancestral emerge das sombras, protegendo seu território.*",
            "phases": [
                {
                    "name": "Guardião da Floresta",
                    "hp": 620,
                    "atk": 31,
                    "xp": 280,
                    "gold": 220,
                    "level": 9,
                    "drops": [
                        {"item": "Poção grande", "chance": 0.35},
                        {"item": "Arco élfico", "chance": 0.12},
                        {"item": "Armadura élfica", "chance": 0.1}
                    ],
                    "effects": ["sangramento", "veneno"],
                    "special_power": {
                        "name": "Raízes Aprisionadoras",
                        "chance": 0.3,
                        "extra_damage_min": 8,
                        "extra_damage_max": 16,
                        "apply_effect": "veneno",
                        "effect_chance": 0.6,
                        "message": "🌿 O Guardião prende você com raízes e drena sua força!"
                    }
                }
            ]
        },
        "next_map_id": "montanhas"
    },
    
    # ===== MAPA 3: MONTANHAS GELADAS (Níveis 8-11) =====
    {
        "id": "montanhas",
        "name": "🏔️ Montanhas Geladas",
        "monster_names": ["Zumbi Lento", "Esqueleto Arqueiro", "Ciclope", "Xamã Goblin", "Gnoll Caçador", "Troll"],
        "regular_scaling": {"hp": 1.45, "atk": 1.35, "gold": 1.6},
        "boss": {
            "name": "Wyvern Glacial",
            "chance": 0.08,
            "intro_text": "📖 *Um rugido ecoa entre os picos gelados. Asas de gelo cortam o céu!*",
            "phase2_text": "📖 *O Wyvern desperta sua fúria congelante!*",
            "phases": [
                {
                    "name": "Wyvern Glacial",
                    "hp": 550,
                    "atk": 35,
                    "xp": 350,
                    "gold": 280,
                    "level": 11,
                    "drops": [
                        {"item": "Poção grande", "chance": 0.4},
                        {"item": "Martelo de gelo", "chance": 0.15},
                        {"item": "Armadura celestial", "chance": 0.12}
                    ],
                    "effects": ["gelo"]
                }
            ]
        },
        "next_map_id": "cavernas"
    },
    
    # ===== MAPA 4: CAVERNAS PROFUNDAS (Níveis 10-13) =====
    {
        "id": "cavernas",
        "name": "⛏️ Cavernas Profundas",
        "monster_names": ["Basilisco", "Quimera", "Espectro", "Lich", "Cerberus"],
        "boss": {
            "name": "Lich",
            "chance": 0.08,
            "intro_text": "📖 *Uma presença morta-viva permeia o ar. O Lich Lord emerge das trevas.*",
            "phase2_text": "📖 *O Lich revela seu verdadeiro poder necromântico!*",
            "phases": [
                {
                    "name": "Lich Lord",
                    "hp": 650,
                    "atk": 42,
                    "xp": 450,
                    "gold": 350,
                    "level": 13,
                    "drops": [
                        {"item": "Poção grande", "chance": 0.45},
                        {"item": "Grimório antigo", "chance": 0.18},
                        {"item": "Armadura élfica", "chance": 0.15}
                    ],
                    "effects": ["veneno", "eletrico"]
                }
            ]
        },
        "next_map_id": "deserto"
    },
    
    # ===== MAPA 5: DESERTO ÁRIDO (Níveis 12-15) =====
    {
        "id": "deserto",
        "name": "🏜️ Deserto Árido",
        "monster_names": ["Cerberus", "Fênix", "Leviatã", "Lich", "Titã da Floresta"],
        "boss": {
            "name": "Fênix",
            "chance": 0.08,
            "intro_text": "📖 *Chamas dançam no horizonte. A Fênix Imortal surge das areias escaldantes!*",
            "phase2_text": "📖 *Das cinzas, a Fênix renasce com poder renovado!*",
            "phases": [
                {
                    "name": "Fênix Imortal",
                    "hp": 700,
                    "atk": 48,
                    "xp": 0,
                    "gold": 0,
                    "level": 14,
                    "drops": [],
                    "effects": ["fogo"]
                },
                {
                    "name": "Fênix Renascida",
                    "hp": 650,
                    "atk": 52,
                    "xp": 600,
                    "gold": 450,
                    "level": 15,
                    "drops": [
                        {"item": "Poção grande", "chance": 0.5},
                        {"item": "Espada flamejante", "chance": 0.18},
                        {"item": "Armadura demoníaca", "chance": 0.15}
                    ],
                    "effects": ["fogo", "fogo"]
                }
            ]
        },
        "next_map_id": "pantano"
    },
    
    # ===== MAPA 6: PÂNTANO TÓXICO (Níveis 14-17) =====
    {
        "id": "pantano",
        "name": "🌊 Pântano Tóxico",
        "monster_names": ["Leviatã", "Titã da Floresta", "Demônio das Chamas", "Gólem de Gelo", "Cerberus"],
        "boss": {
            "name": "Leviatã",
            "chance": 0.08,
            "intro_text": "📖 *As águas turvas se agitam violentamente. O Leviatã emerge das profundezas!*",
            "phase2_text": "📖 *O monstro marinho desencadeia sua fúria aquática!*",
            "phases": [
                {
                    "name": "Leviatã das Profundezas",
                    "hp": 850,
                    "atk": 58,
                    "xp": 750,
                    "gold": 550,
                    "level": 17,
                    "drops": [
                        {"item": "Poção grande", "chance": 0.55},
                        {"item": "Lança divina", "chance": 0.2},
                        {"item": "Armadura celestial", "chance": 0.18}
                    ],
                    "effects": ["gelo", "veneno"]
                }
            ]
        },
        "next_map_id": "ruinas"
    },
    
    # ===== MAPA 7: RUÍNAS AMALDIÇOADAS (Níveis 16-19) =====
    {
        "id": "ruinas",
        "name": "🏛️ Ruínas Amaldiçoadas",
        "monster_names": ["Demônio das Chamas", "Gólem de Gelo", "Dragão Antigo", "Senhor da Noite", "Rei Esqueleto"],
        "boss": {
            "name": "Necromante Supremo",
            "chance": 0.08,
            "intro_text": "📖 *Almas atormentadas sussurram nas ruínas. O Necromante Supremo se ergue!*",
            "phase2_text": "📖 *Invocando legião de mortos-vivos!*",
            "phases": [
                {
                    "name": "Necromante Supremo",
                    "hp": 950,
                    "atk": 65,
                    "xp": 900,
                    "gold": 650,
                    "level": 19,
                    "drops": [
                        {"item": "Poção grande", "chance": 0.6},
                        {"item": "Cajado ancião", "chance": 0.22},
                        {"item": "Armadura de Ainz", "chance": 0.2}
                    ],
                    "effects": ["veneno", "sangramento"]
                }
            ]
        },
        "next_map_id": "vulcao"
    },
    
    # ===== MAPA 8: VULCÃO FLAMEJANTE (Níveis 18-21) =====
    {
        "id": "vulcao",
        "name": "🌋 Vulcão Flamejante",
        "monster_names": ["Dragão Antigo", "Senhor da Noite", "Rei Esqueleto", "Rei Demônio", "Demônio das Chamas"],
        "boss": {
            "name": "Dragão Ancião",
            "chance": 0.08,
            "intro_text": "📖 *A lava ferve intensamente. O Dragão Ancião desperta de seu sono milenar!*",
            "phase2_text": "📖 *O dragão libera seu poder flamejante total!*",
            "phases": [
                {
                    "name": "Dragão Ancião",
                    "hp": 1100,
                    "atk": 75,
                    "xp": 0,
                    "gold": 0,
                    "level": 20,
                    "drops": [],
                    "effects": ["fogo"]
                },
                {
                    "name": "Dragão Enfurecido",
                    "hp": 1000,
                    "atk": 80,
                    "xp": 1200,
                    "gold": 850,
                    "level": 21,
                    "drops": [
                        {"item": "Poção grande", "chance": 0.65},
                        {"item": "Excalibur", "chance": 0.22},
                        {"item": "Armadura divina", "chance": 0.2}
                    ],
                    "effects": ["fogo", "sangramento"],
                    "double_attack": True,
                    "attack_names": ["Garra", "Cauda"]
                }
            ]
        },
        "next_map_id": "castelo"
    },
    
    # ===== MAPA 9: CASTELO DAS TREVAS (Níveis 20-23) =====
    {
        "id": "castelo",
        "name": "🏰 Castelo das Trevas",
        "monster_names": ["Rei Demônio", "Divindade Caída", "Entidade Ancestral", "Abissal", "Rei Esqueleto"],
        "boss": {
            "name": "Rei Demônio",
            "chance": 0.08,
            "intro_text": "📖 *As trevas se adensam. O Rei Demônio finalmente revela sua presença!*",
            "phase2_text": "📖 *Forma demoníaca completa liberada!*",
            "phases": [
                {
                    "name": "Rei Demônio",
                    "hp": 1250,
                    "atk": 88,
                    "xp": 1500,
                    "gold": 1000,
                    "level": 23,
                    "drops": [
                        {"item": "Poção grande", "chance": 0.7},
                        {"item": "Mjolnir", "chance": 0.25},
                        {"item": "Armadura do vazio", "chance": 0.22}
                    ],
                    "effects": ["fogo", "veneno", "eletrico"]
                }
            ]
        },
        "next_map_id": "abismo"
    },
    
    # ===== MAPA 10: ABISMO ETERNO (Níveis 23-25+) =====
    {
        "id": "abismo",
        "name": "🌌 Abismo Eterno",
        "monster_names": ["Divindade Caída", "Entidade Ancestral", "Abissal", "Titã Eterno"],
        "boss": {
            "name": "Entidade Primordial",
            "chance": 0.08,
            "intro_text": "📖 *O vazio se desfaz. A Entidade Primordial, origem de todo caos, se manifesta!*",
            "phase2_text": "📖 *A realidade se distorce! O fim está próximo!*",
            "phases": [
                {
                    "name": "Entidade Primordial",
                    "hp": 1500,
                    "atk": 95,
                    "xp": 0,
                    "gold": 0,
                    "level": 25,
                    "drops": [],
                    "effects": ["fogo", "gelo", "eletrico"]
                },
                {
                    "name": "Caos Absoluto",
                    "hp": 1400,
                    "atk": 100,
                    "xp": 2000,
                    "gold": 1500,
                    "level": 26,
                    "drops": [
                        {"item": "Poção grande", "chance": 0.8},
                        {"item": "Gungnir", "chance": 0.3},
                        {"item": "Armadura de Ainz", "chance": 0.25}
                    ],
                    "effects": ["fogo", "gelo", "eletrico", "veneno"],
                    "double_attack": True,
                    "attack_names": ["Aniquilação", "Destruição"]
                }
            ]
        },
        "next_map_id": None
    }
]

def get_map_by_id(map_id):
    for map_data in MAPS:
        if map_data["id"] == map_id:
            return map_data
    return MAPS[0] if MAPS else None

def get_map_monsters(map_data):
    if not map_data:
        return monsters
    result = []
    for name in map_data.get("monster_names", []):
        template = MONSTER_BY_NAME.get(name)
        if template:
            result.append(template)
    return result or monsters

# ===== MAPEAMENTO DE IMAGENS DOS MONSTROS =====
# Base URL para as imagens no GitHub
BASE_IMAGE_URL = "https://raw.githubusercontent.com/csbarcellos-tk/jogorpg-assets/main/images"

MONSTER_IMAGES = {
    # Bosses Finais
    "Leviatã": f"{BASE_IMAGE_URL}/leviatan.png",
    "Fênix": f"{BASE_IMAGE_URL}/fenix.png",
    "Lich": f"{BASE_IMAGE_URL}/lich.png",
    
    # Dragões
    "Dragão jovem": f"{BASE_IMAGE_URL}/dragao_jovem.png",
    
    # Clássicos
    "Slime": f"{BASE_IMAGE_URL}/Slime.png",
    "Goblin": f"{BASE_IMAGE_URL}/goblin.png",
    "Orc": f"{BASE_IMAGE_URL}/orc.png",
    "Esqueleto": f"{BASE_IMAGE_URL}/esqueleto.png",
    "Troll": f"{BASE_IMAGE_URL}/troll.png",
    "Rato Gigante": f"{BASE_IMAGE_URL}/Rato%20Gigante.png",
    "Morcego Cavernoso": f"{BASE_IMAGE_URL}/Morcego%20Cavernoso.png",
    "Besouro de Lama": f"{BASE_IMAGE_URL}/Besouro%20de%20Lama.png",
    "Lobo Jovem": f"{BASE_IMAGE_URL}/Lobo%20Jovem.png",
    "Bandido Novato": f"{BASE_IMAGE_URL}/Bandido%20Novato.png",
    "Kobold": f"{BASE_IMAGE_URL}/Kobold.png",
    "Esqueleto Arqueiro": f"{BASE_IMAGE_URL}/Esqueleto%20Arqueiro.png",
    # "Zumbi Lento": f"{BASE_IMAGE_URL}/Zumbi%20Lento.png",  # ❌ Imagem não existe no repositório
    "Aranha Sombria": f"{BASE_IMAGE_URL}/Aranha%20Sombria.png",
    "Xamã Goblin": f"{BASE_IMAGE_URL}/Xam%C3%A3%20Goblin.png",
    "Gnoll Caçador": f"{BASE_IMAGE_URL}/Gnoll%20Ca%C3%A7ador.png",
    "Ogro Brutamontes": f"{BASE_IMAGE_URL}/Ogro%20Brutamontes.png",
    "Feiticeiro Renegado": f"{BASE_IMAGE_URL}/Feiticeiro%20Renegado.png",
    
    # Lendários
    "Basilisco": f"{BASE_IMAGE_URL}/basilisco.png",
    "Quimera": f"{BASE_IMAGE_URL}/quimera.png",
    "Ciclope": f"{BASE_IMAGE_URL}/ciclope.png",
    
    # Elementais e Gigantes
    "Gólem de Gelo": f"{BASE_IMAGE_URL}/golem_de_gelo.png",
    "Abissal": f"{BASE_IMAGE_URL}/abissal.png",
    "Cerberus": f"{BASE_IMAGE_URL}/cerberus.png",
    "Demônio das Chamas": f"{BASE_IMAGE_URL}/demonio_das_chamas.png",
    "Divindade Caída": f"{BASE_IMAGE_URL}/divindade_caida.png",
    "Dragão Antigo": f"{BASE_IMAGE_URL}/dragao_antigo.png",
    "Entidade Ancestral": f"{BASE_IMAGE_URL}/entidade_ancestral.png",
    "Espectro": f"{BASE_IMAGE_URL}/espectro.png",
    "Rei Demônio": f"{BASE_IMAGE_URL}/rei_demonio.png",
    "Rei Esqueleto": f"{BASE_IMAGE_URL}/rei_esqueleto.png",
    "Senhor da Noite": f"{BASE_IMAGE_URL}/senhor_da_noite.png",
    "Titã da Floresta": f"{BASE_IMAGE_URL}/tita_da_floresta.png",
    "Titã Eterno": f"{BASE_IMAGE_URL}/tita_eterno.png",

    # Boss da Planicie
    "Javali errante": f"{BASE_IMAGE_URL}/javali_errante.png",
    "Filhos do caido": f"{BASE_IMAGE_URL}/filhos_do_caido.png",
}

MAP_IMAGES = {
    "planicie": f"{BASE_IMAGE_URL}/mapa_planicie.png",
    "floresta": f"{BASE_IMAGE_URL}/mapa_floresta.png",
    "montanhas": f"{BASE_IMAGE_URL}/mapa_montanhas.png",
    "cavernas": f"{BASE_IMAGE_URL}/mapa_cavernas.png",
    "deserto": f"{BASE_IMAGE_URL}/mapa_deserto.png",
    "pantano": f"{BASE_IMAGE_URL}/mapa_pantano.png",
    "ruinas": f"{BASE_IMAGE_URL}/mapa_ruinas.png",
    "vulcao": f"{BASE_IMAGE_URL}/mapa_vulcao.png",
    "castelo": f"{BASE_IMAGE_URL}/mapa_castelo.png",
    "abismo": f"{BASE_IMAGE_URL}/mapa_abismo.png"
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

# ===== IMAGENS DE EVENTOS ESPECIAIS (MAPA 2+) =====
TRAP_IMAGES = [
    f"{BASE_IMAGE_URL}/armadilha1.png",
    f"{BASE_IMAGE_URL}/armadilha2.png",
    f"{BASE_IMAGE_URL}/armadilha3.png"
]
METEOR_IMAGE = f"{BASE_IMAGE_URL}/chuva_de_meteoros.png"
SNAKE_IMAGE = f"{BASE_IMAGE_URL}/cobra.png"
GHOST_IMAGE = f"{BASE_IMAGE_URL}/ghost.png"
PORTAL_IMAGE = f"{BASE_IMAGE_URL}/portal.png"
SANCTUARY_IMAGE = f"{BASE_IMAGE_URL}/santuario.png"

# ===== IMAGEM DO MENU PRINCIPAL =====
MAIN_MENU_IMAGE = f"{BASE_IMAGE_URL}/tenda.png"

# Itens consumíveis
consumables = {
    # Poções de Cura
    "Poção pequena": {"heal": 20, "price": 50, "emoji": "🧪", "effect": None, "category": "cura"},
    "Poção média": {"heal": 40, "price": 100, "emoji": "🧪", "effect": None, "category": "cura"},
    "Poção grande": {"heal": 80, "price": 160, "emoji": "🧪", "effect": None, "category": "cura"},
    
    # Poção de Vida Extra (aumenta max HP)
    "Poção de vida extra": {"max_hp_boost": 50, "price": 300, "emoji": "💚", "effect": "vida_extra", "category": "especial"},
    
    # Antídoto
    "Antídoto": {"heal": 10, "price": 50, "emoji": "💊", "effect": "cura_veneno", "category": "cura"},
    
    # Poções de Força (Bônus de ATK)
    "Poção de força pequena": {"damage_bonus": 3, "duration": 2, "price": 80, "emoji": "💪", "effect": "buff", "category": "forca"},
    "Poção de força média": {"damage_bonus": 6, "duration": 3, "price": 150, "emoji": "💪", "effect": "buff", "category": "forca"},
    "Poção de força grande": {"damage_bonus": 10, "duration": 4, "price": 250, "emoji": "💪", "effect": "buff", "category": "forca"},
    
    # Poções de Resistência (Bônus de DEF)
    "Poção de resistência pequena": {"defense_bonus": 2, "duration": 2, "price": 80, "emoji": "🛡️", "effect": "buff", "category": "resistencia"},
    "Poção de resistência média": {"defense_bonus": 4, "duration": 3, "price": 150, "emoji": "🛡️", "effect": "buff", "category": "resistencia"},
    "Poção de resistência grande": {"defense_bonus": 7, "duration": 4, "price": 250, "emoji": "🛡️", "effect": "buff", "category": "resistencia"},
    
    # Poções de Velocidade (Aumenta crítico/evasão)
    "Poção de velocidade pequena": {"speed_bonus": 0.05, "duration": 2, "price": 100, "emoji": "⚡", "effect": "buff", "category": "velocidade"},
    "Poção de velocidade média": {"speed_bonus": 0.10, "duration": 3, "price": 180, "emoji": "⚡", "effect": "buff", "category": "velocidade"},
    "Poção de velocidade grande": {"speed_bonus": 0.15, "duration": 4, "price": 300, "emoji": "⚡", "effect": "buff", "category": "velocidade"},
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

# Sistema de mochila expansível (fase 1: loja + drops)
BACKPACKS = [
    {"id": "none", "name": "Sem mochila", "slots": 5, "price": 0, "level_req": 1, "source": "inicial", "emoji": "🟫"},
    {"id": "mochila_pano", "name": "Mochila de Pano", "slots": 10, "price": 30, "level_req": 1, "source": "loja", "emoji": "🟫"},
    {"id": "mochila_couro", "name": "Mochila de Couro", "slots": 15, "price": 500, "level_req": 5, "source": "loja", "emoji": "🟫"},
    {"id": "mochila_viagem", "name": "Mochila de Viagem", "slots": 20, "price": 1500, "level_req": 10, "source": "loja", "emoji": "🟫"},
    {"id": "mochila_mochileiro", "name": "Mochila de Mochileiro", "slots": 30, "price": 5000, "level_req": 20, "source": "loja", "emoji": "🟫"},
    {"id": "mochila_elfica", "name": "Mochila Élfica", "slots": 35, "price": 0, "level_req": 25, "source": "drop_raro", "emoji": "🟫"},
    {"id": "bolsa_dimensional", "name": "Bolsa Dimensional", "slots": 70, "price": 0, "level_req": 35, "source": "chefao", "emoji": "🟫"}
]
BACKPACKS_BY_ID = {bp["id"]: bp for bp in BACKPACKS}

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
            
            # Cria backup antes de salvar (previne perda de dados)
            if os.path.exists(SAVE_FILE) and os.path.getsize(SAVE_FILE) > 0:
                try:
                    import shutil
                    shutil.copy2(SAVE_FILE, SAVE_FILE + ".backup")
                except:
                    pass  # Se falhar o backup, continua mesmo assim
            
            # Salva em arquivo temporário primeiro
            temp_file = SAVE_FILE + ".tmp"
            with open(temp_file, "w", encoding='utf-8') as f:
                json.dump(players_serializable, f, ensure_ascii=False, indent=2)
            
            # Só sobrescreve o arquivo principal se o temporário foi salvo com sucesso
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                import shutil
                shutil.move(temp_file, SAVE_FILE)
                logging.debug(f"✅ Jogadores salvos com sucesso! Total: {len(players)}")
            else:
                logging.error("❌ Arquivo temporário vazio ou não criado!")
        except Exception as e:
            logging.error(f"❌ Erro ao salvar jogadores: {e}")
            # Tenta restaurar do backup se algo deu errado
            backup_file = SAVE_FILE + ".backup"
            if os.path.exists(backup_file) and os.path.getsize(backup_file) > 0:
                try:
                    import shutil
                    shutil.copy2(backup_file, SAVE_FILE)
                    logging.info("✅ Backup restaurado após erro de salvamento")
                except:
                    pass

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
            # Verifica se o arquivo tem conteúdo antes de carregar
            if os.path.getsize(SAVE_FILE) == 0:
                logging.warning("Arquivo players.json está vazio! Mantendo dados em memória.")
                return
            
            with open(SAVE_FILE, "r", encoding='utf-8') as f:
                players_loaded = json.load(f)
            
            # Se o arquivo carregou mas está vazio, não sobrescreve
            if not players_loaded:
                logging.warning("players.json carregou vazio! Mantendo dados em memória.")
                return
            
            # Converte strings de volta para datetime
            players = {}
            for user_id, player_data in players_loaded.items():
                players[user_id] = player_data
                players[user_id].setdefault("inventory", {})
                players[user_id].setdefault("backpack_id", "none")
                players[user_id].setdefault("pending_drop_swaps", [])
                players[user_id].setdefault("map_id", "planicie")
                players[user_id].setdefault("unlocked_maps", ["planicie"])
                players[user_id].setdefault("boss_defeated", {"planicie": False})
                for key in ["created_at", "last_daily", "last_hunt", "last_rest"]:
                    if key in player_data and player_data[key]:
                        try:
                            players[user_id][key] = datetime.fromisoformat(player_data[key])
                        except:
                            players[user_id][key] = None
            
            logging.info(f"✅ Jogadores carregados! Total: {len(players)}")
        else:
            logging.info("Nenhum arquivo de save encontrado. Iniciando com dados vazios.")
    except Exception as e:
        logging.error(f"❌ ERRO ao carregar jogadores: {e}")
        # NÃO sobrescreve players se der erro - mantém dados existentes
        if not players:
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

def get_player_backpack(player):
    """Retorna a mochila atual do jogador"""
    backpack_id = player.get("backpack_id", "none")
    backpack = BACKPACKS_BY_ID.get(backpack_id, BACKPACKS_BY_ID["none"])
    player["backpack_id"] = backpack["id"]
    return backpack

def get_inventory_used_slots(player):
    """Conta quantos slots do inventário estão ocupados (itens empilháveis usam 1 slot por tipo)"""
    return sum(1 for qty in player.get("inventory", {}).values() if qty > 0)

def get_inventory_capacity(player):
    """Retorna a capacidade total da mochila equipada"""
    return get_player_backpack(player)["slots"]

def add_item_to_inventory(player, item_name, quantity=1):
    """Adiciona item ao inventário respeitando limite de slots"""
    current_qty = player["inventory"].get(item_name, 0)
    used_slots = get_inventory_used_slots(player)
    capacity = get_inventory_capacity(player)

    needs_new_slot = current_qty <= 0
    if needs_new_slot and used_slots >= capacity:
        return False

    player["inventory"][item_name] = current_qty + quantity
    return True

def queue_pending_drop(player, item_name, item_type):
    """Adiciona um drop pendente para troca quando inventário estiver cheio"""
    pending = player.setdefault("pending_drop_swaps", [])
    emoji = "🎁"
    if item_type == "consumable" and item_name in consumables:
        emoji = consumables[item_name]["emoji"]
    elif item_type == "misc" and item_name in misc_items:
        emoji = misc_items[item_name]["emoji"]

    pending.append({"item": item_name, "type": item_type, "emoji": emoji})

def get_occupied_inventory_items(player):
    """Retorna itens ocupando slots no inventário"""
    return [item for item, qty in player.get("inventory", {}).items() if qty > 0]

def try_drop_backpack_upgrade(player, monster):
    """Tentativa de drop de mochilas especiais por monstros fortes/chefões"""
    current_slots = get_inventory_capacity(player)
    player_level = player.get("level", 1)
    monster_level = monster.get("level", 1)

    # Drop raro: Mochila Élfica (35 slots)
    if current_slots < 35 and player_level >= 25 and monster_level >= 15:
        if random.random() < 0.04:
            player["backpack_id"] = "mochila_elfica"
            return "\n🎒 Drop raro! Você encontrou **Mochila Élfica** (+35 slots)!"

    # Chefão: Bolsa Dimensional (70 slots)
    if current_slots < 70 and player_level >= 35 and monster_level >= 20:
        if random.random() < 0.015:
            player["backpack_id"] = "bolsa_dimensional"
            return "\n🎒 Recompensa de chefão! Você recebeu **Bolsa Dimensional** (+70 slots)!"

    return ""

def format_rest_time(seconds_left):
    """Formata o tempo restante do descanso"""
    seconds_left = max(0, int(seconds_left))
    minutes = seconds_left // 60
    seconds = seconds_left % 60
    return f"{minutes}m {seconds}s"

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

def calculate_monster_damage(player, monster, include_class_defense=True):
    """Calcula dano do monstro com escala mais justa para progressão"""
    armor_defense = armors[player["armor"]]["defense"]
    class_defense = get_class_defense_bonus(player["class"], player["level"]) if include_class_defense else 0
    monster_level = monster.get("level", 1)
    player_level = player.get("level", 1)

    effective_defense = int((armor_defense + class_defense) * PLAYER_DEFENSE_MULTIPLIER)
    
    # AJUSTE: Monstros de nível médio/alto precisam de melhor scaling
    attack_level_scale = 1.0 + max(0, monster_level - 3) * 0.06  # Aumentado de 0.04 para 0.06
    pressure_scale = 1.0 + max(0, monster_level - player_level) * 0.05  # Aumentado de 0.03 para 0.05
    
    # AJUSTE: Aumenta aproveitamento do ATK base do monstro para níveis 5+
    atk_multiplier = MONSTER_ATK_MULTIPLIER
    if monster_level >= 5:
        atk_multiplier += 0.1  # 0.45 -> 0.55 para monstros nível 5+
    if monster_level >= 10:
        atk_multiplier += 0.1  # 0.55 -> 0.65 para monstros nível 10+
    
    monster_attack_component = int(monster["atk"] * atk_multiplier * attack_level_scale * pressure_scale)
    base_roll = random.randint(MONSTER_DAMAGE_RANGE[0], MONSTER_DAMAGE_RANGE[1])

    # Variação real por turno (evita dano fixo em sequência)
    attack_variance = random.randint(0, max(3, monster_level))

    # AJUSTE: Monstros de nível médio/alto atravessam melhor a defesa
    defense_efficiency = max(0.45, 1.0 - (monster_level * 0.020))  # Mudado de 0.015 para 0.020
    mitigated_defense = int(effective_defense * defense_efficiency)
    defense_variance = random.randint(max(0, mitigated_defense - 3), mitigated_defense)  # Mudado de -2 para -3

    raw_damage = base_roll + monster_attack_component + attack_variance - defense_variance

    # Amortece early game sem afetar muito o mid/late game
    if player_level <= 3:
        raw_damage -= 1

    # AJUSTE: Dano mínimo escala melhor com o nível do monstro
    minimum_damage = MONSTER_MIN_DAMAGE
    if monster_level >= 2:
        minimum_damage = max(minimum_damage, 2)
    if monster_level >= 5:
        minimum_damage = max(minimum_damage, 4)  # Mudado de 3 para 4
    if monster_level >= 8:
        minimum_damage = max(minimum_damage, 6)  # Novo threshold
    if monster_level >= 10:
        minimum_damage = max(minimum_damage, 8)  # Mudado de 4 para 8
    if monster_level >= 15:
        minimum_damage = max(minimum_damage, 10)  # Novo threshold
    if monster_level >= 18:
        minimum_damage = max(minimum_damage, 12)  # Mudado de 5 para 12

    # Quando ficar abaixo do mínimo, ainda aplica pequena variação para não travar em valor fixo
    if raw_damage <= minimum_damage:
        return random.randint(minimum_damage, minimum_damage + 2)  # Mudado de +1 para +2

    return raw_damage

def apply_boss_critical(damage, monster):
    """Aplica crítico do boss se configurado"""
    crit_chance = monster.get("crit_chance", 0)
    crit_damage = monster.get("crit_damage")
    
    if crit_chance > 0 and crit_damage and random.random() < crit_chance:
        return crit_damage, True  # Retorna dano crítico e flag
    
    return damage, False  # Retorna dano normal e sem crítico

def apply_monster_special_power(player, monster):
    """Aplica poder especial configurado no monstro (quando houver)."""
    special_power = monster.get("special_power")
    if not special_power:
        return 0, ""

    chance = special_power.get("chance", 0)
    if chance <= 0 or random.random() >= chance:
        return 0, ""

    extra_damage_min = special_power.get("extra_damage_min", 0)
    extra_damage_max = special_power.get("extra_damage_max", extra_damage_min)
    extra_damage = 0
    if extra_damage_max >= extra_damage_min and extra_damage_max > 0:
        extra_damage = random.randint(extra_damage_min, extra_damage_max)

    power_name = special_power.get("name", "Poder Especial")
    power_message = special_power.get("message")
    if power_message:
        text = f"\n{power_message}"
    else:
        text = f"\n✨ {monster['name']} ativou **{power_name}**!"

    if extra_damage > 0:
        text += f" (+{extra_damage} de dano)"

    effect_name = special_power.get("apply_effect")
    effect_chance = special_power.get("effect_chance", 0.0)
    if effect_name and effect_name not in player.get("effects", []) and random.random() < effect_chance:
        player.setdefault("effects", []).append(effect_name)
        text += f"\n☠️ Você foi afetado por {effect_name}!"

    return extra_damage, text

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

def format_monster_effects(player):
    """Formata efeitos ativos no inimigo com detalhes de turno."""
    effects = player.get("monster_effects", [])
    if not effects:
        return ""

    timers = player.get("monster_effect_timers", {})
    formatted = []
    for effect in effects:
        if effect == "veneno":
            venom = timers.get("veneno")
            if venom and venom.get("turns", 0) > 0:
                formatted.append(f"☠️ Veneno ({venom['turns']}T) • -{venom['damage']}/turno")
            else:
                formatted.append("☠️ Veneno")
        else:
            formatted.append(effect.capitalize())
    return " • ".join(formatted)

def format_player_effects(player):
    """Formata efeitos negativos no jogador com detalhes de turno."""
    effects = player.get("effects", [])
    if not effects:
        return ""

    timers = player.get("effect_timers", {})
    formatted = []
    for effect in effects:
        if effect == "veneno":
            venom = timers.get("veneno")
            if venom and venom.get("turns", 0) > 0:
                formatted.append(f"☠️ Veneno ({venom['turns']}T) • -{venom['damage']}/turno")
            else:
                formatted.append("☠️ Veneno")
        else:
            formatted.append(effect.capitalize())
    return " • ".join(formatted)

def format_player_buffs(player):
    """Formata buffs ativos do jogador com duração."""
    active_buffs = [buff for buff in player.get("buffs", []) if buff.get("duration", 0) > 0]
    if not active_buffs:
        return ""

    formatted = []
    for buff in active_buffs:
        formatted.append(f"{buff['name']} ({buff['duration']}T)")
    return " • ".join(formatted)

def format_combat_status(header, monster, player, turn, show_monster_icon=True):
    """Monta o layout do combate em texto"""
    monster_name = f"👹 {monster['name']}" if show_monster_icon else monster["name"]
    monster_bar = hp_bar_blocks(monster["hp"], monster["max_hp"])
    player_bar = hp_bar_blocks(player["hp"], player["max_hp"])

    monster_effects_text = format_monster_effects(player)
    player_buffs_text = format_player_buffs(player)
    player_effects_text = format_player_effects(player)

    # Monta o texto base
    text = (
        f"⚔️ **{header}**\n\n"
        f"👤 {player['name']} ({classes[player['class']]['emoji']} {player['class']})\n"
        f"❤️ HP: {player['hp']}/{player['max_hp']}\n"
        f"{player_bar}\n\n"
        f"vs\n\n"
        f"{monster_name}\n"
        f"❤️ HP: {monster['hp']}/{monster['max_hp']}\n"
        f"{monster_bar}\n\n"
    )
    
    # Adiciona seções somente se houver conteúdo
    if player_buffs_text:
        text += f"🛡️ **BUFFS**\n{player_buffs_text}\n\n"
    
    if player_effects_text:
        text += f"☠️ **EFEITOS EM VOCÊ**\n{player_effects_text}\n\n"
    
    if monster_effects_text:
        text += f"🩸 **EFEITOS NO INIMIGO**\n{monster_effects_text}\n\n"
    
    text += f"🎯 Turno: {turn}"
    
    return text

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

    # Rebalanceamento fixo de poções
    if category == "potions":
        buy_price = max(1, int(buy_price * POTION_PRICE_MULTIPLIER))
    
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
    """Inicia um novo personagem OU exibe menu do personagem existente"""
    user_id = str(update.effective_user.id)
    
    # Limpa chat anterior se existir
    if "last_message" in context.user_data:
        await clean_chat(context, update.effective_chat.id, context.user_data["last_message"])
    
    # SE O JOGADOR JÁ EXISTE, mostra o menu principal
    if user_id in players:
        player = players[user_id]
        
        keyboard = [
            [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt"),
             InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🛌 Descansar", callback_data="rest"),
             InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
            [InlineKeyboardButton("🏪 Loja", callback_data="shop"),
             InlineKeyboardButton("🗺️ Mapa", callback_data="map_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = (
            f"👋 **Bem-vindo de volta, {player['name']}!**\n\n"
            f"📚 **Classe:** {player['class']}\n"
            f"⭐ **Nível:** {player['level']}\n"
            f"❤️ **HP:** {player['hp']}/{player['max_hp']}\n"
            f"💰 **Gold:** {player.get('gold', 0)}\n\n"
            f"**O que deseja fazer?**"
        )
        
        try:
            msg = await update.message.reply_photo(
                photo=MAIN_MENU_IMAGE,
                caption=message_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception:
            msg = await update.message.reply_text(
                message_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        context.user_data["last_message"] = msg.message_id
        return
    
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
        "backpack_id": "none",  # Começa sem mochila (5 slots)
        "pending_drop_swaps": [],
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
        "rest_count": 0,  # Contador de descansos para cooldown progressivo
        "current_map": "Planicie",
        "map_id": "planicie",
        "unlocked_maps": ["planicie"],
        "boss_defeated": {"planicie": False},
        "monster_effects": [],  # Efeitos no monstro causados pelo jogador
        "monster_effect_timers": {},
        "effect_timers": {}
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
        [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt"),
         InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🛌 Descansar", callback_data="rest"),
         InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
        [InlineKeyboardButton("🏪 Loja", callback_data="shop"),
         InlineKeyboardButton("🗺️ Mapa", callback_data="map_menu")]
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

    try:
        msg = await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=MAIN_MENU_IMAGE,
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

    user_id = str(query.from_user.id)
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        return

    player = players[user_id]
    base_price = max(1, int(consumables[MERCHANT_POTION_NAME]["price"] * POTION_PRICE_MULTIPLIER))
    discount_price = max(1, int(base_price * MERCHANT_DISCOUNT))

    if player["gold"] < discount_price:
        faltando = discount_price - player["gold"]
        await query.answer(f"❌ Gold insuficiente. Faltam {faltando}💰.", show_alert=True)
        return

    if not add_item_to_inventory(player, MERCHANT_POTION_NAME):
        await query.answer("❌ Mochila cheia. Compre uma mochila maior na loja.", show_alert=True)
        return

    player["gold"] -= discount_price
    await save_players()
    await query.answer("✅ Compra concluída!")

    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await edit_callback_message(query, f"✅ **COMPRA CONCLUÍDA**\n\n"
        f"Item: {MERCHANT_POTION_NAME}\n"
        f"💰 Custo: {discount_price} gold\n"
        f"💰 Gold restante: {player['gold']}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def merchant_duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia duelo hardcore com o vendedor ambulante"""
    query = update.callback_query

    user_id = str(query.from_user.id)
    if user_id not in players:
        await query.answer("❌ Use /start para criar um personagem!", show_alert=True)
        return

    player = players[user_id]
    if player.get("monster"):
        await query.answer("❌ Você já está em combate!", show_alert=True)
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
    player["monster_effect_timers"] = {}
    player["combat_turn"] = 1
    await save_players()

    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data="attack")],
        [InlineKeyboardButton("🎒 Usar item", callback_data="use_item_menu")],
        [InlineKeyboardButton("🏃 Fugir", callback_data="flee")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.answer("⚔️ Duelo iniciado!")

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
            
            # Primeira vez de combate: deleta msg anterior e envia nova
            if turn == 1:
                try:
                    await query.delete_message()
                except:
                    pass
                # Envia nova mensagem com reply_photo
                await query.message.reply_photo(
                    photo=monster_image,
                    caption=combat_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            elif has_photo:
                # Já em combate: apenas edita caption (mantém imagem)
                try:
                    await query.edit_message_caption(
                        caption=combat_text,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    # Se falhar edit_caption, deleta e reenvia
                    logging.warning(f"Erro ao editar caption: {e}")
                    try:
                        await query.delete_message()
                    except:
                        pass
                    await query.message.reply_photo(
                        photo=monster_image,
                        caption=combat_text,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
            else:
                # Mensagem atual não tem foto: deleta e envia com foto
                try:
                    await query.delete_message()
                except:
                    pass
                await query.message.reply_photo(
                    photo=monster_image,
                    caption=combat_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
        except Exception as e:
            # Último fallback: apenas texto COM botões
            logging.warning(f"Erro ao enviar mensagem de combate com imagem: {e}")
            try:
                # Tenta deletar mensagem atual e enviar nova só com texto
                try:
                    await query.delete_message()
                except:
                    pass
                await query.message.reply_text(
                    combat_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e2:
                # Se tudo falhar, tenta apenas editar
                logging.warning(f"Erro ao enviar nova mensagem: {e2}")
                try:
                    await query.edit_message_text(combat_text, parse_mode='Markdown', reply_markup=reply_markup)
                except:
                    pass
    else:
        # Sem imagem do monstro: enviar apenas texto COM botões
        try:
            await query.edit_message_text(combat_text, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception as e:
            # Fallback: deleta e envia nova
            logging.warning(f"Erro ao editar mensagem sem imagem: {e}")
            try:
                await query.delete_message()
            except:
                pass
            try:
                await query.message.reply_text(
                    combat_text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except:
                pass

async def edit_callback_message(query, text, reply_markup=None, parse_mode=None):
    """Edita mensagem de callback, respeitando fotos com legenda."""
    try:
        if query.message and getattr(query.message, "photo", None):
            # Mensagem tem foto: edita caption
            await query.edit_message_caption(
                caption=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        else:
            # Mensagem sem foto: edita texto
            await query.edit_message_text(
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
    except Exception as e:
        # Fallback 1: Se edit_caption falhou em mensagem com foto, tenta edit_text
        try:
            if query.message and getattr(query.message, "photo", None):
                await query.edit_message_text(
                    text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
            else:
                # Se edit_text já falhou, tenta edit_caption
                await query.edit_message_caption(
                    caption=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
        except Exception as e2:
            # Fallback 2: Deleta mensagem original e envia nova
            try:
                await query.delete_message()
                if reply_markup:
                    await query.message.reply_text(
                        text,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup
                    )
                else:
                    await query.message.reply_text(text, parse_mode=parse_mode)
            except Exception as e3:
                # Último recurso: apenas loga o erro
                logging.warning(f"Erro ao editar mensagem de callback: {e3}")
                pass

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
    map_id = player.get("map_id", "planicie")
    map_data = get_map_by_id(map_id)

    if map_data and map_id != map_data["id"]:
        player["map_id"] = map_data["id"]

    boss_defeated = player.get("boss_defeated", {}).get(map_data["id"], False) if map_data else False
    boss_data = map_data.get("boss") if map_data else None

    if boss_data and not boss_defeated:
        boss_chance = boss_data.get("chance", 0.08)
        if random.random() < boss_chance:
            boss_phase = boss_data["phases"][0].copy()
            monster = {
                "name": boss_phase["name"],
                "hp": boss_phase["hp"],
                "max_hp": boss_phase["hp"],
                "atk": boss_phase["atk"],
                "xp": boss_phase["xp"],
                "gold": boss_phase["gold"],
                "level": boss_phase["level"],
                "drops": boss_phase.get("drops", []),
                "effects": boss_phase.get("effects", []),
                "special_power": boss_phase.get("special_power"),
                "is_boss": True,
                "boss_map_id": map_data["id"],
                "boss_phases": boss_data["phases"],
                "boss_phase_index": 0,
                "boss_intro_text": boss_data.get("intro_text"),
                "boss_phase2_text": boss_data.get("phase2_text")
            }

            player["monster"] = monster
            player["monster_effects"] = []
            player["monster_effect_timers"] = {}
            player["combat_turn"] = 1
            
            # Aplica veneno pendente de evento anterior (cobra)
            if player.get("pending_poison", 0) > 0:
                if "veneno" not in player.get("effects", []):
                    player.setdefault("effects", []).append("veneno")
                player["effect_timers"] = player.get("effect_timers", {})
                player["effect_timers"]["veneno"] = player["pending_poison"]
                player["pending_poison"] = 0  # Remove o pending após aplicar
            
            await save_players()

            intro_text = monster.get("boss_intro_text")
            header = "👑 BOSS ENCONTRADO"
            if intro_text:
                header = f"{intro_text}\n\n{header}"

            await send_combat_message(query, monster, player, header, player["combat_turn"])
            return

    # Escolhe monstro baseado no nível com variedade maior
    min_level = max(1, player["level"] - 1)  # Permite monstros 1 nível abaixo
    max_level = player["level"] + 2  # Permite monstros até 2 níveis acima (rebalanceado)

    map_monsters = get_map_monsters(map_data)
    available_monsters = [m for m in map_monsters if min_level <= m["level"] <= max_level]
    
    if not available_monsters:
        available_monsters = map_monsters[:5] if map_monsters else monsters[:5]
    
    # Sistema de peso: monstros próximos do nível do jogador têm mais chance
    weights = []
    last_monster_name = player.get("last_monster_name")
    for m in available_monsters:
        level_diff = abs(m["level"] - player["level"])
        if level_diff == 0:
            weight = 5  # Mesmo nível: peso 5
        elif level_diff == 1:
            weight = 4  # 1 nível de diferença: peso 4
        elif level_diff == 2:
            weight = 3  # 2 níveis: peso 3
        else:
            weight = 1  # 3+ níveis: peso 1

        if last_monster_name and m["name"] == last_monster_name:
            weight = max(1, int(weight * 0.3))

        weight *= m.get("spawn_weight", 1.0)

        weights.append(weight)
    
    monster_template = random.choices(available_monsters, weights=weights)[0].copy()
    player["last_monster_name"] = monster_template["name"]

    # Cria monstro com stats ajustados
    monster = build_scaled_regular_monster(monster_template, player["level"], map_data)

    player["monster"] = monster
    player["monster_effects"] = []
    player["monster_effect_timers"] = {}
    player["combat_turn"] = 1
    
    # Aplica veneno pendente de evento anterior (cobra)
    if player.get("pending_poison", 0) > 0:
        if "veneno" not in player.get("effects", []):
            player.setdefault("effects", []).append("veneno")
        player["effect_timers"] = player.get("effect_timers", {})
        player["effect_timers"]["veneno"] = player["pending_poison"]
        player["pending_poison"] = 0  # Remove o pending após aplicar
    
    await save_players()

    await send_combat_message(query, monster, player, "⚔️ COMBATE INICIADO", player["combat_turn"])

async def hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia uma caçada com cooldown"""
    query = update.callback_query
    logging.info(f"[HUNT] Callback recebido de user {query.from_user.id}")
    
    try:
        await query.answer()
    except Exception as e:
        logging.error(f"[HUNT] Erro ao responder callback: {e}")
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        await edit_callback_message(query, "❌ Crie seu personagem com /start.")
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
                    [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")],
                    [InlineKeyboardButton("⚔️ Caçar novamente", callback_data="hunt")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await edit_callback_message(query, f"⏳ **CAÇADA EM COOLDOWN**\n\n"
                    f"Tente novamente em {5 - int(time_diff)}s.",
                    parse_mode='Markdown',
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
        # Define eventos baseado no mapa atual
        current_map = player.get("map", 0)
        if current_map == 0:  # Mapa 1 - com vendedor
            encounter = random.choices(
                ["merchant", "camp", "treasure", "potion_small", "potion_medium", "potion_large", "gold_small", "gold_medium", "gold_large", "gold_huge", "nothing"],
                weights=[170, 20, 30, 80, 35, 15, 130, 90, 30, 20, 30]
            )[0]
        else:  # Mapa 2+ - sem vendedor, com eventos especiais
            encounter = random.choices(
                ["camp", "treasure", "potion_small", "potion_medium", "potion_large", "gold_small", "gold_medium", "gold_large", "gold_huge", "trap", "meteor", "snake", "ghost", "portal", "sanctuary", "nothing"],
                weights=[20, 30, 80, 35, 15, 130, 90, 30, 20, 60, 10, 40, 35, 25, 15, 30]
            )[0]

        if encounter == "merchant":
            merchant_narration = random.choice([
                "📖 *Você se depara com um homem estranho perto da trilha, usando roupas gastas. Ele sorri de forma misteriosa e abre sua bolsa repleta de potions. É um vendedor ambulante!*",
                "📖 *Uma figura encapuzada surge da neblina. Ele revela ser um vendedor ambulante com poções mágicas para vender.*",
                "📖 *Um comerciante viajante bloqueia seu caminho. Seus olhos brilham enquanto ele oferece suspeitos frascos de poções.*",
                "📖 *No meio da floresta, você encontra um velho senhor com uma mochila repleta de frascos e garrafas misteriosas.*",
                "📖 *Uma voz rouca chama sua atenção. Um vendedor ambulante emerge entre as árvores, oferecendo seus produtos curiosos.*"
            ])
            base_price = max(1, int(consumables[MERCHANT_POTION_NAME]["price"] * POTION_PRICE_MULTIPLIER))
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
                           f"Ele oferece {MERCHANT_POTION_NAME} por um preço mais barato.\n" \
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
                f"❤️ Recuperou {heal} HP.",
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
                f"💰 Recompensa: +{gold_found} gold",
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
                f"💰 **RECOMPENSA**\n+{gold_found} gold",
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
                f"💰 **RECOMPENSA**\n+{gold_found} gold",
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
                f"💰 **RECOMPENSA**\n+{gold_found} gold",
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
                f"💰 **RECOMPENSA RARA**\n+{gold_found} gold",
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
            added = add_item_to_inventory(player, potion_name)
            if not added:
                queue_pending_drop(player, potion_name, "consumable")
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            if not added:
                keyboard.append([InlineKeyboardButton("🔁 Trocar item pelo drop", callback_data="pending_drops_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            result_text = f"🧪 **ITEM ENCONTRADO**\n{potion_name}" if added else "❌ Mochila cheia. Você encontrou uma poção, mas não conseguiu carregar."
            await edit_callback_message(query, f"{narration}\n\n"
                f"{result_text}",
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
            added = add_item_to_inventory(player, potion_name)
            if not added:
                queue_pending_drop(player, potion_name, "consumable")
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            if not added:
                keyboard.append([InlineKeyboardButton("🔁 Trocar item pelo drop", callback_data="pending_drops_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            result_text = f"🧪 **ITEM ENCONTRADO**\n{potion_name}" if added else "❌ Mochila cheia. Você encontrou uma poção, mas não conseguiu carregar."
            await edit_callback_message(query, f"{narration}\n\n"
                f"{result_text}",
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
            added = add_item_to_inventory(player, potion_name)
            if not added:
                queue_pending_drop(player, potion_name, "consumable")
            await save_players()
            keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
            if not added:
                keyboard.append([InlineKeyboardButton("🔁 Trocar item pelo drop", callback_data="pending_drops_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            result_text = f"🧪 **ITEM ENCONTRADO**\n{potion_name}" if added else "❌ Mochila cheia. Você encontrou uma poção, mas não conseguiu carregar."
            await edit_callback_message(query, f"{narration}\n\n"
                f"{result_text}",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return

        # ===== EVENTOS ESPECIAIS DO MAPA 2+ =====
        
        if encounter == "trap":
            narration = random.choice([
                "📖 *Você avista algo estranho no chão à frente. Parece ser uma armadilha antiga! O que você faz?*",
                "📖 *Um brilho metálico chama sua atenção. É uma armadilha! Você percebe antes de ativá-la.*",
                "📖 *Você nota fios quase invisíveis esticados na passagem. É claramente uma armadilha!*",
                "📖 *Algo parece suspeito na trilha à frente. Você identifica os sinais de uma armadilha perigosa.*"
            ])
            keyboard = [
                [InlineKeyboardButton("🔧 Desarmar (70% sucesso)", callback_data="trap_disarm")],
                [InlineKeyboardButton("🏃 Evitar cuidadosamente (90% sucesso)", callback_data="trap_avoid")],
                [InlineKeyboardButton("➡️ Ignorar e seguir", callback_data="trap_ignore")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            trap_image = random.choice(TRAP_IMAGES)
            try:
                try:
                    await query.delete_message()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=trap_image,
                    caption=f"{narration}\n\n"
                            f"⚠️ **ARMADILHA DETECTADA!**\n\n"
                            f"O que você fará?",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"❌ Erro ao enviar imagem da armadilha: {e}")
                await edit_callback_message(query, f"{narration}\n\n"
                    f"⚠️ **ARMADILHA DETECTADA!**\n\n"
                    f"O que você fará?",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            return

        if encounter == "meteor":
            narration = random.choice([
                "📖 *O céu escurece repentinamente! Meteoros ardentes começam a cair do céu! O que você faz?*",
                "📖 *Um estrondo anuncia perigo! Pedras flamejantes caem do céu em sua direção!*",
                "📖 *As estrelas caem! Meteoros gigantes descem rapidamente! Você precisa agir rápido!*",
                "📖 *O mundo treme! Uma chuva de meteoros se aproxima! Decide seu destino agora!*"
            ])
            keyboard = [
                [InlineKeyboardButton("🏃 Correr (50% evitar)", callback_data="meteor_run")],
                [InlineKeyboardButton("🛡️ Se proteger (reduz dano)", callback_data="meteor_shield")],
                [InlineKeyboardButton("⚔️ Destruir meteoros", callback_data="meteor_attack")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                try:
                    await query.delete_message()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=METEOR_IMAGE,
                    caption=f"{narration}\n\n"
                            f"☄️ **CHUVA DE METEOROS!**\n\n"
                            f"Como você reage?",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"❌ Erro ao enviar imagem de meteoro: {e}")
                await edit_callback_message(query, f"{narration}\n\n"
                    f"☄️ **CHUVA DE METEOROS!**\n\n"
                    f"Como você reage?",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            return

        if encounter == "snake":
            narration = random.choice([
                "📖 *SSSSS! Uma cobra venenosa surge à sua frente! Ela está pronta para atacar!*",
                "📖 *SIBILAR! Uma serpente gigante bloqueia seu caminho! Suas presas gotejam veneno!*",
                "📖 *Você ouve um som sinistro. Uma víbora letal emerge das sombras, encarando você!*",
                "📖 *Uma cobra enorme se enrola no caminho à frente. Ela parece agressiva!*"
            ])
            keyboard = [
                [InlineKeyboardButton("⚔️ Matar a cobra (70% sucesso)", callback_data="snake_kill")],
                [InlineKeyboardButton("🏃 Fugir rapidamente (90% sucesso)", callback_data="snake_flee")],
                [InlineKeyboardButton("👀 Ignorar e passar devagar", callback_data="snake_ignore")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                try:
                    await query.delete_message()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=SNAKE_IMAGE,
                    caption=f"{narration}\n\n"
                            f"🐍 **COBRA VENENOSA!**\n\n"
                            f"O que você fará?",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"❌ Erro ao enviar imagem de cobra: {e}")
                await edit_callback_message(query, f"{narration}\n\n"
                    f"🐍 **COBRA VENENOSA!**\n\n"
                    f"O que você fará?",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            return

        if encounter == "ghost":
            narration = random.choice([
                "📖 *Uma presença gelada envolve você. Um fantasma surge chorando... 'Por favor, ajude-me...'*",
                "📖 *Um espírito triste materializa-se à sua frente. 'Preciso de sua ajuda, viajante...'*",
                "📖 *Uma figura etérea surge das sombras. 'Estou perdido há séculos... pode me ajudar?'*",
                "📖 *O ar congela. Um fantasma antigo aparece suplicando: 'Apenas você pode me libertar...'*"
            ])
            keyboard = [
                [InlineKeyboardButton("🤝 Ajudar o fantasma", callback_data="ghost_help")],
                [InlineKeyboardButton("🚫 Recusar e seguir", callback_data="ghost_refuse")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                try:
                    await query.delete_message()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=GHOST_IMAGE,
                    caption=f"{narration}\n\n"
                            f"👻 **ENCONTRO FANTASMAGÓRICO!**\n\n"
                            f"O fantasma pede sua ajuda. O que você fará?",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"❌ Erro ao enviar imagem de fantasma: {e}")
                await edit_callback_message(query, f"{narration}\n\n"
                    f"👻 **ENCONTRO FANTASMAGÓRICO!**\n\n"
                    f"O fantasma pede sua ajuda. O que você fará?",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            return

        if encounter == "portal":
            narration = random.choice([
                "📖 *Um portal mágico surge à sua frente com um brilho intenso e misterioso!*",
                "📖 *Uma fenda dimensional rasga o espaço. O portal pulsa com energia desconhecida...*",
                "📖 *Um vórtice de energia pura abre-se no ar. Você sente sua atração magnética!*",
                "📖 *O chão brilha com runas antigas. Um portal se materializa diante de você!*"
            ])
            keyboard = [
                [InlineKeyboardButton("✨ Entrar no portal", callback_data="portal_enter")],
                [InlineKeyboardButton("🚫 Ignorar e seguir", callback_data="portal_ignore")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                try:
                    await query.delete_message()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=PORTAL_IMAGE,
                    caption=f"{narration}\n\n"
                            f"🌀 **PORTAL DIMENSIONAL!**\n\n"
                            f"Para onde ele leva? Você ousa entrar?",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"❌ Erro ao enviar imagem de portal: {e}")
                await edit_callback_message(query, f"{narration}\n\n"
                    f"🌀 **PORTAL DIMENSIONAL!**\n\n"
                    f"Para onde ele leva? Você ousa entrar?",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            return

        if encounter == "sanctuary":
            narration = random.choice([
                "📖 *Você descobre um santuário esquecido. Uma aura divina envolve o local...*",
                "📖 *Entre as ruínas, um altar sagrado emana luz dourada. Os deuses oferecem uma bênção...*",
                "📖 *Um templo antigo surge à sua frente. Uma voz divina ecoa: 'Escolha sua bênção...'*",
                "📖 *Você encontra um santuário dos deuses antigos. Três ofertas se manifestam à sua frente...*"
            ])
            keyboard = [
                [InlineKeyboardButton("❤️ Bênção de Cura (40-60% HP)", callback_data="sanctuary_heal")],
                [InlineKeyboardButton("💚 Bênção da Vida (+10 HP máx)", callback_data="sanctuary_hp")],
                [InlineKeyboardButton("💰 Bênção da Fortuna (80-150 gold)", callback_data="sanctuary_gold")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                try:
                    await query.delete_message()
                except:
                    pass
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=SANCTUARY_IMAGE,
                    caption=f"{narration}\n\n"
                            f"⛪ **SANTUÁRIO SAGRADO!**\n\n"
                            f"Os deuses oferecem uma bênção. Escolha sabiamente:",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"❌ Erro ao enviar imagem de santuário: {e}")
                await edit_callback_message(query, f"{narration}\n\n"
                    f"⛪ **SANTUÁRIO SAGRADO!**\n\n"
                    f"Os deuses oferecem uma bênção. Escolha sabiamente:",
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
            "🌫️ **NADA ACONTECEU**",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return

    await start_hunt_combat(query, player)

# ===== HANDLERS DOS EVENTOS ESPECIAIS DO MAPA 2+ =====

async def trap_disarm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tenta desarmar a armadilha"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    success = random.random() < 0.70  # 70% chance
    if success:
        gold_reward = random.randint(30, 80)
        player["gold"] += gold_reward
        await save_players()
        result = f"✅ **SUCESSO!**\n\n" \
                f"Você desarmou a armadilha com maestria!\n" \
                f"💰 Encontrou peças valiosas: +{gold_reward} gold"
    else:
        damage = random.randint(int(player["max_hp"] * 0.20), int(player["max_hp"] * 0.35))
        damage = max(10, damage)
        player["hp"] = max(1, player["hp"] - damage)
        await save_players()
        result = f"❌ **FALHOU!**\n\n" \
                f"A armadilha dispara! Você é atingido!\n" \
                f"💔 Dano: {damage}\n" \
                f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def trap_avoid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tenta evitar a armadilha"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    success = random.random() < 0.90  # 90% chance
    if success:
        result = f"✅ **EVITOU!**\n\n" \
                f"Você passa pela armadilha com cuidado e segue em frente ileso!"
    else:
        damage = random.randint(int(player["max_hp"] * 0.10), int(player["max_hp"] * 0.20))
        damage = max(5, damage)
        player["hp"] = max(1, player["hp"] - damage)
        await save_players()
        result = f"❌ **ATINGIDO!**\n\n" \
                f"Você escorrega e ativa a armadilha!\n" \
                f"💔 Dano: {damage}\n" \
                f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def trap_ignore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ignora a armadilha"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    damage = random.randint(int(player["max_hp"] * 0.25), int(player["max_hp"] * 0.40))
    damage = max(15, damage)
    player["hp"] = max(1, player["hp"] - damage)
    await save_players()
    
    result = f"💥 **ARMADILHA ATIVADA!**\n\n" \
            f"Você ignora os sinais e pisa direto na armadilha!\n" \
            f"💔 Dano crítico: {damage}\n" \
            f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def meteor_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tenta correr dos meteoros"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    success = random.random() < 0.50  # 50% chance
    if success:
        result = f"✅ **ESCAPOU!**\n\n" \
                f"Você corre velozmente e escapa ileso da chuva de meteoros!"
    else:
        damage = random.randint(int(player["max_hp"] * 0.25), int(player["max_hp"] * 0.40))
        damage = max(15, damage)
        player["hp"] = max(1, player["hp"] - damage)
        await save_players()
        result = f"💥 **ATINGIDO!**\n\n" \
                f"Um meteoro atinge você durante a fuga!\n" \
                f"💔 Dano: {damage}\n" \
                f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def meteor_shield(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se protege dos meteoros"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    damage = random.randint(int(player["max_hp"] * 0.10), int(player["max_hp"] * 0.20))
    damage = max(8, damage)
    player["hp"] = max(1, player["hp"] - damage)
    await save_players()
    
    result = f"🛡️ **PROTEGEU-SE!**\n\n" \
            f"Você se cobre e minimiza o impacto!\n" \
            f"💔 Dano reduzido: {damage}\n" \
            f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def meteor_attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tenta destruir os meteoros"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    weapon_damage = weapons.get(player["weapon"], {}).get("damage", 5)
    success = weapon_damage >= 20  # Precisa de arma forte
    
    if success:
        gold_reward = random.randint(60, 120)
        player["gold"] += gold_reward
        await save_players()
        result = f"⚔️ **DESTRUIU!**\n\n" \
                f"Você destrói os meteoros com sua arma poderosa!\n" \
                f"💎 Fragmentos de meteoro: +{gold_reward} gold"
    else:
        damage = random.randint(int(player["max_hp"] * 0.30), int(player["max_hp"] * 0.50))
        damage = max(20, damage)
        player["hp"] = max(1, player["hp"] - damage)
        await save_players()
        result = f"❌ **FALHOU!**\n\n" \
                f"Sua arma é fraca demais! Os meteoros te atingem!\n" \
                f"💔 Dano pesado: {damage}\n" \
                f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def snake_kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tenta matar a cobra"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    success = random.random() < 0.70  # 70% chance
    if success:
        gold_reward = random.randint(40, 90)
        player["gold"] += gold_reward
        await save_players()
        result = f"⚔️ **VITÓRIA!**\n\n" \
                f"Você mata a cobra antes que ela ataque!\n" \
                f"🐍 Pele de cobra valiosa: +{gold_reward} gold"
    else:
        damage = random.randint(int(player["max_hp"] * 0.15), int(player["max_hp"] * 0.25))
        damage = max(10, damage)
        player["hp"] = max(1, player["hp"] - damage)
        # Adiciona efeito de veneno no próximo combate
        player["pending_poison"] = 1  # 1 turno de veneno
        await save_players()
        result = f"🐍 **MORDIDA!**\n\n" \
                f"A cobra te morde antes de morrer!\n" \
                f"💔 Dano: {damage}\n" \
                f"🩸 Veneno aplicado! (1 turno no próximo combate)\n" \
                f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def snake_flee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foge da cobra"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    success = random.random() < 0.90  # 90% chance
    if success:
        result = f"🏃 **FUGIU!**\n\n" \
                f"Você se afasta rapidamente e a cobra desiste da perseguição!"
    else:
        damage = random.randint(int(player["max_hp"] * 0.08), int(player["max_hp"] * 0.15))
        damage = max(5, damage)
        player["hp"] = max(1, player["hp"] - damage)
        await save_players()
        result = f"🐍 **MORDIDA RÁPIDA!**\n\n" \
                f"A cobra consegue uma mordida durante sua fuga!\n" \
                f"💔 Dano leve: {damage}\n" \
                f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def snake_ignore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ignora a cobra"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    damage = random.randint(int(player["max_hp"] * 0.18), int(player["max_hp"] * 0.30))
    damage = max(12, damage)
    player["hp"] = max(1, player["hp"] - damage)
    # Adiciona 2 turnos de veneno
    player["pending_poison"] = 2
    await save_players()
    
    result = f"🐍 **ATAQUE VENENOSO!**\n\n" \
            f"Você ignora a cobra e ela te ataca pelas costas!\n" \
            f"💔 Dano: {damage}\n" \
            f"🩸 Veneno forte aplicado! (2 turnos no próximo combate)\n" \
            f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def ghost_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ajuda o fantasma"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    # Recompensas por ajudar
    reward_type = random.choice(["gold", "heal", "item"])
    
    if reward_type == "gold":
        gold_reward = random.randint(100, 200)
        player["gold"] += gold_reward
        result = f"✨ **GRATIDÃO!**\n\n" \
                f"O fantasma se liberta e desaparece em paz...\n" \
                f"💰 Ele deixa um tesouro: +{gold_reward} gold"
    elif reward_type == "heal":
        heal = random.randint(int(player["max_hp"] * 0.40), int(player["max_hp"] * 0.60))
        player["hp"] = min(player["max_hp"], player["hp"] + heal)
        result = f"✨ **BÊNÇÃO!**\n\n" \
                f"O fantasma envolve você em luz curativa!\n" \
                f"❤️ Restaurou {heal} HP!\n" \
                f"❤️ HP: {player['hp']}/{player['max_hp']}"
    else:  # item
        potion_name = random.choice(["Poção média", "Poção grande"])
        added = add_item_to_inventory(player, potion_name)
        if added:
            result = f"✨ **PRESENTE!**\n\n" \
                    f"O fantasma lhe presenteia uma poção!\n" \
                    f"🧪 Recebeu: {potion_name}"
        else:
            gold_reward = 120
            player["gold"] += gold_reward
            result = f"✨ **PRESENTE!**\n\n" \
                    f"Mochila cheia! O fantasma lhe dá gold ao invés.\n" \
                    f"💰 Recebeu: {gold_reward} gold"
    
    await save_players()
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def ghost_refuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recusa ajudar o fantasma"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    # Penalidade por recusar
    gold_loss = random.randint(30, 80)
    player["gold"] = max(0, player["gold"] - gold_loss)
    await save_players()
    
    result = f"👻 **MALDIÇÃO!**\n\n" \
            f"O fantasma fica furioso com sua recusa!\n" \
            f"💰 Ele amaldiçoa você: -{gold_loss} gold\n" \
            f"💰 Gold: {player['gold']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def portal_enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entra no portal"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    is_good = random.random() < 0.60  # 60% bom, 40% ruim
    
    if is_good:
        reward_type = random.choice(["gold_big", "heal", "both"])
        if reward_type == "gold_big":
            gold_reward = random.randint(120, 250)
            player["gold"] += gold_reward
            result = f"✨ **PORTAL BENÉFICO!**\n\n" \
                    f"Você encontra uma câmara do tesouro!\n" \
                    f"💰 Recompensa épica: +{gold_reward} gold"
        elif reward_type == "heal":
            heal = int(player["max_hp"] * 0.50)
            player["hp"] = min(player["max_hp"], player["hp"] + heal)
            result = f"✨ **PORTAL CURATIVO!**\n\n" \
                    f"Você é teleportado para uma fonte mágica!\n" \
                    f"❤️ Restaurou {heal} HP!\n" \
                    f"❤️ HP: {player['hp']}/{player['max_hp']}"
        else:  # both
            gold_reward = random.randint(80, 150)
            heal = int(player["max_hp"] * 0.30)
            player["gold"] += gold_reward
            player["hp"] = min(player["max_hp"], player["hp"] + heal)
            result = f"✨ **PORTAL DIVINO!**\n\n" \
                    f"Você alcança um oásis dimensional!\n" \
                    f"💰 Gold: +{gold_reward}\n" \
                    f"❤️ HP: +{heal}\n" \
                    f"❤️ HP: {player['hp']}/{player['max_hp']}"
    else:
        penalty_type = random.choice(["damage", "gold_loss", "both"])
        if penalty_type == "damage":
            damage = random.randint(int(player["max_hp"] * 0.25), int(player["max_hp"] * 0.40))
            damage = max(15, damage)
            player["hp"] = max(1, player["hp"] - damage)
            result = f"⚠️ **PORTAL MALIGNO!**\n\n" \
                    f"Você é jogado em um abismo dimensional!\n" \
                    f"💔 Dano: {damage}\n" \
                    f"❤️ HP: {player['hp']}/{player['max_hp']}"
        elif penalty_type == "gold_loss":
            gold_loss = random.randint(50, 120)
            player["gold"] = max(0, player["gold"] - gold_loss)
            result = f"⚠️ **PORTAL LADRÃO!**\n\n" \
                    f"Entidades dimensionais roubam suas riquezas!\n" \
                    f"💰 Perdeu: {gold_loss} gold\n" \
                    f"💰 Gold: {player['gold']}"
        else:  # both
            damage = random.randint(int(player["max_hp"] * 0.15), int(player["max_hp"] * 0.25))
            damage = max(10, damage)
            gold_loss = random.randint(30, 70)
            player["hp"] = max(1, player["hp"] - damage)
            player["gold"] = max(0, player["gold"] - gold_loss)
            result = f"⚠️ **PORTAL DO CAOS!**\n\n" \
                    f"O portal te lança em um pesadelo dimensional!\n" \
                    f"💔 Dano: {damage}\n" \
                    f"💰 Perdeu: {gold_loss} gold\n" \
                    f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    await save_players()
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def portal_ignore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ignora o portal"""
    query = update.callback_query
    await query.answer()
    
    result = f"🚫 **PORTAL IGNORADO**\n\n" \
            f"Você decide não arriscar e continua sua jornada..."
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def sanctuary_heal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Escolhe bênção de cura"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    heal = random.randint(int(player["max_hp"] * 0.40), int(player["max_hp"] * 0.60))
    heal = max(25, heal)
    player["hp"] = min(player["max_hp"], player["hp"] + heal)
    await save_players()
    
    result = f"❤️ **BÊNÇÃO DE CURA!**\n\n" \
            f"Uma luz divina envolve você, restaurando sua vitalidade!\n" \
            f"❤️ Recuperou {heal} HP!\n" \
            f"❤️ HP: {player['hp']}/{player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def sanctuary_hp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Escolhe bênção de vida extra"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    hp_bonus = 10
    player["max_hp"] += hp_bonus
    player["hp"] += hp_bonus  # Também aumenta o HP atual
    await save_players()
    
    result = f"💚 **BÊNÇÃO DA VIDA!**\n\n" \
            f"Os deuses aumentam sua força vital permanentemente!\n" \
            f"💚 HP máximo: +{hp_bonus}\n" \
            f"❤️ Novo HP máximo: {player['max_hp']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def sanctuary_gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Escolhe bênção de fortuna"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    player = players[user_id]
    
    gold_reward = random.randint(80, 150)
    player["gold"] += gold_reward
    await save_players()
    
    result = f"💰 **BÊNÇÃO DA FORTUNA!**\n\n" \
            f"Os deuses abençoam você com riquezas!\n" \
            f"💰 Recebeu: +{gold_reward} gold\n" \
            f"💰 Gold total: {player['gold']}"
    
    keyboard = [[InlineKeyboardButton("➡️ Seguir caçada", callback_data="continue_hunt")]]
    await edit_callback_message(query, result, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def continue_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Continua a caçada apos um encontro"""
    query = update.callback_query

    user_id = str(query.from_user.id)
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        return

    player = players[user_id]
    if player.get("monster"):
        await query.answer("❌ Você já está em combate!", show_alert=True)
        return

    await query.answer()
    await start_hunt_combat(query, player)

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa ataques"""
    query = update.callback_query
    logging.info(f"[ATTACK] Callback recebido de user {query.from_user.id}")
    
    user_id = str(query.from_user.id)
    
    # Debounce: evita múltiplos cliques rápidos processarem attack 2x
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.8):
        try:
            await query.answer("⏳ Aguarde um momento...", show_alert=True)
        except:
            pass
        return
    
    try:
        await query.answer()
    except Exception as e:
        logging.error(f"[ATTACK] Erro ao responder callback: {e}")
    
    if user_id not in players:
        await edit_callback_message(query, "❌ Crie seu personagem com /start.")
        return
    
    player = players[user_id]
    
    if not player.get("monster"):
        await edit_callback_message(query, "❌ Nenhum combate ativo. Use /hunt para iniciar.")
        return
    
    monster = player["monster"]
    
    # Verificação de segurança extra
    if not monster or not isinstance(monster, dict):
        player["monster"] = None
        await edit_callback_message(query, "❌ Erro no combate. Use /hunt para iniciar nova batalha.")
        return
    
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
    base_turn_damage = int(base_damage * damage_multiplier)
    critical_bonus_damage = base_turn_damage if is_critical else 0
    damage = base_turn_damage + critical_bonus_damage
    
    # Aplica efeito da arma
    effect_message = ""
    if weapon_effect and random.random() < 0.3:  # 30% de chance de aplicar efeito
        if weapon_effect not in player.get("monster_effects", []):
            player.setdefault("monster_effects", []).append(weapon_effect)
        if weapon_effect == "veneno":
            player.setdefault("monster_effect_timers", {})["veneno"] = {"turns": 2, "damage": 3}
            effect_message = "\n• ☠️ Veneno aplicado no inimigo: -3 HP/turno por 2 turnos."
        else:
            effect_message = f"\n• ✨ Efeito {weapon_effect} aplicado no inimigo."
    
    # Protege contra monstro sendo None
    if not monster or not isinstance(monster, dict):
        player["monster"] = None
        await edit_callback_message(query, "❌ Erro na batalha. Inicie nova caçada.")
        return
    
    monster["hp"] -= damage

    # Dano contínuo de veneno no monstro (se já estiver ativo)
    poison_tick_text = ""
    monster_venom = player.setdefault("monster_effect_timers", {}).get("veneno")
    if monster_venom and monster_venom.get("turns", 0) > 0 and monster["hp"] > 0:
        poison_damage = monster_venom["damage"]
        monster["hp"] -= poison_damage
        monster_venom["turns"] -= 1
        poison_tick_text = f"\n• ☠️ Veneno no inimigo causou {poison_damage} de dano ({monster_venom['turns']}T restantes)."
        if monster_venom["turns"] <= 0:
            player["monster_effect_timers"].pop("veneno", None)
            player["monster_effects"] = [e for e in player.get("monster_effects", []) if e != "veneno"]

    # Se o monstro caiu por dano direto/veneno, não revida
    player_poison_tick_text = ""
    if monster["hp"] <= 0:
        monster_damage = 0
        monster_attack_text = ""
    else:
        # Dano do monstro rebalanceado
        if monster.get("double_attack"):
            hit_names = monster.get("attack_names", ["Inimigo 1", "Inimigo 2"])
            monster_damage_first = calculate_monster_damage(player, monster, include_class_defense=True)
            monster_damage_second = calculate_monster_damage(player, monster, include_class_defense=True)
            monster_damage = monster_damage_first + monster_damage_second
            monster_attack_text = (
                f"\n• 💔 {hit_names[0]} causou {monster_damage_first} de dano."
                f"\n• 💔 {hit_names[1]} causou {monster_damage_second} de dano."
            )
        else:
            base_monster_damage = calculate_monster_damage(player, monster, include_class_defense=True)
            monster_damage, is_boss_crit = apply_boss_critical(base_monster_damage, monster)
            crit_indicator = " ⚡CRÍTICO!" if is_boss_crit else ""
            monster_attack_text = f"\n• 💔 {monster['name']} atacou: {monster_damage} de dano{crit_indicator}."
    
        special_power_damage, special_power_text = apply_monster_special_power(player, monster)
        if special_power_damage > 0:
            monster_damage += special_power_damage
        if special_power_text:
            monster_attack_text += f"\n• {special_power_text.strip()}"
    
        # Aplica efeitos do monstro no jogador (com proteção extra)
        if monster and isinstance(monster.get("effects"), list):
            for effect in monster.get("effects", []):
                if random.random() < 0.2:
                    if effect not in player.get("effects", []):
                        player.setdefault("effects", []).append(effect)
                    if effect == "veneno":
                        poison_damage = max(2, monster.get("level", 1) // 3)
                        player.setdefault("effect_timers", {})["veneno"] = {"turns": 2, "damage": poison_damage}
    
        player["hp"] -= monster_damage
        player["hp"] = max(0, player["hp"])  # Garante que HP não fique negativo

        # Dano contínuo de veneno no jogador
        player_venom = player.setdefault("effect_timers", {}).get("veneno")
        if player_venom and player_venom.get("turns", 0) > 0 and player["hp"] > 0:
            poison_damage = player_venom["damage"]
            player["hp"] -= poison_damage
            player["hp"] = max(0, player["hp"])
            player_venom["turns"] -= 1
            player_poison_tick_text = f"\n• ☠️ Veneno em você causou {poison_damage} de dano ({player_venom['turns']}T restantes)."
            if player_venom["turns"] <= 0:
                player["effect_timers"].pop("veneno", None)
                player["effects"] = [e for e in player.get("effects", []) if e != "veneno"]
    
    # Verifica se monstro morreu
    if monster["hp"] <= 0:
        if monster.get("is_boss") and monster.get("boss_phases"):
            phases = monster["boss_phases"]
            phase_index = monster.get("boss_phase_index", 0)

            if phase_index < len(phases) - 1:
                next_phase = phases[phase_index + 1]
                monster.update({
                    "name": next_phase["name"],
                    "hp": next_phase["hp"],
                    "max_hp": next_phase["hp"],
                    "atk": next_phase["atk"],
                    "xp": next_phase["xp"],
                    "gold": next_phase["gold"],
                    "level": next_phase["level"],
                    "drops": next_phase.get("drops", []),
                    "effects": next_phase.get("effects", []),
                    "special_power": next_phase.get("special_power"),
                    "boss_phase_index": phase_index + 1
                })
                player["monster_effects"] = []
                save_players_background()

                keyboard = [
                    [InlineKeyboardButton("⚔️ Atacar", callback_data="attack")],
                    [InlineKeyboardButton("🎒 Usar item", callback_data="use_item_menu")],
                    [InlineKeyboardButton("🏃 Fugir", callback_data="flee")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                phase_text = monster.get("boss_phase2_text")
                header = "⚠️ **O boss mudou de fase!**"
                if phase_text:
                    header = f"{phase_text}\n\n{header}"

                await edit_callback_message(
                    query,
                    f"{header}\n\n"
                    f"Agora enfrenta: **{monster['name']}**\n\n"
                    f"{format_combat_status('👑 FASE 2', monster, player, player.get('combat_turn', 1), show_monster_icon=False)}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return

            boss_map_id = monster.get("boss_map_id")
            if boss_map_id:
                player.setdefault("boss_defeated", {})[boss_map_id] = True
                map_data = get_map_by_id(boss_map_id)
                next_map_id = map_data.get("next_map_id") if map_data else None
                if next_map_id:
                    unlocked = player.setdefault("unlocked_maps", [])
                    if next_map_id not in unlocked:
                        unlocked.append(next_map_id)

        # Recompensas
        xp_gain = monster["xp"]
        gold_gain = max(1, int(monster["gold"] * MONSTER_GOLD_MULTIPLIER))
        
        player["xp"] += xp_gain
        player["gold"] += gold_gain
        
        # Processa drops
        drop_message = ""
        shuffled_drops = list(monster["drops"])
        random.shuffle(shuffled_drops)
        for drop in shuffled_drops:
            if random.random() < drop["chance"]:
                item = drop["item"]
                # Verifica se é arma
                if item in weapons:
                    if item not in player.get("equipped_weapons", []):
                        player.setdefault("equipped_weapons", []).append(item)
                        weapon_req = weapons[item].get("level_req", 1)
                        drop_message += f"\n🎁 Drop: arma {get_rarity_emoji(weapons[item]['rarity'])} {item} (Nv {weapon_req})"
                        drop_message += level_requirement_warning(player["level"], weapon_req, "arma")
                # Verifica se é armadura
                elif item in armors:
                    if item not in player.get("equipped_armors", []):
                        player.setdefault("equipped_armors", []).append(item)
                        armor_req = armors[item].get("level_req", 1)
                        drop_message += f"\n🎁 Drop: armadura {get_rarity_emoji(armors[item]['rarity'])} {item} (Nv {armor_req})"
                        drop_message += level_requirement_warning(player["level"], armor_req, "armadura")
                # Item consumível
                elif item in consumables:
                    if add_item_to_inventory(player, item):
                        drop_message += f"\n🎁 Drop: poção {consumables[item]['emoji']} {item}"
                    else:
                        queue_pending_drop(player, item, "consumable")
                        drop_message += f"\n❌ Mochila cheia. Não foi possível pegar {consumables[item]['emoji']} {item}."
                # Item misc
                elif item in misc_items:
                    if add_item_to_inventory(player, item):
                        drop_message += f"\n🎁 Drop: {misc_items[item]['emoji']} {item}"
                    else:
                        queue_pending_drop(player, item, "misc")
                        drop_message += f"\n❌ Mochila cheia. Não foi possível pegar {misc_items[item]['emoji']} {item}."
        
        # Tentativa de drop aleatório de armadura comum (monstros simples)
        if monster.get("level", 1) <= 3 and random.random() < 0.1:
            common_armor_drop = get_random_common_armor_drop(player["level"], monster.get("level", 1))
            if common_armor_drop:
                armor_name, armor_data = common_armor_drop
                if armor_name not in player.get("equipped_armors", []):
                    player.setdefault("equipped_armors", []).append(armor_name)
                    armor_req = armor_data.get("level_req", 1)
                    drop_message += f"\n🎁 Drop: armadura {get_rarity_emoji(armor_data['rarity'])} {armor_name} (Nv {armor_req})"
                    drop_message += level_requirement_warning(player["level"], armor_req, "armadura")

        # Tentativa de drop aleatório de arma (chance extra)
        if random.random() < 0.08:
            weapon_drop = get_random_weapon_drop(player["level"], monster.get("level", 1))
            if weapon_drop:
                weapon_name, weapon_data = weapon_drop
                if weapon_name not in player.get("equipped_weapons", []):
                    player.setdefault("equipped_weapons", []).append(weapon_name)
                    weapon_req = weapon_data.get("level_req", 1)
                    drop_message += f"\n🎁 Drop raro: arma {get_rarity_emoji(weapon_data['rarity'])} {weapon_name} (Nv {weapon_req})"
                    drop_message += level_requirement_warning(player["level"], weapon_req, "arma")
        
        # Tentativa de drop aleatório de armadura (chance extra)
        if random.random() < 0.06:
            armor_drop = get_random_armor_drop(player["level"], monster.get("level", 1))
            if armor_drop:
                armor_name, armor_data = armor_drop
                if armor_name not in player.get("equipped_armors", []):
                    player.setdefault("equipped_armors", []).append(armor_name)
                    armor_req = armor_data.get("level_req", 1)
                    drop_message += f"\n🎁 Drop raro: armadura {get_rarity_emoji(armor_data['rarity'])} {armor_name} (Nv {armor_req})"
                    drop_message += level_requirement_warning(player["level"], armor_req, "armadura")

        # Chance global de dropar poção de vida extra
        if random.random() < 0.12:
            extra_potion = "Poção de vida extra"
            if add_item_to_inventory(player, extra_potion):
                drop_message += f"\n🎁 Drop: poção de vida {consumables[extra_potion]['emoji']} {extra_potion}"
            else:
                queue_pending_drop(player, extra_potion, "consumable")
                drop_message += f"\n❌ Mochila cheia. Não foi possível pegar {consumables[extra_potion]['emoji']} {extra_potion}."

        drop_message += try_drop_backpack_upgrade(player, monster)
        
        xp_next = xp_needed(player["level"])
        message = f"🏆 **VITÓRIA!**\n\n"
        message += f"👹 Inimigo derrotado: {monster['name']}\n\n"
        message += f"🎁 **RECOMPENSAS**\n"
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
            player["rest_count"] = 0  # Reseta cooldown de descanso ao upar
            leveled_up = True
            message += f"\n\n🔥 **LEVEL UP!**\n📈 Novo nível: {player['level']}\n❤️ HP restaurado\n⏳ Cooldown de descanso resetado!"
        
        # Limpa efeitos
        player["monster"] = None
        player["effects"] = []
        player["monster_effects"] = []
        player["effect_timers"] = {}
        player["monster_effect_timers"] = {}
        player.pop("combat_turn", None)
        save_players_background()
        
        keyboard = [
            [InlineKeyboardButton("🎯 Caçar novamente", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")]
        ]
        if player.get("pending_drop_swaps"):
            keyboard.append([InlineKeyboardButton("🔁 Trocar item pelo drop", callback_data="pending_drops_menu")])
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
        player["effect_timers"] = {}
        player["monster_effect_timers"] = {}
        player.pop("combat_turn", None)
        save_players_background()
        keyboard = [
            [InlineKeyboardButton("😢 Recomeçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, f"💀 **DERROTA**\n\n"
            f"❤️ Reviveu com {player['hp']} HP\n"
            f"💰 Perdeu {gold_loss} gold ({percent}%)\n"
            f"⭐ Perdeu {xp_loss} XP ({percent}%)\n\n"
            f"Volte mais forte.",
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
    
    current_turn = player.get("combat_turn", 1)
    next_turn = current_turn + 1
    player["combat_turn"] = next_turn
    save_players_background()

    turn_log = f"\n\n📜 **LOG DO TURNO**\n• ⚔️ Você causou {base_turn_damage} de dano."
    if is_critical:
        turn_log += f"\n• 💥 CRÍTICO! +{critical_bonus_damage} dano (total: {damage})."
    if effect_message:
        turn_log += effect_message
    if poison_tick_text:
        turn_log += poison_tick_text
    turn_log += monster_attack_text
    if player_poison_tick_text:
        turn_log += player_poison_tick_text
    
    await edit_callback_message(query, f"{format_combat_status('⚔️ SEU TURNO', monster, player, next_turn, show_monster_icon=False)}"
        f"{turn_log}",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def flee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tenta fugir do combate"""
    query = update.callback_query
    
    user_id = str(query.from_user.id)
    
    # Debounce: evita múltiplos cliques rápidos
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.8):
        await query.answer("⏳ Aguarde um instante...")
        return
    
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        return
    
    player = players[user_id]
    
    if not player.get("monster"):
        await query.answer("❌ Nenhum combate ativo.", show_alert=True)
        return
    
    if random.random() < 0.5:  # 50% chance de fugir
        player["monster"] = None
        player["effects"] = []
        player["effect_timers"] = {}
        player["monster_effect_timers"] = {}
        player.pop("combat_turn", None)
        save_players_background()
        keyboard = [
            [InlineKeyboardButton("🎯 Caçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.answer("✅ Fuga bem-sucedida!")
        await edit_callback_message(query, 
            "✅ **FUGA BEM-SUCEDIDA**\n\nVocê escapou do combate.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        monster = player["monster"]
        if monster.get("double_attack"):
            hit_names = monster.get("attack_names", ["Inimigo 1", "Inimigo 2"])
            monster_damage_first = calculate_monster_damage(player, monster, include_class_defense=True)
            monster_damage_second = calculate_monster_damage(player, monster, include_class_defense=True)
            monster_damage = monster_damage_first + monster_damage_second
            damage_text = (
                f"💥 {hit_names[0]} causou {monster_damage_first} de dano\n"
                f"💥 {hit_names[1]} causou {monster_damage_second} de dano\n"
            )
        else:
            base_monster_damage = calculate_monster_damage(player, monster, include_class_defense=True)
            monster_damage, is_boss_crit = apply_boss_critical(base_monster_damage, monster)
            crit_indicator = " ⚡CRÍTICO!" if is_boss_crit else ""
            damage_text = f"💥 Tomou {monster_damage} de dano{crit_indicator}\n"
        player["hp"] -= monster_damage
        player["hp"] = max(0, player["hp"])  # Garante que HP não fique negativo
        if player["hp"] <= 0:
            player["hp"] = player["max_hp"] // 2
            player["gold"] = max(0, player["gold"] - player["gold"] // 2)
            xp_loss = math.ceil(player["xp"] * 0.5)
            player["xp"] = max(0, player["xp"] - xp_loss)
            player["monster"] = None
            player["effect_timers"] = {}
            player["monster_effect_timers"] = {}
            player.pop("combat_turn", None)
            save_players_background()
            keyboard = [
                [InlineKeyboardButton("🎯 Caçar", callback_data="hunt")],
                [InlineKeyboardButton("📊 Status", callback_data="status")],
                [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.answer("💀 Você foi derrotado na fuga.", show_alert=True)
            await edit_callback_message(query, f"💀 **DERROTA NA FUGA**\n\n"
                f"Você não conseguiu escapar.\n"
                f"❤️ Reviveu com {player['hp']} HP\n"
                f"💰 Perdeu metade do gold\n"
                f"⭐ Perdeu {xp_loss} XP",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            save_players_background()
            keyboard = [
                [InlineKeyboardButton("🏃 Tentar fugir novamente", callback_data="flee")],
                [InlineKeyboardButton("⚔️ Atacar", callback_data="attack")],
                [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.answer("❌ Falha na fuga!", show_alert=True)
            await edit_callback_message(query, f"❌ **FUGA FALHOU**\n\n"
                f"{damage_text}"
                f"❤️ HP atual: {player['hp']}",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra inventário"""
    query = update.callback_query
    logging.info(f"[INVENTORY] Callback recebido de user {query.from_user.id}")
    
    try:
        await query.answer()
    except Exception as e:
        logging.error(f"[INVENTORY] Erro ao responder callback: {e}")
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    player = players[user_id]
    backpack = get_player_backpack(player)
    used_slots = get_inventory_used_slots(player)
    total_slots = get_inventory_capacity(player)
    
    # Itens consumíveis
    consumable_text = "🧪 **CONSUMÍVEIS**\n"
    has_consumables = False
    for item, qty in player["inventory"].items():
        if item in consumables:
            consumable_text += f"• {consumables[item]['emoji']} {item}: {qty}\n"
            has_consumables = True
    
    if not has_consumables:
        consumable_text += "• Nenhum\n"
    
    # Armas
    weapon_text = "⚔️ **ARMAS**\n"
    for weapon in player.get("equipped_weapons", ["Punhos"]):
        if weapon in weapons:
            rarity_emoji = get_rarity_emoji(weapons[weapon]["rarity"])
            equipped = " (Equipada)" if player["weapon"] == weapon else ""
            weapon_text += f"• {rarity_emoji} {weapon}{equipped}\n"
    
    # Armaduras
    armor_text = "🛡️ **ARMADURAS**\n"
    for armor in player.get("equipped_armors", ["Roupas velhas"]):
        if armor in armors:
            rarity_emoji = get_rarity_emoji(armors[armor]["rarity"])
            equipped = " (Equipada)" if player["armor"] == armor else ""
            armor_text += f"• {rarity_emoji} {armor}{equipped}\n"
    
    # Itens diversos
    misc_text = "📦 **OUTROS ITENS**\n"
    has_misc = False
    for item, qty in player["inventory"].items():
        if item in misc_items:
            misc_text += f"• {misc_items[item]['emoji']} {item}: {qty}\n"
            has_misc = True
    
    if not has_misc:
        misc_text += "• Nenhum\n"
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Equipar", callback_data="equip_menu")],
        [InlineKeyboardButton("💊 Usar item", callback_data="use_item_menu")],
        [InlineKeyboardButton("💰 Vender", callback_data="sell_items")],
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"🎒 **INVENTÁRIO**\n\n"
        f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | 💰 {player['gold']} gold\n"
        f"🟫 Mochila: {backpack['name']}\n"
        f"📦 Slots: {used_slots}/{total_slots}\n\n"
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
            [InlineKeyboardButton("🔙 Voltar", callback_data="shop_sell"),
             InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_callback_message(query, 
            "📦 **VENDER DROPS** › Vender › Loja\n\n"
            "Você não tem drops para vender.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Monta mensagem e botões
    sell_text = "📦 **VENDER DROPS** › Vender › Loja\n\n"
    if offer["type"] == "sell_bonus" and offer["category"] == "misc":
        sell_text += f"⚡ {offer['text']}\n\n"
    sell_text += "Clique para vender:\n\n"
    
    keyboard = []
    for item_name, item_data in sellable_items.items():
        qty_text = f" x{item_data['qty']}" if item_data["qty"] > 1 else ""
        button_text = f"{item_data['emoji']} {item_name}{qty_text} → {item_data['sell_price']}💰"
        sell_text += f"{item_data['emoji']} **{item_name}**: x{item_data['qty']} ({item_data['sell_price']}💰 cada)\n"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sell_{item_name}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop_sell"),
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
            [InlineKeyboardButton("🔙 Voltar", callback_data="shop_sell"),
             InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_callback_message(query, 
            "⚔️🛡️ **VENDER EQUIPAMENTOS** › Vender › Loja\n\n"
            "Você não tem equipamentos velhos para vender.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Monta mensagem e botões
    sell_text = "⚔️🛡️ **VENDER EQUIPAMENTOS** › Vender › Loja\n\n"
    if offer["type"] == "sell_bonus" and (offer["category"] == "weapon" or offer["category"] == "armor"):
        sell_text += f"⚡ {offer['text']}\n\n"
    sell_text += "Clique para vender:\n\n"
    
    keyboard = []
    for item_name, item_data in sellable_items.items():
        button_text = f"{item_data['emoji']} {item_name} → {item_data['sell_price']}💰"
        sell_text += f"{item_data['emoji']} **{item_name}**: {item_data['sell_price']}💰\n"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sell_{item_name}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop_sell"),
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
            [InlineKeyboardButton("🔙 Voltar", callback_data="shop_sell"),
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
    
    items_list = "\n".join(items_sold[:10])  # Mostra até 10 itens
    if len(items_sold) > 10:
        items_list += f"\n... e mais {len(items_sold) - 10} itens"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Voltar", callback_data="shop_sell")],
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
    """Menu para vender itens"""
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
            "💰 **VENDER ITENS** › Inventário\n\n"
            "Você não tem nenhum item para vender.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Monta mensagem e botões
    sell_text = "💰 **VENDER ITENS** › Inventário\n\n"
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
    
    user_id = str(query.from_user.id)
    
    # Debounce: evita múltiplos cliques rápidos (crítico - envolve gold)
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.8):
        await query.answer("⏳ Aguarde um instante...")
        return
    
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
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
        await query.answer("❌ Item não encontrado!", show_alert=True)
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

    await query.answer("✅ Venda concluída!")
    
    await edit_callback_message(query, f"✅ **VENDA CONCLUÍDA**\n\n"
        f"Item vendido: {qty_text}{item_name}\n"
        f"💰 Ganhou: +{total_price} gold\n\n"
        f"💰 Gold atual: {player['gold']}",
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
            required_level = weapon_data.get("level_req", 1)
            locked = player["level"] < required_level
            lock_display = " 🔒" if locked else ""
            req_display = f" | Req Nv {required_level}" if locked else ""
            keyboard.append([
                InlineKeyboardButton(
                    f"{rarity_emoji}{lock_display} {weapon} (Dano: +{weapon_data['damage']}{req_display})",
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
            required_level = armor_data.get("level_req", 1)
            locked = player["level"] < required_level
            lock_display = " 🔒" if locked else ""
            req_display = f" | Req Nv {required_level}" if locked else ""
            keyboard.append([
                InlineKeyboardButton(
                    f"{rarity_emoji}{lock_display} {armor} (Defesa: +{armor_data['defense']}{req_display})",
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
    
    user_id = str(query.from_user.id)
    weapon_name = query.data.replace("equip_weapon_", "")
    
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        return
    
    player = players[user_id]
    
    if weapon_name in player.get("equipped_weapons", []):
        weapon_data = weapons.get(weapon_name)
        if not weapon_data:
            await query.answer("❌ Esta arma não existe mais.", show_alert=True)
            return

        required_level = weapon_data.get("level_req", 1)
        if player["level"] < required_level:
            await query.answer(
                f"🚫 Você é nível {player['level']} e precisa do nível {required_level} para equipar esta arma.",
                show_alert=True
            )
            return

        player["weapon"] = weapon_name
        await save_players()
        keyboard = [
            [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
            [InlineKeyboardButton("🏪 Loja", callback_data="shop")],
            [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.answer("✅ Arma equipada!")
        
        await edit_callback_message(query, f"✅ **ARMA EQUIPADA**\n\n"
            f"{weapons[weapon_name]['emoji']} {weapon_name}\n"
            f"⚔️ Dano: +{weapons[weapon_name]['damage']}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await query.answer("❌ Você não possui esta arma!", show_alert=True)

async def equip_armor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Equipa uma armadura"""
    query = update.callback_query
    
    user_id = str(query.from_user.id)
    armor_name = query.data.replace("equip_armor_", "")
    
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        return
    
    player = players[user_id]
    
    if armor_name in player.get("equipped_armors", []):
        armor_data = armors.get(armor_name)
        if not armor_data:
            await query.answer("❌ Esta armadura não existe mais.", show_alert=True)
            return

        required_level = armor_data.get("level_req", 1)
        if player["level"] < required_level:
            await query.answer(
                f"🚫 Você é nível {player['level']} e precisa do nível {required_level} para equipar esta armadura.",
                show_alert=True
            )
            return

        player["armor"] = armor_name
        await save_players()
        keyboard = [
            [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
            [InlineKeyboardButton("🏪 Loja", callback_data="shop")],
            [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.answer("✅ Armadura equipada!")
        await edit_callback_message(query, f"✅ **ARMADURA EQUIPADA**\n\n"
            f"{armors[armor_name]['emoji']} {armor_name}\n"
            f"🛡️ Defesa: +{armors[armor_name]['defense']}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await query.answer("❌ Você não possui esta armadura!", show_alert=True)

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

    if player.get("monster"):
        keyboard.append([InlineKeyboardButton("🔙 Voltar ao combate", callback_data="combat_menu")])
        menu_text = "💊 **USAR ITEM** › Combate\n\n**Escolha um item:**"
    else:
        keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="inventory"),
                         InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
        menu_text = "💊 **USAR ITEM** › Inventário\n\n**Escolha um item:**"

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, 
        menu_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def combat_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Retorna para o menu de combate sem executar ação."""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id not in players:
        await query.answer("❌ Use /start para criar um personagem!", show_alert=True)
        return

    player = players[user_id]
    if not player.get("monster"):
        await query.answer("❌ Nenhum combate ativo!", show_alert=True)
        return

    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data="attack")],
        [InlineKeyboardButton("🎒 Usar item", callback_data="use_item_menu")],
        [InlineKeyboardButton("🏃 Fugir", callback_data="flee")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await edit_callback_message(
        query,
        format_combat_status(
            "⚔️ COMBATE EM ANDAMENTO",
            player["monster"],
            player,
            player.get("combat_turn", 1),
            show_monster_icon=True
        ),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def use_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usa um item"""
    query = update.callback_query
    
    user_id = str(update.effective_user.id)
    item_name = query.data.replace("use_item_", "")
    
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        log_customizado(
            mensagem=f"Tentativa de usar item sem personagem",
            tipo="AVISO",
            user_id=user_id,
            funcao="use_item",
            context=f"Item: {item_name}"
        )
        return
    
    player = players[user_id]
    
    if player["inventory"].get(item_name, 0) <= 0:
        await query.answer("❌ Você não tem este item!", show_alert=True)
        log_customizado(
            mensagem=f"Tentativa de usar item que não possui",
            tipo="AVISO",
            user_id=user_id,
            funcao="use_item",
            context=f"Item: {item_name}, Invent: {player['inventory'].get(item_name, 0)}"
        )
        return
    
    consumable = consumables[item_name]
    
    # Usa o item
    player["inventory"][item_name] -= 1
    
    message = f"✅ ITEM USADO\n\n{consumable['emoji']} {item_name}\n"
    
    # Log de uso
    log_customizado(
        mensagem=f"Usou item com sucesso",
        tipo="INFO",
        user_id=user_id,
        funcao="use_item",
        context=f"Item: {item_name}"
    )
    
    # Aplica efeitos de cura
    if "heal" in consumable:
        heal = consumable["heal"]
        old_hp = player["hp"]
        player["hp"] = min(player["max_hp"], player["hp"] + heal)
        message += f"❤️ Cura: +{player['hp'] - old_hp} HP\n"
    
    # Aumenta max HP (Poção de vida extra)
    if "max_hp_boost" in consumable:
        boost = consumable["max_hp_boost"]
        player["max_hp"] += boost
        player["base_hp"] += boost  # Também aumenta o base para não perder ao subir de nível
        player["hp"] = min(player["max_hp"], player["hp"] + boost)  # Cura junto
        message += f"💚 Vida máxima aumentada: +{boost} HP (Novo máximo: {player['max_hp']})\n"
    
    # Aplica buffs
    if consumable.get("effect") == "buff":
        buff_entry = {"name": item_name, "duration": consumable["duration"]}
        
        if "damage_bonus" in consumable:
            buff_entry["damage_bonus"] = consumable["damage_bonus"]
            player.setdefault("buffs", []).append(buff_entry.copy())
            message += f"⚔️ Bônus de dano: +{consumable['damage_bonus']} por {consumable['duration']} turnos\n"
        
        if "defense_bonus" in consumable:
            buff_entry["defense_bonus"] = consumable["defense_bonus"]
            player.setdefault("buffs", []).append(buff_entry.copy())
            message += f"🛡️ Bônus de defesa: +{consumable['defense_bonus']} por {consumable['duration']} turnos\n"
        
        if "speed_bonus" in consumable:
            buff_entry["speed_bonus"] = consumable["speed_bonus"]
            player.setdefault("buffs", []).append(buff_entry.copy())
            message += f"⚡ Bônus de velocidade: +{int(consumable['speed_bonus']*100)}% por {consumable['duration']} turnos\n"
    
    if consumable.get("effect") == "cura_veneno":
        player["effects"] = [e for e in player.get("effects", []) if e != "veneno"]
        if "effect_timers" in player:
            player["effect_timers"].pop("veneno", None)
        message += "💊 Veneno curado!\n"
    
    save_players_background()
    await query.answer("✅ Item usado!")
    
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
        await query.answer("⏳ Aguarde um instante...")
        return
    
    if user_id not in players:
        return
    
    player = players[user_id]
    offer = get_daily_offer()
    
    # Layout compacto e direto
    keyboard = [
        [InlineKeyboardButton("🛒 Comprar", callback_data="shop_buy"), InlineKeyboardButton("💰 Vender", callback_data="shop_sell")],
        [InlineKeyboardButton("🎒 Mochilas", callback_data="shop_backpacks"), InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    shop_text = (
        f"🏪 **LOJA DO AVENTUREIRO**\n\n"
        f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | 💰 {player['gold']} gold\n"
        f"⚡ {offer['text']}\n\n"
        f"O que deseja fazer?"
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
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return
    
    player = players[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🧪 Poções", callback_data="shop_potions"), InlineKeyboardButton("⚔️ Armas", callback_data="shop_weapons")],
        [InlineKeyboardButton("🛡️ Armaduras", callback_data="shop_armors"), InlineKeyboardButton("✨ Buffs", callback_data="shop_buffs")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="shop"), InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"🛒 **COMPRAR ITENS**\n\n"
        f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | 💰 {player['gold']} gold\n\n"
        f"Escolha uma categoria:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def shop_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de venda da loja"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return

    player = players[user_id]

    keyboard = [
        [InlineKeyboardButton("📦 Vender Drops", callback_data="sell_drops"), InlineKeyboardButton("⚔️🛡️ Equipamentos", callback_data="sell_equipment")],
        [InlineKeyboardButton("💰 Venda Rápida", callback_data="sell_all_quick")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="shop"), InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await edit_callback_message(query,
        f"💰 **VENDER ITENS**\n\n"
        f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | 💰 {player['gold']} gold\n\n"
        "Escolha uma opção:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def shop_potions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra menu de categorias de poções na loja"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return

    player = players[user_id]
    
    shop_text = "🧪 **POÇÕES DISPONÍVEIS**\n\n"
    shop_text += f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | 💰 {player['gold']} gold\n\n"
    shop_text += "Escolha a categoria:\n"
    
    keyboard = [
        [InlineKeyboardButton("💚 Cura", callback_data="shop_potions_cura")],
        [InlineKeyboardButton("💪 Força", callback_data="shop_potions_forca")],
        [InlineKeyboardButton("🛡️ Resistência", callback_data="shop_potions_resistencia")],
        [InlineKeyboardButton("⚡ Velocidade", callback_data="shop_potions_velocidade")],
        [InlineKeyboardButton("✨ Especial", callback_data="shop_potions_especial")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="shop_buy"),
         InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, shop_text,
        parse_mode='Markdown',
        reply_markup=reply_markup)


async def shop_potions_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """Mostra poções de uma categoria específica"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return

    player = players[user_id]
    offer = get_daily_offer()
    
    category_names = {
        "cura": "💚 Poções de Cura",
        "forca": "💪 Poções de Força",
        "resistencia": "🛡️ Poções de Resistência",
        "velocidade": "⚡ Poções de Velocidade",
        "especial": "✨ Poções Especiais"
    }
    
    shop_text = f"🧪 **{category_names.get(category, 'POÇÕES')}**\n\n"
    if offer["type"] == "buy_discount" and offer["category"] == "potions":
        shop_text += f"⚡ {offer['text']}\n\n"
    shop_text += f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | 💰 {player['gold']} gold\n\n"
    
    keyboard = []
    found_items = False
    
    for item_name, item_data in consumables.items():
        if item_data.get("category") == category:
            found_items = True
            base_price = item_data['price']
            final_price = calculate_buy_price(base_price, "potions")
            
            if final_price < base_price:
                price_display = f"{final_price}💰 🎉"
            else:
                price_display = f"{final_price}💰"
            
            effect_text = ""
            if "heal" in item_data:
                effect_text = f"Cura: {item_data['heal']}"
            elif "damage_bonus" in item_data:
                effect_text = f"Dano +{item_data['damage_bonus']} | Duração: {item_data.get('duration', 1)} turnos"
            elif "defense_bonus" in item_data:
                effect_text = f"Defesa +{item_data['defense_bonus']} | Duração: {item_data.get('duration', 1)} turnos"
            elif "speed_bonus" in item_data:
                effect_text = f"Velocidade +{item_data['speed_bonus']} | Duração: {item_data.get('duration', 1)} turnos"
            elif "max_hp_boost" in item_data:
                effect_text = f"Vida Máx +{item_data['max_hp_boost']}"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{item_data['emoji']} {item_name} - {price_display} | {effect_text}",
                    callback_data=f"buy_potion_{item_name}"
                )
            ])
    
    if not found_items:
        shop_text += "❌ Nenhuma poção nesta categoria"
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop_potions"),
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
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return

    player = players[user_id]
    
    # Pega apenas armas da classe do jogador
    available_weapons = get_weapons_by_class(player["class"], player["level"])
    
    player_level = player["level"]
    filtered = build_showcase_items(available_weapons, player_level, "base_weapon")
    
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
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop_buy"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"⚔️ **ARMAS DISPONÍVEIS**\n\n"
        f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | 💰 {player['gold']} gold\n"
        f"Classe: **{player['class']}**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def shop_armors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra armaduras na loja"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return

    player = players[user_id]
    
    player_level = player["level"]
    filtered = build_showcase_items(armors, player_level, "base_armor")

    rarity_order = ["comum", "rara", "épica", "lendária", "mítica"]
    organized = {rarity: [] for rarity in rarity_order}

    for armor_name, armor_data in filtered.items():
        rarity = armor_data.get("rarity", "comum")
        if rarity in organized:
            organized[rarity].append((armor_name, armor_data))

    for rarity in organized:
        organized[rarity].sort(key=lambda x: x[1]["defense"])

    keyboard = []
    for rarity in rarity_order:
        if organized[rarity]:
            rarity_emoji = get_rarity_emoji(rarity)
            for armor_name, armor_data in organized[rarity]:
                price_display = f"{armor_data['price']}💰"
                defense_display = f"Defesa: +{armor_data['defense']}"
                level_display = f"Nv: {armor_data['level_req']}"
                locked = player_level < armor_data["level_req"]
                lock_display = " 🔒" if locked else ""
                level_req_display = f" | Req: {level_display}" if locked else ""

                keyboard.append([
                    InlineKeyboardButton(
                        f"{rarity_emoji}{lock_display} {armor_name} - {price_display} | {defense_display}{level_req_display}",
                        callback_data=f"buy_armor_{armor_name}"
                    )
                ])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop_buy"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"🛡️ **ARMADURAS DISPONÍVEIS**\n\n"
        f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | 💰 {player['gold']} gold",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def shop_buffs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra buffs na loja"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return

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
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop_buy"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"✨ **BUFFS DISPONÍVEIS**\n\n"
        f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | 💰 {player['gold']} gold",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def shop_backpacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra mochilas disponíveis (somente loja + info de drops especiais)"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id not in players:
        return

    player = players[user_id]
    current_backpack = get_player_backpack(player)
    current_slots = get_inventory_capacity(player)
    used_slots = get_inventory_used_slots(player)

    keyboard = []
    store_backpacks = [bp for bp in BACKPACKS if bp["source"] == "loja"]
    store_backpacks.sort(key=lambda bp: bp["slots"])

    for backpack in store_backpacks:
        level_ok = player["level"] >= backpack["level_req"]
        has_better_or_equal = current_slots >= backpack["slots"]
        lock_display = " 🔒" if not level_ok else ""
        owned_display = " ✅" if has_better_or_equal else ""

        button_text = (
            f"{backpack['emoji']}{lock_display}{owned_display} {backpack['name']}"
            f" - {backpack['price']}💰 | {backpack['slots']} slots | Nv {backpack['level_req']}"
        )
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"backpack_buy_{backpack['id']}")])

    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop"),
                     InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "🎒 **MOCHILAS DISPONÍVEIS**\n\n"
        f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | 💰 {player['gold']} gold\n"
        f"Atual: **{current_backpack['name']}** ({current_slots} slots)\n"
        f"Uso: **{used_slots}/{current_slots}**\n\n"
        "🎁 **Drops Especiais (não compráveis):**\n"
        "• Mochila Élfica (35 slots) - Drop raro\n"
        "• Bolsa Dimensional (70 slots) - Chefão"
    )

    await edit_callback_message(query, text, parse_mode='Markdown', reply_markup=reply_markup)

async def buy_backpack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compra mochila da loja"""
    query = update.callback_query

    user_id = str(query.from_user.id)
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        return

    player = players[user_id]
    backpack_id = query.data.replace("backpack_buy_", "")
    backpack = BACKPACKS_BY_ID.get(backpack_id)
    fail_reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎒 Ver mochilas", callback_data="shop_backpacks")],
        [InlineKeyboardButton("🏪 Voltar à loja", callback_data="shop")],
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ])

    if not backpack or backpack["source"] != "loja":
        await query.answer("❌ Esta mochila não pode ser comprada na loja.", show_alert=True)
        return

    current_slots = get_inventory_capacity(player)
    if current_slots >= backpack["slots"]:
        await query.answer("✅ Você já possui uma mochila igual ou melhor.", show_alert=True)
        return

    if player["level"] < backpack["level_req"]:
        await query.answer(f"❌ Necessário nível {backpack['level_req']} para comprar esta mochila.", show_alert=True)
        return

    if player["gold"] < backpack["price"]:
        faltando = backpack["price"] - player["gold"]
        await query.answer(f"❌ Gold insuficiente. Faltam {faltando}💰.", show_alert=True)
        return

    player["gold"] -= backpack["price"]
    player["backpack_id"] = backpack_id
    await save_players()
    await query.answer("✅ Mochila comprada!")

    keyboard = [
        [InlineKeyboardButton("🎒 Ver mochilas", callback_data="shop_backpacks")],
        [InlineKeyboardButton("🏪 Voltar à loja", callback_data="shop")],
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await edit_callback_message(
        query,
        f"✅ **MOCHILA COMPRADA**\n\n"
        f"🟫 {backpack['name']}\n"
        f"📦 Capacidade: {backpack['slots']} slots\n"
        f"💰 Custo: {backpack['price']} gold\n"
        f"💰 Gold restante: {player['gold']}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def pending_drops_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu para gerenciar drops pendentes quando mochila está cheia"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id not in players:
        return

    player = players[user_id]
    pending = player.get("pending_drop_swaps", [])

    if not pending:
        keyboard = [
            [InlineKeyboardButton("🎯 Caçar", callback_data="hunt")],
            [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query,
            "✅ Não há drops pendentes para troca no momento.",
            reply_markup=reply_markup
        )
        return

    keyboard = []
    text = "🔁 **DROPS PENDENTES**\n\nEscolha qual drop você quer tentar pegar trocando um item:\n\n"
    for idx, drop_data in enumerate(pending):
        text += f"{idx + 1}. {drop_data['emoji']} {drop_data['item']}\n"
        keyboard.append([
            InlineKeyboardButton(
                f"{drop_data['emoji']} Trocar para pegar {drop_data['item']}",
                callback_data=f"pending_drop_pick_{idx}"
            )
        ])

    keyboard.append([InlineKeyboardButton("🗑️ Descartar todos", callback_data="pending_drop_discard_all")])
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await edit_callback_message(query, text, parse_mode='Markdown', reply_markup=reply_markup)

async def pending_drop_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Escolhe um drop pendente e lista itens para substituir"""
    query = update.callback_query

    user_id = str(query.from_user.id)
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        return

    player = players[user_id]
    pending = player.get("pending_drop_swaps", [])

    try:
        drop_index = int(query.data.replace("pending_drop_pick_", ""))
    except ValueError:
        await query.answer("❌ Drop pendente inválido.", show_alert=True)
        return

    if drop_index < 0 or drop_index >= len(pending):
        await query.answer("❌ Este drop pendente não existe mais.", show_alert=True)
        return

    drop_data = pending[drop_index]
    occupied_items = get_occupied_inventory_items(player)

    if not occupied_items:
        if add_item_to_inventory(player, drop_data["item"]):
            pending.pop(drop_index)
            await save_players()
            await query.answer("✅ Drop coletado!")
            await edit_callback_message(query, f"✅ **DROP COLETADO**\n\n{drop_data['emoji']} {drop_data['item']}", parse_mode='Markdown')
        else:
            await query.answer("❌ Não há itens para trocar no inventário.", show_alert=True)
        return

    keyboard = []
    text = (
        f"🔁 **TROCAR ITEM**\n\n"
        f"Novo drop: {drop_data['emoji']} **{drop_data['item']}**\n"
        f"Escolha o item que será removido para liberar 1 slot:\n\n"
    )

    for item_idx, old_item in enumerate(occupied_items):
        qty = player["inventory"].get(old_item, 0)
        item_emoji = "📦"
        if old_item in consumables:
            item_emoji = consumables[old_item]["emoji"]
        elif old_item in misc_items:
            item_emoji = misc_items[old_item]["emoji"]

        keyboard.append([
            InlineKeyboardButton(
                f"{item_emoji} Remover {old_item} x{qty}",
                callback_data=f"pending_drop_do_{drop_index}_{item_idx}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🗑️ Descartar este drop", callback_data=f"pending_drop_discard_{drop_index}")
    ])
    keyboard.append([
        InlineKeyboardButton("🔙 Voltar", callback_data="pending_drops_menu")
    ])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.answer()
    await edit_callback_message(query, text, parse_mode='Markdown', reply_markup=reply_markup)

async def pending_drop_do_replace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Troca um item do inventário pelo drop pendente"""
    query = update.callback_query

    user_id = str(query.from_user.id)
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        return

    player = players[user_id]
    pending = player.get("pending_drop_swaps", [])

    try:
        payload = query.data.replace("pending_drop_do_", "")
        drop_index_str, item_index_str = payload.split("_")
        drop_index = int(drop_index_str)
        item_index = int(item_index_str)
    except Exception:
        await query.answer("❌ Dados de troca inválidos.", show_alert=True)
        return

    if drop_index < 0 or drop_index >= len(pending):
        await query.answer("❌ Este drop pendente não existe mais.", show_alert=True)
        return

    drop_data = pending[drop_index]
    occupied_items = get_occupied_inventory_items(player)
    if item_index < 0 or item_index >= len(occupied_items):
        await query.answer("❌ Item para troca inválido.", show_alert=True)
        return

    old_item = occupied_items[item_index]

    # Se já houver espaço por algum motivo, pega sem remover nada
    if add_item_to_inventory(player, drop_data["item"]):
        pending.pop(drop_index)
        await save_players()
        await query.answer("✅ Drop coletado!")
        await edit_callback_message(query,
            f"✅ **DROP COLETADO**\n\n{drop_data['emoji']} {drop_data['item']}\nSem precisar trocar item.",
            parse_mode='Markdown'
        )
        return

    player["inventory"][old_item] = 0
    add_item_to_inventory(player, drop_data["item"])
    pending.pop(drop_index)
    await save_players()

    keyboard = [
        [InlineKeyboardButton("🔁 Gerenciar outros drops", callback_data="pending_drops_menu")],
        [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.answer("✅ Troca concluída!")

    await edit_callback_message(
        query,
        f"✅ **Troca concluída!**\n\n"
        f"❌ Removido: {old_item}\n"
        f"🎁 Recebido: {drop_data['emoji']} {drop_data['item']}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def pending_drop_discard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Descarta um drop pendente específico ou todos"""
    query = update.callback_query

    user_id = str(query.from_user.id)
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        return

    player = players[user_id]
    pending = player.get("pending_drop_swaps", [])

    if query.data == "pending_drop_discard_all":
        dropped_count = len(pending)
        player["pending_drop_swaps"] = []
        await save_players()
        keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="pending_drops_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.answer("🗑️ Drops descartados!")
        await edit_callback_message(
            query,
            f"🗑️ **DROPS DESCARTADOS**\n\nQuantidade: {dropped_count}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return

    try:
        drop_index = int(query.data.replace("pending_drop_discard_", ""))
    except ValueError:
        await query.answer("❌ Drop pendente inválido.", show_alert=True)
        return

    if drop_index < 0 or drop_index >= len(pending):
        await query.answer("❌ Este drop pendente não existe mais.", show_alert=True)
        return

    removed = pending.pop(drop_index)
    await save_players()
    keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="pending_drops_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.answer("🗑️ Drop descartado!")
    await edit_callback_message(query,
        f"🗑️ **DROP DESCARTADO**\n\n{removed['emoji']} {removed['item']}\n\nUse o menu de drops pendentes para continuar.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa compra de itens"""
    query = update.callback_query
    
    user_id = str(query.from_user.id)
    data = query.data
    
    # Debounce: evita múltiplos cliques rápidos (crítico - envolve gold)
    if not check_user_action_cooldown(user_id, cooldown_seconds=0.8):
        await query.answer("⏳ Aguarde um instante...")
        return
    
    if user_id not in players:
        await query.answer("❌ Crie seu personagem com /start.", show_alert=True)
        return
    
    player = players[user_id]
    
    invalid_item_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ Comprar", callback_data="shop_buy")],
        [InlineKeyboardButton("🏪 Loja", callback_data="shop"), InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ])

    # Determina tipo de compra
    if data.startswith("buy_potion_"):
        item_name = data.replace("buy_potion_", "")
        if item_name not in consumables:
            await query.answer("❌ Este item não está mais disponível na loja.", show_alert=True)
            await edit_callback_message(query, "❌ Este item não está mais disponível na loja.", reply_markup=invalid_item_markup)
            return
        item_data = consumables[item_name]
        category = "potion"
        price_category = "potions"
    elif data.startswith("buy_weapon_"):
        item_name = data.replace("buy_weapon_", "")
        if item_name not in weapons:
            await query.answer("❌ Esta arma não está mais disponível na loja.", show_alert=True)
            await edit_callback_message(query, "❌ Esta arma não está mais disponível na loja.", reply_markup=invalid_item_markup)
            return
        item_data = weapons[item_name]
        category = "weapon"
        price_category = "weapons"
    elif data.startswith("buy_armor_"):
        item_name = data.replace("buy_armor_", "")
        if item_name not in armors:
            await query.answer("❌ Esta armadura não está mais disponível na loja.", show_alert=True)
            await edit_callback_message(query, "❌ Esta armadura não está mais disponível na loja.", reply_markup=invalid_item_markup)
            return
        item_data = armors[item_name]
        category = "armor"
        price_category = "armors"
    elif data.startswith("buy_buff_"):
        item_name = data.replace("buy_buff_", "")
        if item_name not in consumables:
            await query.answer("❌ Este buff não está mais disponível na loja.", show_alert=True)
            await edit_callback_message(query, "❌ Este buff não está mais disponível na loja.", reply_markup=invalid_item_markup)
            return
        item_data = consumables[item_name]
        category = "buff"
        price_category = "buffs"
    else:
        return

    shop_category_map = {
        "potions": "shop_potions",
        "weapons": "shop_weapons",
        "armors": "shop_armors",
        "buffs": "shop_buffs"
    }
    return_category_callback = shop_category_map.get(price_category, "shop_buy")
    fail_reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Voltar para categoria", callback_data=return_category_callback)],
        [InlineKeyboardButton("🛍️ Comprar", callback_data="shop_buy")],
        [InlineKeyboardButton("🏪 Loja", callback_data="shop"), InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ])
    
    # Calcula preço com desconto dinâmico
    base_price = item_data["price"]
    final_price = calculate_buy_price(base_price, price_category)
    
    # Verifica gold
    if player["gold"] < final_price:
        faltando = final_price - player["gold"]
        await query.answer(f"❌ Gold insuficiente. Faltam {faltando}💰.", show_alert=True)
        log_customizado(
            mensagem=f"Tentativa de compra com gold insuficiente",
            tipo="AVISO",
            user_id=user_id,
            funcao="buy_item",
            context=f"{item_name}: {final_price}💰 (tem {player['gold']})"
        )
        return
    
    # Verifica level requerido
    if "level_req" in item_data and player["level"] < item_data["level_req"]:
        await query.answer(f"❌ Necessário nível {item_data['level_req']}!", show_alert=True)
        log_customizado(
            mensagem=f"Tentativa de compra com nível insuficiente",
            tipo="AVISO",
            user_id=user_id,
            funcao="buy_item",
            context=f"{item_name}: requer nível {item_data['level_req']} (tem {player['level']})"
        )
        return

    # Verifica espaço de mochila para itens consumíveis/buffs
    if category in ["potion", "buff"] and not add_item_to_inventory(player, item_name):
        await query.answer("❌ Mochila cheia. Compre uma mochila maior na loja.", show_alert=True)
        log_customizado(
            mensagem=f"Tentativa de compra com mochila cheia",
            tipo="AVISO",
            user_id=user_id,
            funcao="buy_item",
            context=f"{item_name} - Mochila: {player.get('backpack_capacity', 20)}"
        )
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
        item_display = f"{item_data['emoji']} {item_name}"
    
    await save_players()
    
    # Log de compra bem-sucedida
    log_customizado(
        mensagem=f"Compra realizada com sucesso",
        tipo="INFO",
        user_id=user_id,
        funcao="buy_item",
        context=f"{item_name}: {final_price}💰"
    )
    
    await query.answer("✅ Compra concluída!")
    
    # Mostra economia se houver desconto
    saved_text = ""
    if final_price < base_price:
        saved = base_price - final_price
        saved_text = f"\n🎉 Você economizou {saved}💰!"
    
    keyboard = [
        [InlineKeyboardButton("🛒 Comprar mais", callback_data="shop")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await edit_callback_message(query, f"✅ **COMPRA CONCLUÍDA**\n\n"
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
    backpack = get_player_backpack(player)
    used_slots = get_inventory_used_slots(player)
    total_slots = get_inventory_capacity(player)
    
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
    buffs_lines = []
    for buff in player.get("buffs", []):
        if buff["duration"] > 0:
            buffs_lines.append(f"• {buff['name']} ({buff['duration']} turnos)")
    buffs_text = "\n".join(buffs_lines) if buffs_lines else "• Nenhum"
    
    # Efeitos ativos
    effects_text = "Nenhum"
    if player.get("effects"):
        effects_text = ", ".join(player["effects"])
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
        [InlineKeyboardButton("🛌 Descansar", callback_data="rest")],
        [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    status_text = (
        f"📊 **STATUS DO JOGADOR**\n\n"
        f"👤 {player['name']} | {classes[player['class']]['emoji']} {player['class']} | {get_rank(player['level'])}\n"
        f"💰 Gold: {player['gold']} | ❤️ HP: {player['hp']}/{player['max_hp']}\n"
        f"{hp_bar_blocks(player['hp'], player['max_hp'])}\n\n"
        f"⭐ **EXPERIÊNCIA**\n"
        f"📈 Nível: {player['level']}\n"
        f"⭐ XP: {player['xp']}/{xp_next} (Total: {xp_total})\n"
        f"⏳ Próximo nível: {xp_remaining} XP\n\n"
        f"⚔️ **COMBATE**\n"
        f"Dano total: {total_damage} ({weapons[player['weapon']]['emoji']} {player['weapon']} +{weapon_damage} | Classe +{class_damage})\n"
        f"Defesa total: {total_defense} ({armors[player['armor']]['emoji']} {player['armor']} +{armor_defense} | Classe +{class_defense})\n"
        f"💥 Crítico: {crit_percentage}%\n"
        f"⚠️ Efeitos: {effects_text}\n"
        f"🛡️ Buffs ativos:\n{buffs_text}\n\n"
        f"🎒 **INVENTÁRIO**\n"
        f"Mochila: {backpack['name']} ({used_slots}/{total_slots} slots)"
    )
    
    await send_player_message(query, player, status_text, keyboard)

async def rest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Descanso instantâneo com cooldown"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    if user_id not in players:
        return
    
    player = players[user_id]
    
    if player.get("monster"):
        keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, "❌ DESCANSO BLOQUEADO\n\nVocê não pode descansar durante o combate.", reply_markup=reply_markup)
        return
    
    now = datetime.now()
    last_rest = player.get("last_rest")

    if player["hp"] >= player["max_hp"]:
        keyboard = [
            [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
            [InlineKeyboardButton("🏪 Loja", callback_data="shop")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await edit_callback_message(query, "✅ HP JÁ ESTÁ NO MÁXIMO\n\nVocê não precisa descansar agora.", reply_markup=reply_markup)
        return

    if last_rest:
        # Calcula cooldown progressivo: 5s, 10s, 20s, 40s, 80s...
        rest_count = player.get("rest_count", 0)
        current_cooldown = REST_COOLDOWN_BASE * (2 ** rest_count)
        
        elapsed = (now - last_rest).total_seconds()
        if elapsed < current_cooldown:
            remaining = current_cooldown - elapsed
            keyboard = [
                [InlineKeyboardButton("⏳ Tentar novamente", callback_data="rest")],
                [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
                [InlineKeyboardButton("🔙 Menu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await edit_callback_message(
                query,
                "⏳ DESCANSO EM COOLDOWN\n"
                f"⏳ Tempo restante: {format_rest_time(remaining)}\n"
                f"📊 Descanso #{rest_count + 1} • Próximo cooldown: {format_rest_time(current_cooldown * 2)}",
                reply_markup=reply_markup
            )
            return

    heal_amount = max(1, math.ceil(player["max_hp"] * REST_HEAL_PERCENT))
    new_hp = min(player["max_hp"], player["hp"] + heal_amount)
    actual_heal = new_hp - player["hp"]
    player["hp"] = new_hp
    player["last_rest"] = now
    
    # Incrementa contador de descansos (para cooldown progressivo)
    rest_count = player.get("rest_count", 0)
    player["rest_count"] = rest_count + 1
    next_cooldown = REST_COOLDOWN_BASE * (2 ** player["rest_count"])
    
    await save_players()

    keyboard = [
        [InlineKeyboardButton("⏳ Descanso (cooldown)", callback_data="rest")],
        [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
        [InlineKeyboardButton("🏪 Loja", callback_data="shop")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await edit_callback_message(query, f"✅ DESCANSO CONCLUÍDO\n\n"
        f"❤️ Recuperou {actual_heal} de vida (50% do HP máximo).\n"
        f"❤️ HP: {player['hp']}/{player['max_hp']}\n"
        f"{hp_bar_blocks(player['hp'], player['max_hp'])}\n\n"
        f"⏳ Próximo descanso em {format_rest_time(next_cooldown)}\n"
        f"📊 Descanso #{player['rest_count']} • Cooldown dobrando a cada uso",
        reply_markup=reply_markup
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Volta ao menu principal"""
    query = update.callback_query
    logging.info(f"[BACK_MAIN] Callback recebido de user {query.from_user.id}")
    
    try:
        await query.answer()
    except Exception as e:
        logging.error(f"[BACK_MAIN] Erro ao responder callback: {e}")
    
    user_id = str(query.from_user.id)
    
    if user_id not in players:
        return
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Caçar", callback_data="hunt"),
         InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🛌 Descansar", callback_data="rest"),
         InlineKeyboardButton("🎒 Inventário", callback_data="inventory")],
        [InlineKeyboardButton("🏪 Loja", callback_data="shop"),
         InlineKeyboardButton("🗺️ Mapa", callback_data="map_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = f"🏠 **MENU PRINCIPAL**\n\nO que deseja fazer?"
    
    try:
        await query.message.edit_media(
            media=InputMediaPhoto(
                media=MAIN_MENU_IMAGE,
                caption=message_text,
                parse_mode='Markdown'
            ),
            reply_markup=reply_markup
        )
    except Exception:
        await edit_callback_message(query, message_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def map_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de selecao de mapas"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id not in players:
        await edit_callback_message(query, "❌ Use /start para criar um personagem!")
        return

    player = players[user_id]
    current_map_id = player.get("map_id", "planicie")
    unlocked_maps = set(player.get("unlocked_maps", ["planicie"]))

    keyboard = []
    for map_data in MAPS:
        is_unlocked = map_data["id"] in unlocked_maps
        is_current = map_data["id"] == current_map_id
        status_icon = "✅" if is_current else "🔓" if is_unlocked else "🔒"
        label = f"{status_icon} {map_data['name']}"
        callback = f"map_select_{map_data['id']}" if is_unlocked else f"map_locked_{map_data['id']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback)])

    keyboard.append([InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    boss_status = "✅" if player.get("boss_defeated", {}).get(current_map_id) else "❌"
    text = (
        "🗺️ **MAPAS** › Menu Principal\n\n"
        f"Mapa atual: **{get_map_by_id(current_map_id)['name']}**\n"
        f"Boss derrotado: {boss_status}"
    )
    map_image = MAP_IMAGES.get(current_map_id)
    if map_image:
        try:
            if query.message and getattr(query.message, "photo", None):
                await query.edit_message_caption(
                    caption=text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            else:
                await query.message.reply_photo(
                    photo=map_image,
                    caption=text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                await query.delete_message()
        except Exception:
            await edit_callback_message(query, text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await edit_callback_message(query, text, parse_mode='Markdown', reply_markup=reply_markup)

async def map_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Seleciona um mapa desbloqueado"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    if user_id not in players:
        return

    player = players[user_id]
    map_id = query.data.replace("map_select_", "")
    map_data = get_map_by_id(map_id)

    player["map_id"] = map_data["id"]
    await save_players()

    keyboard = [
        [InlineKeyboardButton("🗺️ Voltar aos mapas", callback_data="map_menu")],
        [InlineKeyboardButton("🏠 Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await edit_callback_message(
        query,
        f"✅ Mapa selecionado: **{map_data['name']}**",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def map_locked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Feedback para mapa bloqueado"""
    query = update.callback_query
    await query.answer("🔒 Mapa bloqueado! Derrote o boss do mapa atual para liberar.", show_alert=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa mensagens de texto"""
    if context.user_data.get("awaiting_name"):
        await set_name(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra os comandos disponíveis"""
    help_text = (
        "📖 **COMANDOS DISPONÍVEIS:**\n\n"
        "/start - Criar personagem ou voltar ao menu principal\n"
        "/help - Mostrar esta mensagem\n"
        "/restart - Reiniciar o bot (apenas admin)\n"
        "/stats_dev - Ver estatísticas de erros (apenas admin)\n\n"
        "💡 **Use os botões abaixo das mensagens para interagir com o jogo!**"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')
    
    log_customizado(
        mensagem="Usuário acessou /help",
        tipo="INFO",
        user_id=str(update.effective_user.id)
    )

async def stats_dev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra estatísticas de erros (apenas admin)"""
    user_id = str(update.effective_user.id)
    
    # IDs de admin (hardcoded, você pode mudar)
    ADMIN_IDS = ["1148099842"]  # Adicione seu ID aqui
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Acesso negado!")
        log_customizado(
            mensagem="Tentativa de acesso não autorizado a /stats_dev",
            tipo="AVISO",
            user_id=user_id
        )
        return
    
    # Ler arquivo de log
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            linhas_log = f.readlines()
    except:
        linhas_log = []
    
    stats_text = (
        f"📊 **ESTATÍSTICAS DE ERROS**\n\n"
        f"🔴 Total de eventos: {ERROR_STATS['total']}\n"
        f"🟥 Críticos: {ERROR_STATS['crítico']}\n"
        f"🟧 Erros: {ERROR_STATS['erro']}\n"
        f"🟦 Avisos: {ERROR_STATS['aviso']}\n\n"
        f"📝 Linhas de log: {len(linhas_log)}\n\n"
    )
    
    # Ultimas 5 linhas de log
    if linhas_log:
        stats_text += "**Últimos eventos:**\n"
        for linha in linhas_log[-5:]:
            stats_text += f"`{linha.strip()[:80]}`\n"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    log_customizado(
        mensagem="Acesso a /stats_dev",
        tipo="INFO",
        user_id=user_id
    )

async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reinicia o bot pelo comando /restart"""
    message = update.effective_message
    if message:
        await message.reply_text("🔁 Reiniciando o bot...")

    await save_players()
    os.execl(sys.executable, sys.executable, *sys.argv)

async def shop_potions_cura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de poções de cura"""
    await shop_potions_category(update, context, "cura")

async def shop_potions_forca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de poções de força"""
    await shop_potions_category(update, context, "forca")

async def shop_potions_resistencia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de poções de resistência"""
    await shop_potions_category(update, context, "resistencia")

async def shop_potions_velocidade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de poções de velocidade"""
    await shop_potions_category(update, context, "velocidade")

async def shop_potions_especial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu de poções especiais"""
    await shop_potions_category(update, context, "especial")

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
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("restart", restart_bot))
    app.add_handler(CommandHandler("stats_dev", stats_dev))
    
    # Handlers de callback (botões)
    app.add_handler(CallbackQueryHandler(class_selected, pattern="^class_"))
    app.add_handler(CallbackQueryHandler(random_name, pattern="^random_name$"))
    app.add_handler(CallbackQueryHandler(merchant_buy_potion, pattern="^merchant_buy_potion$"))
    app.add_handler(CallbackQueryHandler(merchant_duel, pattern="^merchant_duel$"))
    app.add_handler(CallbackQueryHandler(continue_hunt, pattern="^continue_hunt$"))
    
    # Handlers dos eventos especiais do mapa 2+
    app.add_handler(CallbackQueryHandler(trap_disarm, pattern="^trap_disarm$"))
    app.add_handler(CallbackQueryHandler(trap_avoid, pattern="^trap_avoid$"))
    app.add_handler(CallbackQueryHandler(trap_ignore, pattern="^trap_ignore$"))
    app.add_handler(CallbackQueryHandler(meteor_run, pattern="^meteor_run$"))
    app.add_handler(CallbackQueryHandler(meteor_shield, pattern="^meteor_shield$"))
    app.add_handler(CallbackQueryHandler(meteor_attack, pattern="^meteor_attack$"))
    app.add_handler(CallbackQueryHandler(snake_kill, pattern="^snake_kill$"))
    app.add_handler(CallbackQueryHandler(snake_flee, pattern="^snake_flee$"))
    app.add_handler(CallbackQueryHandler(snake_ignore, pattern="^snake_ignore$"))
    app.add_handler(CallbackQueryHandler(ghost_help, pattern="^ghost_help$"))
    app.add_handler(CallbackQueryHandler(ghost_refuse, pattern="^ghost_refuse$"))
    app.add_handler(CallbackQueryHandler(portal_enter, pattern="^portal_enter$"))
    app.add_handler(CallbackQueryHandler(portal_ignore, pattern="^portal_ignore$"))
    app.add_handler(CallbackQueryHandler(sanctuary_heal, pattern="^sanctuary_heal$"))
    app.add_handler(CallbackQueryHandler(sanctuary_hp, pattern="^sanctuary_hp$"))
    app.add_handler(CallbackQueryHandler(sanctuary_gold, pattern="^sanctuary_gold$"))
    
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
    app.add_handler(CallbackQueryHandler(combat_menu, pattern="^combat_menu$"))
    app.add_handler(CallbackQueryHandler(use_item, pattern="^use_item_"))
    app.add_handler(CallbackQueryHandler(sell_items, pattern="^sell_items$"))
    app.add_handler(CallbackQueryHandler(sell_drops, pattern="^sell_drops$"))
    app.add_handler(CallbackQueryHandler(sell_equipment, pattern="^sell_equipment$"))
    app.add_handler(CallbackQueryHandler(sell_all_quick, pattern="^sell_all_quick$"))
    app.add_handler(CallbackQueryHandler(sell_item_confirm, pattern="^sell_"))
    app.add_handler(CallbackQueryHandler(shop, pattern="^shop$"))
    app.add_handler(CallbackQueryHandler(shop_buy, pattern="^shop_buy$"))
    app.add_handler(CallbackQueryHandler(shop_sell, pattern="^shop_sell$"))
    app.add_handler(CallbackQueryHandler(shop_potions, pattern="^shop_potions$"))
    app.add_handler(CallbackQueryHandler(shop_potions_cura, pattern="^shop_potions_cura$"))
    app.add_handler(CallbackQueryHandler(shop_potions_forca, pattern="^shop_potions_forca$"))
    app.add_handler(CallbackQueryHandler(shop_potions_resistencia, pattern="^shop_potions_resistencia$"))
    app.add_handler(CallbackQueryHandler(shop_potions_velocidade, pattern="^shop_potions_velocidade$"))
    app.add_handler(CallbackQueryHandler(shop_potions_especial, pattern="^shop_potions_especial$"))
    app.add_handler(CallbackQueryHandler(shop_weapons, pattern="^shop_weapons$"))
    app.add_handler(CallbackQueryHandler(shop_armors, pattern="^shop_armors$"))
    app.add_handler(CallbackQueryHandler(shop_buffs, pattern="^shop_buffs$"))
    app.add_handler(CallbackQueryHandler(shop_backpacks, pattern="^shop_backpacks$"))
    app.add_handler(CallbackQueryHandler(buy_backpack, pattern="^backpack_buy_"))
    app.add_handler(CallbackQueryHandler(map_menu, pattern="^map_menu$"))
    app.add_handler(CallbackQueryHandler(map_select, pattern="^map_select_"))
    app.add_handler(CallbackQueryHandler(map_locked, pattern="^map_locked_"))
    app.add_handler(CallbackQueryHandler(pending_drops_menu, pattern="^pending_drops_menu$"))
    app.add_handler(CallbackQueryHandler(pending_drop_pick, pattern="^pending_drop_pick_"))
    app.add_handler(CallbackQueryHandler(pending_drop_do_replace, pattern="^pending_drop_do_"))
    app.add_handler(CallbackQueryHandler(pending_drop_discard, pattern="^pending_drop_discard_"))
    app.add_handler(CallbackQueryHandler(pending_drop_discard, pattern="^pending_drop_discard_all$"))
    app.add_handler(CallbackQueryHandler(buy_item, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(show_status, pattern="^status$"))
    app.add_handler(CallbackQueryHandler(rest, pattern="^rest$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    
    # Handler para mensagens de texto (nome do personagem)
    from telegram.ext import MessageHandler, filters
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Handler global de erros
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler global de erros com logging detalhado"""
        erro = context.error
        user_id = get_user_context(update)
        
        # Determinar tipo de erro
        tipo_erro = "ERRO"
        if isinstance(erro, Exception):
            nome_erro = type(erro).__name__
            
            # Classificar como crítico se for erro de sistema
            if nome_erro in ["KeyError", "TypeError", "AttributeError", "IndexError"]:
                tipo_erro = "CRÍTICO"
            elif nome_erro in ["ConnectionError", "TimeoutError", "RuntimeError"]:
                tipo_erro = "CRÍTICO"
            else:
                tipo_erro = "ERRO"
        
        # Extrair mensagem de erro
        msg_erro = str(erro)[:200]  # Primeiros 200 caracteres
        
        # Obter stack trace
        stack = traceback.format_exception(type(erro), erro, erro.__traceback__)
        stack_formatado = "".join(stack)
        
        # Registrar no sistema de logging
        log_customizado(
            mensagem=f"{msg_erro}",
            tipo=tipo_erro,
            user_id=user_id,
            funcao="error_handler",
            context=nome_erro if isinstance(erro, Exception) else "Unknown"
        )
        
        # Imprimir stack trace formatado no terminal (apenas se for crítico)
        if tipo_erro == "CRÍTICO":
            print(f"{CORES['CRÍTICO']}╔══ STACK TRACE ══════════════════════════════╗{CORES['RESET']}")
            for linha in stack_formatado.split('\n'):
                if linha.strip():
                    print(f"{CORES['CRÍTICO']}║ {linha[:60]}{CORES['RESET']}")
            print(f"{CORES['CRÍTICO']}╚═════════════════════════════════════════════╝{CORES['RESET']}")
        
        # Notificar usuário
        try:
            if update and hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.answer(
                    "❌ Erro ao processar ação. Tente novamente.",
                    show_alert=True
                )
            elif update and hasattr(update, 'effective_message') and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ Ocorreu um erro. Use /start para voltar ao menu."
                )
        except Exception as e:
            log_customizado(
                mensagem=f"Erro ao notificar usuário: {str(e)[:100]}",
                tipo="AVISO",
                user_id=user_id
            )
    
    app.add_error_handler(error_handler)
    
    print("✅ Handlers registrados")
    print("🤖 Bot iniciado! Pressione Ctrl+C para parar")
    print("=" * 60)
    
    # Iniciar bot
    app.run_polling()

if __name__ == "__main__":
    main()