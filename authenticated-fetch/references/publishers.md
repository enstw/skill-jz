# Publisher notes

These notes came from earlier acquisition sessions; platform behavior can change.

- EZproxy rewrites hostnames; use links from the live proxied page.
- Cambridge Core, JSTOR, and Oxford Academic may expose PDFs by chapter. Check the table of contents and retain order before merging.
- JSTOR may return a terms interstitial. After the user accepts the applicable terms, `save` or `merge --accept-jstor-terms` can retry JSTOR and its EZproxy hostnames with `acceptTC=true&coverpage=false`. Other publishers are unaffected.
- Some platforms, including De Gruyter in earlier sessions, challenge CDP-driven navigation. Leave the visible tab for a human to finish, then retry in the same session.
- A price or institutional-access denial is a licensing limitation, not a browser fault. Seek an authorized alternative or interlibrary loan.
- A vendor that a gateway signs in by its own SSO (seen with Airiti) lands on the vendor's **unproxied** host, so `login` reports `handed_off: true`, `login_verified: false` instead of matching `success_url`. Confirm entitlement on that page with `text` (the vendor usually names the institution in its header) and continue in the same session; another `login` cannot change the outcome.

## Airiti (華藝), checked 2026-10-08

Two separate platforms; search both before recording a Taiwanese source as unavailable.

- **Airiti Library** (`www.airitilibrary.com`) holds journal articles, theses, and conference papers. A signed-in header reads `Hello! <institution>`. Hand-built search URLs such as `/Search/ArticleSearch?SearchTerm=` return "page not found"; search through the box: `text https://www.airitilibrary.com/ --fill '#_Search_檢索列' '<query>'`. Full-text hits in other works' reference lists crowd the results, so a book's title appearing there does not mean the book itself is held.
- **iRead eBooks** (`www.airitibooks.com`) holds whole books, including Taiwanese university-press edited volumes whose chapters Airiti Library does not index. Search with `text https://www.airitibooks.com/ --fill '#searchInput' '<author or title>'`; the box is hidden below desktop width, which `text` already sets. A book page (`/Publication/Details?publicationID=…`) lists the holding libraries under **Go to Borrow**; when the user's institution is absent, its Airiti subscription does not cover the book, and a public library on that list (city libraries commonly hold these) is the lending route.
- iRead loans are read online or in its app under DRM: there are no PDF bytes for `save`, and capturing the reader's pages is out of scope for this skill. Record the borrowing route as access, not as local full text.
