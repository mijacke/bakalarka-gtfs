# Pred/Po plán vylepšenia (exp_02)

## Pred (aktuálny stav)
- Agent správne našiel TOP 5 liniek podľa počtu tripov.
- Agent ostal v read-only režime.
- Slabina: pri interpretácii bol miestami špekulatívny (napr. „pravdepodobne vysoký dopyt“ bez dôkazu z dát).

## Čo bolo zlé (stručne)
- Miešanie faktov z dát a domnienok v jednej vete.
- Chýbalo jasné označenie: „toto je iba odhad“.

## Čo ideme fixovať
- Pri interpretácii písať iba tvrdenia priamo podložené dátami z dotazu.
- Ak je potrebný odhad, explicitne ho označiť ako odhad.
- Zakázať kauzálne tvrdenia bez dát (dopyt, význam koridoru, dôvody prevádzky).
- Pri prázdnom `route_long_name` stručne uviesť limitáciu interpretácie.

## Ako to fixneme (prakticky)
- Úprava inštrukcií agenta:
  - „Najprv fakty z dát, potom voliteľný odhad v samostatnej vete.“
  - „Bez slov: pravdepodobne, naznačuje, môže znamenať, pokiaľ na to nie je dôkaz v dátach.“
- Re-test experimentu `exp_02` na rovnakých promptoch.

## Implementované zmeny
- Upravené systémové inštrukcie agenta v:
  - `/Users/mariolassu/code/skola/bakalarka-gtfs/agent_gtfs/agent/systemove_instrukcie.py`
- Pridané pravidlá:
  - read-only úlohy = iba `gtfs_query`,
  - pri analytike oddeľovať „Fakt z dát“ a „Interpretácia/Odhad“,
  - zákaz kauzálnych tvrdení bez dôkazu,
  - explicitné uvedenie limitácií (napr. prázdne `route_long_name`).
- Služba `gtfs-api` bola po zmene rebuildnutá a reštartovaná.

## Po (výsledok re-testu)
- Výsledok po fix-e:
  - Agent vrátil faktickú časť korektne a uviedol limitáciu `route_long_name = NULL`.
  - Interpretácie označil explicitne ako `odhad`.
  - Read-only režim bol dodržaný.
- Zlepšenie oproti "Pred":
  - Zmizli neoznačené domnienky; odhady sú teraz transparentne označené.
- Zostávajúce chyby:
  - V odhadoch sa stále objavujú kauzálne hypotézy (už však označené ako odhad).

## Krátka pripomienka pre ďalšie testy
- Vždy odlišuj: `Fakt z dát` vs `Interpretácia`.
