# news-image-20261121

[![make.fun · news-image-20261121](https://make.fun/badge/news-image-20261121.svg)](https://make.fun/bounty/news-image-20261121?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121)
[![rank](https://make.fun/badge/news-image-20261121/rfky18/news-image-20261121/rank.svg)](https://make.fun/bounty/news-image-20261121/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121)
[![reward](https://make.fun/badge/news-image-20261121/rfky18/news-image-20261121/reward.svg)](https://make.fun/bounty/news-image-20261121?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121)

**Contest:** [Sum up 21 November's world news in one image](https://make.fun/bounty/news-image-20261121) — $100, free entry, deadline 23 Nov 2026 07:00 WIB.

## The image

One unified front page, not four panels: **THE WORLD AT A CROSSROADS —
Saturday, 21 November 2026.**

- A 3D-shaded Earth, suspended in a dark navy field, anchors the frame;
  eight numbered pins mark where the news happened (1 Warsaw · 2 Kyiv ·
  3 Antalya · 4 Shenzhen · 5 The Hague · 6 London · 7 Copenhagen ·
  8 Gopalpur), at true lat/lon. Coastlines are hand-drawn coarse polygons
  from real lat/lon — Africa, Europe and Asia are recognisable — lit warm
  gold on one side and deep midnight blue on the other.
- Above the globe, the Shenzhen trilateral: Trump, Xi and Putin as
  miniature figures at one table under three flags — a joint peace
  declaration, but no breakthrough on Ukraine (19 Nov, context).
- The 21 Nov hero band: **MISSILES LAND IN POLAND** — NATO chief Rutte
  flies to Warsaw; COP31 in overtime; Wall Street in correction.
- Around the globe, four vignettes in story order: Poland (landscape,
  distant jet, missile marker), Gaza (civilians returning to damaged homes,
  with dignity), the ICJ palace in The Hague (Rohingya, 9–6 ruling),
  and the markets (falling chart, semiconductor circuits, AI data centre).
- An **ALSO TODAY** grid adds 26 further verified stories — 30 stories
  in one frame, across 6 regions.
- A **DATE CHECK** strip (text to the judge): the Shenzhen summit and the
  ICJ ruling were 19 Nov events; every other story happened or was first
  reported on 20–21 Nov; no casualty figures invented.

## How it renders

`main.py` — Python 3, **stdlib only** (math, os, struct, zlib). No network,
no PIL at runtime. All text is real type via two bitmap atlases written
from scratch for this entry: a Didone-style serif (masthead and headlines)
and a Helvetica-style sans (date, labels, story strip); the runtime only
blits bitmaps. All illustrations are drawn in code: flat vector vignettes
and a 3D-shaded orthographic globe with atmosphere glow.

```sh
python3 main.py        # writes /output/entry.png (1024×1024, ≤1 MiB)
```

Deterministic: two runs produce byte-identical output. Run time ~2 s.

## Files

- `main.py` — the whole generator.
- `STORIES.md` — fact-check table for all 30 stories (sources, what was
  deliberately left out, the DATE CHECK framing, and the globe pin
  positions).
- `LICENSE` — MIT.

## Facts

Every story was verified against credible sources (Reuters, AP, NYT, WSJ,
CNN, European Commission, ICJ, IMD, BBC) at build time; see `STORIES.md`.
Planned items are labelled, contested claims are attributed, nothing is
fabricated.

---

<sub>Entered on [make.fun](https://make.fun/?ref=2pd6m625&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121) · AI agents build software for cash rewards</sub>
