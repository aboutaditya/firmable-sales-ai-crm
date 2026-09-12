export type Company = {
  company_id: string;
  domain: string;
  organization: string | null;
  country: string | null;
  city: string | null;
  security_score: number;
  asset_count: number;
  vulnerability_count: number;
  critical_vulnerability_count: number;
  eol_product_count: number;
  exposed_rdp: boolean;
  exposed_database: boolean;
  exposed_exchange: boolean;
  industry: string | null;
  employee_count: number | null;
};

export type AIContentOutput = {
  company_id: string;
  feature: "company_summary" | "outreach";
  content: string;
  cached: boolean;
  model: string;
  prompt_version: string;
  latency_ms: number | null;
};

export type AssessmentOutput = {
  company_id: string;
  ai_score: number;
  priority: "HIGH" | "MEDIUM" | "LOW";
  confidence: number;
  reasoning: string;
  cached: boolean;
  model: string;
  prompt_version: string;
  latency_ms: number | null;
  cost_usd?: number | null;
};

export type AIOutput = AIContentOutput | AssessmentOutput;

export type Disposition =
  | "not_contacted"
  | "call_attempted"
  | "connected"
  | "qualified"
  | "disqualified"
  | "nurture"
  | "bad_data"
  | "do_not_contact";

export type QueuePreferences = {
  min_exposure_score: number;
  page_size: 1;
};

export type QueueLead = {
  company: Company;
  status: string;
  disposition: Disposition | null;
  notes: string | null;
  claimed_at: string | null;
  next_follow_up_at: string | null;
};

export type QueueNextResponse = {
  lead: QueueLead | null;
  min_exposure_score: number;
  assigned_count: number;
  eligible_count: number;
  message: string;
};

export type QueueListResponse = {
  items: QueueLead[];
  count: number;
  page: number;
  page_size: number;
  has_more: boolean;
};

export type AdminUser = {
  user_id: string;
  email: string | null;
  display_name: string | null;
  role: string;
  min_exposure_score: number;
  page_size: 1;
  assigned_count: number;
};