Block Tulna Source Isolation
============================
- Main dashboard / work list / Upyantri cards / Critical / War Room continue using the existing JGSA dashboard workflow and data.
- Only Block Tulna reads official_block_scorecard.js.
- official_block_scorecard.js is based on the official JGSA scorecard URL:
  https://jgsa.nregsmp.org/rankings.php?level=block&date=2026-06-03&district=SATNA
- GitHub Actions has been updated to refresh official_block_scorecard.js separately without touching data.js.
- If official source update fails, existing official_block_scorecard.js remains unchanged and the dashboard still works.
