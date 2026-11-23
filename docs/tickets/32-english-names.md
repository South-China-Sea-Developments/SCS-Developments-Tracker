# 32 — English names on every map

Asked by the maintainer on 2026-11-23: every name on the map in English. Built the same day.

- **Every feature has an English name**, and a test holds it (no pinyin, Vietnamese or Chinese in
  `name_en`). Before, 77 of 321 had none: about 40 showed in Chinese characters, the rest in pinyin
  ("Lidi Ansha") or Vietnamese ("Đá Tam Trung").
- **Duplicates merged.** Most were the same reef twice: Wikidata keeps some features once under the
  English name and once under the Chinese only (安定连礁 is Addington Patch), and GeoNames' Chinese
  dump lists pinyin entries apart from the English ones (Mahuan Dao is Nanshan Island). The Wikidata
  ones are merged in `gazetteer_extra.csv` (kind `=<feature_id>`: its names become the other's aliases);
  the GeoNames step now links names through pinyin and adds a new feature only when it has an English
  name, and no longer merges two neighbouring reefs merely for being within 1.5 km (it had given James
  Shoal's names to Lydie Shoal). 277 features in all.
- **English names found** for the rest from GeoNames and Wikidata aliases, the Chinese Wikipedia
  articles (康泰滩 Coronation Bank, 中北暗沙 Oliver Shoal) and the English Wikipedia lists for
  Macclesfield Bank, the Paracels and the Spratlys. Where Wikipedia gives only a translated name
  (筐仔沙洲 "Little Basket", 咸舍屿 "Salty Hut", 七连屿 "Seven Sisters"), that is used.
- **No English name found** for eight small features; they show the local name with an English feature
  word, recorded as such: Sanzhizai Islet, Yongnan Shoal, Puning Shoal, Suilang Shoal, Yunuo Reef,
  Nhan Gia Reef, Sa Huynh Reef, Tam Trung Reef.
- **Event places** show in English on the Events map and list ("Huangyan Dao (Scarborough Shoal)" →
  "Scarborough Shoal", "Nansha Qundao" → "Spratly Islands"); the recorded name in `events.csv` is not
  changed and is still searchable.
- The basemap already labelled countries and towns in English first; sub-region names were English.
- No move's placement changed (144 of 388 place, the same features).
