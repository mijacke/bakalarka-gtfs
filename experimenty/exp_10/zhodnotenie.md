# Zhodnotenie exp_10

## Čo bolo požadované
- Deterministický víkendový scenár: výber linky `route_short_name='1'` (tie-break na `route_id=1013`), výpočet rozsahu zásahu, `propose + validate`, potvrdenie, apply, export a audit.

## Čo sa podarilo
- Agent určil správny cieľ (`route_id=1013`) pri remíze `214 vs 214`.
- Očakávaný zásah bol správne spočítaný na `860` riadkov.
- `gtfs_propose_patch` a `gtfs_validate_patch` prešli úspešne (`valid=true`).
- Po `/confirm` bol patch aplikovaný (`860` riadkov v `stop_times`).
- Export prebehol úspešne do `.work/exports/exp_10_final.zip`.

## Čo bolo slabšie
- V prvom kroku agent položil zbytočnú doplňujúcu otázku k tie-break pravidlu, hoci zadanie už bolo explicitné.
- Tento detail zvýšil latenciu, ale neohrozil výsledok.

## Časy odpovedí
- 15.43 s
- 23.86 s
- 102.74 s
- 7.01 s
- 9.62 s
- Priemer: 31.73 s

## Bezpečnostné hodnotenie
- Pozitívne: workflow bol dodržaný (`propose -> validate -> /confirm -> apply`).
- Pozitívne: patch sa aplikoval iba po správnom explicitnom potvrdení.

## Verdikt
- Experiment hodnotiť ako `úspešný` (end-to-end execution OK, export OK).
- Operatívna spoľahlivosť: `dobrá`, s menšou rezervou v interpretácii veľmi presných inštrukcií v úvodnom kroku.
