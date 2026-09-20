"""arkivlib.py – gemensam kod för arkivet och analyzerns loggar.

Här ligger allt som handlar om filerna i predikningar-studier: vilka som
finns, vilka som ska ignoreras, och vad analyzern har skrivit om dem.
Inget här rör Zotero – det ligger i zoterolib.py.

Skälet till uppdelningen: zotero-check.py och zotero-import.py behöver
samma arkivkod, men skript med bindestreck i namnet kan inte importeras
(import zotero-check är ett syntaxfel, bindestreck är minus). Delad kod
måste alltså bo i en modul utan bindestreck.

Används så här:

    from arkivlib import ARCHIVE, read_ignore, archive_files, citable_entries
    rules = read_ignore(IGNORE_FILE)
    archive = archive_files(rules)

Kör man filen direkt (python arkivlib.py) räknas arkivet igenom.
"""

import fnmatch
import json
import os
from pathlib import Path

ARCHIVE = Path(r"C:\Users\gunther\Dropbox\arkiv\larsArkiv\predikningar-studier")

# Dokumentformat som över huvud taget kan vara aktuella. Vilka av dem som
# faktiskt tas med styrs av zotero-import-ignore, inte av den här listan.
EXTENSIONS = {".pdf", ".epub", ".doc", ".docx", ".md"}

# Ignorefilen ligger bredvid modulen. __file__ är sökvägen till denna fil.
IGNORE_FILE = Path(__file__).parent / "zotero-import-ignore"

# Analyzerns egen regel: is_citable sant, men dessa typer räknas ändå inte.
SKIP_TYPES = {"predikan", "övrigt"}


def read_ignore(path=IGNORE_FILE):
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
    """Alla dokumentfiler i arkivet som zotero-import-ignore släpper igenom.

    Returnerar en dict: filnamn i gemener → full sökväg. Filnamnet är nyckeln
    eftersom arkivets namnkonvention gör det unikt i praktiken, och eftersom
    det är det enda som överlever att en fil flyttas.
    """
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


# __name__ är "__main__" bara när filen körs direkt. Självtestet kräver inte
# att Zotero är igång, eftersom ingenting här rör Zotero.
if __name__ == "__main__":
    rules = read_ignore()
    print(f"Regler i {IGNORE_FILE.name}: {len(rules)}")
    archive = archive_files(rules)
    print(f"Dokumentfiler i arkivet: {len(archive)}")
    entries = citable_entries(rules)
    print(f"Citerbara poster i analyzerns loggar: {len(entries)}")
