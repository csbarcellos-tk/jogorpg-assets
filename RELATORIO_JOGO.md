# Relatório rápido — 22/02/2026

## 3) Monstros novos estão dropando itens, ferramentas e poções?

**Parcialmente (do jeito que o código está hoje):**

- Os monstros novos (níveis 1-8) **estão dropando poções**.
- Também dropam **itens/equipamentos** (ex.: armas e armaduras em alguns monstros).
- **Não existe categoria “ferramentas” no código** atualmente (nenhuma definição de item/ferramenta com esse nome).

✅ Em resumo: poções + itens/equipamentos = sim; ferramentas = não implementado no sistema atual.

## 4) Chance do boss do mapa 1 aparecer

- Mapa 1 (`Planície`) tem `boss["chance"] = 0.08`.
- Isso significa **8% de chance por tentativa de caça** (enquanto o boss daquele mapa ainda não foi derrotado).

## 5) Quantos monstros tem nos mapas 1, 2 e 3 (rebalanceado)

- **Mapa 1 (Planície): 5 monstros**
	1. Slime
	2. Rato Gigante
	3. Morcego Cavernoso
	4. Goblin
	5. Orc

- **Mapa 2 (Floresta Sombria): 5 monstros**
	1. Lobo Jovem
	2. Bandido Novato
	3. Aranha do Mato
	4. Kobold
	5. Esqueleto

- **Mapa 3 (Montanhas Geladas): 6 monstros**
	1. Zumbi Lento
	2. Esqueleto Arqueiro
	3. Ciclope
	4. Xamã Goblin
	5. Gnoll Caçador
	6. Troll

## Status de ajustes

✅ **Resolvido** — Drop comum de armadura agora considera nível do monstro (e não só do jogador), alinhado com a regra de poder cair item acima do nível do personagem.

✅ **Resolvido** — `starting_weapons` do Guerreiro foi corrigido para arma da própria classe (`Espada de madeira`).

## Qualidade/escala (pendente)

- Arquivo único muito grande dificulta manutenção; separar em módulos (`data`, `combat`, `shop`, `drops`) reduziria bugs futuros.



