"""OCR analysis for page images using RapidOCR (ONNX deep-learning models).

Falls back gracefully when RapidOCR is unavailable. Optional Tesseract support
is used when the system binary is installed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import cv2
import numpy as np

from ..core.config import OCR_ENABLED

logger = logging.getLogger(__name__)

_rapid_engine = None
_rapid_failed = False


@dataclass
class OCRAnalysis:
    text: str
    confidence: float  # 0-100 mean recognition confidence
    word_count: int
    char_count: int
    score: float  # 0-100 readability / OCR quality score
    engine: str
    available: bool

    def to_dict(self) -> Dict[str, Any]:
        preview = self.text.strip().replace("\n", " ")
        if len(preview) > 240:
            preview = preview[:237] + "..."
        return {
            "text_preview": preview,
            "confidence": self.confidence,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "score": self.score,
            "engine": self.engine,
            "available": self.available,
        }


def _get_rapid_ocr():
    global _rapid_engine, _rapid_failed
    if _rapid_failed:
        return None
    if _rapid_engine is not None:
        return _rapid_engine
    try:
        from rapidocr_onnxruntime import RapidOCR

        _rapid_engine = RapidOCR()
        return _rapid_engine
    except Exception as exc:
        logger.warning("RapidOCR unavailable: %s", exc)
        _rapid_failed = True
        return None


def _score_from_ocr(confidence: float, word_count: int, char_count: int, image_area: int) -> float:
    """Map OCR signals into a 0-100 page readability score."""
    dens = min(1.0, char_count / max(image_area / 8000.0, 1.0))
    word_factor = min(1.0, word_count / 40.0)
    conf_factor = confidence / 100.0
    # Empty pages: high score (nothing wrong to read); sparse/noisy OCR: lower
    if word_count == 0 and char_count < 5:
        return 85.0  # blank / graphic page — OCR not a failure
    score = (0.55 * conf_factor + 0.25 * dens + 0.20 * word_factor) * 100.0
    return float(min(100.0, max(0.0, score)))


def _analyze_with_rapid(image_bgr: np.ndarray) -> Optional[OCRAnalysis]:
    engine = _get_rapid_ocr()
    if engine is None:
        return None
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    result, _ = engine(rgb)
    if not result:
        h, w = image_bgr.shape[:2]
        return OCRAnalysis(
            text="",
            confidence=0.0,
            word_count=0,
            char_count=0,
            score=_score_from_ocr(0.0, 0, 0, h * w),
            engine="rapidocr",
            available=True,
        )

    texts = []
    confidences = []
    for item in result:
        # RapidOCR rows: [box, text, score]
        if len(item) < 3:
            continue
        text = str(item[1] or "").strip()
        try:
            conf = float(item[2])
        except (TypeError, ValueError):
            conf = 0.0
        if text:
            texts.append(text)
            confidences.append(conf * 100.0 if conf <= 1.0 else conf)

    joined = "\n".join(texts)
    words = re.findall(r"\w+", joined, flags=re.UNICODE)
    mean_conf = float(np.mean(confidences)) if confidences else 0.0
    h, w = image_bgr.shape[:2]
    return OCRAnalysis(
        text=joined,
        confidence=mean_conf,
        word_count=len(words),
        char_count=len(re.sub(r"\s+", "", joined)),
        score=_score_from_ocr(mean_conf, len(words), len(re.sub(r"\s+", "", joined)), h * w),
        engine="rapidocr",
        available=True,
    )


def _analyze_with_tesseract(image_bgr: np.ndarray) -> Optional[OCRAnalysis]:
    try:
        import pytesseract
        from pytesseract import Output
    except Exception:
        return None

    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        data = pytesseract.image_to_data(gray, output_type=Output.DICT)
        texts = []
        confidences = []
        for text, conf in zip(data.get("text", []), data.get("conf", [])):
            try:
                c = float(conf)
            except (TypeError, ValueError):
                continue
            if c < 0:
                continue
            token = (text or "").strip()
            if token:
                texts.append(token)
                confidences.append(c)
        joined = " ".join(texts)
        words = re.findall(r"\w+", joined, flags=re.UNICODE)
        mean_conf = float(np.mean(confidences)) if confidences else 0.0
        h, w = image_bgr.shape[:2]
        return OCRAnalysis(
            text=joined,
            confidence=mean_conf,
            word_count=len(words),
            char_count=len(re.sub(r"\s+", "", joined)),
            score=_score_from_ocr(mean_conf, len(words), len(re.sub(r"\s+", "", joined)), h * w),
            engine="tesseract",
            available=True,
        )
    except Exception as exc:
        logger.warning("Tesseract OCR failed: %s", exc)
        return None


def analyze_page_ocr(image_bgr: np.ndarray) -> OCRAnalysis:
    """Run OCR on a BGR page image and return readability metrics."""
    result = _analyze_with_rapid(image_bgr)
    if result is None:
        result = _analyze_with_tesseract(image_bgr)
    if result is not None:
        return result

    h, w = image_bgr.shape[:2]
    return OCRAnalysis(
        text="",
        confidence=0.0,
        word_count=0,
        char_count=0,
        score=0.0,
        engine="none",
        available=False,
    )


def ocr_status() -> Dict[str, Any]:
    rapid = _get_rapid_ocr() is not None
    tess = False
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        tess = True
    except Exception:
        tess = False
    return {
        "enabled": OCR_ENABLED,
        "rapidocr_available": rapid,
        "tesseract_available": tess,
        "active_engine": "rapidocr" if rapid else ("tesseract" if tess else "none"),
    }
