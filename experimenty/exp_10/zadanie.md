# Zadanie experimentu exp_10

## Názov
Komplexný scenár: plánovaná zmena + export + audit

## Náročnosť
Najťažšia

## Cieľ
Otestovať celý pipeline na realistickom scenári od analýzy po export.

## Prompt(y) — posielaj po jednom v poradí
1. `Navrhni zmenu pre vybranú linku: posuň arrival_time aj departure_time o +7 min v intervale 08:00-16:00. Najprv vypíš rozsah zásahu (koľko riadkov), potom urob propose + validate.`
2. `Vráť patch_hash a čakaj na potvrdenie.`
3. `/confirm <patch_hash>`
4. `Po aplikácii exportuj feed do .work/exports/exp_10_final.zip a potvrď cestu k súboru.`
5. `Nakoniec vypíš krátky audit: čo sa menilo, koľko riadkov, výsledok validácie.`

## Očakávané správanie
- Korektný end-to-end workflow.
- Export až po úspešnej aplikácii.

## Hodnotenie
- `end_to_end_success`
- `correctness`
- `auditability`
- `operational_readiness`
