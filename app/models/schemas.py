from pydantic import BaseModel
from typing import List, Optional

class SubmitApkResponse(BaseModel):
    task_id: str
    message: str

class GetAPKExtractionStatusResponse(BaseModel):
    status: str
    json_path: Optional[str] = None
    error: Optional[str] = None
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    apk_name: str

class ExtractionMetadata(BaseModel):
    task_id: str
    apk_name: str
    apk_size_byte: int
    start_time: str
    end_time: str
    duration_seconds: float

class GetAPKExtractionResult(BaseModel):
    metadata: ExtractionMetadata
    extraction_id: str
    pca: List[float]

class DeleteAPKExtractionResult(BaseModel):
    message: str