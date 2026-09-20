"""zotero-patch-test.py – steg 4b: ändra sökvägen på en befintlig länk.

Hittar testpostens linked_file-bilaga i samlingen zotero-tools-test och
byter dess path mellan två arkivfiler. Varje körning med --apply växlar,
så skriptet kan köras hur många gånger som helst.

Det är precis det zotero-repair.py ska göra när sort-books flyttat en fil.

Kör:  python zotero-patch-test.py
      python zotero-patch-test.py --apply
"""

import argparse

from zoterolib import fetch, send
from arkivlib import ARCHIVE

COLLECTION_NAME = "zotero-tools-test"

# Två filer som båda finns. Skriptet byter till den som inte används nu.
PATH_A = ("karismatik-helande/pingstkarismatisk-historia-uppsatser-bocker/"
          "alexander-estrelda-the-women-of-azusa-street.pdf")
PATH_B = ("studier/dogmatik-systematisk-teologi-fundamentalteologi/"
          "aquinas-thomas-summa-theologica.pdf")

parser = argparse.ArgumentParser(description="Byter sökväg på testbilagan.")
parser.add_argument("--apply", action="store_true", help="skriv på riktigt")
args = parser.parse_args()

# --- Hitta bilagan ----------------------------------------------------------

collections = [c["data"] for c in fetch("collections")]
matches = [c for c in collections if c["name"] == COLLECTION_NAME]
if len(matches) != 1:
    raise SystemExit(f"Hittar inte exakt en samling som heter {COLLECTION_NAME}.")

top = fetch(f"collections/{matches[0]['key']}/items/top")
if len(top) != 1:
    raise SystemExit(f"Väntade exakt en post i {COLLECTION_NAME}, hittade {len(top)}.")
parent_key = top[0]["key"]

children = [c["data"] for c in fetch(f"items/{parent_key}/children")]
linked = [c for c in children if c.get("linkMode") == "linked_file"]
if len(linked) != 1:
    raise SystemExit(f"Väntade exakt en linked_file, hittade {len(linked)}.")
attachment = linked[0]

# --- Vad som ska ändras -----------------------------------------------------

old_path = attachment["path"]
new_relative = PATH_B if old_path == "attachments:" + PATH_A else PATH_A
if not (ARCHIVE / new_relative).exists():
    raise SystemExit(f"Filen finns inte: {ARCHIVE / new_relative}")
new_path = "attachments:" + new_relative

print(f"Bilaga:  {attachment['key']} (version {attachment['version']})")
print(f"Nu:      {old_path}")
print(f"Blir:    {new_path}")

if not args.apply:
    print("\nDry run. Inget skickat. Kör med --apply för att skriva.")
    raise SystemExit

# --- Skrivning --------------------------------------------------------------

# PATCH skickar bara fälten som ändras. Versionen talar om vilken version vi
# utgick från; har posten ändrats sedan dess vägrar Zotero (412).
send("PATCH", f"items/{attachment['key']}", {"path": new_path},
     version=attachment["version"])

saved = fetch(f"items/{attachment['key']}")["data"]
print("\nSå här ser bilagan ut nu:")
print(f"  path     {saved['path']}")
print(f"  version  {saved['version']}")
print(f"  titel    {saved['title']}")
