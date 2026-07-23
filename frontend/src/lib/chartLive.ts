/** Shared Recharts props for live-updating dashboard charts. */

/**
 * Disable series animation so polling / SSE refetches update bars and lines
 * in place instead of replaying entrance animations every refresh.
 */
export const LIVE_SERIES_PROPS = {
  isAnimationActive: false,
  animationDuration: 0,
} as const;

/**
 * Slight debounce on ResponsiveContainer resize observers — reduces layout
 * thrash when the shell reflows during concurrent updates.
 */
export const LIVE_RESPONSIVE_PROPS = {
  width: "100%" as const,
  height: 360,
  debounce: 50,
};
