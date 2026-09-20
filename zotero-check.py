"""zotero-check.py – steg 2: läsande diagnos av bilagor i Zotero.

Skriver ingenting till Zotero. Kräver Zotero 10 igång och inställningen
Settings → Advanced → "Allow other applications on this computer to
communicate with Zotero".

Kör:  python zotero-check.py
"""

from collections import Counter
from pathlib import Path

# Egna moduler i samma mapp. Python letar först i skriptets egen mapp.
# zoterolib = Zoteros API, arkivlib = arkivet och analyzerns loggar.
from zoterolib import attachment_names, fetch
from arkivlib import (
    ARCHIVE,
    IGNORE_FILE,
    archive_files,
    citable_entries,
    is_ignored,
    read_ignore,
)


# --- Del 1: översikt ------------------------------------------------------

attachments = [a["data"] for a in fetch("items?itemType=attachment")]
print(f"Antal bilagor: {len(attachments)}\n")

modes = Counter(d.get("linkMode") for d in attachments)
print("Per linkMode:")
for mode, count in modes.most_common():
    print(f"  {mode:15} {count}")

linked = [d for d in attachments if d.get("linkMode") == "linked_file"]
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

known = attachment_names(attachments)

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
