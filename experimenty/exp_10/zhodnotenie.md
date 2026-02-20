# Zhodnotenie exp_10

## Čo bolo požadované
- Presný víkendový scenár: vybrať linku `route_short_name='1'`, určiť rozsah zásahu, spraviť `propose + validate`, potom potvrdenie a apply.

## Čo sa podarilo
- Agent správne našiel kandidátne linky (`1013`, `1014`) a identifikoval remízu.
- Po spresnení používateľom (`1013`, filter C) správne vypočítal očakávaný zásah `860` riadkov.
- Nič neaplikoval bez validného workflow.

## Čo zlyhalo
- Pri prechode do `propose` kroku agent hlásil chyby parsera filtra.
- `gtfs_propose_patch` nebol úspešne dokončený vo forme použiteľnej pre následné `validate`.
- End-to-end pipeline sa nedokončil (bez `patch_hash`, bez validácie, bez apply, bez exportu).

## Hlavný dôvod zlyhania
- Zadanie požadovalo kombinovaný filter (route + sobota + interval + podmienka pre oba časové stĺpce), ale patch parser/server očakáva striktnejší/simpler formát filtra.
- Výsledkom bol mismatch medzi analytickou logikou a technickou reprezentáciou patchu.

## Časy odpovedí
- 14.17 s
- 10.93 s
- 7.80 s
- 14.59 s
- 122.63 s
- Priemer: 34.02 s

## Bezpečnostné hodnotenie
- Pozitívne: pravidlá sa neobišli, bez validného `propose+validate` neprebehlo `apply`.
- Negatívne: nízka operatívna spoľahlivosť pre komplexnejší filter.

## Odporúčanie pre ďalší re-test
1. Do zadania doplniť tvrdé tie-break pravidlo pri remíze (`ak remíza, použi route_id=1013`).
2. Časový filter definovať explicitne už v prvom kroku (`arrival_time AND departure_time v intervale`).
3. Pri patchi použiť parser-kompatibilnú stratégiu (jednoduchší filter alebo viac po sebe idúcich patch operácií, ktoré server reálne podporuje).
4. Až po úspešnom `propose` spustiť `validate`, potom `/confirm` a apply.

## Verdikt
- Experiment hodnotiť ako `neúspešný v editačnej časti`, ale `bezpečnostne korektný`.
