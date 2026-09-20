"""zotero-write-test.py – steg 4a: första skrivningen till Zotero.

Skapar EN testpost (bok) i samlingen zotero-tools-test, med en länkad bilaga
(linkMode linked_file) till en fil i arkivet. Läser sedan tillbaka bilagan
och visar hur Zotero sparade sökvägen.

Utan flagga: visar bara vad som skulle skickas (dry run).
Med --apply: skickar på riktigt.

Kör:  python zotero-write-test.py
      python zotero-write-test.py --apply
"""

import argparse
import json

from zoterolib import ARCHIVE, fetch, send

COLLECTION_NAME = "zotero-tools-test"

# En importkandidat som säkert finns. Snedstreck framåt, som Zotero sparar dem.
RELATIVE = ("karismatik-helande/pingstkarismatisk-historia-uppsatser-bocker/"
            "alexander-estrelda-the-women-of-azusa-street.pdf")

# argparse läser flaggor från kommandoraden. action="store_true" betyder att
# args.apply blir True om --apply finns med, annars False.
parser = argparse.ArgumentParser(description="Skapar en testpost i Zotero.")
parser.add_argument("--apply", action="store_true", help="skriv på riktigt")
args = parser.parse_args()

# --- Kontroller innan något byggs -----------------------------------------

collections = [c["data"] for c in fetch("collections")]
matches = [c for c in collections if c["name"] == COLLECTION_NAME]
if len(matches) != 1:
    raise SystemExit(f"Hittar inte exakt en samling som heter {COLLECTION_NAME}.")
collection = matches[0]["key"]

# Samlingen ska vara tom, så att en andra körning inte skapar en dubblett.
existing = fetch(f"collections/{collection}/items/top")
if existing:
    raise SystemExit(f"{COLLECTION_NAME} innehåller redan {len(existing)} post(er). "
                     "Radera dem i Zotero först.")

if not (ARCHIVE / RELATIVE).exists():
    raise SystemExit(f"Filen finns inte: {ARCHIVE / RELATIVE}")

# --- Vad som ska skickas --------------------------------------------------

parent = {
    "itemType": "book",
    "title": "zotero-tools testpost",
    "collections": [collection],
    "tags": [{"tag": "okontrollerad"}],
}

# parentItem fylls i när föräldern har skapats och fått en nyckel.
attachment = {
    "itemType": "attachment",
    "linkMode": "linked_file",
    "parentItem": None,
    "title": "PDF",
    "path": "attachments:" + RELATIVE,
    "contentType": "application/pdf",
}

print(f"Samling: {COLLECTION_NAME} ({collection})")
print("\nFörälder:")
print(json.dumps(parent, indent=2, ensure_ascii=False))
print("\nBilaga:")
print(json.dumps(attachment, indent=2, ensure_ascii=False))

if not args.apply:
    print("\nDry run. Inget skickat. Kör med --apply för att skriva.")
    raise SystemExit

# --- Skrivning ------------------------------------------------------------

# POST tar alltid en lista, även med en enda post. Svaret har "successful"
# (nycklar "0", "1", … i samma ordning som listan) och "failed".
answer = send("POST", "items", [parent])
if answer["failed"]:
    raise SystemExit(f"Föräldern misslyckades: {answer['failed']}")
parent_key = answer["successful"]["0"]["key"]
print(f"\nFörälder skapad: {parent_key}")

attachment["parentItem"] = parent_key
answer = send("POST", "items", [attachment])
if answer["failed"]:
    raise SystemExit(f"Bilagan misslyckades: {answer['failed']}")
attachment_key = answer["successful"]["0"]["key"]
print(f"Bilaga skapad: {attachment_key}")

# Läs tillbaka från Zotero i stället för att lita på det vi skickade.
saved = fetch(f"items/{attachment_key}")["data"]
print("\nSå här sparade Zotero bilagan:")
for field in ("linkMode", "path", "parentItem", "contentType", "version"):
    print(f"  {field:12} {saved.get(field)}")
