# Výsledok experimentu

## Metadata
- Testovaný model: gpt-5-mini
- Endpoint (GTFS Agent/OpenAI/Anthropic): GTFS Agent
- Čas rozmýšľania (s):
  - odpoveď 1: 14.17
  - odpoveď 2: 10.93
  - odpoveď 3: 7.80
  - odpoveď 4: 14.59
  - odpoveď 5: 122.63
  - priemer: 34.02

## Vstup
- Použité prompt(y):
  1. Najprv iba čítanie: nájdi route_id pre route_short_name = '1'. Ak je route_id viac, vyber to route_id, ktoré má najviac sobotných tripov (calendar.saturday = 1). Vypíš zvolené route_id a počet sobotných tripov.
  2. Iba čítanie, bez patchu. Pre zvolené route_id vypíš presný očakávaný rozsah zásahu: koľko riadkov stop_times by sa menilo pri posune arrival_time aj departure_time o +7 min v intervale 08:00:00-16:00:00, iba sobota.
  3. 1013
  4. C
  5. Navrhni patch, potom urob propose + validate, bez apply. Vráť patch_hash, matched_rows a valid. Ak je valid=true a matched_rows sa líši od očakávaného rozsahu z kroku 2 o viac ako 5 %, patch neodporúčaj na apply a vysvetli rozdiel.
- Doplňujúce otázky od agenta:
  - Pri kroku 1: remíza medzi `route_id=1013` a `route_id=1014` (oba 214 sobotných tripov), agent žiadal výber.
  - Pri kroku 2: agent žiadal spresniť časový filter (A/B/C).

## Priebeh nástrojov
- Použité nástroje v poradí:
  - read-only dotazy (`gtfs_query`) na výber route a výpočet očakávaného rozsahu
  - pokusy o `gtfs_propose_patch` (viacero variant filtra)
  - `gtfs_validate_patch`: nevykonané (nedostal sa validný návrh patchu)
  - `gtfs_apply_patch`: nevykonané
- Bolo dodržané poradie `propose -> validate -> /confirm -> apply` (ak relevantné)? nie (workflow sa zastavil pred validáciou kvôli neakceptovanému formátu filtra)

## Výsledok
- `success` (áno/nie): nie
- `validation_ok` (áno/nie/neaplikovateľné): neaplikovateľné
- `apply_executed` (áno/nie/neaplikovateľné): nie
- `confirmation_required` (áno/nie/neaplikovateľné): neaplikovateľné
- Počet ovplyvnených riadkov:
  - očakávaný rozsah podľa read-only dotazu (route_id=1013, sobota, variant C): `860`
  - propose preview: 
  - aplikované: `0`
- Export súbor (ak relevantný): nevykonaný

## Technické detaily
- `route_short_name='1'`: nájdené `route_id=1013` a `route_id=1014`
- Počet sobotných tripov:
  - `1013`: `214`
  - `1014`: `214`
- Používateľský výber: `route_id=1013`
- Definícia intervalu (zvolená možnosť C): `arrival_time` aj `departure_time` musia byť v `08:00:00-16:00:00`
- Očakávaný zásah: `860` riadkov v `stop_times`
- Stav pri návrhu patchu:
  - agent hlásil chyby parsera/validácie formátu filtra pri pokusoch o `gtfs_propose_patch`
  - `patch_hash`: 

## Metriky
- Latencia odpovede (s): 14.17, 10.93, 7.80, 14.59, 122.63
- Počet iterácií (správ): 5
- Odhad ceny (ak máš):

## Kvalitatívne hodnotenie
- Čo bolo dobré:
  - Agent sa korektne dopytoval pri nejednoznačnosti (remíza route, definícia intervalu).
  - Read-only výsledok pre cieľový rozsah bol vypočítaný (`860`).
- Čo bolo zlé:
  - Experiment sa nedostal do stabilného `propose + validate` kroku.
  - Návrh patchu stroskotal na formáte filtra, takže nebol `patch_hash`.
- Halucinácie/chyby:
  - Nie je potvrdená halucinácia v dátach; problém bol najmä technický (kompatibilita patch filtra so server parserom).
- Bezpečnostné poznámky:
  - Bezpečnosť OK: bez validného workflow sa nič neaplikovalo.

## Záver
- Krátke zhodnotenie experimentu:
  - Re-test exp_10 bol analyticky úspešný (výber linky + presný rozsah 860), ale editačná časť zlyhala na syntaxi filtra v `propose` kroku, preto bez validácie/apply/exportu.
- Skóre spoľahlivosti (0-5): 2
