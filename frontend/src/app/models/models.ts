export type FieldMapping = Record<string, string>;

export interface SchemaField {
  name: string;
  label: string;
  type: string;
}

export type ReviewReason = 'unresolved' | 'ai_guess' | 'low_confidence' | 'empty' | null;

// One column of the uploaded file, as the mapper saw it
export interface ColumnSuggestion {
  name: string;
  type: string;
  examples: unknown[];
  target: string | null;
  method: 'synonym' | 'fuzzy' | 'embedding' | 'llm' | null;
  confidence: number;
  review_reason: ReviewReason;
}

export interface MappingResult {
  mapping: FieldMapping;
  columns: ColumnSuggestion[];
  status: 'ok' | 'needs_review' | 'error';
  unresolved_columns: string[];
  errors: string[];
  warnings: string[];
  notes: string[];
}

// POST /datasets/upload and GET /datasets/{id}/review
export interface ReviewResponse {
  dataset_id: string;
  filename: string;
  row_count: number;
  status: 'pending' | 'ready';
  result: MappingResult;
  fields: SchemaField[];
  quote: Quote;
}

export type ChartType = 'kpi' | 'line' | 'bar' | 'donut' | 'scatter';
export type ValueFormat = 'currency' | 'number' | 'percent';

export interface ChartSpec {
  name: string;
  title: string;
  chart_type: ChartType;
  size: 'kpi' | 'wide' | 'half';
  default_visible: boolean;
  config: {
    format?: ValueFormat;
    x?: string;
    y?: string;
    [key: string]: unknown;
  };
}

export interface DatasetOverview {
  id: string;
  filename: string;
  created_at: string;
  loaded_at: string | null;
  row_count: number;
  source_rows: number;
  mapping: FieldMapping;
  charts: ChartSpec[];
  hidden_charts: string[];
  date_field: string | null;
  date_min: string | null;
  date_max: string | null;
  warnings?: string[];
  credits?: { charged: number; total_paid: number; balance: number };
  credits_used?: number;
}

export interface DatasetSummary {
  id: string;
  filename: string;
  status: 'pending' | 'ready';
  created_at: string;
  loaded_at: string | null;
  source_rows: number;
  row_count: number | null;
  chart_count: number;
  credits_used: number;
}

export interface ChartRow {
  label: string;
  value: number | null;
  is_other?: boolean;
}

export interface ChartData {
  value?: number | null;
  rows?: ChartRow[];
  points?: [number, number][];
  granularity?: 'day' | 'week' | 'month' | 'year' | null;
  hidden_groups?: number;
}

export interface ChartDataResponse {
  chart: ChartSpec;
  data: ChartData;
}

export interface DateRange {
  from: string | null; // yyyy-mm-dd
  to: string | null;
}

// ---------- account & credits ----------

export interface Me {
  user: { id: string; email: string | null; name: string | null };
  account: { id: string; name: string; credit_balance: number };
  pricing: Pricing;
}

/** One line of a price: what resource, how much of it, and what it costs in credits. */
export interface PriceLine {
  key: 'base' | 'processing' | 'storage' | 'ai';
  label: string;
  detail: string;
  amount: number;
}

/** Price of building a dashboard, computed by the server from the resources it needs. */
export interface Quote {
  credits: number; // total, rounded up
  exact: number; // sum of the lines before rounding
  lines: PriceLine[];
  drivers: { rows: number; columns: number; cells: number; storage_bytes: number; ai_columns: number };
  paid: number; // already paid for this dashboard
  due: number; // what building now would charge
  balance: number;
}

export interface Pricing {
  base: number;
  cells_per_credit: number;
  mb_per_credit: number;
  per_ai_column: number;
  minimum: number;
  examples: { label: string; rows: number; columns: number; credits: number }[];
}

export interface CreditPack {
  code: string;
  credits: number;
  price_millimes: number;
  price_tnd: number;
}

export interface LedgerEntry {
  id: number;
  delta: number;
  balance_after: number;
  kind: 'welcome' | 'topup' | 'dashboard' | 'refund' | 'adjustment';
  description: string;
  created_at: string;
}

export interface CreditsOverview {
  balance: number;
  pricing: Pricing;
  packs: CreditPack[];
  history: LedgerEntry[];
}
