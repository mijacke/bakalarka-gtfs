# Zhodnotenie exp_08

## Čo bolo požadované
- Overiť správanie pri nejednoznačnom texte „Posuň ranné spoje o 5 minút“.
- Po spresnení pripraviť patch a vykonať `propose + validate`, bez apply.

## Čo agent splnil
- Najprv položil doplňujúce otázky (čas, dni, linky, pravidlo posunu).
- Po spresnení (`pracovné dni`, `06:00–09:00`, `linka 1`) pripravil patch.
- Vykonal `propose + validate` a získal `valid=true`.
- Neaplikoval zmenu bez `/confirm`.

## Kľúčové fakty
- `route_short_name='1'` -> `route_id=1013`, `route_id=1014`
- Vyhovujúce tripy: `109`
- Dotknuté `stop_times`: `971`
- `patch_hash`: `d81c1a41780d1ed82e68b19ae015a881bf7e3f1257f383bd8c896a9627db4eec`
- Validácia: bez chýb a bez varovaní

## Časy odpovedí
- 32.14 s
- 98.05 s
- 105.41 s
- Priemer: 78.53 s

## Čo bolo dobré
- Správne clarification správanie.
- Správna práca so scope po spresnení.
- Dodržanie bezpečnostného workflow.

## Čo zlepšiť
- Skrátiť odpovede.
- Po druhom prompte už bol výsledok hotový; tretí prompt viedol k opakovaniu.

## Verdikt
- Experiment hodnotiť ako `úspešný`.
