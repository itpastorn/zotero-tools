"""zoterolib.py – gemensam kod för zotero-tools.

Allt som rör Zoteros lokala API samlas här, så att zotero-check.py,
zotero-import.py och zotero-repair.py inte har var sin kopia.

Används så här i ett annat skript i samma mapp:

    from zoterolib import fetch
    items = fetch("items?itemType=attachment")

Kör man filen direkt (python zoterolib.py) görs ett enkelt anslutningstest.
"""

import json
import urllib.request
from pathlib import Path

ROOT = "http://localhost:23119/api/"

# Användar-ID 0 betyder "den inloggade användaren" i det lokala API:et.
API = ROOT + "users/0/"

# ARCHIVE bodde här tidigare men hör hemma i arkivlib.py. En konstant ska
# vara definierad på ett enda ställe, annars hinner kopiorna gå isär.

# Nyckeln för skrivning. Ligger i hemkatalogen, utanför Dropbox och Git.
# Path.home() är C:\Users\gunther på Lars dator.
KEY_FILE = Path.home() / ".config" / "zotero-tools" / "api-key"

# Zoteros fältschema. Ändras bara när Zotero uppdateras, men anropet tar
# omkring 20 sekunder per itemType, så svaret sparas bredvid nyckeln.
# Radera filen för att hämta schemat på nytt efter en Zotero-uppdatering.
SCHEMA_FILE = KEY_FILE.parent / "itemtype-fields.json"


def fetch(path):
    """Hämtar path (relativ mot API) och returnerar svaret som Python-data."""
    request = urllib.request.Request(API + path, headers={"Zotero-API-Version": "3"})
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def attachment_names(attachments=None):
    """Filnamnen på alla bilagor som pekar på en fil, i gemener.

    Både länkade (linked_file, path) och lagrade (imported_file, filename).
    Används för att se om en arkivfil redan har en post i Zotero.

    Har anroparen redan hämtat bilagorna skickas de in, så att API:et inte
    behöver frågas två gånger.
    """
    if attachments is None:
        attachments = [a["data"] for a in fetch("items?itemType=attachment")]
    names = set()
    for d in attachments:
        if d.get("linkMode") == "linked_file":
            names.add(Path(d.get("path") or "").name.lower())
        elif d.get("linkMode") == "imported_file":
            names.add((d.get("filename") or "").lower())
    return names


def item_type_fields(item_type):
    """Fälten Zotero tillåter för en itemType, t.ex. {"title", "ISBN", …}.

    Att fråga Zotero är bättre än en egen lista i koden: schemat kan ändras
    mellan versioner, och ett ogiltigt fält märks annars först vid
    skrivningen. Men anropet är långsamt, så svaren sparas i SCHEMA_FILE.

    Ligger under /api/, inte under /api/users/0/, så fetch() passar inte.
    """
    cache = {}
    if SCHEMA_FILE.exists():
        cache = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    if item_type not in cache:
        url = ROOT + f"itemTypeFields?itemType={item_type}"
        request = urllib.request.Request(url, headers={"Zotero-API-Version": "3"})
        with urllib.request.urlopen(request) as response:
            cache[item_type] = [f["field"] for f in json.load(response)]
        SCHEMA_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCHEMA_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return set(cache[item_type])


def server_id():
    """Hämtar Zoteros Server-ID, som krävs vid all skrivning.

    ID:t står inte i svaret utan i ett svarshuvud (header). GET /api/ är det
    minsta anropet som finns: svaret är bara texten "Nothing to see here."
    """
    request = urllib.request.Request(ROOT, headers={"Zotero-API-Version": "3"})
    with urllib.request.urlopen(request) as response:
        return response.headers["Zotero-Server-ID"]


def authorize():
    """Ber Zotero om en ny nyckel. Zotero visar en dialog och väntar på svar.

    Returnerar Zoteros svar, t.ex. {"key": "…", "remember": True}.
    remember är True bara om Lars valde "Always Allow".
    """
    body = json.dumps({"appName": "zotero-tools"}).encode("utf-8")
    request = urllib.request.Request(
        ROOT + "local/authorize",
        data=body,  # att data finns gör anropet till en POST
        headers={
            "Zotero-API-Version": "3",
            "Zotero-Server-ID": server_id(),
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def api_key():
    """Returnerar nyckeln: från KEY_FILE om den finns, annars via authorize()."""
    if KEY_FILE.exists():
        return KEY_FILE.read_text(encoding="utf-8").strip()

    print("Ingen sparad nyckel. Svara på dialogen i Zotero (välj Always Allow).")
    answer = authorize()
    key = answer["key"]
    if answer.get("remember"):
        # parents=True skapar .config och zotero-tools om de saknas;
        # exist_ok=True gör att det inte är fel om de redan finns.
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(key, encoding="utf-8")
        print(f"Nyckeln sparad i {KEY_FILE}")
    else:
        print("Engångsnyckel (inte Always Allow). Den sparas inte.")
    return key


def send(method, path, data=None, version=None):
    """Skickar ett skrivanrop (POST, PUT, PATCH, DELETE) till path under API.

    data är Python-data som skickas som JSON. version behövs vid PATCH, PUT
    och DELETE: postens aktuella version, annars svarar Zotero 412.
    Returnerar svaret som Python-data, eller None om svaret är tomt
    (PATCH och DELETE svarar 204 No Content).
    """
    headers = {
        "Zotero-API-Version": "3",
        "Zotero-API-Key": api_key(),
        "Zotero-Server-ID": server_id(),
        "Content-Type": "application/json",
    }
    if version is not None:
        headers["If-Unmodified-Since-Version"] = str(version)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = urllib.request.Request(API + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request) as response:
        text = response.read()
    return json.loads(text) if text else None


# __name__ är "__main__" bara när filen körs direkt. När ett annat skript gör
# "from zoterolib import fetch" är __name__ "zoterolib", och blocket hoppas över.
if __name__ == "__main__":
    collections = fetch("collections")
    print(f"Anslutningen fungerar. Antal samlingar i Zotero: {len(collections)}")
    print(f"Server-ID: {server_id()}")
    key = api_key()
    # Visa bara början. Hela nyckeln ska inte hamna i utdata som klistras in.
    print(f"Nyckel: {key[:4]}… ({len(key)} tecken)")
