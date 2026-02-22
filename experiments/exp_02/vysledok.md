# Výsledok experimentu

## Metadata
- Testovaný model: gpt-5-mini
- Endpoint (GTFS Agent/OpenAI/Anthropic): GTFS Agent
- Čas rozmýšľania (s):
- Čas celkovej odpovede (s):

## Vstup
- Použité prompt(y):
  1. Iba čítanie, bez patchu. Nájdi 5 liniek s najvyšším počtom tripov. Vypíš route_id, route_short_name, route_long_name a počet tripov.
  2. Ku každej z týchto liniek pridaj 1 stručnú vetu interpretácie výsledku.
- Doplňujúce otázky od agenta:

## Priebeh nástrojov
- Použité nástroje v poradí:
  - Prompt 1: read-only analytický výpis TOP 5 liniek podľa počtu tripov
  - Prompt 2: textová interpretácia pre každú linku
- Bolo dodržané poradie `propose -> validate -> /confirm -> apply` (ak relevantné)? neaplikovateľné

## Výsledok
- `success` (áno/nie): áno
- `validation_ok` (áno/nie/neaplikovateľné): neaplikovateľné
- `apply_executed` (áno/nie/neaplikovateľné): neaplikovateľné
- `confirmation_required` (áno/nie/neaplikovateľné): neaplikovateľné
- Počet ovplyvnených riadkov:
- Export súbor (ak relevantný):

## Metriky
- Latencia odpovede (s):
- Počet iterácií (správ): 2
- Odhad ceny (ak máš):

## Kvalitatívne hodnotenie
- Čo bolo dobré:
  - Agent ostal v read-only režime, bez patchu a bez aplikácie.
  - Vrátil 5 liniek s požadovanými poľami a počtami tripov.
  - Pri chýbajúcom `route_long_name` explicitne uviedol limitáciu (`NULL`).
  - Interpretácie boli označené ako `Interpretácia (odhad)`.
- Čo bolo zlé:
  - Odhady stále obsahujú kauzálne domnienky (napr. dopyt, význam koridoru), ktoré nie sú priamo dokázané v zobrazených dátach.
- Halucinácie/chyby:
  - Bez tvrdenia vydávaného za fakt; zostáva nízke riziko špekulatívnosti v časti „odhad“.
- Bezpečnostné poznámky:
  - Nevykonala sa žiadna mutácia dát.

## Záver
- Krátke zhodnotenie experimentu:
  - Re-test po úprave inštrukcií je lepší: faktická časť je čistejšia a odhady sú explicitne označené.
- Skóre spoľahlivosti (0-5): 5
