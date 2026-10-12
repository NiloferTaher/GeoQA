# GIS Data Quality: Economic Impact and Cost-Benefit Sources

Working reference notes for GeoQA's financial-impact and operational-cost
modules. Compiled 2026-10-11 from web search.

**Status: leads, not yet verified.** Every figure below was returned by a web
search and is recorded with its claim, not yet checked against the primary
document. Before any of these numbers appear in a manuscript, conference paper,
or funding application, open the source and confirm the exact wording, year,
and denominator. Do not cite from this file directly.

---

## Why this file exists

The user asked whether GIS data-quality defects are already known to carry a
real economic cost. They are. The cost side of the literature is mature; what
is missing is per-finding measurement. That gap is GeoQA's opening, and it is
recorded here so the argument is not rebuilt from scratch each time.

---

## 1. EPRI — Electric Power Research Institute

### "Monetizing the GIS: The Value of GIS Data Quality for Electric Utilities"

The single most important source found. States, in substance, that a tolerable
level of error may be economically optimal, and that **that level is not
known**.

Consequences for GeoQA:

- An accuracy target is an economic decision, not a data-cleaning decision.
- The industry publishes cost curves but admits it cannot locate an operator
  on them. That is precisely what a calibrated per-finding confidence score
  would supply.
- The "optimal zone of accuracy" is U-shaped: at very low accuracy the early
  improvement steps do not make the database usable (negative marginal value);
  at very high accuracy the cost of hunting rare errors exceeds the marginal
  value. This is the empirical form of the user's own intuition.

Reported survey figures (verify before use):

| Finding | Value |
|---|---|
| Witnessed significant benefits from high-quality data | 46% |
| Experienced significant repercussions from poor data | 15% |
| Operate a data-improvement programme | 69% |
| Staffed a dedicated team for it | 54% |

The gap between 69% running a programme and 54% staffing one is a useful
argument for making quality assurance a tool rather than a headcount.

Cost vectors named: increased crew time, increased truck rolls, longer outage
durations, wrong materials delivered to the job site.

### "GIS Leading Practices Guidebook: Data Cleanup Methods with Cost-benefit Analysis Guidance"

Companion volume, more operational.
`https://restservice.epri.com/publicdownload/000000003002010509/0/Product`

Licence: to be confirmed before any figure is reproduced.

---

## 2. EBMUD — East Bay Municipal Utility District

Utility case study using Esri's ArcGIS Data Reviewer tool. The closest published
analogue to what GeoQA's endpoint triage does, and therefore a natural
benchmark for a paper.

Reported before/after error counts (verify):

| Error class | Before | After |
|---|---|---|
| Undershoot / overshoot | 2,400 | 400 |
| Crossings | 490 | 6 |
| Not split at tee | 2,100 | 30 |
| Share of errors corrected | — | ~80% over 6 months |

---

## 3. Metje et al. — Birmingham, UK

Buried-utility strike study.

- In **84%** of strikes where a utility appeared on the plans, it was
  **inaccurately plotted**. This is the strongest single argument that a
  correct-but-imprecise feature is still a defect.
- Direct strike cost: roughly **GBP 300** (water) to **GBP 2,800** (fibre).
- Total true cost estimated at roughly **30x direct cost** once consequential
  costs are counted. Any GeoQA cost model must make that multiplier explicit.

---

## 4. Return-on-investment studies

| Source | Reported ROI |
|---|---|
| UK Geospatial Commission, NUAR | GBP 30 per GBP 1 |
| US DOT / Purdue (1999) | USD 4.62 per USD 1 |
| PennDOT / Penn State (2007) | USD 21 per USD 1 |

UK strikes are reported at roughly **GBP 2.4bn per year**.

Caution: these are programme-level ROIs for geospatial infrastructure, not
marginal returns to fixing one specific defect class. Do not present them as
the latter.

---

## 5. Analyst-time evidence

### New York City — American Community Survey

Analysts spent roughly **80%** of their time searching, validating and
formatting data, and about **20%** analysing it. Supports an automation
argument, not a defect-cost argument.

### IBM

Poor data quality attributed to the US economy at roughly **USD 3.1 trillion
per year**. Widely quoted and widely criticised as methodologically opaque.
Treat as a framing device only; never as a citable measurement.

---

## 6. What the literature does *not* contain

This is the defensible gap:

1. **Every source counts defects. None assigns a probability that any single
   finding is genuine.** Counts cannot be traded against the cost of
   investigating them.
2. **None calibrates against outcomes.** Nobody reports which findings were
   later confirmed false.
3. **EPRI explicitly says the optimal accuracy level is unknown.**
4. **No source links a specific defect class to a specific cost model** with
   parameters a user can change.

GeoQA's contribution is therefore the measurement layer, not the cost curves:
per-finding confidence, calibrated against outcomes, feeding a cost model with
user-supplied parameters.

---

## 7. Consequence for the GeoQA cost module

Design commitments that follow from this reading:

- **All costs are parameters.** No baked-in currency, rates, or multipliers.
  EPRI's cost vectors and Metje's 30x multiplier become named defaults the
  caller overrides, each carrying its source.
- **Always report the multiplier explicitly.** Direct cost versus total
  consequential cost is the difference between a defensible and an indefensible
  number.
- **Confidence must gate cost.** A critical finding that is 20% likely to be
  genuine must not be priced like a certain one.
- **Separate "worth fixing" from "cheap to fix".** The U-shaped curve implies
  an interior optimum, which is only identifiable if severity, confidence and
  repair cost are all available together.

---

## Source list to verify

| # | Source | Status |
|---|---|---|
| 1 | EPRI, *Monetizing the GIS* | Not yet opened |
| 2 | EPRI, *GIS Leading Practices Guidebook* | Not yet opened |
| 3 | EBMUD / Esri Data Reviewer case study | Not yet opened |
| 4 | Metje et al., Birmingham utility strikes | Not yet opened |
| 5 | UK Geospatial Commission, NUAR | Not yet opened |
| 6 | US DOT (1999), PennDOT / PSU (2007) | Not yet opened |
| 7 | NYC American Community Survey workflow study | Not yet opened |
| 8 | IBM cost-of-poor-data estimate | Not yet opened; treat sceptically |

Next action: retrieve items 1–5 in full, record exact quotations with page
numbers, confirm licences, then write the parameter schema.