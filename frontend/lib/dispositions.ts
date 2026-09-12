import { Company, Disposition } from "./api";

export const dispositionLabels: Record<Disposition, string> = {
  not_contacted: "Not contacted",
  call_attempted: "Call attempted",
  connected: "Connected",
  qualified: "Qualified",
  disqualified: "Disqualified",
  nurture: "Nurture / follow up",
  bad_data: "Bad data",
  do_not_contact: "Do not contact",
};

export const CALL_OUTCOMES: Disposition[] = [
  "call_attempted",
  "connected",
  "qualified",
  "disqualified",
  "nurture",
  "do_not_contact",
];

export const TERMINAL_DISPOSITIONS: Disposition[] = [
  "qualified",
  "disqualified",
  "bad_data",
  "do_not_contact",
  "nurture",
];

export function observedSignals(company: Company): string[] {
  return [
    company.critical_vulnerability_count > 0 ? `${company.critical_vulnerability_count} critical vulnerability${company.critical_vulnerability_count === 1 ? "" : "ies"}` : "",
    company.vulnerability_count > 0 ? `${company.vulnerability_count} vulnerabilities` : "",
    company.exposed_rdp ? "Exposed RDP" : "",
    company.exposed_database ? "Exposed database" : "",
    company.exposed_exchange ? "Exposed Exchange" : "",
    company.eol_product_count > 0 ? `${company.eol_product_count} EOL product${company.eol_product_count === 1 ? "" : "s"}` : "",
  ].filter(Boolean);
}