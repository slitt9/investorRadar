/** Log-scale market cap range for the screener slider (fine control below ~$5B). */

export const UI_MAX_MARKET_CAP = 2_000_000_000_000;

/** Slider uses discrete steps 0 … CAP_SLIDER_MAX (inclusive). */
export const CAP_SLIDER_MAX = 1000;

/** Lower end of log mapping ($1M); position 0 on the slider still means $0 min. */
const CAP_LOG_LOW = 1_000_000;

export function marketCapFromSliderPosition(pos: number): number {
  const p = Math.max(0, Math.min(CAP_SLIDER_MAX, Math.round(pos)));
  if (p <= 0) return 0;
  const t = p / CAP_SLIDER_MAX;
  const logLo = Math.log10(CAP_LOG_LOW);
  const logHi = Math.log10(UI_MAX_MARKET_CAP);
  const cap = 10 ** (logLo + t * (logHi - logLo));
  return Math.round(cap);
}

export function sliderPositionFromMarketCap(cap: number): number {
  if (cap <= 0) return 0;
  if (cap >= UI_MAX_MARKET_CAP) return CAP_SLIDER_MAX;
  const logLo = Math.log10(CAP_LOG_LOW);
  const logHi = Math.log10(UI_MAX_MARKET_CAP);
  const t =
    (Math.log10(Math.max(cap, CAP_LOG_LOW)) - logLo) / (logHi - logLo);
  return Math.round(Math.min(CAP_SLIDER_MAX, Math.max(0, t * CAP_SLIDER_MAX)));
}
