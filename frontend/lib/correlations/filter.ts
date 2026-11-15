import { SOURCE_NAMES, type Correlation, type Provenance, type Severity, type SourceName } from "../api-types";

export interface CorrelationFilters {
  /** Empty string means all severities. */
  severity: Severity | "";
  /** Empty string means all rules. */
  ruleId: string;
}

export const NO_FILTERS: CorrelationFilters = { severity: "", ruleId: "" };

/** Correlations matching both filters, in the order given. */
export function filterCorrelations(
  correlations: readonly Correlation[],
  filters: CorrelationFilters,
): Correlation[] {
  return correlations.filter(
    (correlation) =>
      (filters.severity === "" || correlation.severity === filters.severity) &&
      (filters.ruleId === "" || correlation.rule_id === filters.ruleId),
  );
}

/** Distinct rule ids, sorted, for the rule filter. */
export function ruleIdsOf(correlations: readonly Correlation[]): string[] {
  return [...new Set(correlations.map((correlation) => correlation.rule_id))].sort();
}

/** Distinct contributing sources in the canonical order (Excel, Access, WhatsApp, MoMo). */
export function contributingSources(provenance: readonly Provenance[]): SourceName[] {
  const present = new Set(provenance.map((entry) => entry.source));
  return SOURCE_NAMES.filter((name) => present.has(name));
}

/** Number of correlations per severity. */
export function countBySeverity(correlations: readonly Correlation[]): Record<Severity, number> {
  const counts: Record<Severity, number> = { info: 0, warning: 0, error: 0 };
  for (const correlation of correlations) {
    counts[correlation.severity] += 1;
  }
  return counts;
}
