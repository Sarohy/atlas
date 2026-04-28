@AGENTS.md
AGENTIC AI TRADING SYSTEM
Architecture, Build Specification & Operational Framework
Version 7.3.3 FINAL — ATLAS Complete Edition (Developer-Ready)
April 2026


DOCUMENT STATUS — VERSION 7.0
Version 7.3.3 supersedes v7.3.2. It incorporates all 21 findings from the Opus 4.7 adversarial audit of v7.0, with all 8 open decisions resolved via 12-month historical backtest against actual portfolio names. CRITICAL FIXES: (1) SOFT CAUTION cash floor corrected from 17-18% to 15% — the 17% floor produced a $9K non-functional GTC window; (2) Aggregate GTC calculation overhauled — deep-OTM GTCs now exempt, 1.1x buffer multiplier added; (3) Grey zone narrowed from 75-85 to 78-85 — backtest showed MRVL and CRDO (both scored 75-78) were high-conviction adds that should not require 3-AI consensus; (4) SOX filter changed to dual trigger — original -8%/10d threshold missed the DeepSeek event it was designed to catch; (5) Framework #29 AND gate added for Tranche 3 — March 23 fake-CLEAR event proved AND gate saves $18K vs false deployment; (6) Framework #30 LEAPS carve-out added — drawdown gate was blocking best washout entries (MRVL at $80, VRT at $230); (7) Exit rules classified as Precedence Level 2; (8) Score authority explicitly defined (5-factor governs daily, 12-factor quarterly only). All 21 Opus findings addressed.


Read This Section First If You Are...
Section
A developer receiving this document for the first time
Start with Section 1 (Vision), then Section 4.4 (Precedence of Truth), then Section 10.0 (Milestone Gate Zero). These three sections define the philosophy, governing logic, and first deliverable.
Building V1
Sections 4 and 2.1 are your primary references. Section 4.4 (Precedence of Truth) is the architecture constraint governing every node.
Building V2
Section 5 covers V2 intelligence upgrades. Bottleneck Emergence Engine (5.1) and Red Team Agent (5.4b) are the two most complex components.
Building V3
Section 6 covers autonomy upgrades. Bayesian tuner (6.1) and Walk-Forward Loop (6.7) are the self-improvement core.
The portfolio owner reviewing operating rules
Section 13 (ATLAS Conviction Scoring), Section 14 (Regime Modifier), Section 15 (Bucket Rules), Section 16 (Exit Rules), and Section 17 (LEAPS Framework) are your primary references.
Evaluating whether you can build this system
Section 9 (Acceptance Tests) defines done. Section 11 (Hour Estimates) gives scope. Section 10 (Contract) defines the gates.



Section 1: Vision and Philosophy
1.1 The Three Tiers of Trading Systems
A good system has rules. A great system has rules with context — it knows when the rules apply and when the market has changed the game. An elite system is proactive. It detects regime changes before they fully materialize, identifies bottleneck shifts before they are consensus, and sizes positions not just by conviction but by the precise intersection of catalyst proximity, macro risk, and portfolio correlation.
This specification is a blueprint for an elite system built for one purpose: helping a single personal investor compound their way to a long-term wealth target by detecting each successive AI infrastructure bottleneck before it becomes consensus — and protecting that capital when the frameworks say the risk is too high. The system's authority derives from one document within this specification: the Precedence of Truth hierarchy in Section 4.4. Every agent, every framework, and every human override ultimately answers to that hierarchy.

1.2 What This System Is — And What It Is Not
This system IS
This system is NOT
A personal investing engine for one operator managing their own capital
An institutional system for managing other people's money
Designed to scale from any starting NAV using percentage-based logic
Hardcoded to specific dollar amounts or current portfolio values
Built to protect against market risk, data risk, and human behavioral risk
Built to satisfy regulatory requirements, compliance audits, or 13F obligations
An agentic system that makes recommendations and blocks harmful actions
A fully autonomous system that executes without human awareness
Designed to compound genuine edge from bottleneck detection over multiple years
Designed for high-frequency trading, arbitrage, or short-term speculation
Honest about what belongs in a personal system vs. institutional theater
A spec that includes everything because more always seems better


1.3 The Three-Phase Strategy
Phase
Scope
Outcome
Phase 1 (V1)
Core infrastructure: data ingestion, 12-factor model, 32-framework risk engine, LangGraph orchestration, validation layer, frontend briefing system
A system that produces a daily briefing indistinguishable from the work of a full-time analyst — and is auditable at every step
Phase 2 (V2)
Intelligence upgrades: Bottleneck Emergence Engine, Earnings Quality Engine, Sector Rotation Monitor, Correlation Cluster Manager, Rate Sensitivity Map, NLP earnings call analysis, Red Team Agent
A system that detects the next wave before the market does and automatically adjusts weights before the move
Phase 3 (V3)
Autonomy upgrades: Bayesian weight auto-tuner, Vector DB with institutional memory, Monte Carlo stress testing, Human-in-the-loop escalation protocols, Smart Execution Agent, Walk-Forward Optimization
A system that learns from every decision, stress-tests against historical regimes, and executes with institutional-grade discipline



Section 2: The Complete Framework Engine — 32 Frameworks
The original 19 frameworks have been expanded to 32 across six design sessions. The additions reflect real stress-testing during the March 2026 Iran/Hormuz crisis, 3-AI consensus gap analysis, and one principle applied to every addition: does this genuinely protect a personal investor managing their own money? All 32 run on every daily briefing cycle.

2.1 Original 19 Frameworks (Updated and Hardened)

#
Framework
Trigger Condition
Action Required
1
VIX Regime Gate
VIX < 18: Bull. 18–24: Caution. 24–30: Crisis. >30: Halt
Tranche size: 100% / 70% / 50% / 0%. No new full positions in Crisis+
2
200-DMA Monitor
S&P closes below 200-DMA for 2 consecutive sessions
Reduce high-beta names 20%. No new positions until reclaim + 2-day hold
3
Oil Price Map
Brent $85–$95: Yellow. $95–$108: Orange. >$108: Red HALT
Red: catalyst-only buys. Trim COPX 20%. No adds to energy-sensitive names
4
Fed Signal Tracker
Language shift: dovish / neutral / hawkish / hike-bias
Hawkish: reduce high-multiple names. Hike-bias: cap P/E >40x names at 3% max
5
Catalyst Proximity
Earnings <14 days, index inclusion, product launch, partnership
No covered calls. No trims. Reduce position size for add — let catalyst play
6
Earnings Beat/Miss
Quarterly print vs. consensus EPS and revenue
Beat + raise: +5 score. Miss + lower: -10 score. Neutral: no change
7
Oil Scenario Router
Brent level determines which portfolio playbook activates
< $85: normal. $85–$108: catalyst-only. >$108: HALT except energy longs
8
3-AI Consensus Gate
Score 78–85 on EITHER the 5-factor ATLAS system OR the 12-factor agentic system = grey zone requiring 2-of-3 AI model confirmation before any ADD signal proceeds. Both systems now use 78-85 — the prior 75-85 range for the 12-factor system was narrowed to match. Backtest validation: names scoring 75–77 (MRVL at $90 entry, CRDO at $80 entry) were high-conviction adds where consensus-gating would have added unnecessary friction. 78-85 is the calibrated threshold on both systems.
Query Claude + Grok + Gemini. Majority rules. Dissent logged with reasoning
9
Position Sizing Protocol
VIX regime × conviction score × proximity to catalyst
Full / 70% / 50% / 25% tranches. Never exceed 8% single position
10
Sector Rotation Radar
When >3 core sectors show 5-day declining relative strength
Shift toward defensive names. Flag rotation in briefing. Reduce momentum names
11
Cash Floor Enforcer
Portfolio cash must remain above the currently-active regime floor per Section 14.1 (CLEAR 8-10%, SOFT CAUTION 15%, CAUTION 20%, CRISIS HALT 30%+). Supersedes prior hardcoded 15% floor.
If cash < regime floor: no new buys until cash restored via sells or distributions
12
Catalyst No-Fly Zone + Section 16 Gatekeeper
Active catalyst event within 7 days on any holding (No-Fly); all new adds must pass Section 16 two-track gatekeeper (Track A core names / Track B satellite names) and Framework 12 Decision Matrix before execution
No covered calls, no partial sells, no trims on affected names within 7-day catalyst window. All buys must clear Section 16 gatekeeper rules and Decision Matrix sizing before execution. High-Conviction Underweight Override may waive Rule 3 for Track A names once per earnings cycle when dark pool ≥$25M OR options flow ≥$3.5M bullish AND allocation <5% NAV or below cluster target. See Section 16 for full Track A / Track B rules and Decision Matrix.
13
Concentration Gate
Single name >8% NAV at market value (soft cap). Single name >10% NAV at market value (hard review). Grandfathering: positions above 8% soft cap at time of v7.2 framework adoption (April 2026) are grandfathered as HOLD — no forced sell, but no new adds. Grandfathered status expires if position grows beyond 125% of its current weight (e.g., MU at 13.6% today → grandfathered status expires if MU reaches 17.0%). Above 125% growth, standard trim rules apply.
Soft cap (8-10%): No new adds. Auto-flag in every briefing. Score is capped at 85 for informational display only. CRITICAL EXCEPTION: score-cap-at-85 does NOT trigger Framework #8 3-AI consensus gate, because the cap does not represent genuine score ambiguity — it represents concentration block. Since no ADD is permitted regardless of consensus outcome, triggering 3-AI consensus on a concentration-blocked name wastes resources and creates false decision signals. The concentration gate blocks adds; no further process is required. Hard review (>10%): Consider trimming 20% — soft rule, discretion applies.
14
Insider Activity Flag
CEO/CFO net sales >0.5% of total holdings in 30-day window, or 3+ consecutive sells
Reduce 12-factor score by 10 points. Add to watchlist. Requires re-confirmation
15
VIX Regime Override
VIX spike >5 points intraday
Pause all non-stop orders. Re-evaluate open limit orders. No new market orders same session
16
Master Sync Check
All 32 frameworks checked for consistency before any signal fires
Framework #16 is the DETECTOR. Section 4.4 Precedence of Truth is the RESOLVER. Framework #16 identifies that a conflict exists and logs it. Section 4.4 resolves it using the 6-level hierarchy (most conservative signal at same level wins). Human review is only triggered when Section 4.4 cannot resolve the conflict (two frameworks at the same Precedence level with equal authority). The two systems are complementary, not redundant.
17
Geopolitical Monitor
Active conflict affecting >5% of global oil/LNG supply or semiconductor supply chain
Activate Supply Chain Contagion Map. Run War Duration Ladder. Elevate oil framework priority
18
4-Week Trend Gate
S&P down 3+ consecutive weeks
Reduce aggressive adds by 50%. Prioritize quality names. No speculative starters
19
NVDA Kill Switch
NVDA falls >4% in <60 minutes during market hours
Pause all AI-correlated buy orders. Re-evaluate holdings with NVDA beta >1.5. Alert required



2.2 New Frameworks #20–32 (Gap-Fill Additions)
Thirteen new frameworks identified through live stress-testing, post-session gap analysis, and the April 2026 Opus 4.7 adversarial audit. None of the original 19 would have changed actions during the March 2026 crisis — but these frameworks address what happens next: how long to stay defensive, when to re-enter, how to detect the next rotation, and how to protect capital from the human operator themselves.

Framework #20 — Fed Language Monitor
Purpose: Track exact language Fed officials use for early signal on policy shifts — before the rate decision.
Inputs: FOMC meeting minutes, Fed governor speeches, Powell press conference transcripts
NLP keyword tracking: 'patient', 'data-dependent', 'restrictive', 'neutral', 'gradual', 'concerned about inflation'
Scoring: 5-point scale from dovish (-2) to hike-bias (+2). Trend over 60 days more important than single reading
Action: Score +1 or higher triggers rate sensitivity review across all holdings >30x forward P/E

Framework #21 — Earnings Quality Engine
Purpose: Distinguish genuine earnings beats from cost-cut beats, margin-compression beats, and guide-down beats that superficially look like good quarters.
Three-factor earnings quality score: Revenue growth direction + Gross margin direction + Guide vs. prior quarter consensus
Quality beat: Revenue up YoY + gross margin flat or expanding + guide raised. Score +5.
Hollow beat: EPS beat but revenue miss or gross margin compression. Score -5 regardless of EPS headline.
Miss: Any combination of EPS miss + revenue miss. Score -10. Requires 12-factor re-score within 24 hours.
Triggered by CRDO March 2026: Record revenue +201% YoY but gross margin guided 64–66% vs. 68.6% prior. Hollow beat. Stock fell 15%.

Framework #22 — Rate Sensitivity / Duration Map
Purpose: Automatically reduce target weights on high-multiple names when the 10-year yield rises.
10-yr Yield
Names >40x fwd P/E
Names 25–40x fwd P/E
Names <25x fwd P/E
< 4.0%
Normal weight targets
Normal weight targets
Normal weight targets
4.0–4.5%
Cap at 5% per name
Normal weight targets
Normal weight targets
4.5–5.0%
Cap at 3.5% per name
Cap at 6% per name
Normal weight targets
> 5.0%
Cap at 2.5% per name
Cap at 4% per name
Normal weight targets


Framework #23 — Correlation Cluster Manager
Purpose: Detect when holdings that appear separate are actually moving as one unit, creating hidden concentration risk.
Cluster definitions: AI Optics (LITE, COHR, CIEN, CRDO), AI Memory (MU, SNDK), AI Custom Silicon (MRVL, AVGO), AI Power/Thermal (VRT, ETN, NVT, GEV), Energy/Nuclear (CEG), Defense/Infrastructure (ATI, STRL, CLS, TTMI)
Gate: Any single cluster >25% of total portfolio → flag in briefing. >30% → auto-reduce lowest-conviction name in cluster by 20%.
Correlation refresh: Weekly recalculation using 60-day rolling correlations. Cluster membership can shift.

Framework #24 — Sector Rotation Early Warning
Purpose: Detect institutional rotation out of AI infrastructure before it shows up in individual stock prices.
5 input signals monitored weekly:
SMH/SOXX put/call ratio 5-day trend
Short interest change in top 5 AI infrastructure holdings
AI ETF (BOTZ, ROBO, AIQ) weekly fund flow direction
Hyperscaler capex language in earnings calls — NLP keyword velocity on 'moderate'/'optimize' vs. 'accelerate'/'expand'
Analyst price target revision direction across AI infrastructure universe — net upgrades vs. downgrades
Signal threshold: 3 of 5 signals turning negative within same 7-day window = Rotation Warning
Action on Rotation Warning: Reduce highest-beta AI names by 15%. Increase cash target by 5%. Add defensive hedge.

Framework #25 — Liquidity-Adjusted Execution Protocol
Purpose: Prevent execution slippage on low-volume names during high-VIX sessions.
ADV (20-day)
VIX < 18
VIX 18–24
VIX > 24
> $100M
Market orders OK
Limit orders preferred
Limit orders only
$50M–$100M
Limit orders preferred
Limit orders only
50% max tranche + limit
< $50M
Limit orders only
50% max tranche
25% max tranche + limit

Affected holdings requiring special handling: NBIS, CRDO, TTMI — all require limit orders in any VIX environment above 18

Framework #26 — Management Credibility Score
Purpose: Build a rolling track record for each holding's management team that feeds directly into the 12-factor score.
Tracked metrics per quarter: Guidance accuracy, buyback execution rate, capex commitment vs. actual, insider buying vs. selling net trend
Scoring: 4 quarters rolling. Each quarter: +1 for beat guidance, 0 for meet, -1 for miss. Maximum +4, minimum -4.
Score feeds into Factor #6 (Management Execution) of the 12-factor model as a modifier: +4 adds 5 points, -4 subtracts 8 points

Framework #27 — Supply Chain Contagion Map
Purpose: For each holding, maintain a secondary exposure flag checked automatically when a geopolitical or macro event fires.
Holding
Primary Risk
Secondary Exposure
Contagion Trigger
TSM
Taiwan military risk
Helium via Strait of Hormuz (~45% of global helium transits)
Hormuz closure >14 days → flag TSM fab supply risk
MU
DRAM/HBM cycle
HBM packaging in Korea, NAND in Japan — Asia logistics exposure
Asia freight disruption >30% → flag
COPX
Copper price
Global slowdown reduces demand — Iran war stagflation scenario
Oil >$110 sustained >30 days → trim COPX signal
LITE / COHR
AI capex cycle
Fab inputs from specialty chemical suppliers — some Hormuz exposure
Sustained disruption >60 days → check fab input costs
ETN / NVT / VRT
Data center build pace
Copper, steel, specialty metals for power infrastructure
Metals disruption or tariff escalation → check build cost assumptions
LITE / COHR
AI capex cycle
InP substrate — China controls majority of global indium supply for high-speed lasers
Indium supply disruption or China export restrictions → flag LITE/COHR/TSEM


Framework #28 — War Duration / Macro Scenario Ladder
Purpose: The oil frameworks (#3/#7) gate on price. This framework models time. A 3-day oil spike and a 6-month Strait closure require fundamentally different portfolio responses.
Duration
Brent Range
Fed Implication
Portfolio Action
0–14 days
$95–$115
Hold — wait for data
Framework #7 active. Catalyst-only buys. No new positions.
15–30 days
$100–$120
No cuts 2026 locked in
Reduce high-multiple names 15%. Raise cash to 25%. Increase GLD/NEM.
30–90 days
$105–$130
Rate hike risk emerges (2027)
Reduce growth names to minimum weights. Target 30%+ cash. Energy longs only new adds.
>90 days
>$110 sustained
Macquarie hike scenario: 1H27
Full defensive posture. Only MU, TSM, GLD, NEM, CEG, ATI as core. Everything else minimum weight or sold.


Framework #29 — Capitulation / Re-Entry Signal
Purpose: Define precisely when the selloff is exhausted and it is time to deploy cash aggressively — replacing judgment-call approach with a structured 5-signal gate.
5 signals monitored:
VIX 5-day average declining (not just a single-day drop)
Put/call ratio normalized below 1.2 for 3 consecutive sessions
S&P 500 closes above 200-DMA for 2 consecutive sessions
Net institutional flow turning positive (tracked via ETF flow data)
Oil (Brent) holding below a declining 7-day moving average
Gate: 3 of 5 signals confirmed = Green Light. System generates 'Deploy Cash' alert with specific names and sizes.

Framework #30 — Max Drawdown Gate
Purpose: Protect accumulated gains by halting aggressive positioning when the portfolio draws down significantly from its peak.
Drawdown calculation: Portfolio NAV vs. rolling 90-day peak. Updated in real time during market hours.
Gate trigger: NAV declines >15% from 90-day peak — all ADD signals halted automatically. Only HOLD, TRIM, and SELL signals permitted. EXCEPTION: LEAPS entries at 0.5% NAV or less per position are permitted during the 15-25% drawdown range only. At 25% drawdown (hard floor), the LEAPS carve-out is suspended — no new LEAPS or any other entries permitted until human written confirmation. LEAPS position growth: a position started at 0.5% NAV during the carve-out period may be sized up toward the standard 0.75-1.0% NAV maximum once the drawdown gate lifts (NAV recovers above 90% of peak), but no additional capital may be added during the gate period itself. Rationale: LEAPS have defined maximum loss (premium paid), provide asymmetric upside on washout recoveries, and a 0.5% NAV LEAPS position cannot meaningfully worsen a portfolio drawdown. PROOF: March 2026 war period — portfolio NAV drew down ~18-20%, triggering Framework #30. Simultaneously, MRVL at $80 (-40% from $135 peak), VRT at $230 (-18%), COHR at $240 (-17%) represented the best LEAPS entry points of the year. Without this carve-out, the drawdown gate systematically prevents the highest-conviction washout entries. The $0.5% NAV cap ensures the carve-out cannot be exploited.
Recovery protocol: Once NAV recovers above 90% of peak (drawdown <10%), ADD signals resume at 150% of normal Half-Kelly sizing for first 30 days of recovery.
Hard floor: Drawdown reaches 25% from peak — all open limit orders cancelled. Human confirmation required before any new order placed.
Interaction with Framework #1: Max Drawdown Gate can trigger independently of VIX. A portfolio can draw down 15% in a bull VIX environment if position selection is wrong.

Framework #31 — Data Oracle / Multi-Source Price Verification
Purpose: Prevent a bad tick, data provider glitch, or feed latency error from triggering a real execution.
Implementation: Every price used in a scoring decision or execution trigger must be verified against two independent sources before acting. Default: Polygon.io + Alpaca market data feed.
Tolerance gate: If two sources diverge by more than 0.5% on bid/ask, execution is blocked. System flags DATA_DIVERGENCE. No order fires until sources reconcile or human confirms override.
Stale data gate: Integrates with 15-minute freshness check in Decision Trace Module. A price that passes divergence check but is stale is also blocked.
Override: Human can override DATA_DIVERGENCE with written reason. Override logged. System re-checks in 60 seconds.
Scope: Applies to all execution triggers only, not informational briefing data.

Framework #32 — Human Bias Cooling-Off Protocol
Purpose: The most personal framework in the entire system. When markets are in crisis and the portfolio is moving, human operators make their worst decisions.
Override frequency monitor: System tracks human override events in real time. An override is any human action that countermands a system signal.
Trigger condition: 3 or more overrides within any 60-minute window during a session where VIX is above 24 (Crisis regime active).
Response: System activates COOLING_OFF_PROTOCOL. All manual trade entry locked for 4 hours. Existing GTC orders remain active.
Override of the override: Human can unlock early by entering a written override reason of minimum 100 characters. Reason logged permanently in Decision Trace.
THIS IS THE MOST PERSONAL PROTECTION IN THE SYSTEM
Every institutional safeguard in this document protects capital from market risk. Framework #32 protects capital from the one risk no institution can model for you: yourself under pressure. It is the difference between a system that works when you feel calm and a system that works when you feel afraid.



Section 3: The 12-Factor Scoring Model (Original Agentic System)
SCORING WEIGHT UNCERTAINTY — READ BEFORE IMPLEMENTING
The weight allocation shown in this section (F1=15%, F2=25%, F3=15%, F4=15%, F5=30%) is theoretically justified — it reduces sentiment triple-counting from the prior equal-weight system. However, these weights have NOT been empirically validated against this portfolio's specific names. They are starting hypotheses. The Bayesian tuner in V3 (Section 6.1) and the Walk-Forward Optimization Loop (Section 6.7) will provide the first systematic validation after 6+ months of live operation. See Section 19.4 for full disclosure. Apply these weights with appropriate confidence — they are principled, not proven.


Every candidate position is scored 0–100 across 12 factors for the agentic system. Scores above 85 are strong buys. Scores 78–85 are grey zone for 12-factor (require 3-AI consensus per Framework #8). Scores below 70 are holds or sells. Scores below 60 are sells. NOTE: The 5-factor ATLAS daily scoring system also uses 78–85 as the grey zone threshold per Section 13 Score Authority.
NOTE: Section 13 documents the ATLAS 5-Factor Conviction Scoring System used for the personal operational framework (F1-F5 with revised weights). The 12-factor model is the comprehensive agentic engine. The 5-factor ATLAS model is the personal daily scoring tool. They are complementary — the 5-factor model runs daily; the 12-factor model provides depth validation on new positions and quarterly re-scores.

Factor
What It Measures
Weight
Data Source
1. Bottleneck Fit
How directly does this name benefit from the current or next AI infrastructure bottleneck?
15%
Bottleneck Emergence Engine (V2)
2. Catalyst Event
Is there a dated, confirmed catalyst within 90 days?
12%
Earnings calendar, product roadmaps, index inclusion data
3. Revenue Quality
Is revenue growing, recurring, and backed by backlog or contracted demand?
12%
SEC filings, earnings transcripts, backlog data
4. Earnings Trend
Direction of EPS and revenue over last 4 quarters plus forward guidance quality
10%
Earnings Quality Engine (Framework #21)
5. Moat / Differentiation
What prevents a competitor from replicating this company's position in 12–18 months?
10%
Analyst reports, patent filings, supply agreements
6. Management Execution
Rolling 4-quarter credibility score plus insider activity flag
8%
Management Credibility Score (Framework #26)
7. Valuation
Forward P/E vs. growth rate (PEG), adjusted for rate regime via Framework #22
8%
Bloomberg consensus estimates, rate sensitivity map
8. Insider Activity
Net insider buying vs. selling trend over 90 days
7%
SEC Form 4 filings, Framework #14
9. Regime Fit
Does the current VIX / macro regime support adding this name at this size?
7%
VIX Regime Gate (Framework #1), Oil Map (#3), 4-Week Trend (#18)
10. Oil / Macro Sensitivity
How exposed is this name's revenue to oil price, rate changes, or geopolitical disruption?
5%
Supply Chain Contagion Map (Framework #27), War Duration Ladder (#28)
11. Concentration Check
Does adding this name violate position or cluster concentration gates?
4%
Correlation Cluster Manager (Framework #23), Concentration Gate (#13)
12. Framework Alignment
Do all 32 frameworks pass for this name at this time?
2%
Master Sync Check (Framework #16)


SCORE INTERPRETATION
90–100: High conviction. Full-size position. Add aggressively on dips. | 85–89: Strong buy. Target weight. Add on any 3–5% pullback. | 78–85: Grey zone (revised from 75–85 per backtest — see Framework #8). Require 3-AI consensus before acting. | 70–77: Tier 2 — GTC adds, no consensus required. | 60–69: Reduce or sell. Flag for exit plan. | Below 60: Sell. Exit within 5 trading sessions.



Section 4: V1 Build Scope — Core Infrastructure
4.1 Data Ingestion Layer
Market data feed: Real-time quotes, OHLCV, options flow (Unusual Whales — UW subscription required before signing contract)
Fundamental data: SEC filings (8-K, 10-Q, 10-K, Form 4 insider transactions), earnings transcripts via NLP pipeline
Macro data: VIX, 10-year yield, Brent/WTI crude, DXY, gold, S&P 500 levels and moving averages
News feed: Financial news NLP with entity extraction and sentiment scoring — per holding and per macro theme
Catalyst calendar: Earnings dates, index rebalancing schedule, product launch dates, conference schedules
Adapter pattern (Gemini non-negotiable): Adding any new data source must take no more than 4 hours of developer time. All sources use standardized adapter interface.

4.2 Unusual Whales Integration
Real-time options flow: Unusual sweeps, dark pool prints, put/call imbalances by ticker
Congressional trading feed: Politician buy/sell activity with 24-hour latency
Heartbeat requirement (Gemini non-negotiable): System must display UW_FEED_OFFLINE status when connection is lost. Silent null data is a hard failure — never pass through zero options flow as if the market is quiet.
Alert thresholds: Unusual sweep with notional exceeding the holding's 20-day average daily options volume by 3x = immediate briefing flag. Bearish flow >3:1 put/call ratio in any holding = score reduction trigger
Dark pool confirmation rule (REVISED v2.1): Dark pool single-session print >$500K for a specific name gates that name's individual tactical add signal. Dark pool data is NOT a regime trigger — it is a per-name portfolio signal only.

4.3 LangGraph Orchestration
Agent graph: DataIngestionAgent → ScoringAgent → FrameworkEnforcerAgent → ValidationAgent → BriefingAgent → HumanEscalationNode
All agent transitions logged to LangSmith with full trace. Weekly trace share with client required per contract.
Error handling: Each agent has a fallback state. DataIngestion failure does not block Briefing — system generates briefing with explicit data gap flags.
State management: Complete portfolio state, all 32 framework statuses, and full scoring history persisted across sessions. No stateless runs.

4.4 The Precedence of Truth — Framework Conflict Resolution Hierarchy
THIS IS THE CONSTITUTION OF THE SYSTEM
When 32 frameworks, a Red Team Agent, a 3-AI consensus layer, a human operator, and a 12-factor scoring engine all have opinions simultaneously, there must be an unambiguous hierarchy that determines whose voice is final. Without this hierarchy, the system is not a system — it is a collection of opinions. Every node, every agent, and every output must check this hierarchy before acting. This check is never optional. It runs in sequence on every execution.


Level
Authority
Examples
Can Be Overridden By
Level 1 — ABSOLUTE HALT
Hard stops that cannot be overridden by anyone or anything
VIX > 30 active, Brent > $108 active, cash below regime-specific floor (Section 14.1 — SOFT CAUTION 15%, CAUTION 20%, CRISIS HALT 30%+), Max Drawdown Gate 25% hard floor
Nothing. System halts. Period.
Level 2 — FRAMEWORK BLOCK
32 frameworks producing a BLOCK signal on specific action
Concentration Gate on MU, Catalyst No-Fly on LITE, Insider Flag on AXTI
Human written override + reason logged in Decision Trace. Override visible in next briefing.
Level 3 — VALIDATION INTERCEPT
Validation layer detecting contradiction between score and flag
Score >80 with active insider sell flag, grey zone name with 3-AI dissent unresolved
Human written confirmation required. System does not proceed without it.
Level 4 — RED TEAM INVALIDATE
Red Team Agent finding structural reason not to buy
Hidden leverage, gross margin compression concealed by revenue growth, crowded positioning signals
Human written override + reason. Override logged. System flags in next morning briefing.
Level 5 — 3-AI CONSENSUS REQUIRED
Grey zone score 78–85 on EITHER the 5-factor ATLAS system OR the 12-factor agentic system. Both systems now unified at 78-85. Prior 75-85 range for 12-factor narrowed to match — see Framework #8.
Any ADD signal where score falls in 78-85 range
Majority vote from Claude + Grok + Gemini. Dissent logged.
Level 6 — HUMAN DECISION
All other decisions not caught by Levels 1–5
Portfolio rebalancing, GTC price adjustments, regime assessment input
Human authority, subject to Framework #32 Cooling-Off Protocol (which operates at Level 2). If Cooling-Off is active, Level 6 human decisions are locked for 4 hours. This makes Cooling-Off the only framework that can restrict Level 6 authority — it sits at Level 2, not Level 1 (it can be unlocked with 100-character written override, unlike Level 1 absolute halts).


4.5 Adaptive Compute Routing Layer
Not all signals require the same compute. Routing signals to the appropriate model tier prevents unnecessary latency and cost while maintaining quality where it matters.
Signal Type
Model Tier
Examples
Rationale
Routine checks
Flash / Haiku
Cash floor check, concentration gate, catalyst proximity scan
Binary yes/no — no reasoning required
Standard scoring
Sonnet
Daily 12-factor score updates, framework status checks, briefing generation
Default for most operations
Complex reasoning
Sonnet Extended / Opus
3-AI consensus grey zone queries, Bottleneck Emergence Engine scans, Supply Chain Contagion Map, War Duration Ladder
Multi-factor ambiguous decisions requiring deep chain-of-thought
Adversarial / Red Team
Sonnet (isolated instance)
Bear Agent invalidation queries, contradiction detection, insider flag cross-checks
Must be isolated from bull reasoning context


4.6 Validation Layer
Price sanity check: Any price used in scoring must have a verified timestamp within 15 minutes. Stale prices flagged and blocked.
Score contradiction detector: If a name scores >80 but has an active insider sell flag (Framework #14), system halts and requires human confirmation.
Framework conflict resolver: If any two frameworks produce directly contradictory signals on the same name, the more conservative signal wins and the conflict is logged.
3-AI consensus enforcer: Grey zone names (78–85 on either 5-factor or 12-factor — both systems now unified at 78-85) cannot generate ADD signals without 3-AI query completion. System blocks the signal until all three models respond. Rationale for 78 threshold on 5-factor: backtest confirmed names scoring 75–77 historically were high-conviction adds (MRVL scored 75–78 in early 2025, rose +49%; CRDO scored 74–78, rose +106%). Applying consensus gate at 75 would have added friction to correct decisions.

4.7 Decision Trace Module — The Black Box Recorder
CONTRACT REQUIREMENT — DECISION TRACE
The Decision Trace format must be explicitly defined in the contract. A trace that records what happened is insufficient. The trace must record WHY it happened: the complete reasoning state, data freshness, framework statuses, and regime snapshot at the exact moment of every signal. This is non-negotiable.


Required fields in every Decision Trace record:
decision_id: Unique identifier for every signal generated
timestamp_utc: Millisecond-precision UTC timestamp
trigger: Which framework or agent initiated the signal
signal_type: ADD / HOLD / TRIM / SELL / BLOCK / ESCALATE
ticker: Affected holding
score_snapshot: Complete 12-factor scores with individual factor values and data sources at moment of decision
framework_states: Status of all 32 frameworks at moment of decision — PASS / WARN / HALT for each
regime_snapshot: VIX, Brent, 10-yr yield, S&P vs. 200-DMA at moment of decision
data_freshness: Timestamp of each data source used. Any source >15 minutes stale flagged explicitly.
conflicts_detected: List of any framework conflicts or validation layer intercepts triggered
model_tier_used: Which compute tier processed this signal
human_override: Boolean. If true, override reason required as mandatory free-text field.
resolution: Final action taken and execution timestamp

4.8 Operational Continuity Protocol
Daily backup: Full system state — vector DB, Decision Trace history, all framework statuses, portfolio weights, GTC order queue — backed up to cloud storage every day at market close and again at 6 AM before morning briefing runs.
Backup broker account: Operator maintains a second brokerage account with read-only API access always connected. If primary broker goes offline, system automatically switches price data feed to backup.
Restart procedure documented: A one-page runbook lives outside the system specifying: (1) how to restart from last backup, (2) how to verify state integrity on restart, (3) which broker to use as fallback. This document is reviewed quarterly.

4.9 Daily Briefing Output
Morning briefing (6:00 AM ET): Macro levels (S&P, VIX, Brent, 10-yr, gold), overnight news scan, framework status dashboard (all 32), holdings thesis check, action plan with specific names/prices/sizes
Close briefing (4:15 PM ET): Position changes executed vs. planned, P&L attribution, any framework status changes during the session, next-day catalyst preview
Soft failure condition: If 2 or more briefing components are missing or stale at send time, system alerts developer and timestamps the gap. Not acceptable to send a silent partial briefing.


Section 5: V2 Intelligence Upgrades
5.1 Bottleneck Emergence Engine
The central intelligence upgrade of V2. The AI infrastructure cycle moves in waves — GPUs → Memory → Optics → Power/Thermal → Grid/Energy. The Bottleneck Emergence Engine detects the next wave before it is consensus.
5 signal inputs per candidate bottleneck category:
Patent filing velocity: 90-day acceleration in patents filed in the target category (USPTO API)
Job posting surge: Indeed/LinkedIn keyword velocity for engineering roles in the category
Earnings transcript keyword velocity: NLP frequency of constraint language in hyperscaler and infrastructure earnings calls
CapEx language shift: Hyperscaler CFO language moving from 'optimizing' to 'accelerating' in a specific infrastructure category
Analyst coverage initiation: Number of new analyst coverage initiations in the category in the prior 90 days
Emergence threshold: 3 of 5 signals firing = Emerging Bottleneck. System generates candidate names list with preliminary 12-factor scores.
Current confirmed waves: GPU (priced in), Memory/HBM (priced in), Optics/CPO (active), Power/Thermal (forming). Next: Grid Infrastructure / Custom Silicon.

5.2 Earnings Call NLP Agent
Real-time transcript ingestion during earnings calls — not post-processing
Keyword categories tracked: Supply constraint language, demand pull-forward signals, margin expansion vs. compression language, forward guidance confidence indicators, competitive threat acknowledgments
Output: Sentiment score delta vs. prior quarter for each holding. Score feeds into Factor #4 (Earnings Trend) within 2 hours of call completion.
Special flag: Any hyperscaler using 'constraint' or 'bottleneck' language about a specific infrastructure category triggers Bottleneck Emergence Engine scan for that category

5.3 Earnings Quality Engine (Framework #21 Implementation)
Automated 3-factor quality scoring on every earnings print for all holdings
Revenue trajectory: QoQ and YoY growth direction
Gross margin direction: Expanding, flat, or compressing vs. prior quarter and vs. guidance
Guide accuracy: Current guidance vs. prior guidance. Beat rate over rolling 4 quarters.
Output: Quality score (-10 to +10) fed into Factor #4. Hollow beats flagged in daily briefing with explanation.

5.4 GEX (Gamma Exposure) Layer
Daily GEX calculation for S&P 500 and top holdings
Negative GEX: Dealer hedging amplifies moves in both directions. Reduces tranche sizes by 25% automatically.
Positive GEX: Dealer hedging dampens volatility. Normal tranche sizes apply.
Triple witching detection: System flags quad/triple witching dates 5 sessions in advance. Reduces all limit orders on affected names by 50% during expiration session.

5.4b Red Team Agent — The Bear Agent
ARCHITECTURE NOTE
The Red Team Agent runs on an isolated Sonnet instance with no shared context from the bull agents. It receives only the ticker, the proposed action, and the raw data — not the bull agent reasoning. Contaminating its context with bull reasoning defeats the purpose entirely.


Red Team Agent inputs: Ticker, proposed signal (ADD/HOLD), current 12-factor score, raw data feeds only
Red Team Agent hunts for: Insider selling patterns (Form 4 velocity), hidden leverage (debt/EBITDA trend), gross margin compression concealed by revenue growth, crowded positioning signals, structural fragility in the bottleneck thesis, any recent management guidance miss in the prior 2 quarters
Output: INVALIDATE (with specific reason) or CONFIRM. If INVALIDATE, signal is blocked and reason logged in Decision Trace.
Integration: Red Team Agent result required before any ADD signal above 5K executes. HOLD and TRIM signals do not require Red Team confirmation.
Override: Human can override Red Team INVALIDATE. Override requires written reason logged in Decision Trace. System flags the override in next morning briefing.
Live example: AXTI March 2026 — Bull score ~78. Red Team Agent flagged CEO net sold >0.5% of reported holdings in 3 consecutive transactions over 2 days. INVALIDATE. Trade blocked. Losses avoided.

5.5 Correlation Cluster Manager (Framework #23 Implementation)
Weekly 60-day rolling correlation matrix across all holdings
Automatic cluster reassignment when correlation shifts
Cluster weight alerts: Real-time tracking of cluster totals. Briefing always shows both individual position weights AND cluster total weights
Auto-reduce trigger: When cluster >30%, system identifies lowest-conviction name and generates REDUCE signal for 20% of position

5.6 Sector Rotation Monitor (Framework #24 Implementation)
Weekly automated scan of all 5 rotation signals
Signal history: 13-week rolling log of each signal state to identify trend vs. noise
Rotation Warning generates specific action list: which names to reduce, by how much, and what to rotate into

5.7 Liquidity-Adjusted Execution Protocol (Framework #25 Implementation)
ADV lookup: System fetches 20-day average daily volume for every holding at market open.
Execution tier assignment: Each holding assigned to ADV tier (>$100M / $50M–$100M / <$50M) at open. Tier determines order type and max tranche size.
VIX integration: Liquidity tier crossed with current VIX level at execution time.

5.8 Half-Kelly Position Sizing Engine
HALF-KELLY FORMULA
f* = 0.5 × [(edge × win_rate − loss_rate) / odds_ratio]. Where: edge = expected return on winning trade, win_rate = historical signal accuracy for this factor score range, loss_rate = 1 − win_rate, odds_ratio = average win size / average loss size. Output: f* as percentage of portfolio NAV. Cap at 8% per Framework #13 regardless of Kelly output.


Inputs: Factor score range (90+, 85–89, 75–84), historical win rate per range (populated from paper trading then live trading history), average win/loss ratio per range, current regime multiplier from Framework #1

5.9 Crowdedness Score — Anti-Crowding Filter
Inputs: Short interest ratio vs. 90-day baseline, ETF overlap score, options open interest concentration (top 3 strikes as % of total OI), analyst consensus skew (% of analysts at Buy vs. Hold vs. Sell)
Output: Crowdedness score 0–100. Score >75 = crowded flag in briefing. Not a hard block — a modifier that reduces the Half-Kelly size by 25%.

5.10 Policy Signal Ingestor
Macro Tripwires (4 specific indicators): (1) Fed funds rate change confirmed, (2) 10-year yield crosses 4.5% threshold, (3) China export restriction on semiconductor materials announced, (4) US AI chip export ban expanded
Each tripwire fires a specific framework check and briefing flag. Not a general news monitor — it is a targeted list of the 4 policy events most likely to affect this specific portfolio.

5.11 Goal Trajectory Tracker
Weekly calculation: Current NAV / Target NAV × (remaining time / total time). Are you ahead of pace, on pace, or behind?
Displayed in every briefing as a single-line status: 'Goal Pace: ON TRACK / AHEAD / BEHIND. [X]% of way to target NAV with [Y] months remaining.'
Not used to override frameworks — does not justify taking more risk than the regime allows. Used for personal motivation and calibration, not as an investment signal.

5.12 Tax-Aware Selling Flag
When any TRIM or SELL signal fires, system checks: holding period for the position, current unrealized gain/loss, current tax lot structure
Flag triggers: Short-term vs. long-term capital gains boundary within 30 days — system flags 'TAX_BOUNDARY_WARNING: selling now triggers short-term rate. Holding [X] more days achieves long-term rate.'
Not a hard block — a soft warning. Risk frameworks override tax considerations. But the flag prevents accidental short-term gains on positions held for 10+ months.

5.13 LEAPS / Dynamic Leverage Module — Scope Placeholder
IMPORTANT: THIS IS A SCOPE BOUNDARY
The LEAPS / Dynamic Leverage Module is NOT included in V1, V2, or V3 as currently specified. It is a V2 addendum that requires a standalone specification before any build begins. The ATLAS operational LEAPS framework is documented in Section 17 of this document as the personal investor ruleset. The agentic module will automate that framework once built.



Section 6: V3 Autonomy Upgrades
6.1 Bayesian Weight Auto-Tuner
GEMINI NON-NEGOTIABLE
The Bayesian updater must perform a genuine mathematical posterior update: posterior = prior × likelihood (normalized). This is not a logging operation, not a note-taking system, not a 'we observed X and adjusted manually.' It is a real Bayesian update on every weight vector after every signal outcome is resolved. If the implementation cannot demonstrate the mathematical update formula in the code with unit tests, it does not pass acceptance.


Weight initialization: Current manually-assigned weights (12-factor model: Factor 1 15%, Factor 2 12%, etc.)
Likelihood function: For each factor, track prediction accuracy over 90-day rolling window. Factor that predicted outcome correctly: likelihood increases. Factor that predicted incorrectly: likelihood decreases.
Update frequency: After every earnings print, every major catalyst event, every regime change. Minimum monthly update.
Guardrails: No single factor weight can fall below 2% or exceed 25% regardless of Bayesian output. Human confirmation required if any weight changes by >5 percentage points in one update cycle.

6.2 Vector DB and Institutional Memory
All briefings, scoring decisions, framework triggers, and human overrides stored in vector database
Retrieval-augmented generation (RAG): When generating a new briefing, system retrieves the 5 most similar historical market regimes and uses those briefings as context
Use case: 'We are in a VIX 27, oil $112, 200-DMA broken environment. The 3 closest historical parallels are X, Y, Z. In each case, the positions that recovered first were...'
Contradiction detection: System flags when current recommendation contradicts a similar historical scenario where the opposite action was taken and the outcome is known

6.3 Human-in-the-Loop Escalation
Trigger
Escalation Type
System Behavior
Score contradiction (>80 but insider sell active)
Hard stop
No signal generated. System waits for human confirmation.
Framework conflict (2+ frameworks contradicting)
Hard stop
Conflict logged with specifics. No action taken until resolved.
3-AI dissent (models disagree on grey zone name)
Soft stop
System presents all 3 model outputs. Human selects or defers.
New position >3% weight in Crisis regime
Hard stop
Blocked automatically. Requires explicit human override with reason logged.
Bayesian weight change >5% on any factor
Review required
System flags change. Human confirms or rejects before update applies.
War Duration Ladder escalation to 30+ day tier
Review required
System presents full portfolio impact analysis. Human confirms defensive posture.


6.4 Monte Carlo Stress Testing
Weekly portfolio stress test: 10,000 simulations across 5 macro scenarios
Scenarios: Normal bull, Correction (-15%), Bear (-30%), Oil shock ($130+ Brent), Rate shock (+100bps rapid)
Output: Portfolio expected value, 5th percentile outcome, 95th percentile outcome for each scenario
Action trigger: If 5th percentile outcome in any scenario shows portfolio loss >25%, system generates defensive rebalancing recommendation

6.5 Smart Execution Agent
VWAP-aware order splitting for any single position representing >0.5% of portfolio NAV: Never execute more than 10% of ADV in a single session
Liquidity Protocol integration (Framework #25): Automatically selects limit vs. market order based on ADV and VIX level
Catalyst No-Fly enforcement (Framework #12): Blocks all sell orders on names within 7 days of catalyst event unless human override
Slippage tracking: Post-execution analysis comparing filled price to VWAP at time of order. Running slippage log feeds back into execution quality scoring

6.6 Performance Attribution Dashboard
Framework-level attribution: For each of the 32 frameworks, track: how many times it fired, how many signals it blocked that would have been wrong, how many signals it allowed that were correct, and its net contribution to portfolio alpha
Factor-level attribution: For the 12 scoring factors, track average factor score on winning vs. losing positions. A factor that scores high on eventual losers is a factor whose weight should decrease — this feeds directly into the Bayesian tuner.
Cluster attribution: Which portfolio cluster generated the most alpha? Which generated only beta? This informs bottleneck wave timing.
Benchmark comparison: Alpha vs. SMH, QQQ, and SPY across all time windows. Displayed alongside Goal Trajectory Tracker.

6.7 Walk-Forward Optimization Loop
Frequency: Monthly. Runs automatically on the first Sunday of each month using the prior 6 months of resolved signals as the test window.
Process: (1) Take current framework and factor weights. (2) Run against prior 6 months of signals and actual outcomes. (3) Compare predicted vs. actual outcomes. (4) Calculate the weight vector that would have produced optimal results. (5) Present proposed updated weights to operator for review.
Human approval required: The walk-forward loop proposes. The Bayesian tuner updates mathematically. But the human reviews both outputs before any weight changes apply.
Decay detection: If walk-forward analysis shows a framework or factor weight has drifted more than 20% from its current setting, system flags WEIGHT DECAY DETECTED.


Section 7: Portfolio Baseline Template — System Initialization
This section defines the portfolio state structure used to initialize the system. All values are expressed as percentages of NAV. Dollar amounts are intentionally excluded — the system is designed to operate identically at any portfolio size.

7.1 Macro Regime Framework Mapping — Runtime Thresholds
Indicator
Framework
Bull Threshold
Caution Threshold
Crisis/Halt Threshold
S&P 500 vs. 200-DMA
Framework #2
Above 200-DMA 5+ sessions
Within 1% of 200-DMA
Below 200-DMA 2+ consecutive sessions
VIX
Framework #1/#15
< 18
18–24
> 24 (Crisis). > 30 (Halt)
Brent Crude
Framework #3/#7
< $85
$85–$108 (catalyst-only)
> $108 (HALT gate)
10-yr Yield
Framework #4/#22
< 4.0%
4.0–4.5% (P/E caps activate)
> 4.5% (hard weight caps on >40x names)
Gold trend
Hedge monitor
Falling (risk-on)
Flat
Rising sharply (risk-off — increase hedge weight)
Geopolitical flag
Framework #17/#27/#28
No active conflict
Regional conflict <5% oil supply
Strait/choke-point closure — War Duration Ladder activates


7.2 Holdings Snapshot — Weights and Scores
All position sizes expressed as percentage of portfolio NAV. Dollar values intentionally omitted. This is a living section — it reflects portfolio state at time of each system deployment. NOTE: All scores shown below are 5-Factor ATLAS scores with SOFT CAUTION (−3) modifier applied, per Score Authority in Section 13.1b. They are NOT 12-factor agentic scores.
Ticker
Weight % NAV
Raw Score
Final Score (SOFT CAUTION −3)
Cluster
Action
MU
13.6%
83
80
AI Memory
HOLD — above 8% concentration soft cap. No new adds.
TSM
11.7%
82
79
Foundry
HOLD — above 8% concentration soft cap. No new adds.
COHR
9.5%
81
78
AI Optics
HOLD — above 8% concentration soft cap. No new adds.
VRT
6.3%
71
68
AI Power/Thermal
HOLD — Tier 3 borderline. Monitor dark pool.
CIEN
7.4%
66
63
AI Optics
HOLD — bearish options flow active. No new adds.
LITE
5.1%
75
72
AI Optics
HOLD — LEAPS Jan 2027 $950C position active.
AVGO
3.4%
82
79
AI Custom Silicon
HOLD — LEAPS Jan 2027 $400C position active.
NBIS
4.3%
54
51
AI Infrastructure
EXIT WATCH — score Watchlist, cycle 1 triggered April 16. Sept $149 put protection active.
MRVL
3.4%
78
75
AI Custom Silicon
HOLD — tactical 100-share add pending CLEAR confirmation per Section 18.2 (dark pool $919K confirmed, underweight vs target). June 4 earnings catalyst.
FN
5.9%
67
64
AI Optics
HOLD — Tier 3. GTC $600 working.
SNDK
3.1%
80
77
AI Memory
HOLD — Nasdaq-100 inclusion April 20. Earnings April 30.
AAOI
4.5%
66
63
AI Optics
HOLD — Tier 3. GTC $130 working.
TSEM
1.8%
62
59
Foundry
HOLD — Tier 3. GTC $200 working.
CLS
2.8%
73
70
AI Infrastructure
HOLD
CRDO
0.9%
78
75
AI Optics
HOLD — DustPhotonics acquisition catalyst.
VICR
1.1%
68
65
AI Power/Thermal
HOLD — Tier 3. GTC $173 working.
TTMI
0.5%
62
59
Defense/Infrastructure
HOLD — Tier 3
UCTT
0.9%
64
61
AI Infrastructure
HOLD — Tier 3
AEHR
0.9%
63
60
AI Testing
HOLD — Tier 3 / Satellite


7.3 Sample GTC Order Logic — How the System Structures Limit Orders
Ticker
GTC Price
Current ~
Gap
Notes
FN
$600
$687
-12.7%
Hold — bearish options flow active
AAOI
$130
$140
-7.1%
Close — may fill on any weakness
MRVL
$113
$134
-15.7%
Deep — realistic on major correction
SNDK
$785
$888
-11.6%
Realistic on pullback
VICR
$173
$187
-7.5%
Close — power conversion add
TSEM
$200
$212
-5.7%
Closest — may fill soon
SIVEF
$1.10
$1.15
-4.3%
OTC — $5K hard cap
CRDO
$158
$165
-4.2%
Close — DustPhotonics catalyst



Section 8: AI Infrastructure Bottleneck Roadmap
This is the investment thesis map that drives the entire system. The portfolio is positioned ahead of each wave, not behind it. The Bottleneck Emergence Engine in V2 exists to detect Wave 5 and beyond before they are consensus.

Wave
Bottleneck
Status
Primary Holdings
Entry Window
Wave 1
GPU / Compute
Fully priced in
NVDA (not held — too late)
2022–2023
Wave 2
Memory / HBM
Priced in, thesis intact
MU (13.6%), SNDK (3.1%)
2023–2024
Wave 3
Optics / CPO / Photonics
ACTIVE — we are here
LITE (5.1%), COHR (9.5%), CIEN (7.4%), CRDO (0.9%), MRVL (3.4%), FN (5.9%)
2025–2026 (NOW)
Wave 4
Power / Thermal Management
Forming — early entry window
VRT (6.3%), VICR (1.1%)
2026 — deploy now
Wave 5
Grid Infrastructure / Energy
Signal forming — 12–18 months
GEV (watchlist)
2026–2027
Wave 6
Custom Silicon / ASICs
Gradual — no single catalyst event
MRVL (3.4%), AVGO (3.4%)
Ongoing



Section 9: Phase 1 Acceptance Test Suite
Ten scenario tests that must pass before the system goes live with real capital. Each test has a hard fail condition — a single hard fail means the system does not proceed to live trading.

Test 1: Oil Shock Scenario
Parameter
Value
Scenario
Brent rises from $90 to $115 in 48 hours. VIX spikes from 18 to 28.
Expected behavior
Framework #3 escalates to RED. Framework #7 activates HALT mode. All non-energy, non-catalyst buy signals blocked. COPX trim signal generated.
Hard fail condition
Any ADD signal fires on non-energy name during the scenario.
Pass condition
System generates briefing with all oil frameworks flagged RED, COPX trim recommendation, and explicit 'HALT — no new positions' language.


Test 2: NVDA Kill Switch
Parameter
Value
Scenario
NVDA falls 4.2% in 52 minutes during market hours.
Expected behavior
Framework #19 fires. All AI-correlated buy orders paused. System generates alert. No new market orders on holdings with NVDA beta >1.5 for remainder of session.
Hard fail condition
Any correlated ADD signal passes through after the kill switch fires.
Pass condition
Kill switch fires within 5 minutes of threshold breach. All flagged orders suspended. Alert sent with list of affected orders.


Test 3: Grey Zone 3-AI Consensus
Parameter
Value
Scenario
A name scores 78 on the 12-factor model. System generates a potential ADD signal.
Expected behavior
Framework #8 intercepts signal. 3-AI query fires automatically to Claude, Grok, and Gemini. System waits for all three responses before proceeding.
Hard fail condition
ADD signal passes through without 3-AI query being triggered.
Pass condition
3-AI query log visible in LangSmith trace. All three responses captured. Majority vote documented.


Test 4: Cash Floor Enforcement
Parameter
Value
Scenario
Portfolio cash is at 13% NAV — below the 15% floor. An ADD signal fires for a name scoring 91.
Expected behavior
Framework #11 blocks the buy. System generates alert that cash floor is violated. Signal is queued, not executed, until cash is restored.
Hard fail condition
Any buy executes when cash is below 15% NAV without explicit human override logged.
Pass condition
Framework #11 flag visible in briefing. Buy signal queued with note. No execution until cash confirmed above floor.


Test 5: Concentration Gate
Parameter
Value
Scenario
MU is at 13.6% weight. ADD signal fires for MU at score 80.
Expected behavior
Framework #13 blocks ADD. Score auto-capped at 85. Briefing notes concentration gate active.
Hard fail condition
ADD fires for MU above 8% position weight without concentration gate flag.
Pass condition
Concentration gate documented in briefing. Score cap applied. No ADD signal generated.


Test 6: Validation Contradiction
Parameter
Value
Scenario
A name scores 88 (strong buy) but has an active CEO sell of $2M in the past 14 days (Framework #14 insider flag).
Expected behavior
Validation layer detects contradiction. Hard stop. Human confirmation required before any signal proceeds on this name.
Hard fail condition
ADD or HOLD signal passes through without human confirmation on a name with active insider sell flag.
Pass condition
Contradiction flagged in validation layer. Signal blocked. Escalation ticket generated.


Test 7: Morning Briefing Completeness
Parameter
Value
Scenario
Morning briefing runs at 6:00 AM. Two data feeds are unavailable (Unusual Whales offline, one earnings calendar feed down).
Expected behavior
Briefing generates with explicit UW_FEED_OFFLINE status displayed. Missing calendar noted. Briefing is NOT silently partial — every missing component is named.
Hard fail condition
Briefing sends without noting missing components. UW_FEED_OFFLINE is not displayed when connection is lost.
Pass condition
Briefing contains data gap section. UW_FEED_OFFLINE displayed prominently. All other available data delivered normally.


Test 8: Wargame Mode — Operator Simulation
Parameter
Value
Scenario
Developer runs a synthetic Iran crisis scenario: VIX 28, Brent $112, S&P 200-DMA broken, Day 20 of conflict. Operator makes 3 impulsive override attempts within 60 minutes.
Expected behavior
System correctly applies War Duration Ladder (15–30 day tier). Frameworks #1, #3, #7, #17, #27, #28 all fire. Cooling-Off Protocol triggers on 3rd override.
Hard fail condition
System fails to trigger Cooling-Off Protocol after 3 overrides in 60 minutes during VIX >24 session.
Pass condition
All 32 frameworks display correct status. Cooling-Off lockout activates. Operator cannot enter new trades for 4 hours. Existing GTC orders remain active.


Test 9: Data Oracle Verification
Parameter
Value
Scenario
Polygon.io reports LITE at $823. Alpaca reports LITE at $791. An ADD signal is pending for LITE.
Expected behavior
Framework #31 fires DATA_DIVERGENCE (>0.5% gap). ADD signal blocked. Briefing flags DATA_DIVERGENCE for LITE. System re-checks in 60 seconds.
Hard fail condition
ADD signal fires during a DATA_DIVERGENCE condition.
Pass condition
DATA_DIVERGENCE flag visible in briefing and Decision Trace. Signal blocked until sources reconcile or human override with written reason.


Test 10: ATLAS 5-Factor Scoring — Regime Modifier Application
Parameter
Value
Scenario
SOFT CAUTION regime active (-3 modifier). MRVL raw score 78 across F1-F5. SOX 10-day return is -9%.
Expected behavior
SOFT CAUTION modifier (-3) applied first. SOX dual trigger check: single day -9% fires AND 5-day -5% fires = dual trigger confirmed = SOX filter adds -2. Final score: 78 - 3 - 2 = 73 (Tier 2, approaching Tier 3 boundary). System flags SOX dual trigger active in briefing with both conditions shown.
Hard fail condition
SOX filter not applied. Score calculated without regime modifier. Any tactical add fires without checking aggregate GTC exposure limit.
Pass condition
Final score 73 displayed with modifier breakdown. SOX filter flag visible. Aggregate GTC exposure check passes or blocks per Section 15 rules.



Section 10: Contract Protections and Non-Negotiables
10.0 Milestone Gate Zero — Before Any Build Begins
THIS GATE CANNOT BE WAIVED
Milestone Gate Zero is the single test that determines whether a developer is capable of building this system before any contract is signed. It takes 30 minutes and requires two live APIs, one ticker, and market hours. There is no substitute and no exception.


The test: Developer must demonstrate, live during market hours with the investor present, that they can pull real-time data from two independent sources for a single ticker, cross-verify the prices with a tolerance gate, and display a structured output showing both source values, the divergence check result, and a timestamp. This is the Data Oracle proof-of-concept. If the developer cannot build this in 30 minutes with two live APIs, they cannot build Framework #31. If they cannot build Framework #31, they cannot build this system.

10.1 Five Hard Contract Gates
The client is responsible for providing all detection prompts for the 3-AI consensus layer and the Bottleneck Emergence Engine before Phase 2 development begins. The developer wires the system; the client authors the intelligence prompts. This is explicitly NOT a developer responsibility. Gate 1 — Prompts delivered before Phase 2 begins:

No live capital connection is permitted until the system has completed a minimum of 4 consecutive weeks of paper trading with documented signal accuracy and framework behavior logs. Gate 2 — Paper trading validation minimum 4 weeks:

Developer provides weekly LangSmith trace exports from project inception through V1 delivery. Failure to provide traces for any week is a contract violation. Gate 3 — Weekly LangSmith trace shares throughout V1:

The client must confirm an active Unusual Whales subscription and provide API credentials before the contract is signed. The system is architecturally dependent on UW real-time options flow. Gate 4 — Unusual Whales subscription confirmed before signing:

The current contract covers V1 only. V2 and V3 are distinct scopes with distinct contracts, distinct timelines, and distinct acceptance criteria. Gate 5 — V2 and V3 are separate fixed-price contracts:

10.2 Gemini's Three Non-Negotiables
NON-NEGOTIABLE 1: UW Heartbeat
Contract language: 'The system shall display UW_FEED_OFFLINE status within 60 seconds of losing connection to the Unusual Whales data feed. Passing through silent null options flow data as if the market is quiet is a critical failure. The system must never allow a zero options flow reading to be interpreted as an absence of unusual activity.'


NON-NEGOTIABLE 2: Adapter Pattern
Contract language: 'Adding any new data source to the system must require no more than 4 hours of developer time. All data sources connect through a standardized adapter interface. Any implementation that requires architectural changes to onboard a new data source fails this requirement.'


NON-NEGOTIABLE 3: Bayesian Updater
Contract language: 'The factor weight auto-tuner in V3 must implement a genuine Bayesian posterior update: posterior = prior × likelihood (normalized). The implementation must include unit tests demonstrating the mathematical update formula. A system that logs observations and adjusts weights manually does not satisfy this requirement.'


10.3 Exact Acceptance Clause Language
ACCEPTANCE CLAUSE
Delivery is considered accepted only when: (1) All 10 Phase 1 acceptance test scenarios pass without hard fail conditions; (2) All 32 framework checks are operational and demonstrated in a live paper trading session; (3) The morning and close briefing systems have run for 5 consecutive business days without silent failures; (4) LangSmith trace documentation is provided for all agent graph executions during the acceptance period; (5) The Unusual Whales heartbeat, adapter pattern, and data source documentation are demonstrated to the client's satisfaction. Partial delivery or delivery that passes some but not all acceptance tests does not trigger payment.



Section 11: Build Estimates — 3-AI Consensus
Component
Claude Est.
Grok Est.
Gemini Est.
Consensus Range
V1 Infrastructure (data ingestion, LangGraph, validation, briefing)
320–340h
330–360h
340–370h
330–370h
V1 Framework Engine (all 32 frameworks)
80–100h
90–110h
85–105h
85–110h
V1 12-Factor Scoring Model + 5-Factor ATLAS Scoring
70–85h
75–90h
70–90h
70–90h
V1 Frontend / Briefing Output
40–55h
45–60h
50–65h
45–65h
V1 Total
510–580h
540–620h
545–630h
520–630h
V2 Intelligence Upgrades (incl. Red Team Agent, Bottleneck Engine)
90–115h
95–120h
100–130h
90–130h
V3 Autonomy Upgrades (incl. Bayesian tuner, Walk-Forward)
110–140h
115–145h
120–150h
110–150h
Full Stack V7 (V1+V2+V3, complete)
710–835h
750–885h
765–910h
710–910h


NOTE ON ESTIMATES
The original V1 estimate of 295 hours (pre-gap analysis) was identified as too low by all three AI models in the consensus review. The revised range of 520–630 hours reflects the full 32-framework engine, the complete validation layer, the ATLAS 5-factor scoring system integration, the liquidity protocol, the supply chain contagion map, and the new acceptance tests. Any contract based on the 295-hour estimate must be renegotiated before signing.



Section 12: Pre-Signature Checklist
Do not sign the contract until all items below are confirmed.

Client Responsibilities (Must Complete Before Signing)
Unusual Whales subscription active and API credentials provided
10 detection prompts for Bottleneck Emergence Engine authored and delivered
10 detection prompts for 3-AI consensus grey zone queries authored and delivered
Phase 1 acceptance test scenarios reviewed and agreed upon (10 tests, not 7)
Paper trading timeline (minimum 4 weeks) agreed and documented in contract
ATLAS 5-factor scoring weights and regime modifier thresholds reviewed and agreed upon (Section 13-14)

Contract Must Include (Verify Before Signing)
All 5 hard contract gates present with exact language
All 3 Gemini non-negotiables present with exact language
Acceptance clause with all 5 conditions present with exact language — updated to reference 10 acceptance tests not 7
V2 and V3 explicitly scoped as separate contracts with no V1 obligation to deliver them
Weekly LangSmith trace requirement documented with delivery schedule
Change order process defined for any scope additions

Developer Deliverables (V1 Scope)
Precedence of Truth hierarchy implemented as ordered entry check on every LangGraph execution node — Level 1 through Level 6 in sequence, every execution, no exceptions
Full LangGraph agent graph with all nodes documented
All 32 frameworks implemented and unit tested
12-factor scoring model with all factor sources documented
ATLAS 5-factor scoring system implemented per Section 13
4-regime modifier system implemented per Section 14
Three-bucket allocation rules implemented per Section 15
Exit rules implemented per Section 16
LEAPS tracking module (read-only initially — tracks positions and theta) per Section 17
Validation layer with all 6 hard-stop conditions implemented
Morning and close briefing systems with data gap detection
Unusual Whales integration with heartbeat monitoring
Paper trading mode fully functional before live capital connection
LangSmith trace export delivered weekly from Day 1
Decision Trace Module implemented with all 14 required fields
Adaptive Compute routing layer implemented with Flash/Sonnet/Extended tiers
Wargame Mode sandbox operational — synthetic crisis injection working before paper trading phase begins
Framework #31 Data Oracle implemented — dual-source price verification with 0.5% tolerance gate
Framework #32 Human Bias Cooling-Off Protocol implemented — 3-override-in-60-minutes trigger with 4-hour lockout
Operational Continuity runbook delivered

The Sequence for Monday Morning
Step 1: Send this document to the developer. Give them 48 hours to read it fully before any discussion.
Step 2: First call is not a kickoff — it is a comprehension check. Ask the developer to explain the Precedence of Truth hierarchy back to you in their own words.
Step 3: Within 5 days of signing, require the Milestone Gate Zero Oracle Demo. Two live APIs, one ticker, live during market hours.
Step 4: Weekly LangSmith traces from day one.
Step 5: Do not wire live capital until paper trading has run for a minimum of 4 weeks and you have personally reviewed at least 20 Decision Trace records end-to-end.


Section 13: ATLAS 5-Factor Conviction Scoring System
The ATLAS 5-Factor system is the personal daily scoring tool used alongside (not replacing) the 12-factor agentic model. It is optimized for speed, clarity, and consistency across a concentrated AI infrastructure portfolio. The 5-factor weights were revised post-Opus 4.7 adversarial audit in April 2026.

13.1 Factor Weights — v2.1 (Revised April 2026)
Factor
Label
OLD Weight
NEW Weight
Rationale for Change
F1
Momentum
20%
15%
Was triple-counting sentiment with F3/F4. Old system gave 60% combined weight to sentiment factors.
F2
Earnings Quality
20%
25%
Fundamental anchor — most predictive for high-beta names. Captures hollow beats vs. quality beats.
F3
Analyst Conviction
20%
15%
Sentiment-correlated with F1 and F4. Redundant signal in bull markets.
F4
Options Flow
20%
15%
Sentiment-correlated with F1 and F3. Dark pool signal moved to per-trade gate (not scoring weight).
F5
Fundamental Quality
20%
30%
Moat, cash generation, balance sheet — anchors vs. sentiment collapse. Most durable predictor.


CRITICAL NOTE: F1 + F3 + F4 = 45% (SENTIMENT). F2 + F5 = 55% (FUNDAMENTALS).
Old equal-weight system gave 60% to sentiment (F1+F3+F4). In a sentiment reversal, all three collapse simultaneously. New system anchors 55% in fundamentals that do not reverse overnight. This is the single most important change from v2.0 to v2.1.


13.1b Score Authority and Precedence (NEW — v2.2)
SCORE AUTHORITY — WHICH MODEL GOVERNS WHAT
5-Factor ATLAS Score: Authoritative score for ALL daily operational decisions. Governs tier assignment (Section 13.3), bucket eligibility (Section 15), exit rule cycle tracking (Section 16.1), LEAPS eligibility (Section 17), and Framework #8 3-AI consensus grey zone (78–85 range). | 12-Factor Agentic Score: Used ONLY for quarterly deep review of existing positions and validation of new-position additions. NOT used for daily tier assignment or exit rule triggers. | When scores diverge by more than 7 points: use the more conservative score. Divergence flagged for reconciliation in next morning briefing. | Holdings Snapshot scores (Section 7.2): All scores shown are 5-Factor ATLAS scores with SOFT CAUTION modifier applied.


13.2 Factor Definitions (0-100 scale each)
F1 — Momentum (15%)
Price vs. 50-day and 200-day moving averages
Recent earnings beat history (last 3 quarters)
Relative strength vs. SOX index. NOTE: SOX also appears in Section 14.3 (SOX dual-trigger regime filter). Names with strong relative strength during a SOX crash receive a benefit in F1 (high relative strength score) while simultaneously receiving the regime filter penalty (-2 modifier). These are different measurements — F1 measures name-vs-index relative outperformance; Section 14.3 measures absolute index level decline. They are not double-counting the same signal, though they are correlated. Scorers should be aware that during SOX crashes, F1 scores for sector outperformers will be elevated at the same time the modifier is most negative.
52-week price trajectory

F2 — Earnings Quality (25%)
Revenue growth rate (YoY and QoQ)
Gross margin trend (expanding, stable, or contracting)
EPS beat consistency (last 4 quarters)
Guidance reliability (does management guide conservatively or aggressively)
Forward revenue visibility (backlog, contracted revenue, design wins)

F3 — Analyst Conviction (15%)
Consensus rating (Strong Buy / Buy / Hold / Sell)
Average price target upside from current price
Number of analysts covering
Recent rating changes (upgrades weighted more than existing ratings)

F4 — Options Flow Signal (15%)
Bullish vs. bearish premium ratio over trailing 5 sessions
Size of largest single prints (above $500K threshold = institutional signal — gates individual trades, not regime)
LEAPS buying vs. put buying (structural vs. tactical)
Dark pool confirmation: >$500K single session for specific name = confirms tactical add signal for that name only

F5 — Fundamental Quality (30%)
Balance sheet strength (cash, debt, liquidity)
Free cash flow generation
Competitive moat (pricing power, switching costs, IP)
Customer concentration risk (single customer >40% = penalty)
Management track record
Pre-profitability penalty: F5 cannot exceed 65 if company is pre-profitability (net income negative trailing 12 months). ALGORITHMIC IMPLEMENTATION: The scoring system must check profitability status BEFORE computing F5 and F2. If pre-profit flag is TRUE: (a) F5 score is hard-capped at 65 regardless of other inputs; (b) the EPS beat consistency sub-factor within F2 is automatically set to 0 and excluded from F2's internal weighted average, with the remaining F2 sub-factors (revenue growth, gross margin trend, guidance reliability, forward visibility) re-weighted proportionally to sum to 100. Pre-profit names are identified by: net income TTM < 0. This check runs at each weekly rescore. If a name crosses to profitability (net income TTM turns positive), the cap lifts automatically at next rescore.

13.3 Scoring Tiers (post-modifier)
Tier
Score Range
Action
Tier 1
85+
Core position — add on any dip, LEAPS eligible
Tier 2
70–84
Core position — GTC adds, LEAPS eligible on flow confirmation
Tier 3
55–69
Satellite or small position — GTC only, no LEAPS
Watchlist
Below 55
No new capital. Exit rule applies to owned names.


13.4 Multi-Model Scoring Calibration Protocol
ATLAS uses two AI models to score names. Systematic calibration gaps must be resolved before scores are used for exit rule decisions.
Gap Size
Protocol
Within 3 points
Use average of the two scores
4–7 points
Flag for review — identify which factor inputs differ. Use the more conservative score for risk decisions.
8+ points
Mandatory reconciliation — both models must provide F1-F5 inputs separately. Investor makes final call on disputed scores.


KNOWN CALIBRATION ISSUE — APRIL 2026
Grok scores are systematically higher than Claude scores by an average of +5.2 points across 21 names. Likely cause: different baseline assumptions on F5 (fundamental quality) factor. Do NOT use Grok scores alone for exit rule decisions until calibration is resolved. Priority reconciliation needed: NBIS, POET, TSEM, FN, SNDK. Ask Grok for F1-F5 factor inputs on NBIS and POET specifically to resolve the exit rule question.



13.5 Factor Scoring Algorithms — Implementation Specification
THIS SECTION IS REQUIRED FOR DEVELOPER IMPLEMENTATION
Section 13.1–13.4 defines what each factor measures. This section defines HOW to convert those measurements into a 0-100 score. Without this, a developer will produce their own scoring algorithm and you will not know it happened. Each factor below has: (a) sub-factor inputs, (b) point allocation per sub-factor, (c) aggregation rule, and (d) data source. Factors are scored 0-100 independently, then weighted per Section 13.1.


F1 — Momentum (15%) — Scoring Algorithm
Sub-Factor
Measurement
Points (max 25 each)
Scoring Rule
Price vs 50-DMA
Current price relative to 50-day moving average
0–25
Above 50-DMA by >5%: 25. Above 0-5%: 18. At 50-DMA (±1%): 12. Below 0-5%: 6. Below by >5%: 0.
Price vs 200-DMA
Current price relative to 200-day moving average
0–25
Above 200-DMA by >10%: 25. Above 5-10%: 20. Above 0-5%: 14. Below 0-5%: 7. Below by >5%: 0.
Earnings beat rate (last 4 quarters)
Count of quarters beating consensus EPS estimate
0–25
4/4 beats: 25. 3/4: 20. 2/4: 12. 1/4: 5. 0/4: 0.
52-week trajectory
Price today vs price 52 weeks ago (percentage)
0–25
+50%+ return: 25. +20-50%: 20. +0-20%: 12. -0-20%: 5. -20%+: 0.

F1 total = sum of 4 sub-factors (max 100). Refresh cadence: daily at morning briefing using prior-day close. 50-DMA and 200-DMA calculated from daily close data, 20-day minimum data required.

F2 — Earnings Quality (25%) — Scoring Algorithm
Pre-profitability flag check runs BEFORE F2 scoring. If flag TRUE: EPS beat sub-factor is automatically set to 0 and excluded. Remaining sub-factors re-weighted proportionally. See Section 13.2 F5 note.
Sub-Factor
Measurement
Points (max 20 each)
Scoring Rule
Revenue growth rate (YoY)
Most recent quarter revenue vs same quarter prior year
0–20
>40% YoY growth: 20. 20-40%: 17. 10-20%: 13. 0-10%: 8. Negative: 0.
Gross margin trend
Most recent quarter GM% vs 4-quarter average GM%
0–20
Expanding >200bps: 20. Expanding 0-200bps: 16. Flat (±50bps): 12. Contracting 0-200bps: 6. Contracting >200bps: 0.
EPS beat consistency
Last 4 quarters vs consensus estimate at time of report (EXCLUDED if pre-profit)
0–20
Beat by >10% all 4 quarters: 20. Beat all 4 quarters (any size): 16. Beat 3/4: 11. Beat 2/4: 6. Beat 1 or fewer: 0.
Guidance reliability
Last 4 quarters: actual results vs company's own prior guidance
0–20
Beat own guidance all 4 quarters: 20. Beat 3/4: 16. Met 2/4 or better: 10. Missed own guidance 2+ times: 4. Missed 3+: 0.
Forward visibility
Score based on backlog, contracted revenue, and design win announcements
0–20
>18 months visible backlog or contracted revenue: 20. 12-18 months: 16. 6-12 months: 10. <6 months: 5. No visibility data: 0.

F2 total = sum of 5 sub-factors (max 100). Refresh cadence: updated within 24 hours of each earnings report. Between quarters: held at last-quarter score unless guidance revision or pre-announcement changes the inputs.

F3 — Analyst Conviction (15%) — Scoring Algorithm
Sub-Factor
Measurement
Points (max 25 each)
Scoring Rule
Consensus rating
Percentage of analysts rating Buy or Strong Buy vs total coverage
0–25
>80% Buy/SB: 25. 60-80%: 20. 40-60%: 13. 20-40%: 6. <20%: 0.
Price target upside
Consensus 12-month PT vs current price
0–25
>40% upside: 25. 20-40%: 20. 10-20%: 13. 0-10%: 6. PT below current: 0.
Coverage breadth
Number of sell-side analysts actively covering
0–25
>15 analysts: 25. 10-15: 20. 5-10: 13. 2-5: 6. <2: 0.
Recent upgrade momentum
Net rating changes (upgrades minus downgrades) in prior 90 days
0–25
3+ net upgrades: 25. 1-2 net upgrades: 18. Flat: 12. 1-2 net downgrades: 5. 3+ net downgrades: 0.

F3 total = sum of 4 sub-factors (max 100). Refresh cadence: weekly. Data source: Bloomberg consensus, Visible Alpha, or FactSet — operator to specify at system setup. If consensus data is unavailable for a name, F3 = 50 (neutral) with a DATA_GAP flag in the briefing.

F4 — Options Flow Signal (15%) — Scoring Algorithm
Sub-Factor
Measurement
Points (max 25 each)
Scoring Rule
Bullish/bearish premium ratio
Bullish call premium vs bearish put premium over trailing 5 sessions
0–25
>3:1 bullish: 25. 2-3:1 bullish: 20. 1-2:1 bullish: 13. Near parity: 7. Net bearish: 0.
Institutional print size
Largest single options print in trailing 5 sessions vs name's 20-day avg daily options volume
0–25
Print >3x ADV and bullish: 25. Print 1-3x ADV and bullish: 18. Normal flow: 12. Bearish outsized print: 3. Multiple bearish institutional prints >$500K: 0.
LEAPS vs puts ratio
Structural (LEAPS call buying 6+ months out) vs tactical (near-term puts)
0–25
Strong LEAPS call buying, minimal puts: 25. Moderate LEAPS activity: 18. Balanced: 12. Put buying dominant: 5. Heavy institutional puts (>$500K): 0.
Dark pool confirmation
Dark pool single-session print volume vs 20-day avg dark pool volume
0–25
Dark pool >$500K AND bullish premium ratio: 25. Dark pool active, neutral: 13. No dark pool activity: 10. Dark pool active with bearish flow: 0.

F4 total = sum of 4 sub-factors (max 100). Refresh cadence: daily using Unusual Whales data feed. If UW_FEED_OFFLINE: F4 = prior day score with DATA_GAP flag. F4 NEVER uses dark pool data to affect regime classification — only this factor score. See Section 14 for regime-vs-signal distinction.

F5 — Fundamental Quality (30%) — Scoring Algorithm
Sub-Factor
Measurement
Points (max 20 each)
Scoring Rule
Balance sheet strength
Cash/debt ratio and current ratio (current assets / current liabilities)
0–20
Net cash >20% of market cap: 20. Net cash 10-20%: 16. Net cash 0-10%: 12. Net debt <0.5x EBITDA: 8. Net debt >0.5x EBITDA: 3. Net debt >2x EBITDA: 0.
Free cash flow generation
FCF margin (FCF / Revenue) trailing 12 months
0–20
FCF margin >20%: 20. 10-20%: 16. 5-10%: 11. 0-5%: 6. Negative FCF: 0. Pre-profit names: auto-score based on cash burn rate vs runway.
Competitive moat
Qualitative score assessed quarterly — pricing power, switching costs, IP protection
0–20
Strong moat (monopoly or near-monopoly positioning, high switching cost): 20. Moderate moat (2-3 comparable competitors, meaningful switching cost): 14. Limited moat (commodity product, easy substitution): 7. No moat (fully commoditized): 0. Assessed by scorer quarterly using analyst reports and supply agreement disclosures.
Customer concentration
Revenue from single largest customer as % of total revenue
0–20
<15% single customer: 20. 15-30%: 15. 30-40%: 9. 40-60%: 3. >60% single customer (high dependency risk): 0.
Management track record
Management Credibility Score per Framework #26 (rolling 4-quarter guidance accuracy)
0–20
F#26 score +4 (beat guidance all 4 quarters): 20. +2 to +3: 16. 0 to +1: 11. -1 to -2: 5. -3 to -4: 0.

F5 total = sum of 5 sub-factors (max 100). PRE-PROFITABILITY ALGORITHMIC RULE: IF net_income_TTM < 0 THEN: (1) hard-cap F5_total at 65 regardless of sub-factor sum; (2) set F2 EPS_beat_consistency sub-factor = 0 and exclude from F2 calculation; (3) re-weight remaining 4 F2 sub-factors proportionally so they still sum to 100 within F2. ELSE: no cap applies, all sub-factors scored normally. This check runs at each weekly rescore — if a name crosses to profitability (net_income_TTM turns positive), the cap lifts automatically at next rescore. Refresh cadence: quarterly (after each earnings report). Moat sub-factor is the only qualitative assessment — requires human review, cannot be fully automated. All other sub-factors are data-driven and automatable.

13.6 Scoring System Validation
Weekly self-check: sum of all 5 weighted factor scores must equal the reported total (F1×0.15 + F2×0.25 + F3×0.15 + F4×0.15 + F5×0.30 = Total before modifier). Any discrepancy >0.5 points flags a DATA_ERROR in the briefing.
Pre-profitability flag verification: system checks net income TTM for all holdings at each weekly rescore. Flag state changes (profitable → pre-profit or vice versa) trigger an immediate re-score and briefing flag.
New position minimum data: before scoring a new name, system requires minimum data: 4 quarters of earnings history (F1, F2), 2+ analyst coverage (F3), 30 days of options flow history (F4), 2 quarters of balance sheet data (F5). If data is insufficient, name receives DATA_INCOMPLETE flag and cannot be added to any bucket.

Section 14: Regime Modifier System — Framework 2 v2.1
The regime modifier is applied to every raw ATLAS score before tier classification. Raw score + modifier = final score used for all trading decisions.

14.1 Regime Table
Regime
Brent
VIX
Geopolitical
Modifier
Cash Floor
CLEAR
Below $95 two consecutive closes
Below 24
Resolved
+5
8% (10% during first 2 weeks post-transition)
SOFT CAUTION
Below $100, not yet two closes below $95
Below 22
De-escalating
−3
15% (v2.2)
CAUTION
$95–110 OR VIX 24–35
Either
Active risk
−5
20%
CRISIS HALT
Above $110 OR VIX above 35
Either
Escalating
−10
30%+


14.2 SOFT CAUTION Trigger Conditions (v2.1 — revised)
ALL THREE must be true simultaneously:
Brent below $100 but not yet two consecutive closes below $95
VIX below 22
Geopolitical tone de-escalating — ceasefire holding, active diplomatic talks, no new kinetic attacks in prior 48 hours

CRITICAL v2.1 CHANGE: DARK POOL REMOVED FROM REGIME TRIGGER
Dark pool confirmation was REMOVED from the SOFT CAUTION trigger conditions. This was a category error identified by the Opus 4.7 adversarial audit — it was mixing portfolio-specific tactical signal into macro regime definition. Dark pool $500K+ confirmation now gates individual tactical trades only (F4 scoring and Section 15 bucket rules). It does not determine which regime we are in.


14.3 SOX Sector Filter (v2.2 — Dual Trigger per Backtest)
If EITHER condition is true, apply an additional −2 modifier on top of the existing regime modifier, regardless of Brent and VIX levels: (1) Philadelphia Semiconductor Index (SOX^) single-day return below −4% AND 5-day return below −5%, OR (2) SOX 10-day return below −8% on its own.
DUAL TRIGGER RATIONALE: The original −8%/10-day threshold was backtested against the January 2025 DeepSeek event. DeepSeek dropped SOX −9% in a single session but only −6.5% over 10 trading days — BELOW the −8% threshold. The filter would NOT have fired on the event it was explicitly designed to catch. On DeepSeek day, COHR fell −12%, MRVL −9%, AVGO −8% in one session. The dual trigger (single day −4% AND 5-day −5%) correctly fires on DeepSeek while not misfiring on routine −3% daily moves.
Example: SOFT CAUTION (−3) during SOX −9% single day event = dual trigger fires = effective modifier −5 (same as CAUTION).
Calculation spec: Use Philadelphia Semiconductor Index (SOX^), close-to-close returns. Calculated at 6:00 AM ET morning briefing and 4:15 PM ET close briefing. Single-day return = prior close vs two-days-prior close. 5-day return = trailing 5 trading day close-to-close. If threshold is crossed intraday but not at briefing time, it does not trigger until next briefing.
NOT triggered by ceasefire rallies or routine market moves — the AND condition (single day < −4% AND 5-day < −5%) prevents false positives on normal volatility. WHY THE SECONDARY OR CLAUSE IS RETAINED: The secondary trigger (10-day < −8% alone) catches slow-motion semiconductor routs that unfold over 2-3 weeks without a single dramatic session — e.g., a grinding 1.5%/day decline across 6 sessions that never triggers the single-day threshold but represents a genuine sector regime shift. Primary trigger = sudden shocks. Secondary trigger = slow-motion routs.

14.4 Regime Transition Rules
CAUTION → SOFT CAUTION: All three SOFT CAUTION conditions met simultaneously. Immediate.
SOFT CAUTION → CLEAR: Two consecutive Brent closes below $95 AND VIX below 24. Two sessions minimum.
SOFT CAUTION → CAUTION: Immediate if Brent closes above $100, VIX spikes above 22, new kinetic attack confirmed, or ceasefire collapses.
Any regime → CRISIS HALT: Immediate if Brent above $110 OR VIX above 35. All tactical adds halt immediately.

14.5 Critical Precedence Rules (NEW — v2.2)
CASH FLOOR PRECEDENCE — SECTION 14 SUPERSEDES FRAMEWORK #11 AND SECTION 4.4
Section 14 regime-specific cash floors are the governing authority for cash management: CLEAR 8-10%, SOFT CAUTION 15%, CAUTION 20%, CRISIS HALT 30%+. Framework #11 and Section 4.4 Level 1 both reference Section 14 as the source. The prior hardcoded 15% in Framework #11 and Section 4.4 is updated to read 'regime-specific floor per Section 14.1.' SOFT CAUTION was revised from 17-18% to 15% in v2.2 based on Opus 4.7 audit and backtest validation.


FRAMEWORK #1/#3 vs SECTION 14 PRECEDENCE
When Framework #1 (VIX Regime Gate) or Framework #3 (Oil Price Map) signal a more restrictive state than Section 14's regime modifier, the more restrictive signal governs. Specifically: Framework #1 Halt (VIX >30) triggers CRISIS HALT regardless of other Section 14 conditions. Framework #3 Red HALT (Brent >$108) triggers CRISIS HALT regardless of other Section 14 conditions. These are floor conditions for CRISIS HALT. Section 14 regime thresholds (VIX 35, Brent $110) are the upper gates — Framework #1 and #3 can trigger CRISIS HALT earlier.


FRAMEWORK #29 AND GATE FOR TRANCHE 3 DEPLOYMENT
CLEAR regime enables Tranche 3 eligibility. Framework #29 is an AND gate — Tranche 3 deploys only when BOTH conditions are met simultaneously: (1) CLEAR regime is active (Brent two consecutive closes below $95, VIX below 24, geopolitical resolved) AND (2) Framework #29 shows 3 of 5 signals confirmed. PROOF: March 23, 2026 — Trump tweeted about Iran talks. Brent dropped $16 in one session, briefly approaching CLEAR threshold. VIX fell to 26. Next day: Iran denied talks, Brent reversed to $109, VIX back to 30. Framework #29 was at 1-2/5 signals on March 23. Without the AND gate, $150,000 in Tranche 3 capital would have deployed into a one-day fake rally and immediately drawn down ~12%. The AND gate prevents false-CLEAR deployments while adding only 2-3 trading days delay on genuine CLEAR confirmations.


FRAMEWORK #29 AND GATE — UNIVERSAL APPLICATION FOR CAPITAL DEPLOYMENTS ABOVE $10,000
The Framework #29 AND gate applies not only to Tranche 3 ($150K) but to ANY single decision deploying more than $10,000 of capital on the basis of a CLEAR regime transition. This includes: all LEAPS entries priced at CLEAR confirmation (MRVL $14,850, TSM $8,000, VRT $10,500, COHR $8,400, MU $15,600 per Section 17.2). Rationale: the March 23 fake-CLEAR event would have triggered not only Tranche 3 but also all pending LEAPS entries totaling ~$57,350. Without universal application, a single one-day fake-CLEAR could deploy $207,350 ($150K Tranche 3 + $57,350 LEAPS) into a reversal. EXCEPTIONS: LEAPS entries under $10K and tactical adds under 0.5% NAV are gated on CLEAR regime alone — these small individual positions cannot create systemic deployment risk from a single fake-CLEAR event. The $10K threshold is per-decision, not aggregate.


14.6 Rate Sensitivity Overlay (NEW — v2.2)
When the 10-year yield enters elevated territory, high-multiple names face multiple compression risk that is independent of Brent oil or VIX levels. The CLEAR regime could be active (low Brent, low VIX) while rates simultaneously create headwinds for growth names. This overlay integrates Framework #22 (Rate Sensitivity Map) into the regime modifier system.
At 10-year yield above 4.5%: apply additional −2 modifier to any name with forward P/E above 40x, on top of the existing regime modifier. Forward P/E data source: Bloomberg consensus earnings estimates (same source as F3). Refreshed weekly. If consensus P/E is unavailable for a name, the overlay does not fire for that name and a DATA_GAP flag is shown in briefing.
At 10-year yield above 5.0%: apply additional −4 modifier to any name with forward P/E above 40x
Current status (April 2026): 10-year yield at 4.35% — below the 4.5% trigger. Overlay is NOT currently active. Will activate if yield moves above 4.5%.
Names currently affected when overlay activates: NBIS (pre-profit, high implied multiple), CRDO (~85x fwd P/E), AEHR (high multiple). These names would receive additional score penalty above their existing Section 14 regime modifier.
This resolves the conflict Opus 4.7 identified: CLEAR regime can now fire simultaneously with rate sensitivity pressure without contradiction — the yield overlay is applied on top of the CLEAR +5 modifier, so CLEAR names with high multiples might net to +3 or +1 modifier instead of +5.

14.7 Regime Transition State Machine — Implementation Specification
MACHINE-READABLE REGIME TRANSITIONS REQUIRED
Section 14.4 describes transitions in prose. This section provides the formal state machine a developer needs to implement regime changes correctly. All inputs are data-driven except the Geopolitical Confirmed flag, which requires human input via the morning briefing UI. No autonomous regime change should fire based on NLP alone — the geopolitical flag requires operator confirmation.


Transition
Required Conditions (ALL must be true)
Confirmation Window
Revert Condition
Human Input Required?
Any → CRISIS HALT
(a) Brent closing price > $110, OR (b) VIX closing level > 35
Immediate — fires at close of the session where threshold is breached. No delay.
Revert to CAUTION: Both Brent ≤ $108 AND VIX ≤ 33 for one full trading session. Auto-revert — no human required.
No — fully data-driven
Any → CAUTION
(a) Brent closing price $95–$110, OR (b) VIX closing level 24–35, OR (c) Geopolitical Confirmed flag = ACTIVE
Immediate at session close where condition first appears.
Revert to SOFT CAUTION: all three SOFT CAUTION conditions met simultaneously for one full session.
YES for Geopolitical flag — operator must set GEOPOLITICAL_ACTIVE in morning briefing UI. Brent and VIX are automatic.
CAUTION → SOFT CAUTION
(a) Brent closing price < $100, AND (b) VIX closing level < 22, AND (c) Geopolitical Confirmed flag = DE-ESCALATING (operator-set)
One full trading session where all three conditions hold at close.
Immediate revert to CAUTION if: Brent closes above $100, OR VIX closes above 22, OR Geopolitical flag changed to ACTIVE.
YES — operator must change Geopolitical flag from ACTIVE to DE-ESCALATING in morning briefing UI. System does not auto-set this flag.
SOFT CAUTION → CLEAR
(a) Brent closing price < $95 for TWO consecutive session closes, AND (b) VIX closing level < 24 for both those sessions, AND (c) Geopolitical flag = RESOLVED (operator-set)
Two consecutive session closes meeting all three conditions. Clock resets if any condition is violated mid-window.
Immediate revert to SOFT CAUTION if: Brent closes above $95 in any single session, OR VIX closes above 22, OR Geopolitical flag changed to DE-ESCALATING.
YES — operator must set Geopolitical flag to RESOLVED. This is the highest-stakes transition. No automatic CLEAR without operator confirmation.
SOX Dual-Trigger
(a) SOX^ single-day return < −4% (close-to-close), AND (b) SOX^ 5-day return < −5% (trailing 5 trading day close-to-close). OR: SOX^ 10-day return < −8% (secondary trigger).
Fires at end of briefing cycle (6 AM or 4:15 PM) where thresholds are breached. SOX filter is additive to existing regime — it does not change the regime label, only adds −2 modifier.
SOX filter lifts when: 5-day SOX return recovers above −3%. The 2-percentage-point gap between trigger threshold (−5%) and lift threshold (−3%) is intentional hysteresis — it prevents rapid on-off cycling when the 5-day return hovers near the threshold. Filter does not require operator action to lift — automatic at next briefing cycle.
No — fully data-driven. SOX^ data from Philadelphia Exchange daily close.


Geopolitical Flag — Human Input Protocol
The Geopolitical flag has three states: NONE (no active conflict affecting >5% of global oil/LNG/semiconductor supply), DE-ESCALATING (active conflict but ceasefire holding / diplomatic progress confirmed / no new kinetic attacks in prior 48 hours), ACTIVE (active conflict, no ceasefire, or new kinetic attacks in prior 48 hours).
Flag is set by the operator in the morning briefing UI each trading day. Default: carries forward from prior day. Operator must actively change it — system does not auto-set based on news.
Recommended input sources: Operator reviews one primary source (Reuters, AP, Bloomberg geopolitical feed) each morning before setting flag. Flag should reflect what is verifiably confirmed, not rumored.
Flag history is logged in Decision Trace. Any regime change triggered by Geopolitical flag is tagged with the operator's flag entry and timestamp. This creates accountability and makes the flag change auditable.
Why not NLP-auto-detection: natural language processing of news for 'kinetic attack confirmed' carries unacceptable false-positive and false-negative risk on a system making $150K+ deployment decisions. Human confirmation is the right control for this specific input.


Section 15: Three-Bucket Allocation Rules (v2.1)
The three-bucket system structures how capital is allocated across the portfolio. Each bucket has hard caps, entry gates, and concentration rules. The aggregate GTC exposure limit is new in v2.1 — it prevents the regime cash floor from being inadvertently breached by a cascade of GTC fills.

15.1 Bucket 1 — Core Tier 1 and Tier 2 Positions
Target allocation: 75–82% of combined NAV
Names: All names scoring Tier 1 (85+) or Tier 2 (70–84) on final ATLAS score
Tactical add rule in SOFT CAUTION: Up to 0.5% NAV per name per week when: (1) dark pool exceeds $500K single session for that specific name AND (2) name is at least 0.5% below target weight AND (3) add does not push any single name above 8% NAV
Limit orders only — no market orders at open
No covered calls on any name with bullish dark pool flow or bullish options flow
GTCs are primary entry mechanism on all regimes. Never raise GTCs because a name is running.

15.2 Concentration Rules (v2.1)
Soft cap: 8% of combined NAV at market value — stop adding above this level
Hard review: 10% of combined NAV through appreciation — consider trimming 20% of position
These apply to market value, not cost basis
Do NOT force-sell names above cap — let natural rebalancing and appreciation of other names bring concentration down over time
CURRENT CONCENTRATION FLAGS (April 2026)
MU 13.6% — above 10% hard review threshold, hold only. TSM 11.7% — above 10% hard review threshold, hold only. COHR 9.5% — above 8% soft cap, hold only. These positions may be trimmed if a specific exit trigger fires, but concentration alone does not require immediate selling.


15.3 Aggregate GTC Exposure Limit (v2.2 — Revised per Opus 4.7 Audit + Backtest)
Sum of active GTC notional — counting only GTCs within 8% of current market price — cannot exceed: (Current cash − 1.1 × Regime cash floor). Deep-OTM GTCs more than 8% below market are excluded from the aggregate count since they will not fill simultaneously.
SOFT CAUTION v2.2 example (15% floor): Cash $468K minus buffered floor (1.1 × 15% × $2.7M = $445K) = $23K available GTC window. Practical implication: the 4 closest GTCs (AAOI, TSEM, CRDO, VICR) total ~$66K. You are oversubscribed at current share counts — reduce to 50 shares per GTC or raise cash to make the window functional.
CLEAR example: Cash $468K minus buffered floor (1.1 × 8% × $2.7M = $238K) = $230K available GTC window. Deep-OTM GTCs (FN at -12.7%, MRVL at -15.7%, SNDK at -11.6%) are exempt and can be held in full.
WHY 15% NOT 17-18%: The original 17-18% range was identified by Opus 4.7 as producing a $9K window at 17% (non-functional) and a negative window at 18% (self-deadlocking). Backtest confirmed: with SOFT CAUTION signaling improving conditions, holding MORE cash than CAUTION (20%) is counterintuitive and contradicts the regime's de-escalating status. 15% is the correct anchor — it matches Framework #11's original design intent while giving the system room to operate.
Purpose: Prevents cascade GTC fills from breaching the regime cash floor. Exempt GTCs will not fill simultaneously — they require a 10-15% market move to trigger, which implies a regime change would already have occurred.

15.4 Bucket 2 — LEAPS
Total cap: 4% of combined NAV
Per name maximum: 0.75–1.0% of NAV
Already deployed (April 2026): LITE 2ct Jan 2027 $950C + AVGO 2ct Jan 2027 $400C ≈ $24,000
Entry hierarchy: (1) Preferred — washout recovery: stock 15–20% below 60-day high AND 30-day IV declined 20%+ from trailing 30-day peak AND IV below 6-month median. (2) Allowed in SOFT CAUTION — exceptional institutional flow ($500K+) + specific catalyst within 60 days. (3) Full budget unlock — CLEAR regime confirmed.
FRAMEWORK #30 DRAWDOWN GATE INTERACTION: During an active drawdown gate (NAV 15-25% below 90-day peak), LEAPS entries are capped at 0.5% NAV per position regardless of the full size shown in Section 17.2. MRVL at $14,850 = 0.64% NAV — above the 0.5% cap. During drawdown, enter MRVL LEAPS at ~$13,500 (0.5% × $2.7M combined NAV), then size up to $14,850 after drawdown gate lifts and NAV recovers above 90% of peak. All washout entries are subject to this rule since washout conditions (stock -15-20% below peak) frequently coincide with portfolio drawdown.
IV rule: Never buy LEAPS on any name with IV above 90%. Premium is too expensive regardless of conviction. SNDK (IV 108%), AAOI (IV 165%) currently excluded. IMPORTANT TIMING NOTE: For earnings-driven LEAPS entries, enter 4–8 weeks before the catalyst (IV expansion zone), NOT within 0–4 weeks of catalyst (IV peak zone). High institutional flow + catalyst within 60 days = elevated IV = typically approaching or above the 90% threshold. The window where (a) flow is exceptional, (b) catalyst is within 60 days, AND (c) IV is below 90% is typically weeks 5–8 before earnings, not weeks 0–4. For war-period washout entries, IV is typically 35–55% — well below the 90% threshold. The IV>90% rule applies primarily to earnings scenarios, not washout recovery scenarios.
Jan 2027 theta warning: Contracts bought today with Jan 2027 expiry have 9 months remaining. Theta acceleration begins inside 12 months. Monitor LITE and AVGO Jan 2027 positions monthly. Roll to Jan 2028 if not sufficiently in-the-money by August 2026.
System alert at 3.5% NAV deployed: any new LEAPS entry above 3.5% NAV total exposure requires explicit human written approval before execution — system flags LEAPS_SOFT_ALERT in morning briefing. Hard stop at 4%: no new LEAPS entries permitted under any circumstances. Existing positions held to expiry or rolled.

15.5 Bucket 3 — Serenity Satellites (Tier 3 High-Risk)
Total cap: 5% of combined NAV
Per name maximum: 0.25% of combined NAV
Foreign OTC hard cap: $5,000 maximum per name regardless of conviction
Score gate: Must score 55+ using CAUTION regime modifier (−5) — not SOFT CAUTION or CLEAR. Prevents regime improvement from artificially qualifying weak names.
Entry method: GTC limits only. No market orders. No chasing gaps.
System alert at 4% satellite exposure. Hard stop at 5%.
CURRENT SATELLITE STATUS (April 2026)
Qualified at CAUTION threshold: SIVEF (59+), AEHR (owned), SIVE (57). Watchlist — not qualified: POET (40), AXTI (46), ALMU (52), IQEPY (51), ALRIB (38). Grok scores POET at 64 — reconciliation pending before any capital deployment.



Section 16: Exit Rules + Framework 12 Gatekeeper (v2.3 — Updated April 24, 2026)
PRECEDENCE OF TRUTH CLASSIFICATION: EXIT RULES ARE LEVEL 2 (FRAMEWORK BLOCK)
Exit rules are classified as Level 2 (Framework Block) in the Section 4.4 Precedence of Truth hierarchy. This means they can be overridden by human written override with reason logged in Decision Trace, but they CANNOT be silently bypassed. Framework #12 (Catalyst No-Fly Zone) is also Level 2, creating a same-level conflict when an exit rule fires within 7 days of a catalyst. Resolution: Framework #12 defers the exit rule trim window by up to 10 trading days post-catalyst, but does NOT cancel the exit rule. The clock pauses, then resumes. This was verified by backtest — NBIS exit rule firing during April 29 earnings window is correctly deferred to post-earnings, not cancelled.


THESE RULES WERE MISSING FROM ALL PRIOR VERSIONS
The original ATLAS framework had no defined exit rules. The Opus 4.7 adversarial audit identified this as the most significant structural gap. Without defined exit rules, positions held based on entry logic alone with no systematic trigger for review. This section adds the missing exit layer.


Section 16 – Gatekeeper (Two Tracks) — Framework 12 Entry Rules (v2.3, April 24, 2026)
All new adds and incremental adds must clear the applicable track gatekeeper before the Framework 12 Decision Matrix determines sizing and timing.

Track A – Core Resilient Names (AVGO, MRVL, LITE, MU, TSM, CIEN, VRT, COHR, FN, and similar)
Must pass ALL 4 rules unless the High-Conviction Underweight Override applies:
Rule 1 – Institutional Conviction
  Priority 1 (earnings ≤ 14 days): Dark pool ≥ $15M OR Options flow ≥ $2M bullish
  Priority 2 (earnings 15–45 days): Dark pool ≥ $20M OR Options flow ≥ $3M bullish
  Priority 3 (no near-term earnings): Dark pool ≥ $40M AND options flow bullish
Rule 2 – Catalyst Timing: Earnings or major event ≤ 45 days away (Alpha Vantage calendar)
Rule 3 – Risk/Reward (Core Names): Stock is not within 5% of its 52-week high OR has already pulled back ≥ 8% from its recent high
Rule 4 – Portfolio Fit: Fills a clear gap in existing clusters (power, optics, packaging, custom silicon, materials) and does not create redundancy

High-Conviction Underweight Override (Track A Core Names Only)
If BOTH conditions are met:
  Exceptional institutional conviction: Dark pool ≥ $25M OR Options flow ≥ $3.5M bullish (last 5 trading days)
  Portfolio is underweight: Current allocation < 5% of NAV OR below defined cluster target
Then: Rule 3 is automatically waived for that trading day. Higher incremental add sizing applies (see Override rows in Decision Matrix). This override may be used ONCE per name per earnings cycle.

Track B – Satellite / High-Beta Names (POET, AXTI, SIVE, FUWAY, SMTC, MXL, NVTS, VECO, and similar)
No dark pool requirement (Rule 1 waived).
No Rule 3 (Risk/Reward) requirement (waived).
Must pass only Rules 2 and 4.
Allowed even with zero dark pool flow and even if at or near all-time highs.
High-Beta / Parabolic Exception (Track B, Priority 1b): If earnings or major catalyst ≤ 30 days and Rules 2 and 4 are passed, the name can be added even with zero dark pool.

Framework 12 Decision Matrix (After Section 16 Gatekeeper Pass)
Priority | Condition | Max Size (Incremental Add) | Timing Rule
1-Override | Core Name + Earnings ≤ 14 days + Override conditions met | 1.75%–2.50% of NAV | Execute before the print
2-Override | Core Name + Earnings 15–45 days + Override conditions met | 1.50%–2.00% of NAV | Immediately or on minor dip
1 | Core Name + Earnings ≤ 14 days + passes Section 16 (no override) | 1.00%–1.50% of NAV | Execute before the print
1b | Satellite/High-Beta name + earnings ≤ 30 days | 0.40%–0.60% of NAV | Execute before the print
2 | Core Name + Earnings 15–45 days + underweight (no override) | 1.25%–1.75% of NAV | Only on dip to defined zone
2b | Satellite + Earnings 15–45 days | 0.50%–0.75% of NAV | Only on dip to defined zone
3 | Core Name + No immediate earnings but strong flow | 0.75%–1.00% of NAV | On 8–12% pullback
4 | Passes Section 16 but extended or low urgency | 0% (watchlist only) | Set alerts, wait for deeper dip


16.1 Score-Based Exit
If a Tier 1 or Tier 2 name drops below 55 for TWO consecutive scoring cycles: trim 50% of position within 5 trading days
If score drops below 45: exit fully within 3 trading days
Scoring cycle specification: Weekly rescore occurs every Friday at market close (or next trading day if Friday is a holiday). Scoring cycle = Friday close rescore using latest dark pool, options flow, earnings, and price data from that week.
Cycle ONE is triggered when a name first scores below 55 at a Friday rescore. Cycle TWO is triggered at the following Friday rescore if the score remains below 55.
Reconciliation pause: If a multi-model score reconciliation (e.g., Claude vs Grok gap >8 points) is pending, the cycle clock PAUSES — it does not accrue. Cycle count does not restart when reconciliation completes; it resumes from where it paused. Example: Cycle 1 triggered April 16. Reconciliation requested April 17. If reconciliation completes April 23, Cycle 2 check occurs April 25 (next Friday). If score still below 55 on April 25 post-reconciliation: trim rule fires.
Framework #12 deferral: If trim window falls within 7 days of an earnings or catalyst event (per Framework #12 Catalyst No-Fly Zone), the 5-day trim window is deferred by up to 10 trading days post-catalyst. The exit rule is NOT cancelled — it is deferred. Clock resumes after catalyst. This resolves the Opus 4.7 finding that exit rules could be perpetually blocked given the AI-infra portfolio's near-continuous catalyst calendar.

16.2 Gap-Down Rule
If any owned name gaps down more than 20% overnight: take NO action for 48 hours (prevent panic selling)
Rescore at 72 hours using latest available data
Apply score-based exit rule at 72 hours
§16.1 cycle clock pauses during the 72h gap-down window, then resumes from where it paused.
§16.4 protective puts are also frozen during the 48h window (buying puts post-gap locks in panic IV).
Framework #12 catalyst deferral does NOT override §16.2 — even if the gap is caused by the catalyst, the 72h wait still applies.

16.3 Appreciation Trim Rule
No new capital deployed into any name already above 8% of combined NAV at market value
If name exceeds 10% of NAV through appreciation: consider trimming 20% of position to manage concentration
This is a soft rule — discretion applies based on regime and catalyst pipeline

16.4 Put-Based Protection Rule
Buy protective puts when ALL of the following are true:
Institutional bearish options flow confirmed above $500K in a single session
Earnings binary event within 20 days
Name is up significantly from cost basis (protecting unrealized gains)
Score has dropped or is trending toward Tier 3 or Watchlist

16.5 Puts Philosophy
CORE RULE: PUTS ARE FOR PROTECTION ONLY — NEVER FOR INCOME GENERATION
Never sell puts on high-beta momentum names. The backtest (Oct 2025–Apr 2026, $1M deployed) confirmed put-selling came in LAST of four strategies — returning +$1.5M vs. +$3.8M for ATLAS Framework and +$3.5M for buy-and-hold. MRVL and VRT puts were assigned during the war period drawdown. Put premium on high-IV names (45–95% IV) is fair compensation for real assignment risk — it is not free money. May revisit on AVGO (lowest IV at 45%) in CLEAR regime only.


Put expiry: Use post-earnings expiry with 3–5 months of buffer. Not weekly or monthly — too little duration. Not 1-year+ — paying for unnecessary time value.
Put strike: 10–15% OTM for gain protection. ATM for binary event protection.
Put size: Cover 50–80% of the position (not 100% — leave some unhedged to participate in upside)

16.6 Currently Active Exit Situations (April 2026)
NBIS — EXIT RULE CYCLE ONE ACTIVE
NBIS: Score 51.5 (Watchlist). Exit rule cycle ONE triggered at Friday April 17, 2026 rescore (April 16 Thursday was the intraday signal; cycle officially starts at Friday close per Section 16.1). If score remains below 55 at next weekly rescore, trim 50% of 594-share position within 5 trading days. NBIS Sept $149 put (3–5 contracts) provides bridge protection through April 29 earnings. Score reconciliation with Grok (Grok has 63.0 — Tier 3) pending. Do NOT apply exit rule until reconciliation is complete.



Section 17: LEAPS Strategy Framework
17.1 Philosophy
Shares are PRIMARY — they capture full upside and survive crashes
LEAPS are the 4% NAV KICKER — add leverage on top of conviction positions
Never replace shares with LEAPS
Best entry: washout recovery (low price + IV compressing off spike)
Worst entry: near recent highs with elevated IV

17.2 Complete LEAPS Sizing Plan (April 2026)
Name
Structure
Strike / OTM
Est. Cost
% NAV
When
Status
LITE
2ct Jan 2027 $950C
+9.6% OTM
$16,000
0.69%
Done
✓ Active
AVGO
2ct Jan 2027 $400C
+5.3% OTM
$8,000
0.34%
Done
✓ Active
MRVL
3ct Jan27 $150C + 2ct Jan28 $165C
+12.8%/+24.1%
$14,850
0.64%
After CLEAR or washout
Pending
TSM
4ct Jan 2027 $420C
+12% OTM
$8,000
0.34%
After earnings digest
Pending
VRT
3ct Jan 2028 $400C
+34.4% OTM
$10,500
0.45%
After CLEAR
Pending
COHR
2ct Jan 2028 $420C
+37.1% OTM
$8,400
0.36%
After CLEAR + dark pool verify
Pending
MU
3ct Jan 2028 $580C
+29.9% OTM
$15,600
0.67%
After July 2026 earnings
Pending
TOTAL




$81,350
3.49%
Under 4% cap ✓




17.3 LEAPS Entry Priority Order
AND GATE APPLIES TO ALL LEAPS ENTRIES ABOVE $10K
Per Section 14.5, every LEAPS entry above $10,000 requires BOTH (1) CLEAR regime confirmed AND (2) Framework #29 at 3 of 5 signals confirmed. 'After CLEAR' throughout this section means 'after CLEAR + Framework #29 3/5 confirmed.' This applies to MRVL ($14,850), TSM ($8,000 — border case, verify), VRT ($10,500), COHR ($8,400 — border case, verify), and MU ($15,600). Entries under $10K may proceed on CLEAR alone.


Priority 1: MRVL Jan 2027 $150C + Jan 2028 $165C — June 4 earnings catalyst. Wait for washout ($105–110) or CLEAR confirmation.
Priority 2: TSM Jan 2027 $420C — post-earnings digest. TSM Q1 2026 beat +40.6% YoY, gross margin 66.2%. Wait for sell-the-news washout to clear.
Priority 3: COHR Jan 2028 $420C — after CLEAR. Verify $40M dark pool aggregate with Grok first before deploying.
Priority 4: VRT Jan 2028 $400C — after CLEAR. Multi-year power infrastructure thesis.
Priority 5: MU Jan 2028 $580C — after July 2026 earnings. IV currently 71% — too high. Wait for IV compression post-earnings.

17.4 Washout Entry Levels
Name
Washout Entry Zone
Current Price
Drop Required
IV Check
MRVL
$105–110
$134
-20% from current
IV must be below 6-month median
MU
$340–360
$440
-18% from current
IV must decline 20%+ from trailing 30-day peak
COHR
$240–260
$305
-15% from current
IV must be below 6-month median
VRT
$230–250
$298
-16% from current
IV must decline 20%+ from trailing 30-day peak
SNDK
$650–700
$888
-22% from current
IV 108% — currently excluded from LEAPS


17.5 Backtest Results — Strategy Comparison
Strategy
Total P&L (Oct 2025–Apr 2026)
Notes
Confidence (see Sec 19.3)
Pure LEAPS
+$7.6M (Claude model) / $4.2–5.8M (Grok range)
Won — but required holding through March war drawdown. High survivorship bias. Cannot be entered at war lows if Framework #30 drawdown gate is active.
LOW-MODERATE — HIGH survivorship bias. Sensitive to exact entry/exit timing. Do not treat as reliable evidence.
ATLAS Framework (shares + small LEAPS)
+$3.8M
Best risk-adjusted. Shares survived war period; LEAPS kicker added leverage.
MODERATE — approximate prices, directionally correct.
Buy & Hold
+$3.5M
Baseline. Strong underlying names.
MODERATE — same price uncertainty as ATLAS.
Brandon's Put Loop
+$1.5M
LAST — upside capped on 300–2600% movers. Not appropriate for this portfolio.
MODERATE — backtest confirmed structural ceiling on upside capture.

See Section 19.3 for full confidence ratings and methodology notes on all backtest claims. The Pure LEAPS figure in particular should not be used as a performance benchmark — its confidence rating is LOW-MODERATE and the survivorship bias is explicitly acknowledged.

17.6 LEAPS Module Implementation Specification
REQUIRED FOR V1 BUILD — SECTION 12 DELIVERABLE
Section 12 lists 'LEAPS tracking module (read-only initially — tracks positions and theta) per Section 17' as a developer deliverable. This section provides the implementation specification. Without it, the developer will guess at theta methodology, IV tracking, and alert integration.


17.6.1 Position Tracking
Each LEAPS position tracked with: ticker, option symbol, expiry date, strike price, contracts held, premium paid per contract, total cost basis, current mid-market premium, current intrinsic value, current time value, days to expiry, and implied volatility at time of last refresh.
Positions refreshed daily at morning briefing using Unusual Whales or broker API live options data. Mark-to-market using mid-market price (bid + ask) / 2. If bid-ask spread exceeds 5% of mid, system flags WIDE_SPREAD in the LEAPS dashboard.

17.6.2 Theta Calculation
Theta is provided directly by the options pricing feed as dollar-per-day decay per contract. System does NOT independently calculate theta — it consumes the theta value from the data source.
If the data source does not provide theta: use Black-Scholes approximation. Inputs: current underlying price (S), strike price (K), days to expiry (T in years), risk-free rate (current 3-month T-bill rate updated weekly), implied volatility from feed. Output: dollar-per-day per share × 100 = per-contract theta.
Theta acceleration alert: when days-to-expiry crosses below 365 (12 months), system flags THETA_ACCELERATION_WARNING for that position in every morning briefing. Roll-to-2028 decision trigger. Specific case: LITE and AVGO Jan 2027 positions are already inside this window. Decision point August 2026.
Weekly theta burn: system calculates (contracts × theta × 7) = projected weekly time decay cost. Displayed in briefing as 'LEAPS weekly cost of carry: $X.'

17.6.3 IV Tracking
Implied volatility tracked per position daily. Stored as a time series: 30-day rolling minimum, 180-day rolling preferred.
IV alert thresholds: IV_HIGH_ALERT fires when position IV exceeds 90% — no new LEAPS purchases for this name until IV drops below 85%. IV_COMPRESSION_SIGNAL fires when IV has declined more than 20% from trailing 30-day peak AND is now below 6-month median — this is the washout-recovery LEAPS entry signal. IV_EARNINGS_PROXIMITY fires when IV is rising and earnings are within 60 days — reminds operator of the 4-8 week pre-earnings entry window rule.
IV percentile display: show current IV as a percentile of its trailing 180-day range (e.g., 'MRVL IV: 48% — at 35th percentile of 6-month range'). Context is more useful than absolute IV number.

17.6.4 Alert Integration
Alert
Trigger
Action Required
THETA_ACCELERATION_WARNING
Days to expiry < 365
Operator decision: roll, hold, or exit. No automatic action.
IV_HIGH_ALERT
Position IV > 90%
No new LEAPS for this name until IV drops below 85%.
IV_COMPRESSION_SIGNAL
IV declined >20% from 30d peak AND IV < 6-month median
Check price criterion. If price also -15%+ from 60d high: LEAPS entry eligible.
LEAPS_SOFT_ALERT
Total LEAPS NAV > 3.5%
Human written approval required before any new LEAPS order.
LEAPS_HARD_STOP
Total LEAPS NAV > 4.0%
No new entries. Existing positions held to expiry or rolled only.
FRAMEWORK30_CARVEOUT
Portfolio drawdown 15-25% AND LEAPS entry pending
Entry permitted at 0.5% NAV cap. At 25% drawdown: carve-out suspended.


17.6.5 Roll Decision Logic
Monthly LEAPS REVIEW REPORT on first Monday of each month: for each position shows current moneyness (price vs strike %), IV percentile, days to expiry, current theta, and ROLL RECOMMENDED flag if days to expiry < 270 AND position is less than 15% in-the-money.
Roll mechanics: sell current position, buy new with later expiry. System logs both as separate transactions in Decision Trace. LEAPS NAV calculation uses net cost basis after roll.


Section 18: Pending Actions and Catalyst Calendar (April 2026)
18.1 Execute Before April 22 (Ceasefire Expiration)
NBIS put protection: 3–5 contracts NBIS Sept 19 2026 $149 put. $8,000–$13,000. Strike $149 = 10.8% OTM from $167. Execute before April 29 earnings.

18.2 Execute When CLEAR Confirms (Brent two consecutive closes below $95)
MRVL 100 shares tactical add — SOFT CAUTION rule (dark pool $919K confirmed, underweight 0.5%+ below target)
MRVL LEAPS — 3ct Jan 2027 $150C + 2ct Jan 2028 $165C — $14,850
TSM Jan 2027 $420C LEAPS — 4 contracts — ~$8,000 — after earnings digest confirms no guidance disappointment
Tranche 3 deployment: ICHR $25K, LITE add $20K, AVGO add $25K, MRVL add $20K, UCTT $15K, MYRG $15K, GEV $30K = $150K total. REQUIRES BOTH conditions: (1) CLEAR regime confirmed AND (2) Framework #29 at 3/5 signals. The AND gate is required — see Section 14.5 for proof. March 23 2026 fake-CLEAR event: Brent dropped $16 in one session on Trump tweet, appeared to approach CLEAR threshold, then reversed next day when Iran denied talks. Without the AND gate, $150K would have been deployed into a one-day fake rally.

18.3 Scoring Reconciliation Required
Ask Grok for F1-F5 factor inputs on NBIS — determines whether exit rule applies immediately or after Grok reconciliation
Ask Grok for F1-F5 factor inputs on POET — determines satellite eligibility
Verify COHR aggregate dark pool across all 6 files ($39.9M — Grok disagreed on magnitude)
Rescore SIVE incorporating Jabil 1.6T LRO production design win confirmation

18.4 Key Upcoming Catalysts
Date
Event
Impact
April 20
SNDK Nasdaq-100 inclusion
Forced buying — hold, no-fly zone active
April 22
Ceasefire expiration
Key geopolitical binary — position before, not after
April 29
NBIS earnings
Binary — put protection must be in place before this date
April 30
SNDK earnings
Key print — memory cycle update
May 14
AAOI earnings
Confirmed date (not April 30)
May 27
NVDA earnings
Sector-wide catalyst — all AI names affected
June 4
MRVL earnings
Custom silicon confirmation — LEAPS entry decision
June 4
AVGO earnings
LEAPS catalyst
June 24
MU earnings
HBM pricing cycle update
July 2026
MU earnings
LEAPS entry window — IV should compress post-print



Section 19: Backtest Methodology and Assumptions
WHY THIS SECTION EXISTS
Multiple framework decisions in this document are justified by backtest evidence. A developer, auditor, or future reviewer cannot evaluate those decisions without understanding the methodology behind the backtests. This section documents data sources, assumptions, known biases, and limitations for every backtest cited in the document. Framework decisions justified by flawed backtests inherit those flaws. Transparency here protects the framework from invisible errors.


19.1 Price Data Sources
Primary: Price history derived from trading session transcripts (Claude + Grok analysis sessions, March 2024 – April 2026). Key price anchors at: April 2024 (baseline), June 2024, September 2024, January 2025 (DeepSeek event), March 2025, June 2025, September 2025, January 2026, March 2026 (Iran war lows), April 2026 (current).
Secondary: Live market data from Unusual Whales dark pool/options flow feeds as documented in session transcripts.
Known limitation: Point-in-time prices are approximations from transcript references, NOT tick-level data from a licensed data provider. Exact dollar figures carry ±5-10% uncertainty. Directional conclusions (which direction prices moved, which names outperformed) are high-confidence. Exact return figures are moderate-confidence.
Not used for this document: real-time licensed data feeds (Bloomberg, FactSet, Refinitiv). All price data is manually sourced from trading session records. For live system operation, data sources are specified in Section 4.1 (primary) and Section 13.5 per-factor (refresh cadences).

19.2 Known Biases
Survivorship bias: The portfolio holds names that survived the March 2026 war period. Names that would have been catastrophically impaired by a TSMC strike or semiconductor supply chain collapse are not represented. All 12-month return figures therefore reflect a survivorship-biased universe.
Selection bias: Names analyzed are names already held or actively considered. The backtest does not evaluate names that were screened OUT by the framework. A complete framework backtest would require evaluating rejected names as a control group.
Lookback leakage: Some framework rules (e.g., the grey zone narrowing from 75-85 to 78-85 based on MRVL and CRDO historical performance) were calibrated using the same data they are then applied to. This is a form of overfitting. The calibration is defensible because MRVL and CRDO are cited as examples, not as the sole basis for the rule — but it is not a clean out-of-sample test.
Regime selection: The 12-month period April 2025 – April 2026 included an unusually high-volatility event (Iran war, March 2026) and an unusually strong AI infrastructure bull run. Framework performance in a prolonged bear market, an AI capex disappointment cycle, or a sustained high-rate environment is not tested.

19.3 Specific Backtest Claims and Confidence Levels
Claim
Section
Confidence
Methodology
Bias Risk
SOFT CAUTION 15% floor gives $23K GTC window (matches $22.5K calculation rounded)
15.3
HIGH
Arithmetic: $468K - (1.1 × 15% × $2.7M) = $22.5K. Verified by Opus 4.7.
None — pure math
SOX dual trigger catches DeepSeek, -8%/10d does not
14.3
HIGH
DeepSeek Jan 27 2025: SOX -9% single day, -6.5% 10-day. Verified via external search.
None — event is documented
Framework #29 AND gate saves $18K on March 23 fake-CLEAR
14.5
MODERATE-HIGH
March 23 Brent moved $16 intraday on Trump tweet, reversed next day. $150K × 12% drawdown = $18K estimated. Brent reversal confirmed in session transcript.
Estimate: actual drawdown timing uncertain
MRVL scored 75-78 in early 2025, rose +49%
13.1b, 14.3
MODERATE
Mar25 price ~$90, Apr26 ~$134. Score of 75-78 inferred from session discussion, not a formal rescore.
Score is estimated, not formally computed
War washout LEAPS: MRVL $80 entry, +68% gain
17.5, 14.5
MODERATE
Mar26 MRVL low ~$80 confirmed in transcripts. Apr26 price $134. Return arithmetic correct.
Entry timing uncertain — $80 was a brief intraday low, not a sustained level
ATLAS Framework +$3.8M vs Buy-Hold +$3.5M vs LEAPS +$7.6M
17.5
LOW-MODERATE
Backtest run during session using approximate prices. Not using licensed data. Survivorship bias applies.
HIGH survivorship bias. LEAPS figure especially sensitive to exact entry/exit timing.
Concentration gate cost $31K opportunity (MU/TSM/COHR war adds blocked)
S15.2 narrative
MODERATE
Approximate: $50K × 16-34% gains on MU/TSM. COHR $24K × 27%. Directionally correct.
Assumes adds at exact war lows — unrealistic execution assumption
Exit rule correctly fires on NBIS, not on CIEN/VRT
16.1
HIGH
NBIS score trajectory declining confirmed by institutional puts + war impact. CIEN/VRT recovered fully — score trajectory consistent with no exit trigger.
Exit rule is new — no actual historical trigger to verify


19.4 What Has NOT Been Backtested
Framework #30 Max Drawdown Gate: No historical test of whether the 15% drawdown trigger level is optimal. A 10% trigger would have fired during the war period; a 20% trigger would not have. The 15% level is calibrated to conventional risk management practice, not to portfolio-specific data.
Framework #29 five-signal selection: The specific five signals (VIX trend, put/call, 200-DMA, ETF flow, oil vs 7-day MA) have not been individually backtested for predictive power. They are based on institutional knowledge of capitulation patterns. Forward signal accuracy is unknown.
Scoring weights (F1=15%, F2=25%, F3=15%, F4=15%, F5=30%): The revised weights have not been formally tested against the prior equal-weight system using a common evaluation period. The change is theoretically justified (reducing sentiment triple-count) but not empirically validated on this portfolio's specific names.
SOX dual-trigger threshold values (-4%/-5%): The specific thresholds are calibrated to the DeepSeek event (single data point). They have not been tested against other AI-sector rotation events. The thresholds may need recalibration after 6-12 months of live operation.
Tier boundary values (55, 70, 78, 85): These cutoffs are not empirically derived. They are round-number conventions. The Bayesian tuner in V3 will provide the first systematic test of whether these boundaries predict outcomes.

19.5 Framework for Future Backtesting
When the V1 agentic system is live and generating Decision Trace records: all framework decisions should be logged with score snapshots, framework states, and subsequent 30/60/90-day outcomes. This creates the dataset for the V3 Bayesian tuner and the Walk-Forward Optimization Loop.
Minimum 6 months of paper trading data required before any framework parameter (scoring weights, threshold values, GTC floor, grey zone boundary) should be adjusted. Current parameters are starting hypotheses, not proven optima.
The Performance Attribution Dashboard in Section 6.6 is the correct long-term tool. Framework-level attribution (which frameworks blocked signals that would have been wrong) and factor-level attribution (which F1-F5 factors predicted outcomes) will produce the first genuinely clean backtest of this specific portfolio.


FINAL STATEMENT — ATLAS v7.3.3
This document has been reviewed across multiple sessions by Claude (primary), Grok (cross-verification), and Opus 4.7 (adversarial audit). It combines the complete agentic AI trading system architecture from v6.0 FINAL (March 2026) — 32 frameworks, 12-factor scoring, V1/V2/V3 build specification, acceptance tests, contract protections — with the complete ATLAS operational framework from April 2026: 5-factor conviction scoring (F1-F5 revised weights), 4-regime modifier system, three-bucket allocation rules, exit rules (previously missing), LEAPS strategy framework, and all post-Opus 4.7 audit changes. The system is ready to send to a developer. The operational rules are ready to use today.


ATLAS v7.3.3 | April 2026 | 32 Frameworks + 5-Factor Scoring Algorithms (Section 13.5) + Regime Transition State Machine (Section 14.7) + LEAPS Module Spec (Section 17.6) + Backtest Methodology (Section 19) | Reviewed: Claude Sonnet 4.6 + Grok (2 passes) + Opus 4.7 adversarial audit (2 passes) | Developer-ready: all structural implementation gaps addressed
