from typing import List, Optional
from pydantic import BaseModel

class StoryBrief(BaseModel):
    who: str
    what: str
    when: str
    where: str
    key_events: List[str]
    main_tension: str
    sentiment: str
    required_assets: Optional[List[str]] = None
