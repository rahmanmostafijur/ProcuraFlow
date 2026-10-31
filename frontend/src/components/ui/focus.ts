/** The 2 px focus ring (token `--focus`) with a 2 px offset, shown for keyboard focus only. */
export const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-surface";

/** Same ring for controls that should also show it on mouse focus (text fields). */
export const FOCUS_RING_ALWAYS =
  "focus:outline-none focus:ring-2 focus:ring-focus focus:ring-offset-1 focus:ring-offset-surface";

/** Forced-focus look for the design-system page. */
export const FORCED_FOCUS = "outline-none ring-2 ring-focus ring-offset-2 ring-offset-surface";
