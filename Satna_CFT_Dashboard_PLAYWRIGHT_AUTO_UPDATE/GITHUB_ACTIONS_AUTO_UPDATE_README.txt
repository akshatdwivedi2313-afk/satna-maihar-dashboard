JGSA GitHub Actions auto-update setup
====================================

What this version does:
- Opens the JGSA dashboard in a real headless browser using Playwright.
- Saves a fresh latest_jgsa.pdf by printing the page.
- Saves jgsa_snapshot.html and jgsa_snapshot.txt for debugging.
- Extracts top JGSA summary cards into jgsa_live_summary.js.
- Commits updated files to GitHub.
- If Netlify is linked to this GitHub repo, Netlify redeploys automatically.

Important honesty:
This can update the LIVE JGSA Snapshot section automatically. Your full work-level filters still use data.js from the Excel work dataset, unless JGSA exposes a work-level export/API later.

Manual run:
1. Open your GitHub repository.
2. Click Actions.
3. Click "Auto update JGSA dashboard".
4. Click "Run workflow".
5. Choose SATNA and optional date.
6. Wait 2-5 minutes.
7. Netlify will redeploy automatically if connected.

Daily run:
It runs automatically every day at 10:00 AM IST.
You can change the time in:
.github/workflows/auto-update-jgsa.yml

If it fails:
Open the failed Action log. If JGSA changed its page or blocked automation, share the error/screenshot and the script can be adjusted.
