import os
import uuid
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from pdf2image import convert_from_path
from pdf2image.pdf2image import pdfinfo_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError
from PIL import Image
import cv2
import numpy as np
from skimage import measure, filters
import logging

from ..core.config import (
    UPLOAD_DIR, PROCESSED_DIR, THUMBNAILS_DIR, 
    IMAGE_DPI, THUMBNAIL_SIZE,
    DPI_EXCELLENT, DPI_GOOD, DPI_ACCEPTABLE, DPI_POOR, DPI_VERY_POOR, DPI_MINIMUM,
    BLUR_CONTENT_DENSITY_MIN, BLUR_TEXT_LINES_MIN, BLUR_TEXT_COLUMNS_MIN, 
    BLUR_EDGE_DENSITY_MIN, BLUR_CONTOUR_AREA_MIN,
    ML_ENABLED, ML_ENSEMBLE_WEIGHT, CONFIDENCE_THRESHOLD_HIGH,
    ML_APPROVED_TARGET, ML_REJECTED_TARGET,
    DL_ENABLED, OCR_ENABLED, DL_ENSEMBLE_WEIGHT, OCR_ENSEMBLE_WEIGHT,
    OCR_LOW_THRESHOLD,
    LLM_ENABLED, LLM_ENSEMBLE_WEIGHT,
)
from ..models.schemas import PageQualityResult, QualityFlag, ReviewStatus
from .feature_extractor import extract_page_features
from .ml_quality_model import quality_ml_model
from .dl_quality_model import dl_quality_model
from .ocr_service import analyze_page_ocr
from .llm_vision_service import analyze_page_with_llm, llm_status
from .file_types import (
    ACCEPT_LABEL,
    classify_bytes,
    classify_path,
    count_image_frames,
    rasterize_image_file,
)

logger = logging.getLogger(__name__)


def detect_non_pdf_type(header: bytes) -> Optional[str]:
    """Identify common non-PDF formats from magic bytes."""
    from .file_types import detect_image_kind, detect_unsupported_kind

    return detect_image_kind(header) or detect_unsupported_kind(header)


def inspect_upload(content: bytes, filename: str) -> str:
    """Validate PDF / image uploads and return 'pdf' or 'image'."""
    return classify_bytes(content, filename)


def is_pdf_encrypted(content: bytes) -> bool:
    """Return True if the PDF declares an Encrypt dictionary."""
    return b"/Encrypt" in content


def conversion_error_message(exc: Exception) -> Optional[str]:
    """Map poppler/pdf2image failures to a user-facing message."""
    error_msg = str(exc).lower()
    if "password" in error_msg or "encrypted" in error_msg:
        if "incorrect" in error_msg:
            return (
                "The PDF password is incorrect. Enter the correct document password "
                "and upload again."
            )
        return (
            "This PDF is password-protected. Enter the document password on the "
            "Upload tab and try again."
        )
    if "corrupted" in error_msg or "damaged" in error_msg:
        return "The PDF file appears to be damaged. Please try a different PDF file."
    return None


def verify_pdf_readable(file_path: str, password: Optional[str] = None) -> int:
    """Raise ValueError if poppler cannot open the PDF. Returns page count."""
    try:
        info = pdfinfo_from_path(file_path, userpw=password)
        return int(info.get("Pages") or 0)
    except PDFInfoNotInstalledError:
        raise ValueError(
            "PDF processing tools (poppler) are not installed on the server. "
            "Install poppler-utils and try again."
        )
    except PDFPageCountError as e:
        mapped = conversion_error_message(e)
        raise ValueError(
            mapped
            or "Unable to read this PDF. It may be damaged, encrypted, or use an unsupported structure."
        )


class PDFProcessor:
    def __init__(self):
        self.jobs = {}  # In-memory job storage (replace with database in production)
        self.batches = {}

    def create_job(
        self,
        filename: str,
        total_pages: int = 0,
        batch_id: Optional[str] = None,
        file_type: Optional[str] = None,
        source_path: Optional[str] = None,
    ) -> str:
        """Register a processing job and return its ID immediately."""
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            "job_id": job_id,
            "filename": filename,
            "status": "processing",
            "total_pages": max(int(total_pages or 0), 0),
            "processed_pages": 0,
            "overall_confidence": 0.0,
            "overall_heuristic_confidence": 0.0,
            "overall_ml_confidence": None,
            "overall_dl_confidence": None,
            "overall_ocr_confidence": None,
            "overall_llm_confidence": None,
            "ml_enabled": ML_ENABLED and quality_ml_model.is_available,
            "dl_enabled": DL_ENABLED and dl_quality_model.is_available,
            "ocr_enabled": OCR_ENABLED,
            "llm_enabled": bool(llm_status().get("available")),
            "auto_approved": False,
            "pages": [],
            "created_at": time.time(),
            "completed_at": None,
            "error_message": None,
            "batch_id": batch_id,
            "file_type": file_type,
            "source_path": source_path,
        }
        return job_id

    def create_batch(self, source: str, source_url: Optional[str] = None) -> str:
        batch_id = str(uuid.uuid4())
        self.batches[batch_id] = {
            "batch_id": batch_id,
            "source": source,
            "source_url": source_url,
            "status": "processing",
            "total_files": 0,
            "processed_files": 0,
            "skipped_files": 0,
            "files": [],
            "created_at": time.time(),
            "completed_at": None,
            "error_message": None,
        }
        return batch_id

    def get_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        return self.batches.get(batch_id)

    def _sync_batch_file(self, batch_id: Optional[str], job_id: str) -> None:
        if not batch_id or batch_id not in self.batches:
            return
        job = self.jobs.get(job_id) or {}
        for item in self.batches[batch_id]["files"]:
            if item.get("job_id") == job_id:
                item["status"] = job.get("status", item.get("status"))
                item["error_message"] = job.get("error_message")
                item["overall_confidence"] = job.get("overall_confidence")
                break
        batch = self.batches[batch_id]
        batch["processed_files"] = sum(
            1 for item in batch["files"] if item.get("status") in {"completed", "failed"}
        )
        if batch["processed_files"] >= batch["total_files"] and batch["total_files"]:
            statuses = {item.get("status") for item in batch["files"]}
            if statuses == {"failed"}:
                batch["status"] = "failed"
            else:
                batch["status"] = "completed"
            batch["completed_at"] = time.time()
    
    async def process_pdf(
        self,
        file_path: str,
        filename: str,
        job_id: Optional[str] = None,
        password: Optional[str] = None,
    ) -> str:
        """Process a PDF file. Creates a job if job_id is not provided."""
        if not job_id or job_id not in self.jobs:
            job_id = self.create_job(filename)
        
        try:
            # Validate the source file before processing
            await self._validate_source_file(file_path, filename)

            file_type = classify_path(file_path, filename)
            self.jobs[job_id]["file_type"] = file_type

            if file_type == "image":
                total = await asyncio.to_thread(count_image_frames, file_path)
                self.jobs[job_id]["total_pages"] = total
                pages = await asyncio.to_thread(
                    self._rasterize_image_pages, file_path, job_id
                )
            else:
                # Set page count before rasterization so the UI can show real progress
                await self._set_total_pages(file_path, job_id, password)
                pages = await self._convert_pdf_to_images(file_path, job_id, password)

            if not pages:
                raise ValueError("The file has no pages to analyze.")
            self.jobs[job_id]["total_pages"] = len(pages)
            
            # Process each page
            page_results = []
            total_confidence = 0.0
            total_heuristic_confidence = 0.0
            total_ml_confidence = 0.0
            total_dl_confidence = 0.0
            total_ocr_confidence = 0.0
            total_llm_confidence = 0.0
            ml_scores_available = 0
            dl_scores_available = 0
            ocr_scores_available = 0
            llm_scores_available = 0
            
            for i, page_path in enumerate(pages):
                page_result = await asyncio.to_thread(
                    self._analyze_page_quality, page_path, i + 1, job_id
                )
                page_results.append(page_result)
                total_confidence += page_result.confidence_score
                total_heuristic_confidence += (
                    page_result.heuristic_confidence_score or page_result.confidence_score
                )
                if page_result.ml_confidence_score is not None:
                    total_ml_confidence += page_result.ml_confidence_score
                    ml_scores_available += 1
                if page_result.dl_confidence_score is not None:
                    total_dl_confidence += page_result.dl_confidence_score
                    dl_scores_available += 1
                if page_result.ocr_confidence_score is not None:
                    total_ocr_confidence += page_result.ocr_confidence_score
                    ocr_scores_available += 1
                if page_result.llm_confidence_score is not None and page_result.llm_invoked:
                    total_llm_confidence += page_result.llm_confidence_score
                    llm_scores_available += 1
                self.jobs[job_id]["processed_pages"] = i + 1
                await asyncio.sleep(0)
            
            # Calculate overall confidence
            overall_confidence = total_confidence / len(pages) if pages else 0.0
            overall_heuristic_confidence = (
                total_heuristic_confidence / len(pages) if pages else 0.0
            )
            overall_ml_confidence = (
                total_ml_confidence / ml_scores_available if ml_scores_available else None
            )
            overall_dl_confidence = (
                total_dl_confidence / dl_scores_available if dl_scores_available else None
            )
            overall_ocr_confidence = (
                total_ocr_confidence / ocr_scores_available if ocr_scores_available else None
            )
            overall_llm_confidence = (
                total_llm_confidence / llm_scores_available if llm_scores_available else None
            )
            self.jobs[job_id]["overall_confidence"] = overall_confidence
            self.jobs[job_id]["overall_heuristic_confidence"] = overall_heuristic_confidence
            self.jobs[job_id]["overall_ml_confidence"] = overall_ml_confidence
            self.jobs[job_id]["overall_dl_confidence"] = overall_dl_confidence
            self.jobs[job_id]["overall_ocr_confidence"] = overall_ocr_confidence
            self.jobs[job_id]["overall_llm_confidence"] = overall_llm_confidence
            self.jobs[job_id]["ml_enabled"] = ML_ENABLED and quality_ml_model.is_available
            self.jobs[job_id]["dl_enabled"] = DL_ENABLED and dl_quality_model.is_available
            self.jobs[job_id]["ocr_enabled"] = OCR_ENABLED
            self.jobs[job_id]["llm_enabled"] = bool(llm_status().get("available"))
            self.jobs[job_id]["auto_approved"] = overall_confidence >= CONFIDENCE_THRESHOLD_HIGH
            self.jobs[job_id]["pages"] = page_results
            self.jobs[job_id]["status"] = "completed"
            self._sync_batch_file(self.jobs[job_id].get("batch_id"), job_id)
            
        except ValueError as e:
            # Handle validation errors (file format issues)
            logger.error(f"File validation error for {filename}: {str(e)}")
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error_message"] = str(e)
            self._sync_batch_file(self.jobs[job_id].get("batch_id"), job_id)
        except Exception as e:
            # Handle other processing errors
            logger.error(f"Error processing PDF {filename}: {str(e)}")
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error_message"] = f"Processing failed: {str(e)}"
            self._sync_batch_file(self.jobs[job_id].get("batch_id"), job_id)
        finally:
            self.jobs[job_id]["completed_at"] = time.time()
            self._sync_batch_file(self.jobs[job_id].get("batch_id"), job_id)
        
        return job_id
    
    async def _validate_source_file(self, file_path: str, filename: str) -> None:
        """Validate that the file is a PDF, scanned image, or photo."""
        try:
            if not os.path.exists(file_path):
                raise ValueError(f"File not found: {filename}")

            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise ValueError(f"The file '{filename}' is empty. Please upload a {ACCEPT_LABEL}.")

            with open(file_path, 'rb') as f:
                header = f.read(1024)
            inspect_upload(header, filename)
                
        except ValueError:
            raise
        except Exception:
            raise ValueError(f"Could not read '{filename}'. Please upload a {ACCEPT_LABEL}.")

    async def _set_total_pages(
        self, file_path: str, job_id: str, password: Optional[str] = None
    ) -> int:
        """Read the PDF page count before conversion so progress is not 0/0."""
        try:
            info = await asyncio.to_thread(pdfinfo_from_path, file_path, userpw=password)
            total = int(info.get("Pages") or 0)
        except Exception as exc:
            logger.warning("Could not read PDF page count before conversion: %s", exc)
            total = 0
        self.jobs[job_id]["total_pages"] = total
        return total
    
    async def _convert_pdf_to_images(
        self, file_path: str, job_id: str, password: Optional[str] = None
    ) -> List[str]:
        """Convert PDF pages to images"""
        try:
            # Create job-specific directory
            job_dir = PROCESSED_DIR / job_id
            job_dir.mkdir(exist_ok=True)
            
            convert_kwargs = {
                "dpi": IMAGE_DPI,
                "output_folder": str(job_dir),
                "fmt": "png",
                "thread_count": 2,
            }
            if password:
                convert_kwargs["userpw"] = password

            # Run poppler and image saves off the event loop so status polling stays live
            image_paths = await asyncio.to_thread(
                self._rasterize_and_save_pages, file_path, job_dir, convert_kwargs
            )
            return image_paths

        except PDFInfoNotInstalledError:
            logger.error("poppler is not installed or not on PATH")
            raise ValueError(
                "PDF processing tools (poppler) are not installed on the server. "
                "Install poppler-utils and try again."
            )
        except PDFPageCountError as e:
            logger.error(f"Unable to read PDF page count: {e}")
            mapped = conversion_error_message(e)
            if mapped:
                raise ValueError(mapped)
            raise ValueError(
                "Unable to read this PDF. It may be damaged, encrypted, or use an unsupported structure."
            )
        except PDFSyntaxError:
            raise ValueError("The PDF file appears to be damaged or unreadable. Please try a different file.")
        except Exception as e:
            mapped = conversion_error_message(e)
            if mapped:
                raise ValueError(mapped)
            logger.error(f"Error converting PDF to images: {str(e)}")
            raise ValueError(f"Unable to process the PDF file: {str(e)}")

    def _rasterize_and_save_pages(
        self, file_path: str, job_dir: Path, convert_kwargs: Dict[str, Any]
    ) -> List[str]:
        """Convert PDF pages to PNG files (runs in a worker thread)."""
        pages = convert_from_path(file_path, **convert_kwargs)
        image_paths = []
        for i, page in enumerate(pages):
            image_path = job_dir / f"page_{i+1}.png"
            page.save(image_path, "PNG")
            image_paths.append(str(image_path))
        return image_paths

    def _rasterize_image_pages(self, file_path: str, job_id: str) -> List[str]:
        """Turn a photo or scanned image into one or more PNG pages."""
        job_dir = PROCESSED_DIR / job_id
        job_dir.mkdir(exist_ok=True)
        return rasterize_image_file(file_path, job_dir)
    
    def _analyze_page_quality(self, image_path: str, page_number: int, job_id: str) -> PageQualityResult:
        """Analyze quality of a single page"""
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Create thumbnail
            thumbnail_path = self._create_thumbnail(image_path, job_id, page_number)
            
            # Run quality checks
            blur_score = self._check_blur(image)
            orientation_score = self._check_orientation(image)
            cropping_score = self._check_cropping(image)
            color_consistency_score = self._check_color_consistency(image)
            dpi_score, actual_dpi = self._check_dpi(image_path)
            
            heuristic_confidence = self._calculate_confidence(
                blur_score, orientation_score, cropping_score, color_consistency_score, dpi_score
            )
            ml_confidence = None
            dl_confidence = None
            ocr_confidence = None
            ocr_text_preview = None
            ocr_word_count = None
            ocr_engine = None
            llm_confidence = None
            llm_summary = None
            llm_issues = None
            llm_model = None
            llm_invoked = False
            confidence_score = heuristic_confidence

            if ML_ENABLED and quality_ml_model.is_available:
                features = extract_page_features(
                    image,
                    blur_score,
                    orientation_score,
                    cropping_score,
                    color_consistency_score,
                    dpi_score,
                    actual_dpi,
                )
                ml_confidence = quality_ml_model.predict(features)
                if ml_confidence is not None:
                    confidence_score = self._blend_confidence(heuristic_confidence, ml_confidence)

            if DL_ENABLED and dl_quality_model.is_available:
                try:
                    dl_confidence = dl_quality_model.predict(image)
                except Exception as exc:
                    logger.warning("DL predict failed on page %s: %s", page_number, exc)

            if OCR_ENABLED:
                try:
                    ocr = analyze_page_ocr(image)
                    if ocr.available:
                        ocr_confidence = ocr.score
                        ocr_text_preview = ocr.to_dict()["text_preview"] or None
                        ocr_word_count = ocr.word_count
                        ocr_engine = ocr.engine
                except Exception as exc:
                    logger.warning("OCR failed on page %s: %s", page_number, exc)

            confidence_score = self._blend_all_scores(
                confidence_score, dl_confidence, ocr_confidence, None
            )

            # Vision LLM layer: only when DL confidence is below threshold (or DL missing)
            if LLM_ENABLED:
                try:
                    llm = analyze_page_with_llm(
                        image,
                        page_number=page_number,
                        dl_confidence=dl_confidence,
                        heuristic_confidence=heuristic_confidence,
                        ocr_preview=ocr_text_preview,
                    )
                    llm_invoked = llm.invoked
                    llm_model = llm.model
                    if llm.invoked and llm.available:
                        llm_confidence = llm.score
                        llm_summary = llm.summary or None
                        llm_issues = llm.issues or None
                        confidence_score = self._blend_all_scores(
                            confidence_score, None, None, llm_confidence
                        )
                    elif llm.invoked and llm.error:
                        llm_summary = f"LLM unavailable: {llm.error}"
                except Exception as exc:
                    logger.warning("LLM vision failed on page %s: %s", page_number, exc)
            
            # Determine flags
            flags = []
            if blur_score < 0.5:
                flags.append(QualityFlag.BLUR)
            if orientation_score < 0.7:
                flags.append(QualityFlag.ORIENTATION)
            if cropping_score < 0.6:
                flags.append(QualityFlag.CROPPING)
            if color_consistency_score < 0.5:
                flags.append(QualityFlag.COLOR_CONSISTENCY)
            if dpi_score < 0.6:
                flags.append(QualityFlag.LOW_DPI)
            if (
                ocr_confidence is not None
                and ocr_word_count is not None
                and ocr_word_count >= 8
                and ocr_confidence < OCR_LOW_THRESHOLD
            ):
                flags.append(QualityFlag.POOR_OCR)
            
            return PageQualityResult(
                page_number=page_number,
                confidence_score=confidence_score,
                heuristic_confidence_score=heuristic_confidence,
                ml_confidence_score=ml_confidence,
                dl_confidence_score=dl_confidence,
                ocr_confidence_score=ocr_confidence,
                ocr_text_preview=ocr_text_preview,
                ocr_word_count=ocr_word_count,
                ocr_engine=ocr_engine,
                llm_confidence_score=llm_confidence,
                llm_summary=llm_summary,
                llm_issues=llm_issues,
                llm_model=llm_model,
                llm_invoked=llm_invoked,
                flags=flags,
                blur_score=blur_score,
                orientation_score=orientation_score,
                cropping_score=cropping_score,
                color_consistency_score=color_consistency_score,
                dpi_score=dpi_score,
                actual_dpi=actual_dpi,
                image_path=image_path,
                thumbnail_path=thumbnail_path
            )
            
        except Exception as e:
            logger.error(f"Error analyzing page {page_number}: {str(e)}")
            # Return default result for failed analysis
            return PageQualityResult(
                page_number=page_number,
                confidence_score=0.0,
                heuristic_confidence_score=0.0,
                ml_confidence_score=None,
                dl_confidence_score=None,
                ocr_confidence_score=None,
                llm_confidence_score=None,
                llm_invoked=False,
                flags=[QualityFlag.BLUR],  # Default flag
                blur_score=0.0,
                orientation_score=0.0,
                cropping_score=0.0,
                color_consistency_score=0.0,
                dpi_score=0.0,
                actual_dpi=0.0,
                image_path=image_path,
                thumbnail_path=""
            )
    
    def _create_thumbnail(self, image_path: str, job_id: str, page_number: int) -> str:
        """Create thumbnail for the page"""
        try:
            # Create thumbnails directory for job
            thumb_dir = THUMBNAILS_DIR / job_id
            thumb_dir.mkdir(exist_ok=True)
            
            # Load and resize image
            with Image.open(image_path) as img:
                img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                thumbnail_path = thumb_dir / f"page_{page_number}_thumb.png"
                img.save(thumbnail_path, "PNG")
            
            return str(thumbnail_path)
            
        except Exception as e:
            logger.error(f"Error creating thumbnail: {str(e)}")
            return ""
    
    def _check_blur(self, image: np.ndarray) -> float:
        """Check for blur using content-aware analysis for better accuracy"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # First, analyze content characteristics
            content_analysis = self._analyze_image_content(gray)
            
            # Skip blur analysis for images with very little content
            if content_analysis['content_density'] < BLUR_CONTENT_DENSITY_MIN:
                return 1.0  # Perfect score for mostly empty pages
            
            # Method 1: Laplacian variance (most reliable for text)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Method 2: Sobel edge detection
            sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            sobel_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
            sobel_var = sobel_magnitude.var()
            
            # Method 3: High-frequency content analysis
            blurred = cv2.GaussianBlur(gray, (15, 15), 0)
            diff = cv2.absdiff(gray, blurred)
            high_freq_content = diff.mean()
            
            # Method 4: Text-specific blur detection
            text_blur_score = self._detect_text_blur(gray, content_analysis)
            
            # Adaptive scoring based on content type and density
            blur_scores = self._calculate_adaptive_blur_scores(
                laplacian_var, sobel_var, high_freq_content, text_blur_score, content_analysis
            )
            
            # Weighted combination based on content type
            if content_analysis['is_text_heavy']:
                # For text-heavy documents, prioritize text-specific methods
                blur_score = (0.4 * blur_scores['laplacian'] + 
                            0.3 * blur_scores['text'] + 
                            0.2 * blur_scores['sobel'] + 
                            0.1 * blur_scores['high_freq'])
            else:
                # For mixed content, use balanced approach
                blur_score = (0.5 * blur_scores['laplacian'] + 
                            0.25 * blur_scores['sobel'] + 
                            0.15 * blur_scores['high_freq'] + 
                            0.1 * blur_scores['text'])
            
            # Apply content density adjustment
            # Low content density should not penalize blur score heavily
            content_adjustment = 0.3 * (1.0 - content_analysis['content_density'])
            blur_score = min(1.0, blur_score + content_adjustment)
            
            return max(0.0, min(1.0, blur_score))
            
        except Exception as e:
            logger.error(f"Error checking blur: {str(e)}")
            return 0.8  # Return good score on error to avoid false negatives
    
    def _analyze_image_content(self, gray_image: np.ndarray) -> dict:
        """Analyze image content characteristics for adaptive blur detection"""
        try:
            height, width = gray_image.shape
            
            # 1. Content density (non-white pixels)
            non_white_pixels = np.sum(gray_image < 240)
            content_density = non_white_pixels / (height * width)
            
            # 2. Text detection using horizontal and vertical projections
            # Horizontal projection (sum of pixels in each row)
            h_projection = np.sum(gray_image < 240, axis=1)
            # Vertical projection (sum of pixels in each column)
            v_projection = np.sum(gray_image < 240, axis=0)
            
            # Find text lines (rows with significant content)
            text_lines = np.sum(h_projection > width * 0.1)  # Rows with >10% content
            text_columns = np.sum(v_projection > height * 0.05)  # Columns with >5% content
            
            # 3. Edge density analysis
            edges = cv2.Canny(gray_image, 50, 150)
            edge_density = np.sum(edges > 0) / (height * width)
            
            # 4. Contrast analysis
            contrast = gray_image.std() / 255.0
            
            # 5. Determine if image is text-heavy
            is_text_heavy = (text_lines > BLUR_TEXT_LINES_MIN and 
                           text_columns > BLUR_TEXT_COLUMNS_MIN and 
                           content_density > 0.1 and 
                           edge_density > BLUR_EDGE_DENSITY_MIN)
            
            # 6. Content complexity
            # High complexity = lots of edges and variation
            complexity = min(1.0, (edge_density * 10 + contrast * 2))
            
            return {
                'content_density': content_density,
                'text_lines': text_lines,
                'text_columns': text_columns,
                'edge_density': edge_density,
                'contrast': contrast,
                'is_text_heavy': is_text_heavy,
                'complexity': complexity
            }
            
        except Exception as e:
            logger.error(f"Error analyzing image content: {str(e)}")
            return {
                'content_density': 0.5,
                'text_lines': 0,
                'text_columns': 0,
                'edge_density': 0.01,
                'contrast': 0.1,
                'is_text_heavy': False,
                'complexity': 0.5
            }
    
    def _detect_text_blur(self, gray_image: np.ndarray, content_analysis: dict) -> float:
        """Detect blur specifically in text regions"""
        try:
            if not content_analysis['is_text_heavy']:
                return 0.5  # Neutral score for non-text content
            
            # Focus on text regions by thresholding
            # Text should be dark on light background
            _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Find contours (potential text regions)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(contours) == 0:
                return 0.5
            
            # Analyze blur in text regions
            text_blur_scores = []
            
            for contour in contours:
                # Filter out very small contours (noise)
                area = cv2.contourArea(contour)
                if area < BLUR_CONTOUR_AREA_MIN:  # Skip small contours
                    continue
                
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Extract region of interest
                roi = gray_image[y:y+h, x:x+w]
                
                if roi.size == 0:
                    continue
                
                # Calculate Laplacian variance for this text region
                laplacian_var = cv2.Laplacian(roi, cv2.CV_64F).var()
                
                # Normalize based on region size (larger regions should have higher variance)
                normalized_score = laplacian_var / (w * h * 0.01)  # Normalize by area
                text_blur_scores.append(min(1.0, max(0.0, normalized_score)))
            
            if len(text_blur_scores) == 0:
                return 0.5
            
            # Return average blur score for text regions
            return np.mean(text_blur_scores)
            
        except Exception as e:
            logger.error(f"Error detecting text blur: {str(e)}")
            return 0.5
    
    def _calculate_adaptive_blur_scores(self, laplacian_var: float, sobel_var: float, 
                                      high_freq_content: float, text_blur_score: float, 
                                      content_analysis: dict) -> dict:
        """Calculate adaptive blur scores based on content characteristics"""
        
        # Adaptive thresholds based on content
        content_density = content_analysis['content_density']
        complexity = content_analysis['complexity']
        
        # Adjust thresholds based on content density and complexity
        # More content and complexity = higher expected variance
        density_factor = max(0.5, content_density * 2)  # 0.5 to 2.0
        complexity_factor = max(0.5, complexity)  # 0.5 to 1.0
        
        # Laplacian scoring (most important for text)
        laplacian_min = 20 * density_factor
        laplacian_max = 200 * density_factor * complexity_factor
        laplacian_score = min(1.0, max(0.0, (laplacian_var - laplacian_min) / (laplacian_max - laplacian_min)))
        
        # Sobel scoring
        sobel_min = 500 * density_factor
        sobel_max = 3000 * density_factor * complexity_factor
        sobel_score = min(1.0, max(0.0, (sobel_var - sobel_min) / (sobel_max - sobel_min)))
        
        # High-frequency content scoring
        hf_min = 2 * density_factor
        hf_max = 15 * density_factor * complexity_factor
        hf_score = min(1.0, max(0.0, (high_freq_content - hf_min) / (hf_max - hf_min)))
        
        # Text blur score (already normalized)
        text_score = text_blur_score
        
        return {
            'laplacian': laplacian_score,
            'sobel': sobel_score,
            'high_freq': hf_score,
            'text': text_score
        }
    
    def _check_orientation(self, image: np.ndarray) -> float:
        """Check if document is properly oriented"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Use Hough lines to detect text orientation
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is None:
                return 0.5  # Neutral score if no lines detected
            
            # Analyze line angles
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = theta * 180 / np.pi
                # Normalize angle to 0-90 degrees
                angle = min(angle, 180 - angle)
                angles.append(angle)
            
            if not angles:
                return 0.5
            
            # Check if most lines are horizontal (0-15 degrees) or vertical (75-90 degrees)
            horizontal_lines = sum(1 for a in angles if a < 15)
            vertical_lines = sum(1 for a in angles if a > 75)
            total_lines = len(angles)
            
            orientation_score = max(horizontal_lines, vertical_lines) / total_lines
            return orientation_score
            
        except Exception as e:
            logger.error(f"Error checking orientation: {str(e)}")
            return 0.5
    
    def _check_cropping(self, image: np.ndarray) -> float:
        """Check if document is properly cropped (no excessive whitespace)"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Find content boundaries
            # Use threshold to separate content from background
            _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return 0.0  # No content detected
            
            # Get bounding box of all content
            all_points = np.concatenate(contours)
            x, y, w, h = cv2.boundingRect(all_points)
            
            # Calculate content area vs image area
            content_area = w * h
            image_area = image.shape[1] * image.shape[0]
            content_ratio = content_area / image_area
            
            # Good cropping should have content ratio > 0.3
            cropping_score = min(1.0, content_ratio / 0.3)
            return cropping_score
            
        except Exception as e:
            logger.error(f"Error checking cropping: {str(e)}")
            return 0.5
    
    def _check_color_consistency(self, image: np.ndarray) -> float:
        """Check color consistency across the image"""
        try:
            # Convert to different color spaces for analysis
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            
            # Check for color uniformity in different regions
            h, w = image.shape[:2]
            
            # Divide image into 4 quadrants
            quadrants = [
                image[0:h//2, 0:w//2],
                image[0:h//2, w//2:w],
                image[h//2:h, 0:w//2],
                image[h//2:h, w//2:w]
            ]
            
            # Calculate mean color for each quadrant
            mean_colors = []
            for quad in quadrants:
                mean_color = np.mean(quad, axis=(0, 1))
                mean_colors.append(mean_color)
            
            # Calculate variance in mean colors
            mean_colors = np.array(mean_colors)
            color_variance = np.var(mean_colors, axis=0)
            avg_variance = np.mean(color_variance)
            
            # Normalize variance (lower variance = better consistency)
            # Typical good values have variance < 100
            consistency_score = max(0.0, 1.0 - (avg_variance / 100.0))
            return consistency_score
            
        except Exception as e:
            logger.error(f"Error checking color consistency: {str(e)}")
            return 0.5
    
    def _check_dpi(self, image_path: str) -> tuple[float, float]:
        """Check DPI (Dots Per Inch) of the image with improved content-aware analysis"""
        try:
            from PIL import Image
            import cv2
            import numpy as np
            
            # Open image and get metadata
            with Image.open(image_path) as img:
                # Get image dimensions in pixels
                width_px, height_px = img.size
                
                # Try to get DPI from image metadata
                dpi = img.info.get('dpi', (72, 72))  # Default to 72 DPI if not specified
                
                # Handle different DPI formats
                if isinstance(dpi, tuple):
                    dpi_x, dpi_y = dpi
                    actual_dpi = (dpi_x + dpi_y) / 2  # Average of X and Y DPI
                else:
                    actual_dpi = float(dpi)
                
                # Content-aware DPI analysis
                content_quality_factor = self._analyze_content_quality(image_path)
                
                # If DPI is not specified in metadata or is default 72, use content analysis
                if actual_dpi <= 72:  # Likely default/unspecified DPI
                    # Estimate DPI based on image dimensions and content quality
                    estimated_dpi = self._estimate_dpi_from_content(width_px, height_px, content_quality_factor)
                    actual_dpi = estimated_dpi
                
                # Calculate DPI score with content quality consideration
                dpi_score = self._calculate_dpi_score(actual_dpi, content_quality_factor)
                
                return dpi_score, actual_dpi
                
        except Exception as e:
            logger.error(f"Error checking DPI: {str(e)}")
            return 0.3, 72.0  # Default to low score and 72 DPI
    
    def _analyze_content_quality(self, image_path: str) -> float:
        """Analyze the actual content quality of the image"""
        try:
            import cv2
            import numpy as np
            
            # Load image
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return 0.5
            
            # Calculate content quality metrics
            quality_factors = []
            
            # 1. Edge density (more edges = more detailed content)
            edges = cv2.Canny(img, 50, 150)
            edge_density = np.sum(edges > 0) / (img.shape[0] * img.shape[1])
            quality_factors.append(min(edge_density * 10, 1.0))  # Normalize to 0-1
            
            # 2. Text clarity (using Laplacian variance)
            laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
            text_clarity = min(laplacian_var / 1000, 1.0)  # Normalize to 0-1
            quality_factors.append(text_clarity)
            
            # 3. Contrast analysis
            contrast = img.std() / 255.0  # Normalize to 0-1
            quality_factors.append(contrast)
            
            # 4. Content area ratio (non-white pixels)
            non_white_ratio = np.sum(img < 240) / (img.shape[0] * img.shape[1])
            quality_factors.append(non_white_ratio)
            
            # Weighted average of quality factors
            weights = [0.3, 0.3, 0.2, 0.2]  # Edge density, text clarity, contrast, content ratio
            content_quality = sum(w * f for w, f in zip(weights, quality_factors))
            
            return min(max(content_quality, 0.1), 1.0)  # Clamp between 0.1 and 1.0
            
        except Exception as e:
            logger.error(f"Error analyzing content quality: {str(e)}")
            return 0.5
    
    def _estimate_dpi_from_content(self, width_px: int, height_px: int, content_quality: float) -> float:
        """Estimate DPI based on image dimensions and content quality"""
        # Calculate area in pixels
        total_pixels = width_px * height_px
        
        # Estimate physical size based on content
        # High content quality suggests larger physical document
        # Low content quality suggests smaller or compressed document
        
        if content_quality > 0.7:  # High quality content
            # Assume standard document sizes
            if total_pixels > 2000000:  # > 2MP
                estimated_dpi = min(width_px / 8.5, height_px / 11.0)
            elif total_pixels > 1000000:  # > 1MP
                estimated_dpi = min(width_px / 6.0, height_px / 8.0)
            else:
                estimated_dpi = min(width_px / 4.0, height_px / 5.5)
        elif content_quality > 0.4:  # Medium quality content
            # Assume smaller document or compressed
            if total_pixels > 1000000:
                estimated_dpi = min(width_px / 6.0, height_px / 8.0) * 0.8
            else:
                estimated_dpi = min(width_px / 4.0, height_px / 5.5) * 0.7
        else:  # Low quality content
            # Assume very small document or heavily compressed
            estimated_dpi = min(width_px / 3.0, height_px / 4.0) * 0.5
        
        # Apply content quality adjustment
        estimated_dpi *= content_quality
        
        # Clamp to reasonable range
        return max(min(estimated_dpi, 600), 50)
    
    def _calculate_dpi_score(self, actual_dpi: float, content_quality: float) -> float:
        """Calculate DPI score considering both actual DPI and content quality"""
        # Base DPI score using configurable thresholds
        if actual_dpi >= DPI_EXCELLENT:
            base_score = 1.0
        elif actual_dpi >= DPI_GOOD:
            base_score = 0.9
        elif actual_dpi >= DPI_ACCEPTABLE:
            base_score = 0.8
        elif actual_dpi >= DPI_POOR:
            base_score = 0.6
        elif actual_dpi >= DPI_VERY_POOR:
            base_score = 0.4
        elif actual_dpi >= DPI_MINIMUM:
            base_score = 0.3
        else:
            base_score = 0.2
        
        # Adjust score based on content quality
        # High DPI with poor content quality should get lower score
        # Low DPI with high content quality should get slightly higher score
        content_adjustment = (content_quality - 0.5) * 0.3  # ±15% adjustment
        final_score = base_score + content_adjustment
        
        # Clamp to valid range
        return max(min(final_score, 1.0), 0.1)
    
    def _calculate_confidence(self, blur: float, orientation: float, cropping: float, color: float, dpi: float) -> float:
        """Calculate overall confidence score (0-100)"""
        # Weighted average of all quality metrics
        weights = {
            'blur': 0.3,      # Most important
            'orientation': 0.15,
            'cropping': 0.15,
            'color': 0.15,
            'dpi': 0.25       # DPI is very important for print quality
        }
        
        confidence = (
            blur * weights['blur'] +
            orientation * weights['orientation'] +
            cropping * weights['cropping'] +
            color * weights['color'] +
            dpi * weights['dpi']
        ) * 100
        
        return min(100.0, max(0.0, confidence))

    def _blend_confidence(self, heuristic_confidence: float, ml_confidence: float) -> float:
        """Combine heuristic and ML scores into a final confidence value."""
        blended = (
            ML_ENSEMBLE_WEIGHT * ml_confidence
            + (1.0 - ML_ENSEMBLE_WEIGHT) * heuristic_confidence
        )
        return min(100.0, max(0.0, blended))

    def _blend_all_scores(
        self,
        base_score: float,
        dl_confidence: Optional[float],
        ocr_confidence: Optional[float],
        llm_confidence: Optional[float] = None,
    ) -> float:
        """Fold DL, OCR, and LLM into the heuristic/ML base score with fixed weights."""
        extras = []
        if dl_confidence is not None and DL_ENSEMBLE_WEIGHT > 0:
            extras.append((dl_confidence, DL_ENSEMBLE_WEIGHT))
        if ocr_confidence is not None and OCR_ENSEMBLE_WEIGHT > 0:
            extras.append((ocr_confidence, OCR_ENSEMBLE_WEIGHT))
        if llm_confidence is not None and LLM_ENSEMBLE_WEIGHT > 0:
            extras.append((llm_confidence, LLM_ENSEMBLE_WEIGHT))
        if not extras:
            return min(100.0, max(0.0, base_score))
        # Renormalize: base keeps remaining mass after extra weights
        extra = sum(w for _, w in extras)
        base_w = max(0.0, 1.0 - extra)
        weighted = base_w * base_score + sum(score * w for score, w in extras)
        return min(100.0, max(0.0, weighted))

    def extract_page_features_from_result(self, page: PageQualityResult, image: np.ndarray):
        """Expose feature extraction for review-based retraining."""
        return extract_page_features(
            image,
            page.blur_score,
            page.orientation_score,
            page.cropping_score,
            page.color_consistency_score,
            page.dpi_score,
            page.actual_dpi,
        )

    def record_review_training_samples(self, job_id: str, review_status: str) -> int:
        """Persist page features with human review labels for ML retraining."""
        job = self.jobs.get(job_id)
        if not job or not job.get("pages"):
            return 0

        if review_status == ReviewStatus.APPROVED.value:
            target = ML_APPROVED_TARGET
        elif review_status == ReviewStatus.REJECTED.value:
            target = ML_REJECTED_TARGET
        else:
            return 0

        samples_added = 0
        for page in job["pages"]:
            image = cv2.imread(page.image_path)
            if image is None:
                continue
            features = self.extract_page_features_from_result(page, image)
            quality_ml_model.append_training_sample(features, target)
            samples_added += 1

        return samples_added
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get current status of a processing job"""
        return self.jobs.get(job_id, None)
    
    def get_job_result(self, job_id: str) -> Dict[str, Any]:
        """Get complete result of a processing job"""
        return self.jobs.get(job_id, None)
