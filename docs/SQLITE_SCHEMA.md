# SQLite Schema

Tento dokument shrnuje první verzi databázového modelu pro `Photos Tagger`.

## Hlavní entity

- `sources`
  - registrované kořenové adresáře s fotkami
- `folders`
  - indexované složky uvnitř zdrojů
- `events`
  - logické skupiny fotek podle času, místa nebo ruční editace
- `assets`
  - jednotlivé fotky a videa
  - obsahují `captured_at` jako efektivní datum, které aplikace používá pro řazení a filtry
  - obsahují `captured_at_source`, aby bylo jasné, odkud efektivní datum pochází
- `asset_metadata`
  - EXIF, původní datum pořízení, GPS, kamera, rozměry
- `places`
  - normalizované místo odvozené z GPS nebo ručního zásahu
- `date_correction_batches`
  - hlavičky hromadných nebo jednotlivých oprav data pořízení
- `asset_date_corrections`
  - audit a aktivní ruční korekce data na úrovni jednotlivých assetů
- `tags`
  - slovník tagů
- `tag_shortcuts`
  - mapování kláves na tagy
- `asset_tags`
  - přímé tagy assetu
- `folder_tags`
  - tagy aplikované na složku
- `event_tags`
  - tagy aplikované na event
- `albums`
  - statická, smart a event alba
- `album_items`
  - ručně přiřazené položky statických alb
- `album_rules`
  - JSON definice pravidel pro smart alba
- `thumbnails`
  - cache miniatur

## Efektivní tagy

Aplikace by při filtrování neměla pracovat jen s přímými tagy assetu.

Doporučený koncept je `effective tags`:

- přímé tagy z `asset_tags`
- zděděné tagy z `folder_tags`
- zděděné tagy z `event_tags`

To umožní rychlé hromadné tagování bez fyzického kopírování stejného tagu na tisíce fotek.

## Datum pořízení a korekce

Aplikace by měla rozlišovat tři vrstvy času:

1. `asset_metadata.taken_at_original`
   - syrová hodnota z EXIF nebo jiného metadatového zdroje
2. `assets.captured_at`
   - efektivní datum, se kterým aplikace opravdu pracuje
3. `asset_date_corrections`
   - audit a aktivní ruční korekce, které vysvětlují, proč se efektivní datum liší od originálu

`assets.captured_at_source` říká, odkud efektivní datum pochází:

- `exif`
- `filesystem`
- `manual`
- `derived`
- `unknown`

Díky tomu lze bezpečně řešit scénáře:

- špatně nastavený čas ve foťáku
- hromadný posun o několik hodin nebo dní
- opravu celé série z dovolené nebo jednoho eventu
- návrat zpět na původní EXIF datum

## Hromadné opravy datumu

Model je rozdělený na dvě vrstvy:

### `date_correction_batches`

Hlavička operace, která říká:

- jaký typ opravy proběhl: `set`, `shift`, `timezone`, `clear`
- na jaký scope byla aplikovaná: `asset`, `folder`, `event`, `selection`, `filter`
- s jakými parametry byla spuštěná

### `asset_date_corrections`

Jeden řádek na jeden ovlivněný asset.

Ukládá:

- předchozí efektivní datum
- nové efektivní datum
- předchozí a nový source
- mód opravy
- případný ruční timestamp nebo posun v minutách
- vazbu na batch
- `is_active`, aby bylo možné poznat aktuálně platnou korekci

Tohle je důležité pro:

- audit oprav
- pozdější undo
- rozlišení mezi původním EXIF a uživatelskou korekcí
- hromadné operace bez destrukce originálních metadat

## Smart alba

Smart album je definované JSON pravidlem uloženým v `album_rules.rule_json`.

Ukázka:

```json
{
  "operator": "and",
  "conditions": [
    {"field": "effective_tags", "op": "contains", "value": "tema:rodina"},
    {"field": "effective_tags", "op": "contains", "value": "kvalita:top"},
    {"field": "captured_at", "op": "between", "value": ["2025-01-01", "2025-12-31"]},
    {"field": "place.country_code", "op": "=", "value": "IT"},
    {"field": "effective_tags", "op": "not_contains", "value": "stav:mazat"}
  ]
}
```

## Poznámky k návrhu

- `assets` drží základní katalogizační stav i efektivní datum pro filtrování
- `asset_metadata` odděluje technická metadata od uživatelské vrstvy
- `places` je připravené pro offline reverse geocoding
- `events` jsou důležité pro seskupení výletů, dovolených a akcí
- `albums` rozlišují `static`, `smart` a `event`
- korekce data jsou uložené tak, aby byly auditovatelné a hromadně aplikovatelné

## Důležité indexy

V SQL schématu jsou připravené indexy hlavně pro:

- datum pořízení
- složku assetu
- event assetu
- vazby tag -> asset/folder/event
- typ alba
- batch a aktivní záznamy korekcí data

To je minimum pro rychlé filtrování v desktopové aplikaci bez serveru.
