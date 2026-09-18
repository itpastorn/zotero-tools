"""zotero-check.py – steg 2: läsande diagnos av bilagor i Zotero.

Skriver ingenting till Zotero. Kräver Zotero 10 igång och inställningen
Settings → Advanced → "Allow other applications on this computer to
communicate with Zotero".

Kör:  python zotero-check.py
"""

import fnmatch
import json
import os
import urllib.request
from collections import Counter
from pathlib import Path

# Användar-ID 0 betyder "den inloggade användaren" i det lokala API:et.
URL = "http://localhost:23119/api/users/0/items?itemType=attachment"
ARCHIVE = Path(r"C:\Users\gunther\Dropbox\arkiv\larsArkiv\predikningar-studier")

# Dokumentformat som över huvud taget kan vara aktuella. Vilka av dem som
# faktiskt tas med styrs av zotero-import-ignore, inte av den här listan.
EXTENSIONS = {".pdf", ".epub", ".doc", ".docx", ".md"}

# Ignorefilen ligger bredvid skriptet. __file__ är sökvägen till denna fil.
IGNORE_FILE = Path(__file__).parent / "zotero-import-ignore"

# Analyzerns egen regel: is_citable sant, men dessa typer räknas ändå inte.
SKIP_TYPES = {"predikan", "övrigt"}


def fetch(url):
    """Hämtar en URL och returnerar svaret som Python-data (lista av dict)."""
    request = urllib.request.Request(url, headers={"Zotero-API-Version": "3"})
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def read_ignore(path):
    """Läser zotero-import-ignore och returnerar reglerna som en lista.

    Varje regel blir en tupel (mönster, bara_mappar, är_undantag).
    """
    rules = []
    if not path.exists():
        print(f"Varning: {path.name} saknas, inget filtreras bort.")
        return rules
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        dir_only = line.endswith("/")
        rules.append((line.strip("/"), dir_only, negated))
    return rules


def is_ignored(relative, is_dir, rules):
    """Sant om sökvägen (relativ mot arkivroten) ska ignoreras.

    Mönster utan snedstreck jämförs mot varje led i sökvägen, så att
    "analyzer/" träffar var som helst i trädet. Mönster med snedstreck
    jämförs mot hela sökvägen från arkivroten.

    Allt jämförs i gemener. Windows filsystem är skiftlägesokänsligt, och
    arkivet innehåller både "rapport.doc" och "RAPPORT.DOC". fnmatchcase
    sköter jokertecknen ("*.doc"); den egna gemeneringen gör jämförelsen
    skiftlägesokänslig utan att bero på vilket operativsystem som kör.
    """
    text = relative.as_posix().lower()
    ignored = False
    for pattern, dir_only, negated in rules:
        pattern = pattern.lower()
        if dir_only and not is_dir:
            continue
        if "/" in pattern:
            # Mappmönster täcker även allt som ligger under mappen.
            hit = fnmatch.fnmatchcase(text, pattern) or text.startswith(pattern + "/")
        else:
            hit = any(fnmatch.fnmatchcase(p.lower(), pattern) for p in relative.parts)
        # Sista träffande regeln avgör, precis som i .gitignore.
        if hit:
            ignored = not negated
    return ignored


def archive_files(rules):
    """Alla dokumentfiler i arkivet som zotero-import-ignore släpper igenom."""
    found = {}
    for root, dirs, files in os.walk(ARCHIVE):
        base = Path(root).relative_to(ARCHIVE)
        # Beskär listan på plats så att os.walk inte går ner i uteslutna mappar.
        dirs[:] = [d for d in dirs if not is_ignored(base / d, True, rules)]
        for name in files:
            if Path(name).suffix.lower() not in EXTENSIONS:
                continue
            if is_ignored(base / name, False, rules):
                continue
            found[name.lower()] = Path(root) / name
    return found


# --- Del 1: översikt ------------------------------------------------------

attachments = [a["data"] for a in fetch(URL)]
print(f"Antal bilagor: {len(attachments)}\n")

modes = Counter(d.get("linkMode") for d in attachments)
print("Per linkMode:")
for mode, count in modes.most_common():
    print(f"  {mode:15} {count}")

linked = [d for d in attachments if d.get("linkMode") == "linked_file"]
stored = [d for d in attachments if d.get("linkMode") == "imported_file"]
relative = [d for d in linked if (d.get("path") or "").startswith("attachments:")]
print(f"\nLänkade filer: {len(linked)}, varav relativa (attachments:): {len(relative)}")

# --- Del 2: trasiga länkar ------------------------------------------------

# Relativa sökvägar löses mot arkivroten; absoluta används som de är.
def resolve(path):
    if path.startswith("attachments:"):
        return ARCHIVE / path[len("attachments:"):]
    return Path(path)

broken = [d for d in linked if not resolve(d.get("path") or "").exists()]
print(f"\nTrasiga länkar: {len(broken)}")
for d in broken:
    print("  ", d.get("path"))

# --- Del 3: arkivfiler som Zotero inte känner till -------------------------

known = set()
for d in linked:
    known.add(Path(d.get("path") or "").name.lower())
for d in stored:
    known.add((d.get("filename") or "").lower())

rules = read_ignore(IGNORE_FILE)
archive = archive_files(rules)
missing = sorted(name for name in archive if name not in known)
print(f"\nDokumentfiler i arkivet: {len(archive)}")
print(f"Varav utan Zotero-bilaga: {len(missing)}")

by_ext = Counter(Path(n).suffix for n in missing)
print("  per filtyp:", dict(by_ext))
print("\nFem exempel:")
for name in missing[:5]:
    print("  ", archive[name].relative_to(ARCHIVE))

# --- Del 4: importkandidater ur analyzerns loggar --------------------------


def citable_entries(rules):
    """Citerbara poster ur alla processed_files.json, nyckel = filnamn i gemener.

    Poster som bara har "primary" är sekundära filer i en grupp (t.ex. en EPUB
    vid sidan av en PDF) och hoppas över. Att nyckeln är filnamnet gör att de
    fyra dubblettloggarna som bara skiljer i skiftläge slås ihop av sig själva.
    """
    entries = {}
    for json_path in ARCHIVE.rglob("processed_files.json"):
        # Mappen analyzern kördes på, alltså analyzer-mappens förälder.
        folder = json_path.parent.parent.relative_to(ARCHIVE)
        if is_ignored(folder, True, rules):
            continue
        log = json.loads(json_path.read_text(encoding="utf-8"))
        for logged_path, record in log.items():
            analysis = record.get("analysis")
            if not analysis or not analysis.get("is_citable"):
                continue
            if analysis.get("type") in SKIP_TYPES:
                continue
            # filepath pekar på PDF:en när en sådan finns i gruppen.
            name = Path(analysis.get("filepath") or logged_path).name.lower()
            if Path(name).suffix in {".ppt", ".pptx"}:
                continue
            entries[name] = analysis
    return entries


candidates = citable_entries(rules)
print(f"\nCiterbara poster i analyzerns loggar: {len(candidates)}")
print("  per typ:", dict(Counter(a.get("type") for a in candidates.values())))

# Filnamnet är nyckeln: JSON-sökvägarna är frusna vid analystillfället, men
# arkivet är genomsökt nu. Saknas namnet i archive har filen flyttats bort,
# bytt namn, eller uteslutits av zotero-import-ignore.
found_now = [n for n in candidates if n in archive]
to_import = sorted(n for n in found_now if n not in known)

# Resten saknas av två helt olika skäl som inte ska blandas ihop: antingen
# har ignorefilen uteslutit formatet, eller så är filen verkligen borta.
absent = [n for n in candidates if n not in archive]
excluded = sorted(n for n in absent if is_ignored(Path(n), False, rules))
lost = sorted(n for n in absent if not is_ignored(Path(n), False, rules))

print(f"  hittas i arkivet nu: {len(found_now)}")
print(f"  har redan Zotero-bilaga: {len(found_now) - len(to_import)}")
print(f"  uteslutna av ignorefilen: {len(excluded)}")
print(f"  filen hittas inte: {len(lost)}")

print(f"\nImportkandidater: {len(to_import)}")
for name in to_import[:5]:
    print("  ", archive[name].relative_to(ARCHIVE))

if lost:
    print("\nCiterbara poster vars fil inte hittas (kräver åtgärd):")
    for name in lost:
        print("  ", name)
