/** Close codes that must NOT be retried (fatal). */
export const FATAL_CLOSE_CODES = new Set<number>([1008, 4400, 4401]);

/** Report if a close code is fatal (no retry). */
export function isFatalCode(code: number): boolean {
  return FATAL_CLOSE_CODES.has(code);
}

/** Options for the exponential backoff calculation. */
export interface BackoffOptions {
  baseMs: number;
  capMs: number;
  retryCount: number;
  jitter?: "full" | "none";
}

/** Calculate the backoff delay in milliseconds. */
export function calculateBackoff(options: BackoffOptions): number {
  const { baseMs, capMs, retryCount, jitter = "full" } = options;
  const exponential = baseMs * 2 ** retryCount;
  const capped = Math.min(exponential, capMs);
  const jitterFactor = jitter === "full" ? Math.random() : 1;
  return capped * jitterFactor;
}
