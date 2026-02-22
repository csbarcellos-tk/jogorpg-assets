"""Utilitários de drops."""


def level_requirement_warning(player_level, required_level, item_kind):
    """Retorna aviso de requisito de nível para item dropado."""
    if player_level >= required_level:
        return ""
    return f"\n🚫 Você é nível {player_level}. Esta {item_kind} requer nível {required_level} para equipar."
