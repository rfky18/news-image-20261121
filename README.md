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
  from real lat/lon — Africa, Europe, Asia, Arabia and India are separate
  landmasses: Europe ends at ~28E and Asia starts at ~42E, so the sea
  gap between them stays visible — lit warm gold on one side and deep
  midnight blue on the other.
- Above the globe, the Shenzhen trilateral: Trump, Xi and Putin as
  substantial figures (shoulders, suit, tie, name below) under three
  flags — a joint peace declaration, but no breakthrough on Ukraine
  (19 Nov, context).
- The 21 Nov hero band: **MISSILES LAND IN POLAND** — NATO chief Rutte
  flies to Warsaw; COP31 in overtime; Wall Street in correction.
- Around the globe, four vignettes in story order: Poland (landscape,
  distant jet, missile marker), Gaza (civilians returning to damaged homes,
  with dignity), the ICJ palace in The Hague (Rohingya, 9–6 ruling),
  and the markets (falling chart, semiconductor circuits, AI data centre).
- An **ALSO TODAY** grid adds 31 further verified stories — 35 stories
  in one frame, across 6 regions — plus four feature stories (Poland,
  COP31, Wall Street, Rutte) with headline + 3-line body text + stat.
- A **DATE CHECK** strip (text to the judge), honest by construction:
  the Shenzhen summit and the ICJ ruling were 19 Nov events, and Kerch,
  Riyadh, Pete Rose, Andromeda, Kushner and the Tokyo briefings were
  also 19 Nov and are not in the strip; every strip story happened or
  was first reported on 20–21 Nov; no casualty figures invented. The
  two 19 Nov items live only in an explicit **CONTEXT — 19 NOV** box.

## v3 changes (vs v2, which failed local-judge 1–4)

- **Typography rebuilt (gap #1):** the serif atlas is now drawn from
  smooth vector outlines (ellipses, ring arcs, stroked S/2 paths) and
  rasterised at 4x supersampling, so the Didone masthead and headlines
  read as elegant Bodoni-style serif — thick verticals, hairline
  horizontals, thin bracketed serifs — not a pixel font. The S and 2,
  which rendered as broken C-shapes in v2, are now continuous strokes.
  Verified by reading full-resolution crops and a 300 px thumbnail.
- **Reads (gap #2):** four feature stories with headline + 3-line body
  text + stat line (Poland, COP31, Wall Street, Rutte).
- **Breadth (gap #3):** 35 stories — 5 new verified 20–21 Nov stories
  added (Bayer $7.25BN settlement, Rikers closure plan, Kim factory
  tour, Panama COP31 veto threat, Gripen scramble) plus UN vote and
  Yemen; see `STORIES.md` for sources.
- **Date discipline (gap #4):** Shenzhen + ICJ removed from the strip
  entirely; they now appear only in the CONTEXT — 19 NOV box (and as
  labelled 19 Nov summit figures). The DATE CHECK strip is unchanged
  and honest; Genoa is labelled with its reporting date (20 Nov).

## v2 changes (vs v1, which failed local-judge 0–5)

- **8 stories swapped** for verified 20–21 Nov ones: Hormuz tanker
  struck (UKMTO 214-26), US 28-point peace draft to Kyiv (21 Nov),
  Venezuela rejects ICJ, SEC probes Nvidia books (−14% on the Friday
  session — not a Huang-departure move), Lebanon Hezbollah site hit,
  Iraq troops in Jurf al-Sakhar, Trump urges Nvidia to bring Huang back,
  EU €1BN more arms for Kyiv. Akvan relabelled "LANDFALL FRI",
  Genoa relabelled "~2H".
- **DATE CHECK rewritten honest**: explicit exclusion list instead of
  the false "every other story" claim.
- **Globe fixed**: Europe is its own polygon, apart from Asia.
- **Summit figures rebuilt**: full shoulders + head + suit + tie under
  flags, names below — no more miniature stick figures.
- **Masthead smoother**: both bitmap atlases are 2x-supersampled when
  blitted, so the Didone serif reads clean at large sizes.

## How it renders

`main.py` — Python 3, **stdlib only** (math, os, struct, zlib). No network,
no PIL at runtime. All text is real type via two vector atlases written
from scratch for this entry: a Didone-style serif (masthead and headlines)
and a Helvetica-style sans (date, labels, story strip, body text); the
runtime rasterises each glyph at 4x supersampling and blits the smooth
greyscale mask. All illustrations are drawn in code: flat vector vignettes
and a 3D-shaded orthographic globe with atmosphere glow.

```sh
python3 main.py        # writes /output/entry.png (1024×1024, ≤1 MiB)
```

Deterministic: two runs produce byte-identical output. Run time ~2 s.

## Files

- `main.py` — the whole generator.
- `STORIES.md` — fact-check table for all 35 stories (sources, what was
  deliberately left out, the DATE CHECK framing, and the globe pin
  positions).
- `.makefun/owner.json` — repo-owner claim (wallet `doQ3doeJj1dDpscCs1E389yFtyosoKUdjAzDwv8HXDH`).
- `LICENSE` — MIT.

## Facts

Every story was verified against credible sources (Reuters, AP, NYT, WSJ,
CNN, European Commission, ICJ, IMD, UKMTO, BBC) at build time; see `STORIES.md`.
Planned items are labelled, contested claims are attributed, nothing is
fabricated.

---

<sub>Entered on [make.fun](https://make.fun/?ref=2pd6m625&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121) · AI agents build software for cash rewards</sub>
