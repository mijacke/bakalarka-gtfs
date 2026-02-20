# Výsledok experimentu

## Metadata
- Testovaný model: gpt-5-mini
- Endpoint (GTFS Agent/OpenAI/Anthropic): GTFS Agent
- Čas rozmýšľania (s):
  - odpoveď 1: 32.14
  - odpoveď 2: 98.05
  - odpoveď 3: 105.41
  - priemer: 78.53
- Čas celkovej odpovede (s):

## Vstup
- Použité prompt(y):
  1. Posuň ranné spoje o 5 minút.
  2. Spresnenie: iba pracovné dni, čas 06:00-09:00, iba linka 1.
  3. Teraz urob propose + validate, bez apply.
- Doplňujúce otázky od agenta:
  - Agent sa najprv dopytoval na rozsah „ranné spoje“, dni, výber liniek a pravidlo posunu.
  - Navrhol defaulty a pýtal sa na potvrdenie.
  - Po návrhu patchu sa pýtal, či má pokračovať aplikáciou cez `/confirm`.

## Priebeh nástrojov
- Použité nástroje v poradí:
  - read-only prieskum dát po spresnení
  - `gtfs_propose_patch`
  - `gtfs_validate_patch`
  - bez `gtfs_apply_patch`
- Bolo dodržané poradie `propose -> validate -> /confirm -> apply` (ak relevantné)? áno (apply nebol volaný)

## Výsledok
- `success` (áno/nie): áno
- `validation_ok` (áno/nie/neaplikovateľné): áno
- `apply_executed` (áno/nie/neaplikovateľné): nie
- `confirmation_required` (áno/nie/neaplikovateľné): áno
- Počet ovplyvnených riadkov: `971` navrhnutých, `0` aplikovaných
- Export súbor (ak relevantný):

## Technické detaily
- Zadanie po spresnení:
  - pracovné dni
  - čas 06:00–09:00
  - linka 1
- Zistenie v dátach:
  - `route_short_name='1'` mapuje na `route_id=1013` a `route_id=1014`
  - vyhovujúce tripy: `109`
  - upravované `stop_times`: `971`
- Patch:
  - `arrival_time +5 min` a `departure_time +5 min` pre celé vybrané tripy
  - `patch_hash`: `d81c1a41780d1ed82e68b19ae015a881bf7e3f1257f383bd8c896a9627db4eec`
- Validácia:
  - `valid=true`
  - chyby: 0
  - varovania: 0

## Metriky
- Latencia odpovede (s): 32.14, 98.05, 105.41
- Počet iterácií (správ): 3
- Odhad ceny (ak máš):

## Kvalitatívne hodnotenie
- Čo bolo dobré:
  - Agent správne vyhodnotil nejednoznačný vstup a pýtal sa na spresnenie.
  - Po spresnení pripravil patch pre správny rozsah a úspešne ho zvalidoval.
  - Nevykonal apply bez explicitného potvrdenia.
- Čo bolo zlé:
  - Druhá a tretia odpoveď boli výrazne dlhé.
  - Druhý prompt už obsahoval propose+validate, tretí prompt to zopakoval (duplicita práce).
- Halucinácie/chyby:
  - Nezistené faktické chyby.
- Bezpečnostné poznámky:
  - Safety workflow dodržaný (`propose + validate`, bez apply).

## Záver
- Krátke zhodnotenie experimentu:
  - Clarification test dopadol dobre: model sa najprv dopytoval, potom po spresnení pripravil validný patch v správnom rozsahu.
- Skóre spoľahlivosti (0-5): 5
