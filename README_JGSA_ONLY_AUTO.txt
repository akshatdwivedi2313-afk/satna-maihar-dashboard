JGSA-only auto update setup

This package keeps the main dashboard work-level data as the manually generated Excel/static dataset.
GitHub Actions will NOT fetch or merge MNREGA data.

The workflow only updates these JGSA snapshot/live-summary files:
- latest_jgsa.pdf
- jgsa_snapshot.html
- jgsa_snapshot.txt
- jgsa_live_summary.js

Main dashboard metrics and Upyantri cards stay from the prepared static data.js until a new Excel-based dashboard ZIP is generated.
