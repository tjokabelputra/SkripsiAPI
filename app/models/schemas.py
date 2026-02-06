from pydantic import BaseModel
from typing import List, Optional, Any

class ResponseMessage(BaseModel):
    code: int
    status: str
    data: Optional[Any] = None
    message: Optional[str] = None

class SubmitApkData(BaseModel):
    task_id: str

class ExtractionMetadata(BaseModel):
    task_id: str
    apk_name: str
    apk_size_bytes: int
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None

class ExtractionStatus(BaseModel):
    status: str
    error: Optional[str] = None
    metadata: ExtractionMetadata

class ExtractionResultData(BaseModel):
    metadata: ExtractionMetadata
    pca: List[float]