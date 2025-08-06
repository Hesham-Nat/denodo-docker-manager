from pydantic import BaseModel

class CopyRequest(BaseModel):
    source_path: str
    target_path: str