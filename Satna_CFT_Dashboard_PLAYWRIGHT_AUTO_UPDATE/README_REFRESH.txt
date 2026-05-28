JGSA Refresh Dashboard

How to use:
1. Extract this ZIP fully.
2. Double-click start_dashboard.bat.
3. Keep the black Python window open.
4. Click "🔄 Refresh JGSA Data" in the dashboard.

What it does:
- Python fetches the JGSA page for today's date.
- If the JGSA page exposes work-level JSON/export data, data.js is regenerated and the dashboard reloads.
- A copy of the fetched page is saved as jgsa_snapshot.html.

Important:
If the JGSA site does not expose work-level data in page HTML, the refresh button will show an error. In that case, share the site's CSV/Excel/API export link and the refresh will be made fully automatic.
