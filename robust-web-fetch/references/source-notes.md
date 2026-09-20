## Beyond the tiers: locating a fetchable URL (2026-07-05 field notes)

The tiers assume you already hold a fetchable URL. Three techniques from real acquisition work sit *upstream* of the tiers — they change or discover the URL instead of attacking the block:

1. **Wayback CDX search when the cited URL is dead.** The availability API returns nothing useful for restructured sites (e.g. gov.cn now 302s old article URLs to its homepage). Query the CDX index directly and filter on URL fragments you can guess (a date, a content ID):

   ```
   http://web.archive.org/cdx/search/cdx?url=<domain>*&filter=original:.*<fragment>.*&collapse=urlkey&fl=original,timestamp,statuscode
   ```

   **Pick the snapshot contemporaneous with publication, not the newest.** A 2022 snapshot of a 2013 pbc.gov.cn page is a JS shell with no content; the 2013-12-05 snapshot has the full static text. Sites that later adopted JS rendering silently poison recent snapshots.

1. **Check Internet Archive *lending* status before promising "borrow from IA" as a fallback.** Post-Hachette, most scanned books report `lending___status = is_printdisabled` — not borrowable by normal accounts. Verify programmatically instead of assuming:

   ```
   https://archive.org/advancedsearch.php?q=title:(...)+AND+creator:(...)&fl[]=identifier,lending___status&output=json
   ```

   If it says `is_printdisabled`, the real fallback is interlibrary loan, not IA.

1. **Hunt the alternative open version before fighting the paywall.** Paywalled books and articles often have a legally open sibling the tiers never need to fight: the working-paper version of a book chapter (university repositories: SFU Summit, EUI Cadmus, SSRN), the journal-article version of a book's core argument (law journals host their own open PDFs), or an official primary source that supersedes the secondary one (central-bank white papers). Search `<author> <topic> working paper|SSRN|repository` first; a five-minute hunt beats a four-tier escalation that ends blocked anyway. Cite with the version actually used, noted as such.
