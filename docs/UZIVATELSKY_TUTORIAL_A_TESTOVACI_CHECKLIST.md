# Photos Tagger: Uvodni Guide + Testovaci Checklist

Tento dokument je prakticky navod pro prvni pouziti aplikace a zaroven checklist, co otestovat po kazde zmene.

## 1. Co aplikace umi (aktualni verze)

- Pridat zdrojovou slozku (koren) a rekurzivne ji naskenovat.
- Prochazet assety (fotky/videa) po slozkach.
- Tagovat:
  - jednotlive fotky,
  - cele slozky,
  - slozku vcetne podslozek.
- Pracovat s rychlymi tagy:
  - klasicky pres mapovani 1..0,
  - pres `Ctrl+pismeno` podle `tagy.txt`,
  - cisla `1..0` jako podkategorie k aktivnimu pismenu,
  - specialni 1-klavesove zkratky z `tagy.txt` (napr. `;`, `\`).
- Automaticky vytvaret datum tagy z metadata:
  - `rok:YYYY`
  - `mesic:YYYY-MM`
- Hromadne datum tagy rucne prepsat (Trideni i Alba) a vratit zpet do rezimu Auto.
- Filtrovat v sekci `Alba` podle efektivnich tagu a prochazet vysledky jako miniatury.
- Otevrit detail fotky, fullscreen a slideshow.
- Ve fullscreen rezimu zobrazit `?` overlay s aktualnimi tagy.

## 2. Prvni spusteni (5 minut)

1. Spust `start.bat`.
2. Pockej na vytvoreni runtime prostredi (pri prvnim spusteni).
3. Otevri zalozku `Katalog`.
4. Klikni `Pridat slozku` a vyber koren (napr. `D:\Foto\2025`).
5. Klikni `Spustit scan`.

Ocekavany vysledek:
- V `Katalogu` uvidis zdroj.
- V panelu struktury slozek uvidis i podslozky (rekurzivni scan).
- V poctech se zvysi `folders` a `assets`.
- U fotek se po importu automaticky doplni datum tagy (`rok:*`, `mesic:*`), pokud je k dispozici datum.

## 3. Rychly tutorial workflow

## 3.1 Katalog -> nacteni zdroje

Pouzivej vzdy logicky koren, ne jednotlive male podslozky:
- dobre: `2025`
- mene vhodne: jednotlive event slozky po jedne

Pro scenar "Rok -> Eventy":
1. Pridej zdroj `2025`.
2. Scan.
3. Over strom slozek.

## 3.2 Trideni -> hromadne tagovani slozky

1. Otevri zalozku `Trideni`.
2. Vyber zdroj a slozku.
3. Klikni `Tagovat slozku`.
4. Vypln tagy (radek = 1 tag).
5. Pokud chces aplikovat i na podstrom, zapni `Aplikovat i na vsechny podslozky`.

Priklad:
- ve slozce `2025` nastav tag `projekt:2025`
- ve slozce `2025/Dovolena Italie` nastav `tema:dovolena`

## 3.3 Trideni -> datum tagy (rok/mesic)

1. V `Trideni` vyber slozku.
2. Klikni `Datum tagy (rok/mesic)`.
3. Vyber rezim:
   - `Auto z metadata`
   - `Manualne nastavit rok i mesic`
   - `Manualne nastavit jen rok`
4. Volitelne zapni `Aplikovat i na podslozky`.
5. Potvrd `OK`.

Poznamka:
- `Auto` cte datum z metadata (`captured_at`) a udrzuje `rok:*`/`mesic:*`.
- `Manual` tento automat pro vybrane fotky prebije.

## 3.4 Trideni -> individualni tagovani fotek

1. Vyber konkretni fotku.
2. Taguj pres:
   - `Ctrl+pismeno` podle `tagy.txt` (hlavni tag),
   - `1..0` jako podkategorie pro naposledy aktivni pismeno.
3. Pro orientaci sleduj:
   - panel `Prime tagy`,
   - panel `Efektivni tagy`,
   - `Posledni akce`.

Dalsi ovladani:
- `F` favorite on/off
- `X` reject on/off
- `U` undo posledni akce
- `Left/Right/Space` navigace
- `F11` fullscreen preview
- `?` ve fullscreen: zobrazit/skryt aktualni prime tagy v pravem dolnim rohu

## 3.5 Alba -> filtr, miniatury, prohlizeni

1. Otevri `Alba`.
2. Vyber jeden nebo vice tagu.
3. Zvol rezim:
   - `AND`: fotka musi mit vsechny vybrane tagy
   - `OR`: staci libovolny z vybranych
4. Dvojklik na miniaturu otevre detail.
5. V detailu:
   - `Prizpusobit` / `1:1`
   - `Fullscreen`
   - `Start prezentace` (slideshow)
   - metadata + prime/efektivni tagy
   - tagovani i v detailu (Ctrl+pismeno, `1..0`, specialni klavesy dle `tagy.txt`)
   - `?` pro overlay aktualnich tagu
   - panel `Akce` s `Favorite/Reject` uz zde neni (nahrazeno tagovanim)

## 3.6 Alba -> hromadna zmena datum tagu na vyfiltrovanem vyberu

1. Nech si zobrazit cilovy vyber pomoci filtru.
2. Klikni `Datum tagy pro vyfiltrovane`.
3. Vyber rezim Auto nebo Manual.
4. Potvrd.

Toto je nejrychlejsi cesta, jak prepnout velkou sadu fotek mezi:
- automatickym odvozovanim roku/mesice z metadata,
- manualnim prepisem roku/mesice.

## 4. Jak pripravit tagy.txt

Soubor je v rootu projektu: `tagy.txt`.

Zakladni format:
- `A - Adelka`
- `R - Rodina`
- `T - Traveling`

Volitelne mapovani podkategorii:
- `A1 - Adelka:portret`
- `A2 - Adelka:akce`
- `R1 - Rodina:vyber`
- `T1 - Traveling:top`

Specialni klavesy (jedna klavesa bez Ctrl):
- `; - Vyber (prezentace)`
- `\ - Top foto`

Poznamky:
- Kdyz podkategorie (`A1`) neni definovana, app pouzije fallback `HlavniTag:cislo` (napr. `Rodina:1`).
- Specialni klavesy se pouzivaji hlavne v `Alba` detail/fullscreen pro rychle oznacovani.
- Prazdne nebo neplatne radky se ignoruji.

## 5. Co otestovat po kazde zmene (smoke test)

## 5.1 Katalog

1. Pridat novy zdroj.
2. Spustit scan.
3. Overit, ze se nactou i podslozky.
4. Overit pocty (`sources/folders/assets`).
5. U nahodne fotky overit, ze se objevily datum tagy `rok:*` a `mesic:*` (pokud ma datum).

## 5.2 Trideni

1. Vybrat slozku a fotku.
2. `Tagovat slozku` bez podslozek.
3. `Tagovat slozku` s podslozkami.
4. `Ctrl+pismeno` z `tagy.txt` -> tag se prepina.
5. `1..0` po aktivaci pismene -> vznikne podkategorie.
6. `F`, `X`, `U` funguje.
7. `F11` fullscreen funguje.
8. Ve fullscreen:
   - `Left/Right/Space` prepina fotky,
   - tagovani funguje,
   - `?` prepina overlay aktualnich tagu.
9. `Datum tagy (rok/mesic)`:
   - Auto rezim,
   - Manual rok+mesic,
   - Manual jen rok,
   - aplikace s podslozkami.

## 5.3 Alba

1. Filtrovani AND/OR vraci ocekavany pocet.
2. Miniatury se zobrazi.
3. Dvojklik otevre detail.
4. Detail: navigace, fullscreen, slideshow.
5. Detail: metadata + prime/efektivni tagy odpovidaji stavu.
6. Detail: `;` a `\` (nebo jine specialni klavesy z `tagy.txt`) prida/odebere odpovidajici tag.
7. Detail: `?` zobrazi/skryje overlay tagu.
8. Tlacitko `Datum tagy pro vyfiltrovane`:
   - prepnout vyber na Manual,
   - vratit vyber na Auto,
   - overit propis do filtru a tag listu.

## 5.4 Auto vs. Manual datum tagy

1. Vyber testovaci sadu fotek.
2. Nastav Manual rok/mesic.
3. Udelej zmenu data fotek (date correction), nebo reimport zdroje.
4. Over:
   - fotky v Manual zustanou na manualni hodnote,
   - fotky v Auto se prepocitaji z aktualniho metadata data.

## 6. Doporuceny hlubsi test pred vydanim

1. Otestovat na male sade (100-300 fotek) a vetsi sade (2000+).
2. Otestovat ruzne struktury slozek (hluboke vs. ploche).
3. Otestovat ruzne formaty (JPG/PNG/HEIC pokud jsou k dispozici).
4. Otestovat zmenu `tagy.txt` za behu:
   - uprava souboru,
   - klik `Obnovit tagy.txt`,
   - overit nove mapovani.
5. Otestovat datum tagy na fotkach bez EXIF data (fallback na filesystem / nebo bez tagu).

## 7. Co hlasit jako bug

U kazde chyby uloz:
- kde to spadlo (`Katalog/Trideni/Alba`)
- co jsi presne zmacknul (kroky)
- ocekavane vs. realne chovani
- jestli jde chybu zopakovat
- screenshot (pokud jde)

Tohle vyrazne zrychli opravu.

## 8. Jak se vytvari databaze (DB)

Databaze se pripravuje automaticky pri startu aplikace:

1. Spustis `start.bat`.
2. Aplikace nacte `database/schema.sql`.
3. SQL prikazy `CREATE TABLE IF NOT EXISTS` vytvori tabulky, ktere chybi.
4. Pri dalsim startu se schema jen zkontroluje (existujici tabulky zustanou).

Kam se DB uklada:
- Windows standardne: `%LOCALAPPDATA%\\PhotosTagger\\catalog.sqlite3`
- Ve stejne slozce mohou byt i soubory `catalog.sqlite3-wal` a `catalog.sqlite3-shm` (WAL rezim SQLite).

Co se do DB uklada:
- katalog zdroju/slozek/fotek,
- metadata, tagy, vazby tagu,
- datum korekce a dalsi provozni data.

Co se do DB neuklada:
- samotne obrazky a videa (zustavaji na tvem disku ve zdrojovych slozkach).

Prakticky dopad na velikost:
- DB roste hlavne podle poctu assetu a metadat, ne podle velikosti fotek v GB/TB.
- Knihovna o velikosti 4 TB fotek je bezna, pokud je DB i zdrojove disky na spolehlivem ulozisti.
