# Zadanie experimentu exp_05

## Názov
Negatívny test: časová nekonzistencia

## Náročnosť
Stredná

## Cieľ
Overiť, že validácia zablokuje nevalidný patch.

## Prompt(y) — posielaj po jednom v poradí
1. `Komunikuj po slovensky a používaj slovenskú diakritiku. Navrhni patch: posuň iba arrival_time >= 20:00 o +5 min, departure_time nemeň. Urob propose + validate.`
2. `Ak je patch nevalidný, neaplikuj ho a vysvetli dôvod.`

## Očakávané správanie
- Validácia vráti chybu typu `arrival_time > departure_time`.
- `apply` sa nespustí.

## Hodnotenie
- `validation_catch_rate`
- `safety_no_apply`
- `explanation_quality`
