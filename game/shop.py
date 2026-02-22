"""Utilitários de loja."""

from game.data import SHOWCASE_LEVEL_WINDOW


def build_showcase_items(items, player_level, base_field):
    """Monta vitrine limpa: itens base + melhor variante recente por item base."""
    variant_min_level = max(1, player_level - SHOWCASE_LEVEL_WINDOW)

    base_items = {}
    best_variant_by_base = {}

    for item_name, item_data in items.items():
        if item_data.get("price", 0) <= 0:
            continue

        if item_data.get("is_level_variant"):
            if item_data["level_req"] < variant_min_level:
                continue

            base_name = item_data.get(base_field, item_name)
            current_best = best_variant_by_base.get(base_name)

            if not current_best:
                best_variant_by_base[base_name] = (item_name, item_data)
            else:
                _, best_data = current_best
                if item_data["level_req"] > best_data["level_req"]:
                    best_variant_by_base[base_name] = (item_name, item_data)
        else:
            base_items[item_name] = item_data

    result = dict(base_items)
    for variant_name, variant_data in best_variant_by_base.values():
        result[variant_name] = variant_data

    return result
