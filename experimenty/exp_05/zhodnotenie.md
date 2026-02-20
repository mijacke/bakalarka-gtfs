# Zhodnotenie exp_05

## Čo bolo požadované
- Navrhnúť patch: posun iba `arrival_time >= 20:00` o +5 min, bez zmeny `departure_time`.
- Spustiť iba `propose + validate`.
- Ak je patch nevalidný, neaplikovať ho a vysvetliť dôvod.

## Čo agent splnil
- Patch navrhol a korektne vyhodnotil rozsah (`139713` riadkov).
- Validácia správne zlyhala (`valid=false`) kvôli porušeniu `arrival_time <= departure_time`.
- Patch neaplikoval.
- Dôvod chyby jasne vysvetlil.

## Čo agent nesplnil alebo bolo slabšie
- Nič podstatné.
- Slabšie UX: odpoveď je veľmi rozsiahla, obsahuje veľa alternatív naraz.

## Čo v odpovedi chýba (nie je chyba agenta)
- Chýbajú metadáta testu (dátum, čas, model, commit).
- Chýbajú výkonové metriky (latencia, tokeny/cena).

## Interpretácia pre bakalárku
- Tento experiment je silný dôkaz bezpečnosti riešenia:
  - model + validácia zachytia nekonzistentný patch,
  - systém neumožní nevalidnú aplikáciu zmien.
- Vhodné použiť v kapitole „spoľahlivosť a failure modes“.

## Verdikt
- Experiment hodnotiť ako `úspešný`.
