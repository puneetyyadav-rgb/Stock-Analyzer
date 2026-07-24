# Concall Guidance & Hesitation Matrix — Implementation Plan

## Why this is built the way it is

The pitch document behind this feature makes a real claim: that the gap between a
company's PR-polished prepared remarks and its unscripted analyst Q&A carries
predictive signal about future earnings. That premise has genuine academic grounding
(deception-detection and linguistic-analysis research on earnings calls). But the
document oversells the strength of that signal with an unsourced "predicts downgrades
1-2 quarters out" claim, and it jumps straight to a full dashboard build — heatmaps,
scorecards, trend charts — before anyone has checked whether the signal holds up on
real Indian-market transcripts.

So this plan is built in two stages, in this order:

1. **Prove the signal cheaply** before writing a data pipeline or NLP scoring engine.
2. **Wire it in as a factor** feeding the existing Alpha158/SHAP/IC scoring pipeline —
   not as a standalone dashboard tab. Concall tone should be tested for IC (information
   coefficient) contribution the same way every other factor in Stock-Analyzer is,
   before it earns a permanent UI surface.

The dashboard elements from the original pitch (topic heatmap, reliability scorecard,
8-quarter trend chart) are real, but they're Phase 5 — gated on Phases 0-4 actually
producing a validated, non-zero signal. Building the UI first means burning weeks on
NLP infrastructure for a feature that might not survive first contact with real data.

## Architecture

```
Phase 0: Manual validation (no code, or throwaway scripts only)
   |
   v
Phase 1: Transcript acquisition pipeline
   |
   v
Phase 2: Transcript segmentation (prepared remarks vs Q&A)
   |
   v
Phase 3: NLP scoring engine (sentiment + hesitation index)
   |
   v
Phase 4: Factor integration into existing IC scoring pipeline
   |
   v
Phase 5 (conditional): Dashboard UI — only if Phase 4 shows IC contribution
```

### Phase 0 — Validate before building anything
Pick 15-20 NSE-listed stocks already covered in Stock-Analyzer. Manually pull their
last 8 quarters of concall transcripts (company IR pages, Screener.in, or
Trendlyne — no scraping yet, just download PDFs by hand). Eyeball the tone shift
between prepared remarks and Q&A per quarter, and check it against what actually
happened to earnings/guidance the following quarter. This costs an afternoon, not a
sprint. If there's no visible pattern here, stop — don't proceed to Phase 1.

### Phase 1 — Transcript acquisition pipeline
Realistic sourcing options for Indian concall transcripts, in order of reliability:
- Company investor-relations pages (PDF transcripts, posted per-quarter, inconsistent
  formatting company to company)
- BSE/NSE corporate announcement filings (transcripts are sometimes attached as PDFs)
- Screener.in / Trendlyne aggregation pages (easier to scrape, but coverage and
  formatting consistency need to be checked, and terms of use should be reviewed
  before scraping at volume)

No single source has clean API access — this phase is fundamentally PDF-scraping and
normalization work, similar in shape to the existing Scrapling-based data pipeline
work already underway for Stock-Analyzer.

### Phase 2 — Transcript segmentation
Concall PDFs don't reliably label "Prepared Remarks" vs "Q&A" as structured sections.
This needs a rules-based splitter first (look for standard phrases like "we will now
open the floor for questions," moderator handoffs, speaker-tag changes), with manual
verification against the Phase 0 sample set before trusting it at scale.

### Phase 3 — NLP scoring engine
- Sentiment scoring on each segment. FinBERT is the safer default over VADER (VADER is
  tuned for social media, not analyst calls) — but FinBERT is trained on largely
  US financial text, so its output should be spot-checked against the Phase 0 manual
  reads for Indian-English concall speech before being trusted.
- Hesitation Index: keyword-frequency scoring across uncertainty/evasive/margin-stress/
  delay-word categories. This is a weighted keyword counter, not a deep model — its
  quality lives entirely in the keyword list, which should be built and tuned against
  the Phase 0 sample, not written from scratch and shipped.
- Guidance Delivery Ratio: deprioritize this sub-feature. It requires hand-built
  historical data (management's stated targets vs. delivered results per company per
  quarter) that has no clean structured source — treat as a manual/optional add-on,
  not part of the initial build.

### Phase 4 — Factor integration
Output of Phase 3 (divergence score, hesitation index) becomes one more factor fed
into the existing Alpha158/SHAP/IC scoring pipeline, scored for IC contribution the
same way as every other factor already in the system. This is the actual go/no-go
gate for the feature.

### Phase 5 — Dashboard UI (conditional)
Only build if Phase 4 shows the factor adds IC. If it does, the original pitch's UI
ideas are reasonable groundwork: 8-quarter tone/hesitation trend chart, topic-wise
Q&A heatmap, red-flag snippet cards, and reliability scorecard (this last one depends
on Guidance Delivery Ratio data, so may lag the rest).

## Task List

**Phase 0 (validation)**
- [ ] Select 15-20 tracked NSE stocks with consistent quarterly concall history
- [ ] Manually source last 8 quarters of transcripts per stock (IR pages/Screener/Trendlyne)
- [ ] Manually tag prepared-remarks vs Q&A boundary per transcript
- [ ] Read and hand-score tone shift per quarter (rough +/- call is enough)
- [ ] Cross-check tone shift against actual next-quarter results/guidance changes
- [ ] Go/no-go decision on proceeding to Phase 1

**Phase 1 (data pipeline)**
- [ ] Evaluate transcript coverage/consistency across IR pages, BSE/NSE filings, Screener, Trendlyne
- [ ] Build scraper/downloader for chosen source(s), reusing existing Scrapling pipeline patterns
- [ ] Build PDF-to-text extraction and storage (raw transcript store, keyed by stock+quarter)

**Phase 2 (segmentation)**
- [ ] Build rules-based prepared-remarks/Q&A splitter
- [ ] Validate splitter output against Phase 0 manually-tagged transcripts
- [ ] Handle edge cases (no Q&A section, multiple moderators, non-standard formats)

**Phase 3 (NLP scoring)**
- [ ] Integrate FinBERT (or comparable) sentiment scoring on both segments
- [ ] Build/tune hedging-keyword lists per category (uncertainty/evasive/margin/delay)
- [ ] Compute Divergence and Hesitation Index per transcript
- [ ] Spot-check scores against Phase 0 manual reads; recalibrate keyword lists as needed

**Phase 4 (factor integration)**
- [ ] Feed Divergence/Hesitation Index into existing IC scoring framework as a new factor
- [ ] Run IC/SHAP evaluation to check standalone and combined contribution
- [ ] Decide whether factor is retained, reweighted, or dropped

**Phase 5 (UI — conditional on Phase 4 passing)**
- [ ] 8-quarter tone/hesitation trend chart (alongside price chart)
- [ ] Topic-wise Q&A heatmap by category
- [ ] Red-flag snippet cards (exact Q&A excerpts flagged high-hesitation)
- [ ] Guidance Delivery Ratio / reliability scorecard (if historical guidance data sourced)

## Open risks to flag to the coder
- Transcript source coverage/reliability is the single biggest unknown — this could
  turn out to be the majority of the effort.
- FinBERT domain mismatch on Indian-English concall speech is unverified until spot-checked.
- Guidance Delivery Ratio has no clean data source and should not block the rest of the build.
- The whole feature is gated on Phase 0 and Phase 4 — don't let Phase 5 UI work start early.
