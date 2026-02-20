# Výsledok experimentu

## Metadata
- Dátum:
- Čas:
- Testovaný model:
- Endpoint (GTFS Agent/OpenAI/Anthropic):
- Verzia kódu (git commit):

## Vstup
- Použité prompt(y):
  1. Iba čítanie, bez patchu. Nájdi 5 liniek s najvyšším počtom tripov. Vypíš route_id, route_short_name, route_long_name a počet tripov.
  2. Ku každej z týchto liniek pridaj 1 stručnú vetu interpretácie výsledku.
- Doplňujúce otázky od agenta:

## Priebeh nástrojov
- Použité nástroje v poradí:
  - Prompt 1: read-only analytický výpis (TOP 5 podľa počtu tripov)
  - Prompt 2: textová interpretácia výsledkov
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
  - Agent vrátil 5 liniek s požadovanými stĺpcami a počtami tripov.
  - Ostal v read-only režime (bez patchu a bez aplikácie).
  - Interpretačné vety boli stručné a zrozumiteľné.
- Čo bolo zlé:
  - Viaceré interpretácie obsahujú odhady typu „pravdepodobne“, ktoré nie sú priamo podložené iba zobrazenými dátami.
- Halucinácie/chyby:
  - Možná mierna interpretačná halucinácia (príčiny dopytu/cestovania bez dôkazu z dát).
- Bezpečnostné poznámky:
  - Nevykonala sa žiadna mutácia dát.

## Záver
- Krátke zhodnotenie experimentu:
  - Experiment bol úspešný pre read-only analytiku; slabším miestom je mierne špekulatívna interpretácia niektorých liniek.
- Skóre spoľahlivosti (0-5): 4
