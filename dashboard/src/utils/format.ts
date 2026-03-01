/** Format a number as currency: $1,234.56 */
export function fmt(n: number | null | undefined): string {
  if (n == null) return '\u2014';
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Format an integer with commas: 1,234 */
export function fmtInt(n: number | null | undefined): string {
  if (n == null) return '\u2014';
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
}
