# Photos Tagger

Offline desktop aplikace pro rychle trideni fotek pomoci tagu, klavesovych zkratek a smart alb.

## Cil projektu

Projekt je navrzeny jako osobni katalog nad existujicimi soubory na disku.

Hlavni principy:

- originalni soubory zustavaji na miste
- metadata se ctou automaticky z fotek
- tagy a alba se ukladaji primarne do lokalni SQLite databaze
- hromadne tagovani funguje na urovni slozek, eventu i jednotlivych fotek
- chytra alba se skladaji nad tagy, datem, mistem a hodnocenim

## Aktualni stav

Tato kostra obsahuje:

- navrhovy dokument produktu
- SQL schema pro lokalni katalog
- dokumentaci k MVP obrazovkam
- minimalni PySide6 skeleton aplikace
- inicializaci SQLite databaze v `%LOCALAPPDATA%\PhotosTagger`

## Struktura projektu

- `NAVRH_FOTO_TRIDENI.md`
- `docs/SQLITE_SCHEMA.md`
- `docs/MVP_OBRAZOVKY.md`
- `database/schema.sql`
- `src/photos_tagger/`
- `requirements.txt`
- `start.bat`

## Spusteni

Nejjednodussi varianta je spustit `start.bat`.

Co udela automaticky:

- najde `python` nebo `py -3`
- vytvori virtualni prostredi mimo projekt v `%LOCALAPPDATA%\PhotosTagger\venv`
- doinstaluje zavislosti z `requirements.txt`, pokud chybi
- spusti aplikaci

Pri prvnim spusteni tedy staci:

```bat
start.bat
```

Pripadne muzes skript spustit i dvojklikem ve Windows Exploreru.

### Kde lezi runtime data

Projektova slozka v `PycharmProjects` zustava mala. Runtime veci se ukladaji mimo projekt sem:

- virtualni prostredi: `%LOCALAPPDATA%\PhotosTagger\venv`
- SQLite databaze a cache: `%LOCALAPPDATA%\PhotosTagger`

### Rucni fallback

Pokud by automaticky start selhal, muzes projekt pripravit rucne:

```powershell
cd "C:\Users\Tomas.Balak\PycharmProjects\photos_tagger"
python -m venv "$env:LOCALAPPDATA\PhotosTagger\venv"
& "$env:LOCALAPPDATA\PhotosTagger\venv\Scripts\python.exe" -m pip install -r requirements.txt
.\start.bat
```

## Co je zatim zamerne jen skeleton

- skutecna indexace souboru
- generovani nahledu
- cteni EXIF a GPS
- zapis tagu a alb z GUI do databaze
- engine pro vyhodnoceni smart alb

## Doporucene dalsi kroky

1. doplnit repository vrstvu nad SQLite
2. pridat import zdrojovych slozek a scan adresaru
3. nacist EXIF datum a GPS do `asset_metadata`
4. napojit shortcut workflow na skutecne tagovani assetu
5. doplnit smart album query builder
