Browser scraper version
=======================
Run start_dashboard.bat.
Click "Refresh JGSA Data".

What it does:
- Opens the JGSA website in a hidden Chromium browser.
- Captures JSON/API responses loaded by the page.
- If work-level records are found, rewrites data.js and reloads the dashboard.

First run requirement:
- Internet must be on.
- Python will auto-install Playwright and Chromium if missing. First refresh can take 3-10 minutes.

Important:
- If JGSA does not expose work-level records in browser/API responses, the scraper cannot create full row-level dashboard data. It will save jgsa_browser_snapshot.html and jgsa_browser_snapshot.png in this folder for inspection.
