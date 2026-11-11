# FutureProofing outbound dashboard

A static page (`index.html`) that shows campaign totals from Instantly. A GitHub Action runs `fetch.py` every two days, writes `data.json` and `history.json`, and commits them; GitHub Pages serves the page.

- Totals only: no lead names, emails, companies or opens are fetched into the repo.
- The Instantly API key lives in the repo secret `INSTANTLY_KEY`. Update it with `gh secret set INSTANTLY_KEY`.
- Run an update now: Actions tab, "Update dashboard", "Run workflow" (or `gh workflow run update.yml`).
