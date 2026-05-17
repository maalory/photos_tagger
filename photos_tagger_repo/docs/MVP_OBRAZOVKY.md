# MVP Obrazovky

Tento dokument popisuje první tři obrazovky aplikace.

## 1. Katalog

Účel:

- přidání kořenových složek
- spuštění indexace
- rychlá kontrola stavu databáze a cache
- později i hromadné opravy datumu nad složkou nebo eventem

Prvky obrazovky:

- seznam zdrojových složek
- tlačítko `Přidat složku`
- tlačítko `Spustit scan`
- tlačítko `Opravit datum` pro hromadné operace nad vybraným zdrojem nebo složkou
- přehled počtů `sources`, `folders`, `assets`, `albums`, `tags`
- informace o cestě k databázi a cache

## 2. Třídění

Účel:

- rychlé procházení fotek přes klávesnici
- přiřazování tagů
- označování favorite/reject
- hromadné opravy datumu nad výběrem, eventem nebo sérií fotek

Prvky obrazovky:

- velký preview panel
- pravý sidebar s metadaty a aktivními tagy
- panel rychlých zkratek
- log posledních akcí
- panel pro datum s možností `nastavit`, `posunout`, `změnit časovou zónu`, `vrátit původní`

Doporučené zkratky pro MVP:

- `1` = `kvalita:top`
- `2` = `tema:rodina`
- `3` = `obsah:dite`
- `4` = `obsah:priroda`
- `5` = `obsah:jidlo`
- `6` = `tema:vylety`
- `7` = `kvalita:tisk`
- `8` = `stav:archiv`
- `9` = `stav:mazat`
- `0` = `stav:rozmazane`
- `F` = favorite
- `X` = reject
- `Space` nebo `Right` = další fotka
- `Left` = předchozí fotka
- `U` = undo

## 3. Alba

Účel:

- ruční tvorba statických alb
- návrh smart alb podle pravidel
- pozdější export výběrů

Prvky obrazovky:

- seznam alb vlevo
- detail vybraného alba vpravo
- ukázka pravidel pro smart album
- tlačítka `Nové statické album`, `Nové smart album`, `Export`

## 4. Hromadné opravy data pořízení

MVP by měl umět tyto základní operace:

- nastavit pevné datum/čas pro aktuální výběr
- posunout datum o `+/-` minuty, hodiny nebo dny
- opravit jen časovou zónu
- vrátit asset nebo výběr na původní EXIF hodnotu

Důležité chování:

- EXIF originál se nepřepisuje automaticky
- aplikace pracuje s efektivním datem v katalogu
- hromadná oprava se má propsat do filtrování, eventů i smart alb
- batch operace musí být auditovatelná kvůli pozdějšímu undo

## Poznámka k první implementaci

První GUI může fungovat i bez skutečných fotek. Důležité je uzavřít:

- navigaci mezi obrazovkami
- klávesové workflow
- inicializaci katalogu
- datový model a repository vrstvu
- efektivní model datumu pořízení a korekcí

Až potom má smysl přidávat scan disků, miniatury a EXIF parser.
