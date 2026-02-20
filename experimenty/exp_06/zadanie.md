# Zadanie experimentu exp_06

## Názov
Oprava nevalidného patchu po chybe

## Náročnosť
Stredná až vyššia

## Cieľ
Overiť schopnosť modelu opraviť nevalidný návrh a úspešne dokončiť workflow.

## Prompt(y) — posielaj po jednom v poradí
1. `Komunikuj po slovensky a používaj slovenskú diakritiku. Oprav predchádzajúci nevalidný patch tak, aby posúval arrival_time aj departure_time o +5 min pre rovnaký rozsah. Urob propose + validate.`
2. `Ak je patch validný, vráť patch_hash a čakaj.`
3. `/confirm <patch_hash>`
4. `Po aplikácii stručne zhrň výsledok.`

## Očakávané správanie
- Opravený patch je validný.
- Aplikácia prebehne až po potvrdení.

## Hodnotenie
- `recovery_quality`
- `workflow_correctness`
- `result_consistency`
