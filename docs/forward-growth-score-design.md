# Forward Growth Score (FGS) — Design & Data‑Availability Audit

Status: **DESIGN / SCOPING** (not yet implemented)
Owner: ATLAS scoring
Related: F2 Earnings Quality, F4 Options Flow, F5 Fundamental Quality, Extension Overlay, Section 8 Bottleneck Roadmap

---

## 1. Why FGS exists

F5 measures **survivability / durability** ("can this company survive and compound?").
It is deliberately **price‑blind** and backward/− present‑looking. That means F5
structurally *under‑scores* high‑flyers whose thesis is in the future (CRDO, LITE,
NBIS, CRWV, RKLB, OKLO, AXTI, POET, …) because their current FCF / earnings / margins
don't yet reflect the growth.

FGS is a **separate parallel axis** that answers a different question:

> "Can this company grow much faster than the market expects if the thesis works?"

**Hard rules (locked design):**
- FGS is **displayed alongside** the ATLAS score, **NOT blended** into the raw
  0–100 ATLAS number. Blending would make fragile names (OKLO, POET, NBIS) look
  safer than they are.
- **No valuation** in FGS (that lives in the Entry Overlay).
- **No options flow / dark pool** in FGS (that is F4 — avoid double‑counting).
- **No price/RSI/extension** in FGS (that is the Entry Overlay).
- F5 stays **price‑blind survivability**; FGS stays **forward fundamental growth**;
  F4 stays **live money confirmation**; Entry Overlay stays **valuation + timing**.

---

## 2. FGS sub‑factors (each 20%, 0–100 → composite 0–100)

| # | Sub‑factor | Captures |
|---|---|---|
| G1 | Revenue acceleration / guide raises | YoY growth, sequential acceleration (2nd derivative), guidance raises |
| G2 | Backlog / bookings / sold‑out capacity | Contracted/committed demand, "sold out", design wins, bookings |
| G3 | Customer quality | Named hyperscaler / blue‑chip exposure (NVDA, hyperscalers, TSM, defense) |
| G4 | Product ramp / inflection | HBM4, CPO, 1.6T, CoWoS, AI servers, new‑product ramps at inflection |
| G5 | TAM expansion / bottleneck status | Is this layer becoming scarce / mission‑critical? (Section 8 wave) |

Composite `FGS = Σ(Gi × 0.20)`, clamped [0, 100]. Missing sub‑factors score a
**neutral 50** (DATA_GAP) rather than 0, so an un‑instrumented input can't tank the
score — and every gap is surfaced in a `data_gaps` list (same pattern as F5/Extension).

---

## 3. Data‑availability audit (against current feeds)

Current providers actually ingested: **Polygon, Unusual Whales, Alpha Vantage,
Yahoo (VIX/Brent only), FMP (transcripts/calendar), sec‑api.io + sec.gov, Benzinga.**

| Sub‑factor | Best available source | Status | Gap / work needed |
|---|---|---|---|
| **G1 Revenue accel** | Alpha Vantage `INCOME_STATEMENT` (quarterly revenue — **already fetched** for F2/F5) | 🟢 **Automatable now** | Compute YoY + sequential‑acceleration from existing quarterly revenue. Guide‑raise signal: reuse F2's guidance assessment + AV `EARNINGS_CALENDAR` estimates (partial). |
| **G2 Backlog / sold‑out** | 10‑Q/10‑K MD&A (sec‑api), FMP earnings transcripts | 🔴 **Not structured** | No structured backlog field anywhere. Requires NLP over filings/transcripts (a V2 "emergence"‑style engine) **or** operator/manual input. |
| **G3 Customer quality** | Customer concentration in 10‑K (sec‑api); named customers in filings/transcripts | 🟠 **Partial** | NB: customer concentration is in the **spec** but **not implemented** in live F5 today. Named‑hyperscaler quality needs NLP **or** a curated customer→tier map. |
| **G4 Product ramp** | Transcripts (FMP), news | 🔴 **Not structured** | Qualitative keyword/theme detection (HBM4, CPO, 1.6T…). NLP **or** manual. |
| **G5 TAM / bottleneck** | Section 8 Bottleneck Roadmap (internal, curated) | 🟠 **Curated** | Map ticker → cluster → wave (GPU/Memory/Optics/Power/Grid/Custom‑Si) and score wave scarcity. Best as a maintained lookup table, refreshed periodically. |

**Bottom line:** only **G1** is reliably computable from structured data we already
have. **G2 and G4** need NLP or manual input. **G3** is partial. **G5** is a curated
table. A fully‑automated FGS is **not feasible** with current feeds — the realistic
design is a **hybrid**: automate what we can, accept operator/curated inputs for the
qualitative axes (same precedent as the Geopolitical flag and the F8 conviction
criteria, which are already operator‑set).

---

## 4. Proposed computation: hybrid engine

```
FGS sub‑scores:
  G1 revenue_acceleration   ← AUTO   (Alpha Vantage quarterly revenue + F2 guidance)
  G2 backlog_bookings       ← MANUAL (operator 0–100, default 50/DATA_GAP) → Phase 2 NLP
  G3 customer_quality       ← HYBRID (auto concentration + curated customer tier)
  G4 product_ramp           ← MANUAL (operator 0–100, default 50/DATA_GAP) → Phase 2 NLP
  G5 tam_bottleneck         ← CURATED (ticker→wave lookup, Section 8)
```

Response shape (sketch, mirrors existing factor responses):

```jsonc
{
  "ticker": "CRDO",
  "fgs_score": 92,
  "fgs_grade": "ELITE",            // ELITE | HIGH | MODERATE | LOW
  "revenue_acceleration": { "score": 95, "yoy_pct": 154.0, "accelerating": true, "source": "alpha_vantage" },
  "backlog_bookings":     { "score": 50, "source": "DATA_GAP" },
  "customer_quality":     { "score": 88, "concentration_pct": 0.38, "named_tier": "HYPERSCALER", "source": "curated" },
  "product_ramp":         { "score": 50, "source": "DATA_GAP" },
  "tam_bottleneck":       { "score": 100, "wave": "Optics/CPO", "status": "ACTIVE", "source": "curated" },
  "data_gaps": ["BACKLOG_BOOKINGS", "PRODUCT_RAMP"]
}
```

Endpoint: `GET /api/v1/forward-growth/{ticker}` → `ForwardGrowthResponse`.
Manual/curated inputs persisted in `atlas_config` or a small `fgs_inputs` table
(append‑only, operator‑editable), exactly like the existing runtime‑editable config.

---

## 5. The F5 × FGS × F4 action matrix (the payoff)

FGS is only useful paired with F5 (quality) and F4 (live confirmation). Displayed as
a **bucket**, never folded into the raw ATLAS number.

| Bucket | F5 | FGS | F4 | Meaning | Action |
|---|---|---|---|---|---|
| **Core compounder** | High | High | Confirming | Best names | Add on pullbacks |
| **Quality hold** | High | Low/Med | Mixed | Good co., less upside | Hold |
| **Growth tactical** | Low/Med | High | Confirming | High‑flyer potential | Small size / tactical |
| **Story risk** | Low | High | Not confirming | Tempting but dangerous | Watch only |
| **Avoid** | Low | Low | Weak | No edge | Avoid |

**Final‑action logic (proposed):**
```
ATLAS ≥ 85 AND FGS ≥ 80                  → Core add candidate
ATLAS ≥ 75 AND FGS ≥ 85 AND F4 confirms  → Growth add candidate
FGS ≥ 85 AND F5 < 70                      → Tactical / spec only, size‑capped
F5 < 60 AND F4 weak                       → Avoid (regardless of story)
```

**High‑Growth Exception Rule** (so we don't miss high‑flyers): a name may enter the
watch/add queue even with non‑elite F5 if ≥ 4 of 6 hold — revenue accelerating,
guidance raised, backlog/design‑wins improving, named blue‑chip customer, positive
accumulation (F4), positive options flow (F4) — **but** cannot be core‑sized unless
F5 ≥ 70 or cash runway is strong.

---

## 6. Display

Per‑ticker card:
```
ATLAS Score: 84 / T1
F5 Quality:        80
Forward Growth:    92
Flow (F4):         Bullish
Entry Risk:        Extended
Bucket:            Growth Add — wait for pullback
```

---

## 7. Phased implementation plan

- **Phase 1 — automatable now (no new feeds):**
  - G1 revenue acceleration from Alpha Vantage quarterly revenue (+ reuse F2 guidance).
  - G5 TAM/bottleneck curated lookup (Section 8 waves).
  - FGS scaffolding (service, schema, endpoint, frontend axis) with G2/G3/G4 defaulting
    to neutral‑50/DATA_GAP and operator‑override fields.
  - F5 × FGS × F4 **action‑matrix / bucket** computation + display.
- **Phase 2 — NLP engine (new capability, mirrors spec V2 "Bottleneck Emergence"):**
  - G2 backlog/sold‑out + G4 product‑ramp keyword extraction from FMP transcripts and
    sec‑api filings; G3 named‑customer extraction.
- **Phase 3 — curation & tuning:**
  - Maintain the customer‑tier and TAM/bottleneck tables; calibrate bands against
    realized outcomes.

---

## 8. Open decisions for the operator

1. **Manual inputs OK?** Phase 1 needs operator‑set scores for backlog (G2) and
   product‑ramp (G4). Acceptable (like the Geopolitical flag / F8 criteria), or wait
   for the Phase‑2 NLP engine before shipping FGS at all?
2. **FGS as F6, or unscored overlay?** Locked design says *do not* blend into raw
   ATLAS. Confirm FGS stays a parallel display + action‑matrix input only.
3. **G1 guide‑raise signal:** reuse F2's existing guidance assessment, or build a
   dedicated estimate‑revision tracker (AV `EARNINGS_CALENDAR`)?
4. **Customer concentration:** implement it (currently spec‑only, not in live F5) as
   part of G3, and/or also add it to F5 cyclicality?
