// Extend/merge this with your existing src/app/models/models.ts.
// Shapes below mirror exactly what api.py returns.

export interface FieldMapping {
  [sourceColumn: string]: string;
}

export interface NeedsConfirmationItem {
  source: string;
  suggestions?: string[];
  confidence?: number;
}

export interface MappingResult {
  mapping: FieldMapping;
  unresolved_columns: string[];
  needs_confirmation: NeedsConfirmationItem[];
  errors: string[];
}

export interface UploadResponse {
  job_id: string;
  result: MappingResult;
}

export interface FieldConfirmation {
  source_column: string;
  target_field?: string | null; // null/undefined = leave unresolved
}

export interface ChartSpec {
  name: string;
  title?: string;
  type?: string;
  config: Record<string, any>;
}

export interface ConfirmResponse {
  job_id: string;
  result: MappingResult;
  charts: ChartSpec[];
}

export interface ChartDataResponse {
  chart: ChartSpec;
  data: Record<string, any>[];
}
