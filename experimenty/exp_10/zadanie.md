# Zadanie experimentu exp_10

## Názov
Deterministický víkendový scenár: zmena + export + audit

## Náročnosť
Najťažšia

## Cieľ
Otestovať celý pipeline na presne definovanom scenári bez nejasností v rozsahu.

## Prompt(y) — posielaj po jednom v poradí
1. `Najprv iba čítanie: nájdi route_id pre route_short_name = '1'. Ak je route_id viac a je remíza v počte sobotných tripov (calendar.saturday = 1), použi route_id = 1013. Vypíš zvolené route_id a počet sobotných tripov.`
2. `Iba čítanie, bez patchu. Pre route_id = 1013 vypíš presný očakávaný rozsah zásahu: koľko riadkov stop_times by sa menilo pri posune arrival_time aj departure_time o +7 min, iba sobota, a zároveň arrival_time aj departure_time musia byť v intervale 08:00:00-16:00:00.`
3. `Navrhni patch, potom urob propose + validate, bez apply. Vráť patch_hash, matched_rows a valid.`
4. `/confirm <patch_hash>`
5. `Po aplikácii exportuj feed do .work/exports/exp_10_final.zip a vypíš krátky audit: route_id, časový interval, deň, počet upravených riadkov, patch_hash, cesta k exportu.`

## Očakávané správanie
- Bez doplňujúcich otázok na výber linky alebo definíciu intervalu (všetko je zadané).
- Pred aplikáciou je jasne porovnaný očakávaný a navrhnutý rozsah zásahu.
- Korektný end-to-end workflow vrátane exportu po úspešnom apply.

## Hodnotenie
- `end_to_end_success`
- `correctness`
- `auditability`
- `scope_consistency`
- `operational_readiness`
