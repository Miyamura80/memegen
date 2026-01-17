from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class Template(BaseModel):
    template_id: str
    name: str
    format: str
    image_path: str
    text_areas: str
    aspect_ratio: str
    tags: List[str]
    tone_affinity: List[str]
    example_captions: List[List[str]]
    embedding: Optional[List[float]] = None
    constraints: Optional[Dict[str, Any]] = None
    external_assets: Optional[List[str]] = None
