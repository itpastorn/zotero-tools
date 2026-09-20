# CLAUDE.md – zotero-tools

## Projektbeskrivning

Python-skript som kopplar ihop Lars Gunthers Zotero-bibliotek med
dokumentarkivet `predikningar-studier` via Zoteros **lokala API**
(`http://localhost:23119/api/`). Målen, i prioritetsordning:

1. **Diagnos** – vad finns i Zotero, vilka länkar är trasiga, vilka arkivfiler
   saknar Zotero-post. (`zotero-check.py`, läsande, klart i steg 2.)
2. **Import** – skapa Zotero-poster direkt från analyzerns
   `processed_files.json` med länkade bilagor (`linked_file`) till arkivet.
   Ersätter RIS-vägen.
3. **Reparation** – hitta och uppdatera länkar som pekar fel efter att filer
   flyttats (t.ex. av `sort-books`-skillen).
4. Senare: MCP-server för sökning, anteckningar och taggar från Claude
   Desktop/Cowork/Code. Beslut ej fattat, se "MCP" nedan.

Detta projekt hanterar det **deterministiska** (kontroll, import, reparation).
Det samtalsbaserade (söka, anteckna, tagga) ska en MCP-server sköta.

## Arbetssätt

- Lars lär sig Python. Utveckla **steg för steg**: ett avgränsat tillägg per
  steg, förklara nya konstruktioner kort, låt Lars köra och klistra in utdata
  innan nästa steg. Skriv inte färdiga stora skript.
- Läsande skript först, skrivande skript därefter. Varje skrivande skript ska
  ha `--dry-run` som standardläge och kräva en flagga (`--apply`) för att
  skriva. Skriv aldrig till Zotero utan att först visa vad som kommer att
  hända.
- Backup av Zoteros datakatalog är tagen 2026-09-19, före första
  skrivande körning. Ta ny backup före första skarpa importen. Zotero-synk
  är ingen backup: raderingar synkas också.
- Enbart standardbiblioteket (`urllib`, `json`, `pathlib`, `argparse`) så
  länge det räcker. Ingen `.venv` behövs då.
- Svenska i kommentarer, docstrings och utdata. Engelska termer behålls när
  svensk term saknas (`linkMode`, `itemType`).

## Körmiljö

- Windows 11, Git Bash, Python direkt i Windows (`python zotero-check.py`).
- **Zotero 10.0.3** (lokal skrivning kräver 10+). Inställningen
  Settings → Advanced → "Allow other applications on this computer to
  communicate with Zotero" är på. `403` betyder att den är av,
  "connection refused" att Zotero inte är igång.
- Cowork/Claude Code i molnet når **inte** `localhost` på Lars dator.
  Skript mot Zotero körs av Lars lokalt (eller av Claude Code lokalt).
- Arkivrot: `C:\Users\gunther\Dropbox\arkiv\larsArkiv\predikningar-studier`
- Analyzern: `..\document-analyzer\analyzer.py` (eget repo, egen CLAUDE.md).

## Filer

| Fil | Status | Beskrivning |
|-----|--------|-------------|
| `zotero-check.py` | klart, steg 2 | Läsande diagnos: bilagor per `linkMode`, trasiga länkar, arkivfiler utan Zotero-post, importkandidater |
| `zotero-import-ignore` | klart | Vad som aldrig tas med, i diagnos eller import. `.gitignore`-liknande regler, sista träffande regeln avgör |
| `zoterolib.py` | klart, steg 3–4 | Gemensam modul: `fetch` (läsning), `send` (skrivning med nyckel, Server-ID och version), `server_id`, `authorize`, `api_key`. Importeras av de tre skripten så att API-detaljerna finns på ett ställe |
| `zotero-write-test.py` | klart, steg 4a | Skapar en testpost med `linked_file` i `zotero-tools-test`. Vägrar om samlingen inte är tom. Samlingen är omdöpt till `Automated-imports`, så skriptet behöver nytt namn i koden för att köras igen |
| `zotero-patch-test.py` | klart, steg 4b | Växlar testbilagans `path` mellan två filer med `PATCH`. Mönstret för `zotero-repair.py` |
| `zotero-import.py` | planerad | JSON → Zotero via lokala API:et, med matchning mot befintliga poster |
| `zotero-repair.py` | planerad | Hittar trasiga `linked_file`-sökvägar, letar filnamnet i arkivet, uppdaterar `path` (kan eventuellt slås ihop med import) |
| `notes.txt` | – | Lars egna anteckningar |

`zoterolib.py` är ett medvetet pedagogiskt steg: modulbegreppet (import,
`__name__`, var Python letar) ska gås igenom för sig innan skrivningen börjar.

## Nuläge i Zotero (2026-09-19, från zotero-check.py steg 2)

- 533 bilagor: 290 `imported_url` (sparade webbsidor), 115 `imported_file`
  (äldre lagrade filer, tillagda innan Lars började länka), 81 `linked_file`,
  44 `linked_url`, 3 `embedded_image`.
- **Linked Attachment Base Directory är satt till arkivroten.** Alla 81
  länkade sökvägar är nu relativa (`attachments:karismatik-helande/…`).
  Zotero konverterade de befintliga absoluta länkarna automatiskt.
- **0 trasiga länkar.** Inga länkar pekar in i `books-to-fix`.
- Arkivet: 1 202 dokumentfiler (PDF/EPUB efter `zotero-import-ignore`), varav
  1 047 saknar Zotero-bilaga. (Körning 2026-09-19 efter att fler mappar
  analyserats och flera mappar blockerats temporärt i ignorefilen; tidigare
  1 458/1 293.)
- **Reparationen är i praktiken klar innan den börjat.** `zotero-repair.py`
  behövs först när `sort-books` flyttat filer igen. Importen är hela jobbet.

### Importkandidater (samma körning)

| Steg | Antal |
| --- | --- |
| Citerbara poster i analyzerns loggar | 718 |
| – varav filen hittas i arkivet nu | 674 |
| – varav redan har Zotero-bilaga | 132 |
| **Att importera** | **542** |
| Uteslutna av `zotero-import-ignore` (fel format) | 44 |
| Filen hittas inte alls | 0 |

Typfördelning bland de 718: 510 bok, 175 artikel, 29 uppsats, 4 studie.

Loggar i blockerade mappar hoppas över helt, så siffrorna stiger igen när
de temporärt blockerade mapparna (se ignorefilen) släpps efter kontroll.

De 44 uteslutna är citerbara enligt analyzern men har format som ignorefilen
stoppar (`.doc`, `.docx`, `.md`, …). Det är avsiktligt – de försvinner tyst
och ska inte förväxlas med fel.

## Arkivet och analyzern

- `analyzer.py` skriver per mapp `analyzer/processed_files.json` (loggen) och
  `analyzer/zotero-import-<mapp>.ris`. 111 JSON-filer, ~1 574 analyserade
  poster.
- **JSON-struktur:** dict med absolut Windows-sökväg som nyckel. Primära
  poster har `analysis` (title, author, summary, type, year, date_full,
  is_citable, publication, publisher, publisher_place, isbn, pages_total,
  edition, institution, institution_place, thesis_type, filepath,
  all_filepaths). Sekundära filer i en grupp (t.ex. EPUB vid sidan av PDF) har
  bara `primary` som pekar på den primära. `analysis.filepath` pekar på PDF om
  sådan finns.
- **Citerbar** enligt analyzerns egen regel: `is_citable` sant och `type`
  inte i {`predikan`, `övrigt`}, och inte PPT/PPTX. Typmappning i RIS:
  artikel→JOUR, uppsats/avhandling→THES, bok→BOOK, studie→RPRT.
  Fördelning: se tabellen under Nuläge.
- **Sökvägarna i JSON fryses vid analystillfället.** Importskriptet ska därför
  **slå upp filens aktuella plats på filnamn** i importögonblicket, inte lita
  på `filepath`. Vid genomgång 2026-09-19 hittades 692 av 740 så, 47 föll på
  formatfiltret och 1 hittades inte.
- Filnamnskonventionen (bara `a-z0-9.-`) gör filnamnet i praktiken unikt i
  arkivet. Det är nyckeln för all matchning. Två mönster:
  - Normalfallet: `efternamn-fornamn-titel.ext`
  - **Biografier: den omskrivne först, sedan titel och författare** –
    `jonathan-edwards-a-life-by-marsden-george.pdf`
- **Filnamnsmatchning överlever flytt men inte omdöpning.** Enda fyndet
  2026-09-19: `marsden-george-jonathan-edwards.pdf` analyserades i
  `studier/historia-sociologi-psykologi/`, döptes sedan om enligt
  biografikonventionen och flyttades till
  `studier/kyrkohistoria/individuals-movements-groups/jonathan-edwards/`.
  Analysen blev föräldralös: det nya namnet finns i ingen
  `processed_files.json`. Åtgärd = kör analyzern på den nya mappen. En
  omdöpning per 740 poster är acceptabelt; något försök att spåra omdöpningar
  automatiskt ska inte byggas.
- Fyra poster har dubbla loggnycklar som bara skiljer i skiftläge (Windows
  `Path.exists()` är skiftlägesokänslig, så `cleanup_missing_files` i
  analyzern rensar inte dem). Importskriptet ska dedupa på gemener.
- **`books-to-fix/` med undermappar ignoreras alltid.** Länkning sker först
  när filen sorterats in på permanent plats. Finns länkar dit ska de
  uppdateras.
- **RIS-filerna används inte längre för import.** Skälen: `L1`-sökvägen är
  inaktuell efter sortering, filen skrivs om i sin helhet varje körning
  (ominport ger dubbletter), och `/connector/import` saknar dubblettkontroll
  och lägger posterna i den samling som råkar vara markerad i gränssnittet.
  Gamla `zotero_import_*.ris` (understreck, äldre skriptversion) raderades
  2026-09-18.

## Designregler för zotero-import.py

- Källa: alla `processed_files.json`, filtrerade med analyzerns
  citerbarhetsregel, exklusive allt som `zotero-import-ignore` stoppar.
- **Matchning mot befintliga Zotero-poster i tre steg** innan något skapas:
  (1) bilagans filnamn (`linked_file.path` eller `imported_file.filename`,
  gemener), (2) ISBN, (3) titel + år. Träff = uppdatera/länka, inte skapa.
- **Samlingar: alla importerade poster hamnar i en enda importsamling**, inte
  i en speglad mapphierarki. Skäl: lätt att överblicka och lätt att ångra
  (markera allt, radera). Lars flyttar ut dem själv efter granskning.
  Beslut 2026-09-20: samlingen heter **`Automated-imports`** (nyckel
  `L6YLCBVC`) och är skapad av Lars i gränssnittet – skriptet skapar den inte,
  utan slår upp nyckeln på namnet och avbryter om den saknas. Det är den
  tidigare testsamlingen `zotero-tools-test`, omdöpt och tömd.
- **Befintliga lagrade bilagor rörs inte** (115 `imported_file`, 290
  `imported_url`). De läses bara i matchningssteget, så att importen inte
  skapar dubbletter. Känd konsekvens: poster vars enda bilaga är en lagrad
  kopia får ingen arkivlänk.
- Typmappning: bok→`book`, artikel→`journalArticle`, uppsats→`thesis`,
  studie→`report`. Fält: summary→`abstractNote`, publication→
  `publicationTitle`, publisher_place→`place`, isbn→`ISBN`, edition→
  `edition`, institution→`university`, thesis_type→`thesisType`,
  year/date_full→`date`.
- Författare: `author` är en sträng "Efternamn, Förnamn; Efternamn, Förnamn".
  Institutionella författare ("Assemblies of God, General Presbytery") ska bli
  enfältsnamn (`{"creatorType":"author","name":…}`), inte splittas. Lösning:
  **heuristik plus granskningslista.** Namn som ser ut som "Efternamn,
  Förnamn" splittas i två fält, övriga blir enfältsnamn – och skriptet skriver
  ut **alla** enfältsnamn det skapat, så att Lars kan rätta de som blev fel.
- Metadata är LLM-extraherad ur dokumentets första 6 000 tecken och kan vara
  fel. Sätt taggen **`okontrollerad`** på varje importerad post; Lars tar bort
  den efter granskning.
- Bilaga: `linked_file` med relativ sökväg om Base Directory är satt.
- Batchgräns i API:et: 50 objekt per POST.
- Idempotent: en andra körning ska inte skapa något nytt.

## Zoteros lokala API – vad som gäller (Zotero 10, dok. 2026-07-29)

- Bas: `http://localhost:23119/api/users/0/…` (user 0 = inloggad användare).
  Header `Zotero-API-Version: 3`. Ingen paginering som standard: hela
  resultatet kommer i ett svar. Ingen rate limiting.
- **Läsning** kräver ingen nyckel. `GET …/items?itemType=attachment`,
  `…/items/<key>/children`, `…/collections`, `…/tags`, `…/searches/<key>/items`
  (kör en sparad sökning, finns bara lokalt), `format=ris|bibtex|csljson|…`.
- **Skrivning** (`POST`/`PUT`/`PATCH`/`DELETE` för items, collections, saved
  searches) kräver:
  1. En lokal nyckel: `POST /api/local/authorize` med body
     `{"appName": "zotero-tools"}` och header `Zotero-Server-ID`. Zotero visar
     dialog Allow / Always Allow / Deny. Svar `{"key": "<32 tecken>",
     "remember": true|false}`. Utan "Always Allow" är nyckeln engångs.
     Max 5 dialoger per minut. Nyckeln skickas som header `Zotero-API-Key`.
     Beslut 2026-09-19: nyckeln sparas i
     `~/.config/zotero-tools/api-key` (utanför Dropbox och Git), se
     `zoterolib.api_key()`.
  2. Header `Zotero-Server-ID` (läs den från valfritt svar, t.ex. `GET /api/`;
     verifierat 2026-09-19: finns som svarshuvud på alla anrop, även
     `GET /api/` vars svar bara är "Nothing to see here.").
     Saknas den: `428`. Fel ID: `412` = annan databas, kasta cache.
  3. Versionskrav: `PUT`/`PATCH` kräver postens aktuella `version` (i JSON
     eller `If-Unmodified-Since-Version`), annars `412`. Lokala versioner har
     **inget** samband med webb-API:ets versioner.
- `PATCH` skickar bara ändrade fält, men arrayer (`tags`, `collections`,
  `creators`) ersätts i sin helhet. Att "lägga till en tagg" = läs, komplettera
  arrayen, skriv tillbaka.
- Anteckningar är items (`itemType: note`, `parentItem`). Taggar ligger i
  `tags: [{"tag": "…"}]`.
- Ändringar via lokala API:et är vanliga lokala ändringar och synkas till
  zotero.org vid nästa synk.
- Filuppladdning stöds bara för lagrade bilagor (`imported_file`,
  `imported_url`).
- **Verifierat 2026-09-19 (`zotero-write-test.py`, samling
  `zotero-tools-test`):** `POST …/items` skapar en förälder och därefter en
  `linked_file`-bilaga med `parentItem` och
  `path: "attachments:relativ/sokvag.pdf"`. Zotero sparar sökvägen oförändrad
  (relativ, snedstreck framåt). Svaret på POST har `successful["0"]["key"]`.
  Skrivningen gjordes i två anrop: föräldern först, sedan bilagan.
- **Verifierat 2026-09-19 (`zotero-patch-test.py`):** `PATCH …/items/<key>`
  med `{"path": "attachments:…"}` och `If-Unmodified-Since-Version` ändrar
  sökvägen på en befintlig `linked_file`. Versionen ökade 109→110, svaret är
  tomt (204), och den nya filen öppnas i Zotero. Bilagans titel ändras inte.
- Zotero-teamet: utvecklarguiderna är inte alltid uppdaterade; källkoden
  gäller (adomasven, forum 2025-12-11). Dokumentation:
  - https://www.zotero.org/support/dev/web_api/v3/local_api
  - https://www.zotero.org/support/dev/web_api/v3/basics
  - https://www.zotero.org/support/dev/web_api/v3/write_requests
- Alternativ väg som **inte** ska användas: `POST /connector/import` (rå RIS,
  ingen nyckel, ingen dubblettkontroll, hamnar i markerad samling, taggar blir
  automatiska, inte ett stabilt gränssnitt).

## MCP – kandidater (läge 2026-09-17), beslut ej fattat

| Projekt | Arkitektur | Skrivning utan molnnyckel | Kommentar |
|---|---|---|---|
| 54yyyu/zotero-mcp (PyPI `zotero-mcp-server` 0.12.4) | Python, stdio, lokal läsning | Ja på Zotero 10+ (`zotero-mcp authorize-local`) | Störst (~5k stjärnor), semantisk sökning (ChromaDB), verktyg för anteckningar/taggar, ~13k token fast kontext (`ZOTERO_MCP_TOOLSETS`), underhållaren saknar Windows-maskin |
| cookjohn/zotero-mcp | Plugin (.xpi) i Zotero, Streamable HTTP port 23120 | Ja, från Zotero 7 | Kräver troligen `mcp-remote`-brygga i Claude Desktop-config |
| dvdsosa/zotero-native-mcp | Node, stdio, enbart lokala API:et | Ja, Zotero 10+ | Tunn, bara verifierad med Claude Code, ersätter tagg-array vid uppdatering |
| oscardvs/zoteus | Node, hybrid | Delvis (taggar/metadata/samlingar kräver molnnyckel) | Kommersiell hostad nivå |

Avförda: danielostrow (enbart webb-API, 7 commits), "MCP for Zotero"
(hostad proxy, API-nyckel hos tredje part). ChatGPT ignoreras tills vidare
(stöder inte lokala stdio-servrar).

Preliminär hållning: 54yyyu, med dvdsosa som reserv. Ett MCP-verktyg som
"lägger till tagg" måste läsa arrayen först; kontrollera det innan Claude får
skrivrätt. Claude Desktop-konfigen ligger i
`C:\Users\gunther\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`
(Microsoft Store-versionen; slå samman, skriv aldrig över, redigera bara när
appen är helt avslutad).

## Beroenden till andra projekt

- `sort-books`-skillen flyttar filer i arkivet och bryter därmed länkar.
  Regel tills vidare: **sortera först, importera till Zotero sedan.**
  Möjlig senare utbyggnad: skillen anropar `zotero-repair.py` efter flytt.
- `document-analyzer`: JSON-formatet ovan är kontraktet. Ändras det, ändra
  här.

## Namnregler för filer

Alla filer i projektet (skript, utdata) följer arkivets konvention:

1. Enbart gemener
2. Mellanslag och understreck → bindestreck
3. Icke-ASCII → ASCII (å→a, ä→a, ö→o, ü→u)
4. Bara `a-z`, `0-9`, `-` och `.` före filändelsen
5. Inga dubbla bindestreck, inga inledande/avslutande

Använd **aldrig** understreck i filnamn. Undantag: `CLAUDE.md`, `README.md`.

## Nästa steg

Steg 1–4 är klara: diagnosen kör, Base Directory är satt, alla länkar är
relativa och hela. `zoterolib.py` finns, `zotero-check.py` använder den, och
`POST /api/local/authorize` är verifierat 2026-09-19: "Always Allow" gav
`remember: true` och en nyckel på 32 tecken, sparad i
`~/.config/zotero-tools/api-key`. Steg 4 (2026-09-19, backup
tagen före): nyckeln fungerar för skrivning, `POST` skapar `linked_file` och
`PATCH` ändrar `path`.

1. Steg 5: `zotero-import.py` med `--dry-run`, en mapp i taget, upp till de
   542 kandidaterna (fler när de blockerade mapparna släpps).

Sidospår när tillfälle ges: gå igenom de temporärt blockerade mapparna i
`zotero-import-ignore` och ta bort raderna en i taget. Marsden-biografin har
fått ny analys (0 filer saknas), men ligger just nu i en blockerad mapp.
