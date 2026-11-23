# 41 — Every record to the same place rules

Asked by the maintainer on 2026-11-23: every record, Chubb's and the ~1,200 candidates in and not yet in
Airtable, brought up to the place rules decided that day. Decisions (2026-11-23): Chubb's coding is not
changed and the moves whose named features lie outside their coded sub-regions are listed for the
maintainer; decided Airtable rows get context only, never the decision fields; a candidate's place
becomes its English form with the source's wording kept in the note.

- `pipeline.enrich`: a candidate's place in English (`gazetteer.english_place`, rewritten to two
  conservative rules: a name with another name of the same feature in brackets becomes the English
  name, "Pag-asa (Thitu) Island" -> "Thitu Island"; a name in pinyin, Vietnamese or Chinese script
  becomes the English name of the one feature it names; Latin-script local names such as Natuna or
  Kalayaan stay), the source's wording in the review note, and a named feature placed (coordinates,
  sub-region). It runs at intake (`pipeline.queue` opens a run through it) and by hand on runs open.
- Chubb's 125 dated incidents (the MAVD seed events) had no place: 40 now carry their move's named
  features, 19 with coordinates (one feature, inside a coded sub-region). His sub-region flags are not
  touched.
- `docs/notes/chubb-place-checks.md`: the 15 Chubb moves naming a feature outside their coded
  sub-regions, for the maintainer to decide.
- "Hoang Sa" alone now means the Paracels (Pattle Island keeps "Đảo Hoàng Sa"); "Zhongsha Islands" is
  kept as an English name (English Wikipedia's title).
