import httpx
import json
import logging

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, api_key: str, api_endpoint: str):
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.timeout = 30  # seconds

    async def get_completion(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-coder", # Example, replace with actual model
            "prompt": prompt,
            "max_tokens": 1500,
            "temperature": 0.1,
            # "response_format": {"type": "json_object"} # If LLM supports
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.api_endpoint, headers=headers, json=payload)
                response.raise_for_status()
                response_data = response.json()

                # This parsing logic needs to be adapted to your specific LLM API response structure
                if "choices" in response_data and response_data["choices"]:
                    message = response_data["choices"][0].get("message", {})
                    if "content" in message:
                        return message["content"]
                
                # Fallback or alternative parsing if the above structure is not found
                # For example, some APIs might return text directly or in a different path
                # text_content = response_data.get("text") or response_data.get("generated_text")
                # if text_content:
                #     return text_content

                logger.error(f"Could not extract valid content from LLM response: {response_data}")
                raise ValueError("Could not extract valid content from LLM response.")

            except httpx.HTTPStatusError as e:
                logger.error(f"LLM API request failed with status {e.response.status_code}: {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"LLM API request failed due to network issue or timeout: {e}")
                raise
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error(f"Failed to parse LLM API JSON response: {e}. Response text: {response.text if 'response' in locals() else 'No response object'}")
                raise ValueError(f"Error parsing LLM API response: {str(e)}") 