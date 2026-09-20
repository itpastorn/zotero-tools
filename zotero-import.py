"""zotero-import.py – steg 5: skapa Zotero-poster ur analyzerns loggar.

DEL 3 AV FLERA. Skriptet läser, matchar och bygger de JSON-poster som
skulle skickas – men skriver fortfarande ingenting till Zotero.

Tre utfall per kandidat:
  NY POST     inget liknande finns – förälder + bilaga skulle skapas
  TRÄFF       posten finns redan – bara bilagan skulle skapas
  TVETYDIGT   flera möjliga kopplingar – hoppas över, kräver handpåläggning

Kör:  python zotero-import.py            (tio kandidater)
      python zotero-import.py --antal 3  (tre)
      python zotero-import.py --antal 9999  (alla som finns)
      python zotero-import.py --json     (visa hela JSON-posten)
"""

import argparse
import json
import re
from collections import defaultdict
from itertools import islice

from zoterolib import attachment_names, fetch, item_type_fields
from arkivlib import ARCHIVE, archive_files, citable_entries, read_ignore

# Samlingen skapas av Lars i Zotero, inte av skriptet. Saknas den avbryts
# körningen – hellre det än att posterna hamnar på okänd plats.
COLLECTION_NAME = "Automated-imports"

# Taggen sitter på varje NY post. Metadatan är LLM-extraherad ur dokumentets
# första 6 000 tecken och kan vara fel. Lars tar bort taggen efter granskning.
REVIEW_TAG = "okontrollerad"

# analyzerns typ → Zoteros itemType
TYPE_MAP = {
    "bok": "book",
    "artikel": "journalArticle",
    "uppsats": "thesis",
    "studie": "report",
}

# Fält som alla fyra typerna delar: analyzerns namn → Zoteros namn.
COMMON_FIELDS = {
    "summary": "abstractNote",
    "isbn": "ISBN",
    "publisher_place": "place",
}

# Fält som bara gäller vissa typer. Sidantalet heter olika saker beroende på
# om verket har egna sidor (numPages) eller sidor i något större (pages).
TYPE_FIELDS = {
    "book": {"publisher": "publisher", "edition": "edition", "pages_total": "numPages"},
    "journalArticle": {"publication": "publicationTitle", "pages_total": "pages"},
    "thesis": {
        "institution": "university",
        "thesis_type": "thesisType",
        "institution_place": "place",
        "pages_total": "numPages",
    },
    "report": {
        "institution": "institution",
        "institution_place": "place",
        "pages_total": "pages",
    },
}

# Ord som avslöjar att ett "Efternamn, Förnamn" i själva verket är en
# organisation. Då ska namnet inte splittas i två fält.
ORG_WORDS = (
    "university", "church", "assemblies", "society", "institute", "press",
    "department", "ministries", "council", "commission", "school", "seminary",
    "college", "board", "conference", "association", "foundation",
)

CONTENT_TYPES = {".pdf": "application/pdf", ".epub": "application/epub+zip"}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--antal", type=int, default=10,
                    help="hur många kandidater som behandlas (standard: 10)")
parser.add_argument("--json", action="store_true",
                    help="visa hela JSON-posten som skulle skickas")
args = parser.parse_args()


# --- Normalisering --------------------------------------------------------


def norm(text):
    """Gemener utan skiljetecken. \\w behåller å, ä, ö – det gör inte a-z."""
    return re.sub(r"[\W_]+", "", (text or ""), flags=re.UNICODE).lower()


def norm_isbn(text):
    """Alla ISBN i en sträng, som siffror (och X) utan bindestreck."""
    found = set()
    for part in re.split(r"[;,\s]+", (text or "")):
        digits = re.sub(r"[^0-9Xx]", "", part).upper()
        if len(digits) in (10, 13):
            found.add(digits)
    return found


def surname(author):
    """Första författarens efternamn ur "Efternamn, Förnamn; Efternamn, …"."""
    return norm((author or "").split(";")[0].split(",")[0])


def zotero_surnames(item):
    """Efternamnen på en Zotero-posts författare. Enfältsnamn räknas som ett."""
    names = {norm(c.get("lastName") or c.get("name"))
             for c in item.get("creators") or []}
    return names - {""}


# --- Zoteros eget schema --------------------------------------------------


# Fältschemat kommer från Zotero men cachas på disk av zoterolib – anropet
# tar omkring 20 sekunder per typ.
SCHEMA = {t: item_type_fields(t) for t in TYPE_MAP.values()}


# --- Bygg posterna --------------------------------------------------------

# Namn som blivit enfältsnamn. Skrivs ut till sist så att Lars kan rätta de
# som heuristiken tog fel på.
single_field_names = []


def creators(author, source):
    """Författarsträngen → Zoteros creators-lista.

    "Efternamn, Förnamn" blir två fält. Allt annat – ett enda namn, tre
    kommatecken, eller något som innehåller ett organisationsord – blir ett
    enfältsnamn, eftersom "Assemblies of God, General Presbytery" inte är
    ett förnamn och ett efternamn.
    """
    result = []
    for part in (author or "").split(";"):
        part = part.strip()
        if not part:
            continue
        looks_organisational = any(w in part.lower() for w in ORG_WORDS)
        if part.count(",") == 1 and not looks_organisational:
            last, first = (x.strip() for x in part.split(","))
            if last and first:
                result.append({"creatorType": "author",
                               "firstName": first, "lastName": last})
                continue
        result.append({"creatorType": "author", "name": part})
        single_field_names.append((part, source))
    return result


def build_parent(name, analysis, collection):
    """JSON-posten för själva verket (föräldern till bilagan)."""
    item_type = TYPE_MAP[analysis.get("type")]
    item = {
        "itemType": item_type,
        "title": analysis.get("title") or name,
        "creators": creators(analysis.get("author"), name),
        "collections": [collection],
        "tags": [{"tag": REVIEW_TAG}],
    }

    # date_full är mer exakt men finns bara på 18 %. year på 85 %. Saknas
    # båda utelämnas fältet – Zotero klarar en post utan datum.
    date = analysis.get("date_full") or analysis.get("year")
    if date:
        item["date"] = str(date)

    mapping = {**COMMON_FIELDS, **TYPE_FIELDS[item_type]}
    for ours, theirs in mapping.items():
        value = analysis.get(ours)
        if not value:
            continue
        if theirs not in SCHEMA[item_type]:
            # Fältet passar inte den här typen. Att tappa det är rätt – ett
            # ISBN på en tidskriftsartikel hör ingenstans hemma.
            continue
        item[theirs] = str(value)
    return item


def build_attachment(name, parent_key):
    """JSON-posten för den länkade bilagan.

    Sökvägen är relativ mot Linked Attachment Base Directory (arkivroten)
    och skrivs med snedstreck framåt, precis som Zotero sparar den.
    """
    relative = archive[name].relative_to(ARCHIVE).as_posix()
    suffix = archive[name].suffix.lower()
    return {
        "itemType": "attachment",
        "linkMode": "linked_file",
        "parentItem": parent_key,
        "title": suffix.lstrip(".").upper(),
        "path": "attachments:" + relative,
        "contentType": CONTENT_TYPES.get(suffix, ""),
    }


# --- Hämta läget i Zotero -------------------------------------------------

collections = [c["data"] for c in fetch("collections")]
matches = [c for c in collections if c["name"] == COLLECTION_NAME]
if len(matches) != 1:
    raise SystemExit(
        f"Hittar inte exakt en samling som heter {COLLECTION_NAME}. "
        "Skapa den i Zotero först – skriptet skapar den inte självt."
    )
COLLECTION = matches[0]["key"]

items = [i["data"] for i in fetch("items")]
attachments = [d for d in items if d.get("itemType") == "attachment"]
known = attachment_names(attachments)
tops = [d for d in items
        if d.get("itemType") not in ("attachment", "note", "annotation")]

by_isbn = defaultdict(list)
by_title = defaultdict(list)
for d in tops:
    for i in norm_isbn(d.get("ISBN")):
        by_isbn[i].append(d)
    if d.get("title"):
        by_title[norm(d["title"])].append(d)


def match(analysis):
    """Letar befintlig post. Returnerar (lista av träffar, hur de hittades)."""
    for isbn in norm_isbn(analysis.get("isbn")):
        if by_isbn[isbn]:
            return by_isbn[isbn], f"ISBN {isbn}"

    hits = by_title[norm(analysis.get("title"))]
    if hits:
        want = surname(analysis.get("author"))
        agreeing = [d for d in hits if want in zotero_surnames(d)]
        if agreeing:
            return agreeing, f"titel + {want}"
        return [], f"titel men fel författare ({want})"
    return [], ""


# --- Kandidaterna ---------------------------------------------------------

rules = read_ignore()
archive = archive_files(rules)
candidates = citable_entries(rules)

queue = sorted(n for n in candidates if n in archive and n not in known)

claims = defaultdict(list)
for name in queue:
    hits, _ = match(candidates[name])
    for d in hits:
        claims[d["key"]].append(name)


def classify(name):
    """Utfallet för en kandidat: (etikett, förklaring, träffad post)."""
    hits, how = match(candidates[name])
    if not hits:
        if candidates[name].get("type") not in TYPE_MAP:
            return "OKÄND TYP", candidates[name].get("type"), None
        return "NY POST", how, None
    if len(hits) > 1:
        return "TVETYDIGT", f"{how} matchar {len(hits)} poster", None
    item = hits[0]
    if len(claims[item["key"]]) > 1:
        others = [n for n in claims[item["key"]] if n != name]
        return "TVETYDIGT", f"samma post som {', '.join(others)}", item
    return "TRÄFF", how, item


# --- Utdata ---------------------------------------------------------------

print(f"Samling: {COLLECTION_NAME} ({COLLECTION})")
print(f"Kandidater totalt: {len(queue)}")
print(f"Visar: {min(args.antal, len(queue))}\n")

for number, name in enumerate(islice(queue, args.antal), start=1):
    analysis = candidates[name]
    label, how, item = classify(name)

    print(f"{number}. {name}")
    print(f"   {label:10} {how}")

    if label == "TVETYDIGT":
        print(f"   hoppas över, ingen ändring")
        print()
        continue

    if label == "NY POST":
        parent = build_parent(name, analysis, COLLECTION)
        attachment = build_attachment(name, "<föräldern>")
        if args.json:
            print(json.dumps(parent, indent=2, ensure_ascii=False))
            print(json.dumps(attachment, indent=2, ensure_ascii=False))
        else:
            print(f"   skapas som: {parent['itemType']}")
            print(f"   titel:      {parent['title']}")
            print(f"   författare: {[c.get('lastName') or c.get('name') for c in parent['creators']]}")
            # Sammanfattningen är flera hundra tecken och skulle dränka
            # resten. Hela texten syns med --json.
            skip = ("itemType", "title", "creators", "collections", "tags")
            extra = {}
            for key, value in parent.items():
                if key in skip:
                    continue
                extra[key] = value[:50] + "…" if len(value) > 50 else value
            print(f"   fält:       {extra}")
    elif item is not None:
        attachment = build_attachment(name, item["key"])
        print(f"   befintlig:  {item.get('title')}  [{item['key']}]")
        print(f"   åtgärd:     bara bilagan, posten rörs inte")
        if args.json:
            print(json.dumps(attachment, indent=2, ensure_ascii=False))
        theirs = re.search(r"\d{4}", str(item.get("date") or ""))
        ours = str(analysis.get("year") or "")
        if theirs and ours and theirs.group(0) != ours:
            print(f"   OBS årtal:  analyzern {ours}, Zotero {theirs.group(0)}")

    print(f"   bilaga:     attachments:{archive[name].relative_to(ARCHIVE).as_posix()}")
    print()

# Summering över hela kön, så att den inte ändras av --antal.
totals = defaultdict(int)
for name in queue:
    totals[classify(name)[0]] += 1

print("Hela kön:")
for label in ("NY POST", "TRÄFF", "TVETYDIGT", "OKÄND TYP"):
    if totals[label]:
        print(f"  {label:10} {totals[label]:4}")

# Granskningslistan: varje enfältsnamn heuristiken skapat i den visade satsen.
if single_field_names:
    print("\nEnfältsnamn att kontrollera (organisation eller feltolkning?):")
    for person, source in single_field_names:
        print(f"  {person!r}\n      ur {source}")

remaining = len(queue) - args.antal
print(f"\nÅterstår efter dessa: {remaining}" if remaining > 0 else "\nDet var alla.")
