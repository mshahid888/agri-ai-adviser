"""Multimodal/Vision Abstraction for M15 Agricultural AI Agent."""
import base64
import os
from dataclasses import dataclass, field
from typing import Optional, List
from openai import OpenAI
from app.config import OMNIROUTE_BASE_URL, OMNIROUTE_API_KEY, AGRI_AI_MODEL

@dataclass
class VisionResult:
    observations: List[str] = field(default_factory=list)
    candidates: List[str] = field(default_factory=list)
    confidence: float = 0.0
    uncertainty: str = ""
    limitations: str = ""

class VisionAnalyzer:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.client = None
        if self.enabled and OMNIROUTE_API_KEY:
            self.client = OpenAI(base_url=OMNIROUTE_BASE_URL, api_key=OMNIROUTE_API_KEY)

    def validate_image(self, image_path: str) -> bool:
        if not os.path.exists(image_path):
            return False
        valid_ext = {".jpg", ".jpeg", ".png", ".webp"}
        if not any(image_path.lower().endswith(ext) for ext in valid_ext):
            return False
        if os.path.getsize(image_path) > 10 * 1024 * 1024: # 10MB limit
            return False
        return True

    def analyze(self, image_path: str, query: str = "") -> VisionResult:
        if not self.enabled or not self.client:
            return VisionResult(uncertainty="Vision system unavailable.")
        
        if not self.validate_image(image_path):
            return VisionResult(uncertainty="Invalid or missing image.")

        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            ext = os.path.splitext(image_path)[1].lower()
            mime = "image/jpeg"
            if ext == ".png": mime = "image/png"
            elif ext == ".webp": mime = "image/webp"

            prompt = f"Analyze this agricultural image. {query} List observations, candidate issues, and confidence."
            
            response = self.client.chat.completions.create(
                model=AGRI_AI_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}}
                    ]
                }]
            )
            text = response.choices[0].message.content
            return VisionResult(observations=[text], confidence=0.8)
        except Exception as e:
            return VisionResult(uncertainty=f"Vision analysis failed: {str(e)}")
