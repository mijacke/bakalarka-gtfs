# One-shot prompt pre Claude Opus: GTFS editor agent (MCP + UI)

> Skopíruj celý tento prompt do Claude Opus (alebo iného LLM) a nechaj ho vygenerovať kompletný návrh + MVP plán.

---

## PROMPT (vložiť do Claude Opus)

Si **hlavný technický architekt a výskumný konzultant** pre bakalársku prácu:

**Téma:** Tvorba/editácia cestovného poriadku s využitím dostupných LLM (GTFS) iba cez textový input  
**Cieľ:** Preskúmať a navrhnúť systém, ktorý umožní automatizovanú editáciu GTFS (alebo databázy nad GTFS) cez textové príkazy pomocou LLM, ideálne cez **Model Context Protocol (MCP)**. Porovnať modely (Claude/ChatGPT/Gemini + lokálne Qwen), spoľahlivosť, cenu a odporúčania.

### 1) Čo mám dostať ako výstup (musíš dodať všetko)
Vygeneruj mi **kompletný návrh riešenia od začiatku do konca** tak, aby som podľa toho vedel okamžite začať implementovať a písať bakalárku.

Dodaj tieto sekcie:

#### A) Produktový popis (1–2 strany)
- Čo presne systém robí (use-cases typu: „posuň všetky spoje po 20:00 o 10 min“, „zmeň zastávky od 8:00 do 16:00“, „vymaž spoje na linke X v dátumoch Y“, „pridaj výluku“).
- Aké sú vstupy/výstupy (textový príkaz → plán → návrh zmien → diff → aplikácia → audit log).
- Čo je „hotové“ v MVP vs. čo je „nice-to-have“.

#### B) Architektúra systému (praktická, implementovateľná)
Navrhni architektúru s modulmi:
- **UI/Agent IDE** (neprogramovať frontend od nuly): používame momentálne LibreChat
- **LLM Orchestrator / Agent runtime**: návrh agentového toku (plánovanie → výber nástrojov → vykonanie → validácia → návrh diffu → potvrdenie používateľom → commit).
- **Tools (MCP)**: navrhni MCP server(y) a konkrétne nástroje:
  1) načítanie GTFS (zip/dir) + indexovanie  
  2) query nad GTFS (trips/stop_times/calendar)  
  3) generovanie návrhu zmien (napr. patch/diff)  
  4) validácia a integritné kontroly (GTFS pravidlá + sanity checks)  
  5) aplikácia zmien (do súborov aj alternatívne do DB)  
  6) audit log + rollback
- **Dáta**: odporuč, či MVP robiť nad:
  - priamymi GTFS súbormi (zmeny v txt + export), alebo
  - databázou (SQLite/Postgres) s import/export pipeline.
  Zvoľ 1 primárny smer pre MVP a druhý ako rozšírenie.

#### C) Návrh „agentového správania“
- Definuj **policy**: agent nesmie meniť dáta bez návrhu diffu a explicitného potvrdenia (ak navrhneš auto-commit, tak len v „safe mode“).
- Ako má agent komunikovať:  
  - vždy ukáž „Plán úloh“ (task list),  
  - vždy ukáž „Použité nástroje“ (tool calls) a ich výsledky v zrozumiteľnej forme,  
  - **nezverejňuj interné úvahy**, iba stručný plán a odôvodnenie výberu nástrojov.
- Pridaj šablónu, ako má vyzerať „Task“ (názov, kroky, nástroje, očakávaný výstup, riziká).

#### D) Konkrétny tech-stack a repo štruktúra
- Jazyk a frameworky (preferuj Python + FastAPI pre backend, ak je to rozumné).
- MCP server implementácia (kde, ako, API kontrakty).
- Ako prepojíš UI (vybraný existujúci agent-frontend) s MCP nástrojmi.
- Repo strom (adresáre, moduly), konfigy, env vars, lokálny dev setup.

#### E) MVP implementačný plán po týždňoch (konkrétne)
- Minimálne 4–6 míľnikov, každý s:
  - čo sa implementuje,
  - aké testy/validácie pribudnú,
  - čo bude demonštrácia (demo scenár s GTFS).

#### F) Evaluácia a porovnanie modelov (bakalárske)
Navrhni metodiku:
- dataset scenáre (min. 10 príkazov: jednoduché, stredné, komplikované),
- metriky: úspešnosť editácie, počet chýb, počet iterácií, čas, cena, kvalita vysvetlenia, robustnosť na nejednoznačný príkaz,
- „failure modes“ (napr. rozbitie kalendára, duplicita trip_id, nekonzistentné stop_times),
- čo porovnať: Claude/ChatGPT/Gemini + lokálny Qwen (citlivé dáta) a ako to zapojiť.

#### G) Cena a prevádzka
- Ako počítať náklady (tokeny, cache, priemerný príkaz, „heavy“ príkaz).
- Kde sa oplatí lokálny model (Qwen) a aké kompromisy (latencia, presnosť).
- Doporučenie pre „produkčný“ režim: cloud LLM vs hybrid.

#### H) Bezpečnosť, citlivé dáta, audit
- Minimalizácia odosielaných dát do cloudu (maskovanie, výrezy kontextu, selekcia len relevantných tabuliek).
- Audit log, reprodukovateľnosť, rollback.

### 2) Obmedzenia a preferencie (dodrž)
- Nechcem programovať celý frontend od nuly: použi existujúce agentové UI/IDE riešenie alebo plugin (open-source), ktoré už má chat, log akcií, prípadne integráciu do IDE.
- Riešenie musí byť realistické na bakalárku: MVP nech je postaviteľné za ~6–10 týždňov sólo vývojom.
- Primárny formát dát: **GTFS** (stops.txt, routes.txt, trips.txt, stop_times.txt, calendar*.txt).
- Textový input je jediný spôsob zadania zmien (žiadne klikanie pravidiel).
- Uprednostni MCP ako spôsob prepojenia modelu na nástroje, ak je to rozumné.

### 3) Formát odpovede
- Použi jasné nadpisy A–H presne podľa štruktúry vyššie.
- Pri každej technologickej voľbe uveď krátke „prečo“ + alternatívu.
- Zahrň aspoň 2 diagramy v textovej forme (ASCII alebo mermaid bez renderu):  
  1) architektúra modulov, 2) tok jednej editácie (command → tools → diff → commit).

---

## Poznámka (pre hľadanie existujúceho agent UI)
Pri výbere existujúceho agentového UI/IDE riešenia uprednostni:
- Open-source agentové UI s logom nástrojov / task listom
- ľahká integrácia s backendom cez HTTP / websockets
- model-agnostic prístup (Claude/ChatGPT/Gemini/locals)

Uveď 2–3 kandidátov a vyber 1 pre MVP.

---
