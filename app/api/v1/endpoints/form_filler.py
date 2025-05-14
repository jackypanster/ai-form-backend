from fastapi import APIRouter, HTTPException, Depends, status
from app.models.form_models import FillFormRequest, FillFormSuccessResponse, ErrorResponse
from app.core.llm_services import LLMService
from app.core.config import Settings, get_settings
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/fill-form",
    response_model=FillFormSuccessResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Request data validation failed"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse, "description": "Server internal error"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse, "description": "LLM service unavailable or request failed"}
    }
)
async def fill_form_endpoint(
    request_data: FillFormRequest,
    settings: Settings = Depends(get_settings)
):
    logger.info(f"Received request to fill form with {len(request_data.fields)} fields.")

    llm_service = LLMService(api_key=settings.llm_api_key, api_endpoint=settings.llm_api_endpoint)

    fields_str = "\n".join([f"- {field}" for field in request_data.fields])
    # Default prompt template, can be expanded based on request_data.prompt_template_id
    prompt = f"""You are an AI assistant tasked with filling out a form.
Below are the fields of the form:
--- FIELDS START ---
{fields_str}
--- FIELDS END ---

Here is the source content from which to extract the information:
--- CONTENT START ---
{request_data.source_content}
--- CONTENT END ---

Please extract the relevant information from the CONTENT and fill in each FIELD.
Return the output as a JSON object where each key is a field name from the FIELDS list and its value is the corresponding extracted content.
If information for a field is not found, use an empty string or "Not Found" as its value.
Ensure the output is only the JSON object itself, without any additional explanations or markings.
"""
    logger.debug(f"Constructed prompt for LLM: {prompt[:200]}...") # Log snippet of prompt

    try:
        llm_response_text = await llm_service.get_completion(prompt)
        logger.info("Successfully received response from LLM service.")
        logger.debug(f"LLM response text: {llm_response_text}")
    except Exception as e:
        logger.error(f"LLM service request failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"LLM service request failed: {str(e)}")

    try:
        filled_data = json.loads(llm_response_text)
        if not isinstance(filled_data, dict):
            logger.error(f"LLM response was not a valid JSON object. Received: {llm_response_text}")
            raise ValueError("LLM response was not a valid JSON object.")
        logger.info("Successfully parsed LLM response.")
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse LLM response: {e}. Response was: {llm_response_text}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to parse LLM response: {str(e)}")

    return FillFormSuccessResponse(filled_data=filled_data) 