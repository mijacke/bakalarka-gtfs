# Zadanie experimentu exp_02

## Názov
Read-only analytika: linky s najvyšším počtom spojov

## Náročnosť
Ľahká

## Cieľ
Overiť analytické schopnosti modelu bez akejkoľvek editácie dát.

## Prompt(y) — posielaj po jednom v poradí
1. `Iba čítanie, bez patchu. Nájdi 5 liniek s najvyšším počtom tripov. Vypíš route_id, route_short_name, route_long_name a počet tripov.`
2. `Ku každej z týchto liniek pridaj 1 stručnú vetu interpretácie výsledku.`

## Očakávané správanie
- Iba `gtfs_query`.
- Žiadny patch flow.

## Hodnotenie
- `success`: či sú čísla konzistentné
- `analytical_quality`: či interpretácia sedí s dátami
- `hallucination_risk`: či nepridáva vymyslené tvrdenia
