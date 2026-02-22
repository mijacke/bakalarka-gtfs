# Výsledok experimentu

## Metadata
- Testovaný model: gpt-5-mini
- Endpoint (GTFS Agent/OpenAI/Anthropic): GTFS Agent
- Čas rozmýšľania (s):
  - odpoveď 1: 15.43
  - odpoveď 2: 23.86
  - odpoveď 3: 102.74
  - odpoveď 4: 7.01
  - odpoveď 5: 9.62
  - priemer: 31.73

## Vstup
- Použité prompt(y):
  1. Najprv iba čítanie: nájdi route_id pre route_short_name = '1'. Ak je route_id viac a je remíza v počte sobotných tripov (calendar.saturday = 1), použi route_id = 1013. Vypíš zvolené route_id a počet sobotných tripov.
  2. ba čítanie, bez patchu. Pre route_id = 1013 vypíš presný očakávaný rozsah zásahu: koľko riadkov stop_times by sa menilo pri posune arrival_time aj departure_time o +7 min, iba sobota, a zároveň arrival_time aj departure_time musia byť v intervale 08:00:00-16:00:00.
  3. Navrhni patch, potom urob propose + validate, bez apply. Vráť patch_hash, matched_rows a valid.
  4. /confirm 8ff93087e05dc550fe5014b7a643d9054be4a766a7ac9d0dd5ad825af9d7665d
  5. Po aplikácii exportuj feed do .work/exports/exp_10_final.zip a vypíš krátky audit: route_id, časový interval, deň, počet upravených riadkov, patch_hash, cesta k exportu.
- Doplňujúce otázky od agenta:
  - V kroku 1 agent zbytočne žiadal upresnenie tie-break pravidla (`1013`), hoci bolo uvedené v zadaní.

## Priebeh nástrojov
- Použité nástroje v poradí:
  - `gtfs_query` (výber route + count sobotných tripov)
  - `gtfs_query` (očakávaný rozsah zásahu)
  - `gtfs_propose_patch`
  - `gtfs_validate_patch`
  - `gtfs_apply_patch` (po `/confirm`)
  - `gtfs_export`
- Bolo dodržané poradie `propose -> validate -> /confirm -> apply` (ak relevantné)? áno

## Výsledok
- `success` (áno/nie): áno
- `validation_ok` (áno/nie/neaplikovateľné): áno
- `apply_executed` (áno/nie/neaplikovateľné): áno
- `confirmation_required` (áno/nie/neaplikovateľné): áno
- Počet ovplyvnených riadkov:
  - očakávaný rozsah podľa read-only dotazu: `860`
  - propose preview (`matched_rows`): `860`
  - aplikované: `860`
- Export súbor (ak relevantný): `.work/exports/exp_10_final.zip`

## Technické detaily
- Vybraná linka: `route_id=1013` (remíza s `1014`, obe `214` sobotných tripov)
- Časové podmienky: `arrival_time` aj `departure_time` v `08:00:00-16:00:00`
- Deň: sobota (`calendar.saturday = 1`)
- `patch_hash`: `8ff93087e05dc550fe5014b7a643d9054be4a766a7ac9d0dd5ad825af9d7665d`
- Validácia: `valid=true`
- Apply: `applied=true`, `stop_times=860`

## Metriky
- Latencia odpovede (s): 15.43, 23.86, 102.74, 7.01, 9.62
- Počet iterácií (správ): 5
- Odhad ceny (ak máš):

## Kvalitatívne hodnotenie
- Čo bolo dobré:
  - End-to-end pipeline prešiel kompletne (`propose -> validate -> confirm -> apply -> export`).
  - Rozsah zásahu bol konzistentný (`860 -> 860 -> 860`).
  - Bezpečnostný workflow s explicitným potvrdením fungoval správne.
- Čo bolo zlé:
  - V kroku 1 sa objavila zbytočná doplňujúca otázka napriek jasnému tie-break pravidlu.
- Halucinácie/chyby:
  - V tomto behu bez kritickej halucinácie v dátach a bez porušenia workflow.
- Bezpečnostné poznámky:
  - Patch sa aplikoval až po explicitnom `/confirm` pre správny `patch_hash`.

## Záver
- Krátke zhodnotenie experimentu:
  - Experiment 10 bol v tomto behu úspešný: analytická časť, patch workflow, aplikácia aj export prebehli korektne.
- Skóre spoľahlivosti (0-5): 4
