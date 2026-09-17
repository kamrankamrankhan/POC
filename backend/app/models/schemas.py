from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class QualityFlag(str, Enum):
    BLUR = "blur"
    ORIENTATION = "orientation"
    CROPPING = "cropping"
    COLOR_CONSISTENCY = "color_consistency"
    LOW_RESOLUTION = "low_resolution"
    LOW_DPI = "low_dpi"
    POOR_OCR = "poor_ocr"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PageQualityResult(BaseModel):
    page_number: int
    confidence_score: float  # 0-100 blended final score
    heuristic_confidence_score: Optional[float] = None
    ml_confidence_score: Optional[float] = None
    dl_confidence_score: Optional[float] = None
    ocr_confidence_score: Optional[float] = None
    ocr_text_preview: Optional[str] = None
    ocr_word_count: Optional[int] = None
    ocr_engine: Optional[str] = None
    flags: List[QualityFlag]
    blur_score: float
    orientation_score: float
    cropping_score: float
    color_consistency_score: float
    dpi_score: float
    actual_dpi: float
    image_path: str
    thumbnail_path: str


class ProcessingJob(BaseModel):
    job_id: str
    filename: str
    status: ProcessingStatus
    total_pages: int
    processed_pages: int
    overall_confidence: float
    auto_approved: bool
    created_at: float
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    batch_id: Optional[str] = None
    file_type: Optional[str] = None
    source_path: Optional[str] = None


class ProcessingResult(BaseModel):
    job_id: str
    filename: str
    status: ProcessingStatus
    total_pages: int
    overall_confidence: float
    overall_heuristic_confidence: Optional[float] = None
    overall_ml_confidence: Optional[float] = None
    overall_dl_confidence: Optional[float] = None
    overall_ocr_confidence: Optional[float] = None
    ml_enabled: bool = False
    dl_enabled: bool = False
    ocr_enabled: bool = False
    auto_approved: bool
    pages: List[PageQualityResult]
    review_status: ReviewStatus
    created_at: float
    completed_at: Optional[float] = None


class MLModelStatus(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool
    model_loaded: bool
    model_path: str
    training_samples_path: str = ""
    review_sample_count: int = 0
    metadata: Dict[str, Any] = {}


class DLModelStatus(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    enabled: bool
    model_loaded: bool
    model_path: str
    metadata: Dict[str, Any] = {}


class OCRStatus(BaseModel):
    enabled: bool
    rapidocr_available: bool
    tesseract_available: bool
    active_engine: str


class MLRetrainResponse(BaseModel):
    message: str
    metadata: Dict[str, Any]


class UploadResponse(BaseModel):
    job_id: str
    message: str
    status: ProcessingStatus
    batch_id: Optional[str] = None


class BatchFileStatus(BaseModel):
    filename: str
    relative_path: str = ""
    job_id: Optional[str] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    file_type: Optional[str] = None
    size: Optional[int] = None
    error_message: Optional[str] = None
    overall_confidence: Optional[float] = None


class BatchJob(BaseModel):
    batch_id: str
    source: str
    source_url: Optional[str] = None
    status: ProcessingStatus
    total_files: int
    processed_files: int = 0
    skipped_files: int = 0
    files: List[BatchFileStatus] = []
    created_at: float
    completed_at: Optional[float] = None
    error_message: Optional[str] = None


class BatchUploadResponse(BaseModel):
    batch_id: str
    message: str
    status: ProcessingStatus
    total_files: int
    job_ids: List[str] = []


class SharePointPreviewRequest(BaseModel):
    url: str
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    access_token: Optional[str] = None


class SharePointFilePreview(BaseModel):
    name: str
    relative_path: str
    size: int
    web_url: str = ""
    file_type: str


class SharePointPreviewResponse(BaseModel):
    url: str
    total_files: int
    files: List[SharePointFilePreview]


class SharePointProcessRequest(SharePointPreviewRequest):
    pass


class ReviewRequest(BaseModel):
    job_id: str
    review_status: ReviewStatus
    comments: Optional[str] = None


class ReviewResponse(BaseModel):
    job_id: str
    review_status: ReviewStatus
    message: str


class PageImageResponse(BaseModel):
    page_number: int
    image_url: str
    thumbnail_url: str
    quality_result: PageQualityResult


class ReportRequest(BaseModel):
    job_id: str
    format: str  # "json" or "csv"


class ReportResponse(BaseModel):
    job_id: str
    format: str
    download_url: str
    generated_at: datetime
