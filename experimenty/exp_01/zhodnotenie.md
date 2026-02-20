# Zhodnotenie exp_01

## Čo bolo požadované
- Načítať GTFS feed (alebo použiť existujúci).
- Vypísať počty riadkov v hlavných tabuľkách.
- Vypísať 5 existujúcich zastávok (`stop_id`, `stop_name`).
- Nevykonať žiadnu zmenu dát.

## Čo agent splnil
- Potvrdil, že feed je načítaný.
- Vypísal počty tabuliek:
  - `stops`: 1354
  - `routes`: 102
  - `calendar`: 16
  - `trips`: 42 024
  - `stop_times`: 792 065
- Vypísal 5 existujúcich záznamov zo `stops` v požadovanom tvare.
- Nevykonal patch ani aplikáciu zmien.

## Čo agent nesplnil
- Nič podstatné.

## Čo v odpovedi chýba (nie je chyba agenta)
- Chýbajú metadáta testu: dátum, čas, model, commit.
- Chýbajú výkonové metriky: latencia a odhad ceny.

## Interpretácia pre bakalárku
- Read-only scenár je zvládnutý správne.
- Model vedel dodržať explicitné obmedzenie „iba SELECT“.
- Experiment podporuje tvrdenie, že systém je použiteľný na bezpečný prieskum GTFS dát cez textový vstup.

## Verdikt
- Experiment hodnotiť ako `úspešný`.
