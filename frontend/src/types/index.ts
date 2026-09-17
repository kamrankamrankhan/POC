export interface ProcessingStatus {
  pending: 'pending';
  processing: 'processing';
  completed: 'completed';
  failed: 'failed';
}

export interface QualityFlag {
  blur: 'blur';
  orientation: 'orientation';
  cropping: 'cropping';
  color_consistency: 'color_consistency';
  low_resolution: 'low_resolution';
  low_dpi: 'low_dpi';
  poor_ocr: 'poor_ocr';
}

export interface ReviewStatus {
  pending: 'pending';
  approved: 'approved';
  rejected: 'rejected';
}

export interface PageQualityResult {
  page_number: number;
  confidence_score: number;
  heuristic_confidence_score?: number;
  ml_confidence_score?: number;
  dl_confidence_score?: number;
  ocr_confidence_score?: number;
  ocr_text_preview?: string;
  ocr_word_count?: number;
  ocr_engine?: string;
  llm_confidence_score?: number;
  llm_summary?: string;
  llm_issues?: string[];
  llm_model?: string;
  llm_invoked?: boolean;
  flags: string[];
  blur_score: number;
  orientation_score: number;
  cropping_score: number;
  color_consistency_score: number;
  dpi_score: number;
  actual_dpi: number;
  image_path: string;
  thumbnail_path: string;
}

export interface ProcessingJob {
  job_id: string;
  filename: string;
  status: keyof ProcessingStatus;
  total_pages: number;
  processed_pages: number;
  overall_confidence: number;
  auto_approved: boolean;
  created_at: number;
  completed_at?: number;
  error_message?: string;
  batch_id?: string;
  file_type?: string;
  source_path?: string;
}

export interface ProcessingResult {
  job_id: string;
  filename: string;
  status: keyof ProcessingStatus;
  total_pages: number;
  overall_confidence: number;
  overall_heuristic_confidence?: number;
  overall_ml_confidence?: number;
  overall_dl_confidence?: number;
  overall_ocr_confidence?: number;
  overall_llm_confidence?: number;
  ml_enabled?: boolean;
  dl_enabled?: boolean;
  ocr_enabled?: boolean;
  llm_enabled?: boolean;
  auto_approved: boolean;
  pages: PageQualityResult[];
  review_status: keyof ReviewStatus;
  created_at: number;
  completed_at?: number;
}

export interface UploadResponse {
  job_id: string;
  message: string;
  status: keyof ProcessingStatus;
  batch_id?: string;
}

export interface BatchFileStatus {
  filename: string;
  relative_path?: string;
  job_id?: string | null;
  status: keyof ProcessingStatus;
  file_type?: string | null;
  size?: number | null;
  error_message?: string | null;
  overall_confidence?: number | null;
}

export interface BatchJob {
  batch_id: string;
  source: string;
  source_url?: string | null;
  status: keyof ProcessingStatus;
  total_files: number;
  processed_files: number;
  skipped_files: number;
  files: BatchFileStatus[];
  created_at: number;
  completed_at?: number | null;
  error_message?: string | null;
}

export interface BatchUploadResponse {
  batch_id: string;
  message: string;
  status: keyof ProcessingStatus;
  total_files: number;
  job_ids: string[];
}

export interface SharePointPreviewFile {
  name: string;
  relative_path: string;
  size: number;
  web_url?: string;
  file_type: string;
}

export interface SharePointPreviewResponse {
  url: string;
  total_files: number;
  files: SharePointPreviewFile[];
}

export interface SharePointProcessRequest {
  url: string;
  tenant_id?: string;
  client_id?: string;
  client_secret?: string;
  access_token?: string;
}

export interface ReviewRequest {
  job_id: string;
  review_status: keyof ReviewStatus;
  comments?: string;
}

export interface ReviewResponse {
  job_id: string;
  review_status: keyof ReviewStatus;
  message: string;
}

export interface PageImageResponse {
  page_number: number;
  image_url: string;
  thumbnail_url: string;
  quality_result: PageQualityResult;
}

export interface ReportRequest {
  job_id: string;
  format: string;
}

export interface ReportResponse {
  job_id: string;
  format: string;
  download_url: string;
  generated_at: number;
}
