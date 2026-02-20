# Zadanie experimentu exp_01

## Názov
Read-only baseline: načítanie feedu a základné počty

## Náročnosť
Veľmi ľahká

## Cieľ
Overiť, že agent vie pracovať iba v režime čítania a nevytvára patch, keď to nie je žiadané.

## Prompt(y) — posielaj po jednom v poradí
1. `Najprv načítaj GTFS dáta z data/gtfs_latest (ak ešte nie sú načítané). Potom vypíš počet riadkov v tabuľkách stops, routes, calendar, trips, stop_times. Iba čítanie, bez patchu a bez aplikácie zmien.`
2. `Vypíš presne 5 existujúcich záznamov zo stops iba v tvare stop_id a stop_name. Nevytváraj nové zastávky. Iba SELECT.`

## Očakávané správanie
- Použije sa `gtfs_load` a `gtfs_query`.
- Nepoužije sa `gtfs_propose_patch`, `gtfs_validate_patch`, `gtfs_apply_patch`, `gtfs_export`.

## Hodnotenie
- `success`: či sú výstupy správne a úplné
- `tool_discipline`: či ostal v read-only režime
- `response_quality`: či je odpoveď jasná a s diakritikou
