# Protokol experimentov GTFS LLM

## Ako spúšťať experimenty
- Každý experiment (`exp_01` až `exp_10`) spúšťaj v samostatnom chate.
- V rámci jedného experimentu posielaj prompty postupne, po jednom, v poradí.
- Pred začiatkom nového experimentu otvor nový chat.

## Jazykové pravidlo
- V prvom prompte vždy vyžaduj: „Komunikuj po slovensky a používaj slovenskú diakritiku.“
- Anglické názvy tabuliek a stĺpcov (napr. `stop_times`, `arrival_time`) sú povolené.

## Bezpečnostné pravidlo
- Ak experiment nevyžaduje zápis, explicitne uveď: „Iba čítanie, bez patchu a bez aplikácie zmien.“
- Ak experiment vyžaduje zmenu, dodrž workflow `propose -> validate -> /confirm -> apply`.

## Výsledky
- Každý experiment zapisuj do príslušného `vysledok.md`.
- Neznáme metriky nechaj prázdne.
