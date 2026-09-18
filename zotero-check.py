"""zotero-check.py – steg 1: läsande diagnos av bilagor i Zotero.

Skriver ingenting till Zotero. Kräver Zotero 10 igång och inställningen
Settings → Advanced → "Allow other applications on this computer to
communicate with Zotero".

Kör:  python zotero-check.py
"""

import json
import urllib.request
from collections import Counter

# Användar-ID 0 betyder "den inloggade användaren" i det lokala API:et.
URL = "http://localhost:23119/api/users/0/items?itemType=attachment"


def fetch(url):
    """Hämtar en URL och returnerar svaret som Python-data (lista av dict)."""
    request = urllib.request.Request(url, headers={"Zotero-API-Version": "3"})
    with urllib.request.urlopen(request) as response:
        return json.load(response)


# Det lokala API:et paginerar inte: alla bilagor kommer i ett enda svar.
attachments = fetch(URL)
print(f"Antal bilagor: {len(attachments)}\n")

# Varje post har sina fält under nyckeln "data".
modes = Counter(item["data"].get("linkMode") for item in attachments)
print("Per linkMode:")
for mode, count in modes.most_common():
    print(f"  {mode:15} {count}")

# Hur ser sökvägarna ut? "attachments:…" = relativ mot Base Directory,
# "C:\…" = absolut.
linked = [a["data"] for a in attachments if a["data"].get("linkMode") == "linked_file"]
relative = [d for d in linked if (d.get("path") or "").startswith("attachments:")]
print(f"\nLänkade filer: {len(linked)}, varav relativa (attachments:): {len(relative)}")

# Länkar som pekar in i staging-mappen ska senare uppdateras.
staging = [d for d in linked if "books-to-" in (d.get("path") or "")]
print(f"Länkar in i books-to-fix/books-to-sort: {len(staging)}")

print("\nFem exempel på path:")
for d in linked[:5]:
    print(" ", d.get("path"))