# Zhodnotenie exp_02

## Čo bolo požadované
- Nájsť 5 liniek s najvyšším počtom tripov.
- Vypísať `route_id`, `route_short_name`, `route_long_name`, `trip_count`.
- Ku každej linke doplniť 1 stručnú vetu interpretácie.
- Ostať v read-only režime.

## Čo agent splnil
- Vypísal TOP 5 liniek podľa počtu tripov s požadovanými poľami.
- Ku každej linke doplnil stručnú interpretáciu.
- Nevykonal patch, validáciu, apply ani export.

## Čo agent nesplnil alebo bolo slabšie
- Interpretačné vety sú miestami špekulatívne (napr. odhady dopytu), bez explicitného podkladu v poskytnutých dátach.
- Pri prázdnom `route_long_name` nepridal upozornenie na možnú limitáciu interpretácie.

## Čo v odpovedi chýba (nie je chyba agenta)
- Chýbajú metadáta testu (dátum, čas, model, commit).
- Chýbajú výkonové metriky (latencia, tokeny/cena).

## Interpretácia pre bakalárku
- Model spoľahlivo zvláda read-only SQL analytiku.
- Pri textovej interpretácii je potrebné počítať s rizikom miernej „nad-interpretácie“.
- Tento experiment je vhodný do kapitoly o kompromisoch medzi analytickou správnosťou a naratívnym vysvetľovaním.

## Verdikt
- Experiment hodnotiť ako `úspešný` s poznámkou o strednom riziku interpretačných domnienok.
