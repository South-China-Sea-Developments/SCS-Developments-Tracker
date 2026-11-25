# 40 — What's new, and a feed

Improvement 8 of the eight agreed on 2026-11-23.

- `whats-new.html`: the moves the project added (by the date they were coded), corrections to moves
  (`corrections.csv`) and retractions (`retired_moves.csv`), newest first, grouped by day, each linking to
  its case. Chubb's own moves are the starting point, not news.
- `feed.xml`: the same, the 50 newest, as an Atom feed with absolute links to the public site
  (`SITE_URL`, default https://south-china-sea-developments.github.io/SCS-Developments-Tracker/; set the
  environment variable to build for another address). Every page announces the feed.
- Linked from the footer of every page and from the Cases page. The weekly apply fills it: accepted
  moves carry their decision date.
