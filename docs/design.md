# AI Form Filler - Backend Design Document (Phase 1 MVP)

## 1. Introduction

This document outlines the backend design for Phase 1 (MVP) of the AI Form Filler project. The backend will be implemented using FastAPI (Python) and will serve as the intermediary between the Next.js frontend and an external Large Language Model (LLM) API. The primary responsibilities include receiving form data, orchestrating LLM interactions, and returning structured results to the frontend.

This design explicitly defers data persistence and focuses on a stateless request-response model.

## 2. Guiding Principles & Assumptions for Backend

* **Rapid MVP Development**: Prioritize speed of delivery for core backend functionality.
* **Stateless Operations**: The backend will be stateless, processing each API request independently without relying on stored session data.
* **External LLM API Integration**: The backend will manage communication with a public LLM API (e.g., DeepSeek API).
* **Text-Based Data Handling**: The backend will primarily process text-based inputs (field names, source content) and aims to output structured JSON data.

## 3. Python Virtual Environment Management

* **Tool**: `uv` will be used for managing the Python virtual development environment for the backend. This includes creating the virtual environment and managing project dependencies.

## 4. Backend Architecture (FastAPI)

### 4.1. Core Responsibilities

* **API Endpoint Provision**: Expose a secure API endpoint to receive form field names, source content text, and potentially a prompt template identifier from the frontend.
* **Input Validation**: Validate all incoming request data using Pydantic models to ensure data integrity and prevent issues.
* **Prompt Engineering**: Dynamically construct precise and effective prompts for the external LLM API. This involves combining user-provided field names, source content, and predefined prompt templates.
* **LLM API Orchestration**:
    * Securely manage and use the API key for the chosen external LLM service.
    * Make authenticated API calls to the external LLM service (e.g., DeepSeek API) using an asynchronous HTTP client like `httpx`.
* **Response Processing**:
    * Receive the response from the LLM.
    * Parse and transform the LLM's response into a consistent JSON structure (e.g., `{"field_name": "filled_content", ...}`). This is a critical step to ensure the frontend receives data in a predictable format.
* **Data Serialization**: Return structured JSON data (or appropriate error messages) to the frontend.

### 4.2. API Endpoint Definition

* **Endpoint**: `POST /api/v1/fill-form`
* **Request Body (JSON)**:
    * To be defined and validated using Pydantic models.
    * Expected fields:
        * `fields`: A list of strings representing the form field names (e.g., `["Field Name 1", "Field Name 2", ...]`). Alternatively, `fields_text` as a single multi-line string could be considered.
        * `source_content`: A string containing the full text content from which information needs to be extracted.
        * `prompt_template_id` (Optional): A string identifier to allow for different prompt strategies in the future (e.g., `"default_v1"`).
    ```json
    // Example Request Body
    {
      "fields": ["Full Name", "Email Address", "Phone Number"],
      "source_content": "John Doe can be reached at john.doe@email.com or by phone at 123-456-7890.",
      "prompt_template_id": "default_v1"
    }
    ```
* **Response Body (JSON) - Success**:
    * A JSON object containing the status and the extracted data.
    ```json
    // Example Success Response
    {
      "status": "success",
      "filled_data": {
        "Full Name": "John Doe",
        "Email Address": "john.doe@email.com",
        "Phone Number": "123-456-7890"
      }
    }
    ```
* **Response Body (JSON) - Error**:
    * A JSON object containing an error status and a descriptive message.
    ```json
    // Example Error Response
    {
      "status": "error",
      "message": "Error processing request: LLM API unreachable."
    }
    ```

### 4.3. LLM Integration Details

* **HTTP Client**: `httpx` is recommended for making asynchronous API calls to the external LLM, aligning with FastAPI's asynchronous nature.
* **API Key Management**: The LLM API key must be stored securely as an environment variable (e.g., `LLM_API_KEY`) and accessed by the backend at runtime. It must not be hardcoded into the application.
* **Prompt Engineering Strategy**:
    * The backend will dynamically construct prompts. A general template would be:
        ```
        You are an AI assistant tasked with filling out a form.
        Below are the fields of the form:
        --- FIELDS START ---
        {list_of_fields_from_user}
        --- FIELDS END ---

        Here is the source content from which to extract the information:
        --- CONTENT START ---
        {source_content_from_user}
        --- CONTENT END ---

        Please extract the relevant information from the CONTENT and fill in each FIELD.
        Return the output as a JSON object where each key is a field name from the FIELDS list and its value is the corresponding extracted content.
        If information for a field is not found, use an empty string or "Not Found" as its value.
        Ensure the output is only the JSON object.
        ```
    * This template will be populated with the `fields` and `source_content` from the API request.
* **Response Parsing**:
    * The ideal scenario is that the LLM API can be configured to return a JSON object directly.
    * If the LLM returns a string representation of JSON, the backend must parse it into a Python dictionary.
    * If the LLM returns unstructured text containing field-value pairs, robust parsing logic (potentially involving regular expressions) will be needed. For MVP, aiming for direct JSON output from the LLM is preferred to minimize parsing complexity.

### 4.4. Data Models (Pydantic Schemas)

Pydantic models will be used for request and response validation and serialization.

* **`FillFormRequest`**:
    * `fields: List[str]`
    * `source_content: str`
    * `prompt_template_id: Optional[str]`
* **`FillFormSuccessResponse`**:
    * `status: str` (e.g., "success")
    * `filled_data: Dict[str, str]` (mapping field names to their filled content)
* **`ErrorResponse`**:
    * `status: str` (e.g., "error")
    * `message: str`

(These would translate into Python Pydantic class definitions as shown in the architecture document).

## 5. Deployment Considerations (Backend)

* **Containerization**: The FastAPI backend will be containerized using Docker.
* **Backend Dockerfile**:
    * Start from a suitable Python base image.
    * Install dependencies listed in `requirements.txt` (managed via `uv`).
    * Run the application using an ASGI server like Uvicorn.
* **Environment Variables**:
    * `LLM_API_KEY`: Essential for authenticating with the external LLM service.
    * `LLM_API_ENDPOINT`: The base URL for the external LLM API.
    * Other necessary configurations (e.g., logging levels).

## 6. Security Considerations (Backend)

* **LLM API Key Security**: Store and manage the LLM API key strictly via environment variables.
* **Input Validation**: Utilize Pydantic for robust validation of all incoming data to prevent excessively large requests or malformed data that could impact performance or cost.
* **Rate Limiting**: Consider implementing basic rate limiting on the `/api/v1/fill-form` endpoint to prevent abuse, especially if the API becomes accessible.
* **PII Handling**:
    * The backend will transiently handle user-provided content that may contain PII.
    * No PII will be stored by the backend in this phase.
    * The data is passed to an external LLM; understanding the LLM provider's data handling policies is crucial.
* **HTTPS**: Ensure the FastAPI application is served over HTTPS in a production environment (typically handled by a reverse proxy like Nginx or a managed cloud service).
* **CORS (Cross-Origin Resource Sharing)**: Configure FastAPI's CORS middleware to allow requests specifically from the Next.js frontend's domain.

## 7. Data Persistence

* As per the MVP scope, data persistence (e.g., saving form requests, results, or user data) is **not included** in this backend design phase. The backend will operate statelessly.

## 8. Future Considerations (Post-MVP Backend Enhancements)

* Implementing user authentication and authorization.
* Developing more sophisticated prompt management and allowing user-defined prompt templates.
* Integrating with a database if data persistence becomes a requirement.
* Adding capabilities for managing and potentially fine-tuning a self-hosted LLM.