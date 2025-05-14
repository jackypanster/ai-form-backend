from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class FillFormRequest(BaseModel):
    fields: List[str] = Field(..., description="List of field names to be filled.")
    source_content: str = Field(..., description="The source text content for information extraction.")
    prompt_template_id: Optional[str] = Field("default_v1", description="Identifier for the prompt template to be used.")

class FillFormSuccessResponse(BaseModel):
    status: str = "success"
    filled_data: Dict[str, str] # Field name as key, filled content as value

class ErrorResponse(BaseModel):
    status: str = "error"
    message: str 