export const DISCLAIMER_TEXT =
  "AI-generated analysis from public data sources. Not investment advice. Confidence and target-price figures reflect qualitative AI reasoning, not statistical or regulatory-grade forecasts. Verify independently before any financial decision.";

export const DisclaimerNote = ({ className = "" }) => (
  <p
    className={`text-[10px] tracking-wider leading-snug text-zinc-500 ${className}`}
    data-testid="disclaimer-note"
  >
    {DISCLAIMER_TEXT}
  </p>
);
