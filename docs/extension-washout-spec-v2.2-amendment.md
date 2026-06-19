# ATLAS SPEC v2.2 — Additive Amendment: F4 Rename + Equity-Accumulation Firewall

**Status:** APPROVED — implemented.
**Scope:** F4 scoring label + the F4a/F4b firewall. Additive amendment to SPEC v2 / v2.1.
**Does NOT change:** F4 math, the 15% weight, F1–F5, the Extension & Washout Overlay
state machine, or Overshoot Elasticity (v2.1). This is a relabel + a display/firewall
correction, plus the formal home for equity accumulation as an overlay flag.

---

## 0. Read this first

The hypothesis that triggered this amendment: *equity accumulation is an independent
flow signal that options flow misses, and should be folded into the F4 weight.*

The data says no. So v2.2 does two things:
1. **Renames F4** to what it actually is — **Options Flow Persistence** — so it stops
   over-claiming to be "institutional flow."
2. **Firewalls equity accumulation (F4a) out of the score** and gives it its correct
   home: an **overlay confirmation / absorption-divergence flag**, never a score input.

---

## 1. The finding (why equity accumulation does not earn a score weight)

Close-to-close / volume-proxy study on the working sample:

| Test | Result | Reading |
| --- | --- | --- |
| corr(EquityAccum, 21d momentum) | **+0.62** | strongly collinear with momentum |
| Incremental R² adding EquityAccum to a momentum+vol regression | **+0.0000** | adds nothing |
| Its coefficient in that regression | **≈ 0 (slightly negative)** | no independent signal |
| Quintile spread Q5−Q1 on 20d fwd return | **+0.4 pts** | flat |

**Conclusion:** the equity-accumulation proxy is *momentum wearing a flow costume*.
Momentum is already F1. Folding EquityAccum into the 15% F4 weight would **double-count
momentum under a "flow" label** and manufacture a fake independent factor — the exact
failure mode the methodology forbids. On this sample it barely predicts at all.

**What the study DID find worth keeping (overlay material, not score material):**
- **29%** of high-accumulation states had **negative** forward 20d returns — concentrated
  in DesignGPU / Power / DesignIP (**33–35%**). That's "the tape shows accumulation but
  price won't follow" → the **absorption / distribution warning** (the June-9 MU lesson:
  ~$790M absorbed, closed −7.9%).
- Mildly useful as **confirmation**: high-accum states had a better hit-rate (**71% vs
  62%**) and shallower drawdowns — so it can *confirm* an entry the ATLAS score already
  justifies, **never generate one**.

---

## 2. Resolution

### 2.1 Scored layer — F4 stays options-only, renamed
- **F4 = "Options Flow Persistence"** (a.k.a. Derivatives Positioning Persistence).
- 15% weight unchanged; math unchanged (time-decayed options net flow over 5 sessions,
  the SPEC v2 "résumé" redesign).
- Equity accumulation **does not enter the score.**

### 2.2 F4a vs F4b
| Stream | Role | Home |
| --- | --- | --- |
| **F4b** — options flow | the **scored** 15% factor | F4 score |
| **F4a** — equity / dark-pool accumulation | **overlay confirmation + absorption-divergence flag** (not a level, not a buy-weight) | Extension & Washout Overlay + F4 panel overlay lane |

### 2.3 Overlay layer (F4a) behaviour
- **Divergence flag**, not a level: "accumulation present but price not following →
  distribution warning." This is the existing **absorption flag** (§4 of the overlay:
  extreme extension + aggressive DP buying + no price follow-through) plus the
  **dark-pool state chips** (Fresh / Persistent Accumulation / Fading / Active
  Distribution).
- **Confirm-only positive use:** may confirm an entry the score already justifies; may
  **never** generate one.

### 2.4 Display firewall
The dashboard must not show F4a and F4b as if both feed F4:
- **F4b** is tagged **scored** (shows /100).
- **F4a** is tagged **overlay · not scored** (no /100 score framing).
- An explicit firewall note states F4 scores options only.

---

## 3. Implementation status (code map)

| Item | Where | Status |
| --- | --- | --- |
| F4 factor label → "Options Flow Persistence" | `backend/.../services/framework_score_service.py` (`F4 Options Flow Persistence`, factor tuple) | ✅ |
| F4 panel title rename | `frontend/.../frameworks/f4-options-panel.tsx` | ✅ |
| F4b tagged scored (/100) | `f4-options-panel.tsx` → `Options Flow (F4b · scored)` | ✅ |
| F4a tagged overlay · not scored (no /100) | `f4-options-panel.tsx` → `Dark Pool · Equity Accum (F4a)` | ✅ |
| Firewall note on panel | `f4-options-panel.tsx` (`data-testid="f4-firewall-note"`) | ✅ |
| F4 score = options-only (equity accum excluded) | `services/options_flow_service.py` (SPEC v2 redesign) | ✅ |
| Absorption / distribution-divergence flag | `core/extension_washout.py` (`absorption`, §4) + chips | ✅ |
| Confirm-only (never generates a buy) | overlay `clearance` never emits BUY; F4a not in score | ✅ |

---

## 4. Dev checklist (panel)

- [x] F4 panel header reads "F4 Options Flow Persistence".
- [x] Options sub-card labeled `(F4b · scored)`, shows /100.
- [x] Dark-pool/equity-accum sub-card labeled `(F4a)`, shows `overlay · not scored`
      (no /100), net flow shown as overlay context only.
- [x] Firewall note rendered explaining F4 scores options only.
- [x] Dark-pool state chip (F4a) presented in the overlay lane, not as a score input.
- [ ] (Future) When real options-premium + institutional-flow feeds exist, re-run the
      net-of-options test before reconsidering any score weight for equity accumulation.

---

## 5. The one genuinely open question

The *true* net-of-options test needs **real historical options premium** and **real
institutional flow** — both currently **DATA_GAP**. Until those feeds exist, equity
accumulation cannot earn its way into the score even in principle, because step one is
"beat momentum," and it doesn't.

So **overlay-only is not a temporary parking spot** — given the data we can actually get,
it is the correct home.

---

*Amendment authored from the v2.2 finding; mirrors the v2.1 (Overshoot Elasticity)
amendment structure. Internal framework specification — not investment advice.*

---

## 6. Ali Ticket Addendum — F4b Universe Governance + DRAM Treatment

### 6.1 Official framing for audit responses

Use this exact language in reviews and incident notes:

**The formula is likely reproducing the app's selected universe. The unresolved issue is whether that selected universe is appropriate for official F4b scoring.**

This avoids over-claiming "confirmed good" when the core dispute is universe construction.

### 6.2 F4b universe-construction policy (alerts vs tape)

If `UW_ALERTS_2_SESSION` remains the official F4b scoring universe, it must be deduped
before scoring to reduce repeated-hit cluster overweight.

Dedup key (minimum):
- ticker
- expiry
- strike
- option type
- side
- price band
- short time window

Diagnostic transparency must expose all three side by side:
- raw-alert bull share
- dedup-alert bull share
- full-tape bull share

If official scoring later migrates to full tape, keep alert-based shares as secondary
diagnostics only.

### 6.3 Coverage mismatch warning

When F4b uses a 2-session options window while F4a dark-pool coverage spans only 1 of 2
sessions, surface an explicit coverage-warning badge/message. This is a confidence warning,
not a formula override.

### 6.4 DRAM instrument treatment

DRAM is a real ETF/fund instrument, not a dead symbol and not an operating company.
Do not run DRAM through the normal equity F1-F5 engine.

Treat DRAM as:
- memory/HBM proxy exposure
- lower-confidence ETF flow pulse for F4
- portfolio overlap risk with existing memory names

Current action posture under extreme extension:
- no fresh add
- hold small only
- protect / wait for reset

### 6.5 Portfolio overlap rule (required)

ETF/fund instruments must map holdings/exposure back to existing portfolio clusters.
For DRAM, count overlap into the Memory/HBM cluster and MU/SNDK/Samsung/SK Hynix exposure.
Do not treat DRAM as independent diversification.

### 6.6 ETF F4 rule (required)

ETF/fund options flow is hedge/overlay-heavy and lower-confidence.
It may be displayed as a pulse, but must not satisfy an add gate by itself.

### 6.7 Leveraged ETF rule (required)

If a leveraged DRAM-linked product appears:
- tag separately as leveraged fund exposure
- do not run through standard equity scoring
- apply dedicated leveraged-product controls
