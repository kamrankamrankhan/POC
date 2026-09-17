import os
import uuid
import shutil
import time
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import aiofiles
import logging

from ..models.schemas import (
    UploadResponse, ProcessingJob, ProcessingResult, 
    ReviewRequest, ReviewResponse, PageImageResponse,
    ReportRequest, ReportResponse, ProcessingStatus, ReviewStatus,
    MLModelStatus, MLRetrainResponse, DLModelStatus, OCRStatus,
    BatchJob, BatchFileStatus, BatchUploadResponse,
    SharePointPreviewRequest, SharePointPreviewResponse, SharePointFilePreview,
    SharePointProcessRequest,
)
from ..services.pdf_processor import (
    PDFProcessor, inspect_upload, is_pdf_encrypted, verify_pdf_readable
)
from ..services.file_types import ACCEPT_LABEL, count_image_frames, is_supported_filename
from ..services.sharepoint_client import SharePointClient, SharePointError
from ..services.ml_quality_model import quality_ml_model
from ..services.dl_quality_model import dl_quality_model
from ..services.ocr_service import ocr_status
from ..core.config import UPLOAD_DIR, MAX_FILE_SIZE, ALLOWED_EXTENSIONS, OCR_ENABLED

logger = logging.getLogger(__name__)

router = APIRouter()
processor = PDFProcessor()

# In-memory storage for reviews (replace with database in production)
reviews = {}


async def _store_upload(
    file_content: bytes,
    filename: str,
    password: Optional[str] = None,
    batch_id: Optional[str] = None,
    source_path: Optional[str] = None,
) -> tuple:
    """Validate, save, and register a job for one PDF or image file."""
    if not filename:
        raise HTTPException(status_code=400, detail="No file provided")
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024 * 1024):.1f}MB",
        )
    try:
        file_type = inspect_upload(file_content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    pdf_password = password.strip() if password else None
    if file_type == "pdf" and is_pdf_encrypted(file_content) and not pdf_password:
        raise HTTPException(
            status_code=400,
            detail=(
                "This PDF is password-protected. Enter the document password "
                "and upload again."
            ),
        )

    original_name = Path(filename).name or "upload"
    file_path = UPLOAD_DIR / f"{uuid.uuid4()}_{original_name}"
    async with aiofiles.open(file_path, "wb") as handle:
        await handle.write(file_content)

    try:
        if file_type == "pdf":
            total_pages = verify_pdf_readable(str(file_path), pdf_password)
        else:
            total_pages = count_image_frames(str(file_path))
    except ValueError as exc:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=str(exc))

    job_id = processor.create_job(
        original_name,
        total_pages=total_pages,
        batch_id=batch_id,
        file_type=file_type,
        source_path=source_path or original_name,
    )
    return job_id, str(file_path), original_name, pdf_password, file_type


async def _run_jobs(queue: list) -> None:
    for job_id, file_path, filename, password in queue:
        await processor.process_pdf(file_path, filename, job_id, password)


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
):
    """Upload a PDF, scanned image, or photo for quality analysis"""
    try:
        file_content = await file.read()
        job_id, file_path, original_name, pdf_password, _file_type = await _store_upload(
            file_content, file.filename or "upload", password
        )
        background_tasks.add_task(
            processor.process_pdf, file_path, original_name, job_id, pdf_password
        )
        return UploadResponse(
            job_id=job_id,
            message="File uploaded successfully. Processing started.",
            status=ProcessingStatus.PROCESSING,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/status/{job_id}", response_model=ProcessingJob)
async def get_job_status(job_id: str):
    """Get the status of a processing job"""
    try:
        job_data = processor.get_job_status(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return ProcessingJob(**job_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.get("/results/{job_id}", response_model=ProcessingResult)
async def get_job_results(job_id: str):
    """Get the complete results of a processing job"""
    try:
        job_data = processor.get_job_result(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_data["status"] == "failed":
            # For failed jobs, show the error message
            error_msg = job_data.get("error_message", "Job processing failed")
            raise HTTPException(status_code=400, detail=error_msg)
        elif job_data["status"] != "completed":
            raise HTTPException(status_code=400, detail="Job not completed yet")
        
        # Get review status
        review_status = reviews.get(job_id, ReviewStatus.PENDING)
        
        result = ProcessingResult(
            job_id=job_data["job_id"],
            filename=job_data["filename"],
            status=ProcessingStatus(job_data["status"]),
            total_pages=job_data["total_pages"],
            overall_confidence=job_data["overall_confidence"],
            overall_heuristic_confidence=job_data.get("overall_heuristic_confidence"),
            overall_ml_confidence=job_data.get("overall_ml_confidence"),
            overall_dl_confidence=job_data.get("overall_dl_confidence"),
            overall_ocr_confidence=job_data.get("overall_ocr_confidence"),
            ml_enabled=job_data.get("ml_enabled", False),
            dl_enabled=job_data.get("dl_enabled", False),
            ocr_enabled=job_data.get("ocr_enabled", False),
            auto_approved=job_data["auto_approved"],
            pages=job_data["pages"],
            review_status=review_status,
            created_at=job_data["created_at"],
            completed_at=job_data.get("completed_at")
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get job results: {str(e)}")


@router.get("/page/{job_id}/{page_number}", response_model=PageImageResponse)
async def get_page_image(job_id: str, page_number: int):
    """Get a specific page image and its quality analysis"""
    try:
        job_data = processor.get_job_result(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_data["status"] == "failed":
            # For failed jobs, show the error message
            error_msg = job_data.get("error_message", "Job processing failed")
            raise HTTPException(status_code=400, detail=error_msg)
        elif job_data["status"] != "completed":
            raise HTTPException(status_code=400, detail="Job not completed yet")
        
        # Find the requested page
        page_result = None
        for page in job_data["pages"]:
            if page.page_number == page_number:
                page_result = page
                break
        
        if not page_result:
            raise HTTPException(status_code=404, detail="Page not found")
        
        # Check if files exist
        if not os.path.exists(page_result.image_path):
            raise HTTPException(status_code=404, detail="Page image not found")
        
        return PageImageResponse(
            page_number=page_number,
            image_url=f"/api/v1/images/{job_id}/{page_number}",
            thumbnail_url=f"/api/v1/thumbnails/{job_id}/{page_number}",
            quality_result=page_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting page image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get page image: {str(e)}")


@router.get("/images/{job_id}/{page_number}")
async def serve_page_image(job_id: str, page_number: int):
    """Serve the actual page image file"""
    try:
        job_data = processor.get_job_result(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Find the requested page
        page_result = None
        for page in job_data["pages"]:
            if page.page_number == page_number:
                page_result = page
                break
        
        if not page_result or not os.path.exists(page_result.image_path):
            raise HTTPException(status_code=404, detail="Page image not found")
        
        return FileResponse(
            page_result.image_path,
            media_type="image/png",
            filename=f"page_{page_number}.png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving page image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve page image: {str(e)}")


@router.get("/thumbnails/{job_id}/{page_number}")
async def serve_thumbnail(job_id: str, page_number: int):
    """Serve the thumbnail image file"""
    try:
        job_data = processor.get_job_result(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Find the requested page
        page_result = None
        for page in job_data["pages"]:
            if page.page_number == page_number:
                page_result = page
                break
        
        if not page_result or not os.path.exists(page_result.thumbnail_path):
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        
        return FileResponse(
            page_result.thumbnail_path,
            media_type="image/png",
            filename=f"page_{page_number}_thumb.png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving thumbnail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to serve thumbnail: {str(e)}")


@router.post("/review/{job_id}", response_model=ReviewResponse)
async def submit_review(job_id: str, review_request: ReviewRequest):
    """Submit a manual review for a job"""
    try:
        job_data = processor.get_job_result(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_data["status"] != "completed":
            raise HTTPException(status_code=400, detail="Job not completed yet")
        
        # Store review
        reviews[job_id] = review_request.review_status

        samples_added = processor.record_review_training_samples(
            job_id,
            review_request.review_status.value,
        )
        
        return ReviewResponse(
            job_id=job_id,
            review_status=review_request.review_status,
            message=(
                "Review submitted successfully"
                + (f". Added {samples_added} ML training sample(s)." if samples_added else "")
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting review: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to submit review: {str(e)}")


@router.post("/reports/{job_id}", response_model=ReportResponse)
async def generate_report(job_id: str, report_request: ReportRequest):
    """Generate a report for a completed job"""
    try:
        job_data = processor.get_job_result(job_id)
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job_data["status"] != "completed":
            raise HTTPException(status_code=400, detail="Job not completed yet")
        
        # Generate report based on format
        if report_request.format.lower() == "json":
            report_data = {
                "job_id": job_data["job_id"],
                "filename": job_data["filename"],
                "overall_confidence": job_data["overall_confidence"],
                "overall_heuristic_confidence": job_data.get("overall_heuristic_confidence"),
                "overall_ml_confidence": job_data.get("overall_ml_confidence"),
                "overall_dl_confidence": job_data.get("overall_dl_confidence"),
                "overall_ocr_confidence": job_data.get("overall_ocr_confidence"),
                "ml_enabled": job_data.get("ml_enabled", False),
                "dl_enabled": job_data.get("dl_enabled", False),
                "ocr_enabled": job_data.get("ocr_enabled", False),
                "auto_approved": job_data["auto_approved"],
                "total_pages": job_data["total_pages"],
                "pages": [
                    {
                        "page_number": page.page_number,
                        "confidence_score": page.confidence_score,
                        "heuristic_confidence_score": page.heuristic_confidence_score,
                        "ml_confidence_score": page.ml_confidence_score,
                        "dl_confidence_score": page.dl_confidence_score,
                        "ocr_confidence_score": page.ocr_confidence_score,
                        "ocr_text_preview": page.ocr_text_preview,
                        "ocr_word_count": page.ocr_word_count,
                        "ocr_engine": page.ocr_engine,
                        "flags": [flag.value for flag in page.flags],
                        "blur_score": page.blur_score,
                        "orientation_score": page.orientation_score,
                        "cropping_score": page.cropping_score,
                        "color_consistency_score": page.color_consistency_score,
                        "dpi_score": page.dpi_score,
                        "actual_dpi": page.actual_dpi
                    }
                    for page in job_data["pages"]
                ],
                "review_status": reviews.get(job_id, "pending")
            }
            
            # Save report
            report_path = UPLOAD_DIR / f"{job_id}_report.json"
            import json
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            return ReportResponse(
                job_id=job_id,
                format="json",
                download_url=f"/api/v1/download/{job_id}/report.json",
                generated_at=job_data.get("completed_at", job_data["created_at"])
            )
        
        elif report_request.format.lower() == "csv":
            import csv
            report_path = UPLOAD_DIR / f"{job_id}_report.csv"
            
            with open(report_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Page", "Confidence", "Heuristic", "ML", "DL", "OCR", "Flags", "Blur", "Orientation", 
                    "Cropping", "Color Consistency", "DPI Score", "Actual DPI", "OCR Words", "OCR Engine"
                ])
                
                for page in job_data["pages"]:
                    writer.writerow([
                        page.page_number,
                        f"{page.confidence_score:.2f}",
                        f"{(page.heuristic_confidence_score or 0):.2f}",
                        f"{page.ml_confidence_score:.2f}" if page.ml_confidence_score is not None else "",
                        f"{page.dl_confidence_score:.2f}" if page.dl_confidence_score is not None else "",
                        f"{page.ocr_confidence_score:.2f}" if page.ocr_confidence_score is not None else "",
                        ";".join([flag.value for flag in page.flags]),
                        f"{page.blur_score:.2f}",
                        f"{page.orientation_score:.2f}",
                        f"{page.cropping_score:.2f}",
                        f"{page.color_consistency_score:.2f}",
                        f"{page.dpi_score:.2f}",
                        f"{page.actual_dpi:.0f}",
                        page.ocr_word_count if page.ocr_word_count is not None else "",
                        page.ocr_engine or "",
                    ])
            
            return ReportResponse(
                job_id=job_id,
                format="csv",
                download_url=f"/api/v1/download/{job_id}/report.csv",
                generated_at=job_data.get("completed_at", job_data["created_at"])
            )
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported report format")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    """Download a generated report file"""
    try:
        file_path = UPLOAD_DIR / f"{job_id}_{filename}"
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            file_path,
            filename=filename,
            media_type="application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


@router.get("/jobs", response_model=List[ProcessingJob])
async def list_jobs():
    """List all processing jobs"""
    try:
        jobs = []
        for job_data in processor.jobs.values():
            jobs.append(ProcessingJob(**job_data))
        
        return jobs
        
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@router.get("/ml/status", response_model=MLModelStatus)
async def get_ml_status():
    """Get ML model availability and training metadata."""
    return MLModelStatus(**quality_ml_model.get_status())


@router.post("/ml/retrain", response_model=MLRetrainResponse)
async def retrain_ml_model():
    """Retrain the quality model from bootstrap and review samples."""
    try:
        metadata = quality_ml_model.train()
        quality_ml_model.load()
        return MLRetrainResponse(
            message="Quality ML model retrained successfully",
            metadata=metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Error retraining ML model: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to retrain ML model: {str(exc)}")


@router.get("/dl/status", response_model=DLModelStatus)
async def get_dl_status():
    """Get deep-learning CNN availability and training metadata."""
    return DLModelStatus(**dl_quality_model.get_status())


@router.post("/dl/retrain", response_model=MLRetrainResponse)
async def retrain_dl_model():
    """Retrain the bootstrap CNN quality model."""
    try:
        metadata = dl_quality_model.train_bootstrap()
        return MLRetrainResponse(
            message="Deep-learning quality model retrained successfully",
            metadata=metadata,
        )
    except Exception as exc:
        logger.error("Error retraining DL model: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to retrain DL model: {str(exc)}")


@router.get("/ocr/status", response_model=OCRStatus)
async def get_ocr_status():
    """Get OCR engine availability."""
    status = ocr_status()
    status["enabled"] = OCR_ENABLED
    return OCRStatus(**status)


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    password: Optional[str] = Form(None),
):
    """Upload multiple PDFs, scans, or photos and process them as a batch."""
    if not files:
        raise HTTPException(status_code=400, detail="Select one or more files to analyze.")

    batch_id = processor.create_batch("upload")
    batch = processor.batches[batch_id]
    queue = []
    skipped = 0

    for upload in files:
        filename = Path(upload.filename or "upload").name
        content = await upload.read()
        try:
            job_id, file_path, original_name, pdf_password, file_type = await _store_upload(
                content, filename, password, batch_id=batch_id, source_path=filename
            )
        except HTTPException as exc:
            skipped += 1
            batch["files"].append(
                {
                    "filename": filename,
                    "relative_path": filename,
                    "job_id": None,
                    "status": "failed",
                    "file_type": None,
                    "size": len(content),
                    "error_message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                    "overall_confidence": None,
                }
            )
            continue

        batch["files"].append(
            {
                "filename": original_name,
                "relative_path": original_name,
                "job_id": job_id,
                "status": "processing",
                "file_type": file_type,
                "size": len(content),
                "error_message": None,
                "overall_confidence": None,
            }
        )
        queue.append((job_id, file_path, original_name, pdf_password))

    batch["total_files"] = len(batch["files"])
    batch["skipped_files"] = skipped
    batch["processed_files"] = skipped
    if not queue:
        batch["status"] = "failed"
        batch["completed_at"] = time.time()
        raise HTTPException(
            status_code=400,
            detail=f"None of the selected files could be processed. Upload a {ACCEPT_LABEL}.",
        )

    background_tasks.add_task(_run_jobs, queue)
    return BatchUploadResponse(
        batch_id=batch_id,
        message=f"Processing {len(queue)} file(s).",
        status=ProcessingStatus.PROCESSING,
        total_files=len(queue),
        job_ids=[item[0] for item in queue],
    )


@router.get("/batches/{batch_id}", response_model=BatchJob)
async def get_batch(batch_id: str):
    batch = processor.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return BatchJob(**batch)


@router.post("/sharepoint/preview", response_model=SharePointPreviewResponse)
async def preview_sharepoint(request: SharePointPreviewRequest):
    """List supported files in a SharePoint document library without processing them."""
    try:
        client = SharePointClient(
            tenant_id=request.tenant_id,
            client_id=request.client_id,
            client_secret=request.client_secret,
            access_token=request.access_token,
        )
        files = await client.list_supported_files(request.url)
        return SharePointPreviewResponse(
            url=request.url,
            total_files=len(files),
            files=[
                SharePointFilePreview(
                    name=item.name,
                    relative_path=item.relative_path,
                    size=item.size,
                    web_url=item.web_url,
                    file_type="pdf" if item.name.lower().endswith(".pdf") else "image",
                )
                for item in files
            ],
        )
    except SharePointError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("SharePoint preview failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"SharePoint preview failed: {exc}")


async def _run_sharepoint_batch(batch_id: str, request: SharePointProcessRequest) -> None:
    batch = processor.batches[batch_id]
    try:
        client = SharePointClient(
            tenant_id=request.tenant_id,
            client_id=request.client_id,
            client_secret=request.client_secret,
            access_token=request.access_token,
        )
        files = await client.list_supported_files(request.url)
        batch["total_files"] = len(files)
        batch["files"] = [
            {
                "filename": item.name,
                "relative_path": item.relative_path,
                "job_id": None,
                "status": "pending",
                "file_type": "pdf" if item.name.lower().endswith(".pdf") else "image",
                "size": item.size,
                "error_message": None,
                "overall_confidence": None,
            }
            for item in files
        ]

        for index, item in enumerate(files):
            try:
                content = await client.download_file(item)
                job_id, file_path, original_name, pdf_password, file_type = await _store_upload(
                    content,
                    item.name,
                    batch_id=batch_id,
                    source_path=item.relative_path,
                )
                batch["files"][index]["job_id"] = job_id
                batch["files"][index]["status"] = "processing"
                batch["files"][index]["file_type"] = file_type
                await processor.process_pdf(file_path, original_name, job_id, pdf_password)
            except HTTPException as exc:
                batch["files"][index]["status"] = "failed"
                batch["files"][index]["error_message"] = (
                    exc.detail if isinstance(exc.detail, str) else str(exc.detail)
                )
                batch["processed_files"] = sum(
                    1 for entry in batch["files"] if entry.get("status") in {"completed", "failed"}
                )
            except Exception as exc:
                logger.error("SharePoint file failed (%s): %s", item.relative_path, exc)
                batch["files"][index]["status"] = "failed"
                batch["files"][index]["error_message"] = str(exc)
                batch["processed_files"] = sum(
                    1 for entry in batch["files"] if entry.get("status") in {"completed", "failed"}
                )

        batch["processed_files"] = sum(
            1 for entry in batch["files"] if entry.get("status") in {"completed", "failed"}
        )
        batch["status"] = "completed"
        batch["completed_at"] = time.time()
    except Exception as exc:
        logger.error("SharePoint batch failed: %s", exc)
        batch["status"] = "failed"
        batch["error_message"] = str(exc)
        batch["completed_at"] = time.time()


@router.post("/sharepoint/process", response_model=BatchUploadResponse)
async def process_sharepoint(
    request: SharePointProcessRequest,
    background_tasks: BackgroundTasks,
):
    """Traverse a SharePoint library and run quality analysis on every supported file."""
    if not request.url.strip():
        raise HTTPException(status_code=400, detail="Enter a SharePoint site or document library URL.")
    try:
        client = SharePointClient(
            tenant_id=request.tenant_id,
            client_id=request.client_id,
            client_secret=request.client_secret,
            access_token=request.access_token,
        )
        await client.get_token()
    except SharePointError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    batch_id = processor.create_batch("sharepoint", source_url=request.url)
    background_tasks.add_task(_run_sharepoint_batch, batch_id, request)
    return BatchUploadResponse(
        batch_id=batch_id,
        message="Scanning the SharePoint library and starting analysis.",
        status=ProcessingStatus.PROCESSING,
        total_files=0,
        job_ids=[],
    )
