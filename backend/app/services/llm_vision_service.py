"""OpenAI Vision LLM quality review for low DL-confidence pages."""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import cv2
import httpx
import numpy as np

from ..core.config import (
    LLM_ENABLED,
    LLM_DL_TRIGGER,
    OPENAI_API_KEY,
    OPENAI_VISION_MODEL,
)

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


@dataclass
class LLMVisionAnalysis:
    score: float  # 0-100
    summary: str
    issues: List[str]
    model: str
    invoked: bool
    available: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "summary": self.summary,
            "issues": self.issues,
            "model": self.model,
            "invoked": self.invoked,
            "available": self.available,
            "error": self.error,
        }


def llm_status() -> Dict[str, Any]:
    key_present = bool(OPENAI_API_KEY and OPENAI_API_KEY.strip())
    return {
        "enabled": LLM_ENABLED,
        "api_key_configured": key_present,
        "model": OPENAI_VISION_MODEL,
        "dl_trigger_threshold": LLM_DL_TRIGGER,
        "available": LLM_ENABLED and key_present,
    }


def should_invoke_llm(dl_confidence: Optional[float]) -> bool:
    """Invoke Vision LLM when DL is missing or below the configured threshold."""
    if not LLM_ENABLED or not (OPENAI_API_KEY and OPENAI_API_KEY.strip()):
        return False
    if dl_confidence is None:
        return True
    return float(dl_confidence) < float(LLM_DL_TRIGGER)


def _encode_image_jpeg(image_bgr: np.ndarray, max_side: int = 1280) -> str:
    h, w = image_bgr.shape[:2]
    scale = min(1.0, max_side / float(max(h, w)))
    if scale < 1.0:
        image_bgr = cv2.resize(
            image_bgr,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_AREA,
        )
    ok, buf = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise ValueError("Failed to encode page image for Vision LLM")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _parse_llm_json(content: str) -> Dict[str, Any]:
    text = (content or "").strip()
    if not text:
        return {}
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {"summary": text[:400], "score": None}


def _http_error_detail(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        try:
            payload = exc.response.json()
            err = payload.get("error") or {}
            msg = err.get("message") or payload
            code = err.get("code") or err.get("type") or ""
            detail = str(msg)
            if code:
                detail = f"{code}: {detail}"
            return detail[:240]
        except Exception:
            return (exc.response.text or str(exc))[:240]
    return str(exc)[:240]


def analyze_page_with_llm(
    image_bgr: np.ndarray,
    *,
    page_number: int = 1,
    dl_confidence: Optional[float] = None,
    heuristic_confidence: Optional[float] = None,
    ocr_preview: Optional[str] = None,
) -> LLMVisionAnalysis:
    """Ask OpenAI Vision to score scan/page quality (0-100) with a short rationale."""
    if not should_invoke_llm(dl_confidence):
        return LLMVisionAnalysis(
            score=0.0,
            summary="",
            issues=[],
            model=OPENAI_VISION_MODEL,
            invoked=False,
            available=True,
        )

    if not OPENAI_API_KEY:
        return LLMVisionAnalysis(
            score=0.0,
            summary="",
            issues=[],
            model=OPENAI_VISION_MODEL,
            invoked=False,
            available=False,
            error="OPENAI_API_KEY not configured",
        )

    try:
        b64 = _encode_image_jpeg(image_bgr)
        context_bits = [
            f"page_number={page_number}",
            f"dl_confidence={dl_confidence}",
            f"heuristic_confidence={heuristic_confidence}",
        ]
        if ocr_preview:
            context_bits.append(f"ocr_preview={ocr_preview[:200]}")

        prompt = (
            "You are a document scan quality inspector. Review the page image and "
            "return ONLY valid JSON with keys:\n"
            '  "score": number 0-100 (100 = excellent scan quality for archival/OCR),\n'
            '  "summary": short 1-2 sentence assessment,\n'
            '  "issues": array of short issue labels '
            "(e.g. blur, skew, crop, low_contrast, glare, noise, low_dpi, none).\n"
            "Focus on visual scan quality (sharpness, orientation, cropping, contrast, "
            "legibility), not document business content.\n"
            f"Context: {'; '.join(context_bits)}"
        )

        payload = {
            "model": OPENAI_VISION_MODEL,
            "temperature": 0.1,
            "max_tokens": 400,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        last_error: Optional[Exception] = None
        data = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(OPENAI_CHAT_URL, headers=headers, json=payload)
                    if response.status_code == 429 and attempt < 2:
                        # Quota exhaustion won't recover with retries; only retry soft rate limits
                        try:
                            body = response.json()
                            code = ((body.get("error") or {}).get("code") or "")
                            if code in {"insufficient_quota", "credit_balance_exhausted"}:
                                response.raise_for_status()
                        except httpx.HTTPStatusError:
                            raise
                        except Exception:
                            pass
                        import time

                        wait_s = 2 ** attempt
                        logger.info("OpenAI rate limited; retrying in %ss", wait_s)
                        time.sleep(wait_s)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    break
            except Exception as exc:
                last_error = exc
                if attempt >= 2:
                    raise
                # Don't keep retrying non-429 errors repeatedly unless first attempt
                if not isinstance(exc, httpx.HTTPStatusError) or (
                    exc.response is not None and exc.response.status_code != 429
                ):
                    raise
        if data is None:
            raise last_error or RuntimeError("OpenAI Vision call failed")

        content = ""
        choices = data.get("choices") or []
        if choices:
            content = ((choices[0].get("message") or {}).get("content")) or ""
        parsed = _parse_llm_json(content)
        raw_score = parsed.get("score")
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 50.0
        score = float(min(100.0, max(0.0, score)))
        summary = str(parsed.get("summary") or content or "").strip()[:500]
        issues = parsed.get("issues") or []
        if not isinstance(issues, list):
            issues = [str(issues)]
        issues = [str(i)[:40] for i in issues[:8]]
        return LLMVisionAnalysis(
            score=score,
            summary=summary,
            issues=issues,
            model=OPENAI_VISION_MODEL,
            invoked=True,
            available=True,
        )
    except Exception as exc:
        detail = _http_error_detail(exc)
        logger.warning("OpenAI Vision LLM failed on page %s: %s", page_number, detail)
        return LLMVisionAnalysis(
            score=0.0,
            summary="",
            issues=[],
            model=OPENAI_VISION_MODEL,
            invoked=True,
            available=False,
            error=detail,
        )
