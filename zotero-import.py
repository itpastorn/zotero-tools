"""zotero-import.py – steg 5: skapa Zotero-poster ur analyzerns loggar.

DEL 2 AV FLERA. Skriptet läser och matchar, men skriver ännu ingenting:
det visar vad som skulle hända med varje kandidat.

Tre utfall per kandidat:
  NY POST     inget liknande finns – en post skulle skapas
  TRÄFF       posten finns redan – bara filen skulle bifogas
  TVETYDIGT   flera möjliga kopplingar – hoppas över, kräver handpåläggning

Kör:  python zotero-import.py            (tio kandidater)
      python zotero-import.py --antal 3  (tre)
      python zotero-import.py --antal 9999  (alla som finns)
"""

import argparse
import re
from collections import defaultdict
from itertools import islice

from zoterolib import attachment_names, fetch
from arkivlib import ARCHIVE, archive_files, citable_entries, read_ignore

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--antal",
    type=int,
    default=10,
    help="hur många kandidater som behandlas (standard: 10)",
)
args = parser.parse_args()


# --- Normalisering --------------------------------------------------------
# Jämförelser måste tåla skillnader i skiftläge, skiljetecken och mellanslag.
# "God's Empowering Presence" och "Gods empowering presence" är samma titel.


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
    first = (author or "").split(";")[0]
    return norm(first.split(",")[0])


def zotero_surnames(item):
    """Efternamnen på en Zotero-posts författare. Enfältsnamn räknas som ett."""
    names = set()
    for creator in item.get("creators") or []:
        names.add(norm(creator.get("lastName") or creator.get("name")))
    return names - {""}


# --- Hämta läget i Zotero -------------------------------------------------

items = [i["data"] for i in fetch("items")]
attachments = [d for d in items if d.get("itemType") == "attachment"]
known = attachment_names(attachments)

# Toppnivåposter: allt som inte är bilaga, anteckning eller annotering.
tops = [
    d
    for d in items
    if d.get("itemType") not in ("attachment", "note", "annotation")
]

# Två uppslagsregister. defaultdict(list) ger en tom lista för okända nycklar,
# så att vi slipper kontrollera om nyckeln finns innan vi lägger till.
by_isbn = defaultdict(list)
by_title = defaultdict(list)
for d in tops:
    for i in norm_isbn(d.get("ISBN")):
        by_isbn[i].append(d)
    if d.get("title"):
        by_title[norm(d["title"])].append(d)


def match(analysis):
    """Letar befintlig post. Returnerar (lista av träffar, hur de hittades)."""
    # Steg 2: ISBN. Starkast signal – ett ISBN identifierar en utgåva.
    for isbn in norm_isbn(analysis.get("isbn")):
        if by_isbn[isbn]:
            return by_isbn[isbn], f"ISBN {isbn}"

    # Steg 3: titel plus efternamn. Året används inte: samma verk har olika
    # år i olika utgåvor, och det gav tio felaktiga missar i mätningen.
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

# Steg 1 i matchningen: filnamnet. Kandidater vars fil redan har en bilaga
# i Zotero sorteras bort direkt och kommer aldrig in i kön.
queue = sorted(n for n in candidates if n in archive and n not in known)

# Vilka kandidater pekar på samma befintliga post? Måste räknas ut över hela
# kön, inte bara den visade satsen, annars beror svaret på --antal.
claims = defaultdict(list)
for name in queue:
    hits, _ = match(candidates[name])
    for d in hits:
        claims[d["key"]].append(name)


def classify(name):
    """Utfallet för en kandidat: (etikett, förklaring, träffad post)."""
    hits, how = match(candidates[name])
    if not hits:
        return "NY POST", how, None
    if len(hits) > 1:
        return "TVETYDIGT", f"{how} matchar {len(hits)} poster", None
    item = hits[0]
    if len(claims[item["key"]]) > 1:
        others = [n for n in claims[item["key"]] if n != name]
        return "TVETYDIGT", f"samma post som {', '.join(others)}", item
    return "TRÄFF", how, item


# --- Utdata ---------------------------------------------------------------

print(f"Kandidater totalt: {len(queue)}")
print(f"Visar: {min(args.antal, len(queue))}\n")

for number, name in enumerate(islice(queue, args.antal), start=1):
    analysis = candidates[name]
    label, how, item = classify(name)

    print(f"{number}. {name}")
    print(f"   {label:10} {how}")
    if label == "NY POST":
        print(f"   skapas som: {analysis.get('type')} / {analysis.get('year')}")
        print(f"   titel:      {analysis.get('title')}")
        print(f"   författare: {analysis.get('author')}")
    elif item is not None:
        print(f"   befintlig:  {item.get('title')}  [{item['key']}]")
        # Året är ingen matchningsregel men värt att se: skiljer det sig är
        # det oftast två utgåvor av samma verk, ibland två olika verk.
        theirs = re.search(r"\d{4}", str(item.get("date") or ""))
        ours = str(analysis.get("year") or "")
        if theirs and ours and theirs.group(0) != ours:
            print(f"   OBS årtal:  analyzern {ours}, Zotero {theirs.group(0)}")
    print(f"   plats:      {archive[name].parent.relative_to(ARCHIVE)}")
    print()

# Summering över hela kön, så att den inte ändras av --antal.
totals = defaultdict(int)
for name in queue:
    totals[classify(name)[0]] += 1

print("Hela kön:")
for label in ("NY POST", "TRÄFF", "TVETYDIGT"):
    print(f"  {label:10} {totals[label]:4}")

remaining = len(queue) - args.antal
print(f"\nÅterstår efter dessa: {remaining}" if remaining > 0 else "\nDet var alla.")
