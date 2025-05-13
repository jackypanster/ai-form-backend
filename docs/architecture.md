# Phase 1: AI Form Filler (MVP) - Technical Architecture Document

## 1. Introduction

This document outlines the technical architecture for Phase 1 (MVP) of the AI Form Filler project. The primary goal of this phase is to quickly deploy a minimal viable product that allows users to manually input form fields (extracted via external OCR tools) and source content. An external Large Language Model (LLM) API will then be used to process this input and suggest filled values for the fields.

The key technology stack for this phase includes:
-   **Frontend**: Next.js with Shadcn UI for componentry and styling.
-   **Backend**: FastAPI (Python).
-   **AI Model**: External LLM API (e.g., DeepSeek API, or similar).
-   **Deployment**: Containerization (Docker).

## 2. Guiding Principles & Assumptions

-   **Rapid MVP Development**: Prioritize speed of delivery for core functionality.
-   **External LLM API**: Utilize a readily available public LLM API to avoid the overhead of managing a self-hosted model in this initial phase.
-   **Manual OCR Pre-processing**: The system will *not* perform OCR. Users are responsible for extracting field names from form images using external tools (e.g., WeChat screenshot OCR) and pasting them as text.
-   **Text-Based Input**: All inputs to the system (field names, source content) are text.
-   **User-Centric UI**: Employ Shadcn UI for a clean, modern, and accessible user interface.
-   **Stateless Backend**: The backend will be stateless, processing each request independently.
-   **Structured Output Goal**: The system will aim to receive structured data (e.g., JSON mapping fields to content) from the LLM, or parse it into such a format.

## 3. Overall Architecture

The system comprises a Next.js frontend (with Shadcn UI), a FastAPI backend, and an external LLM API service.

```mermaid
graph LR
    A --> B{Next.js Frontend <br/> (Shadcn UI, API Client)};
    B -- API Request (Fields, Content, Prompt) --> C{FastAPI Backend <br/> (API Logic, Prompt Engineering, LLM API Orchestration)};
    C -- API Call (Constructed Prompt) --> D;
    D -- LLM Response (Filled Data) --> C;
    C -- API Response (Structured Data) --> B;
    B -- Display Results --> A;
```

**Data Flow:**
1.  The user extracts field names from a form image using an external OCR tool.
2.  The user navigates to the web application. On the Next.js frontend, they paste the extracted field names (e.g., one per line) into a designated text area.
3.  The user pastes the source content (the text from which information should be extracted) into another text area.
4.  The user clicks a "Fill Form" (or similar) button.
5.  The Next.js frontend sends the field names (as a list of strings or a single multi-line string), the source content, and a predefined prompt template to the FastAPI backend via an HTTP API call.
6.  The FastAPI backend receives the request. It performs prompt engineering by combining the user-provided fields, source content, and the prompt template into a final prompt suitable for the external LLM.
7.  The backend makes an API call to the chosen external LLM service (e.g., DeepSeek API), including necessary authentication (e.g., API key).
8.  The external LLM processes the input prompt and returns the generated content (ideally structured, or text that can be parsed into "Field: Content" pairs).
9.  The FastAPI backend receives the LLM's response, processes/parses it if necessary to ensure a consistent structured format (e.g., JSON), and sends this structured data back to the Next.js frontend.
10. The Next.js frontend receives the structured data and displays the filled form information to the user in a clear and readable format.

## 4. Frontend (Next.js with Shadcn UI)

### 4.1. Responsibilities
-   Provide a clean, intuitive, and responsive user interface for:
    -   Inputting a list of form field names.
    -   Inputting the source content text.
    -   Initiating the form-filling process.
-   Manage client-side state (input values, loading indicators, results, errors).
-   Communicate securely and efficiently with the FastAPI backend.
-   Display the structured filled-form data returned by the backend.
-   Provide user feedback (e.g., loading states, success messages, error notifications).

### 4.2. Key Components & UI Framework
-   **UI Framework**: Shadcn UI will be used for building the user interface. This involves utilizing its library of accessible and stylable components (e.g., `Input`, `Textarea`, `Button`, `Card`, `Toast` for notifications) built on Radix UI and Tailwind CSS.
-   **Main Page (`app/page.tsx` or `pages/index.tsx`)**:
    -   Serves as the primary interface for the application.
    -   Manages overall page layout and orchestrates component interactions.
-   **Input Section**:
    -   A `Textarea` (from Shadcn UI) for users to paste field names (e.g., one field name per line).
    -   A `Textarea` for users to paste the source content.
-   **Controls**:
    -   A `Button` (from Shadcn UI) to submit the data to the backend for processing.
-   **Output Section**:
    -   A component (e.g., using `Card` and text elements from Shadcn UI) to display the returned "Field: Content" pairs in a structured and readable manner.
    -   Visual cues for loading states (e.g., a spinner or disabled button).
-   **State Management**:
    -   React `useState` and `useEffect` hooks for managing local component state (inputs, loading, results).
    -   For more complex global state or cross-component communication if needed, consider Zustand or React Context API.
-   **Styling**: Tailwind CSS (integrated with Shadcn UI) for utility-first styling.

### 4.3. API Communication
-   Utilize the `fetch` API or a lightweight library like `axios` for making asynchronous POST requests to the FastAPI backend.
-   Requests will send a JSON payload containing the field list, source content, and the default prompt.
-   Handle API responses, including successful data and potential error states.

## 5. Backend (FastAPI)

### 5.1. Responsibilities
-   Expose a secure API endpoint to receive field names, source content, and the prompt from the frontend.
-   Validate incoming request data.
-   Perform prompt engineering: construct a precise and effective prompt for the external LLM API by combining the user inputs and a predefined template.
-   Securely manage and use the API key for the external LLM service.
-   Make authenticated API calls to the external LLM service (e.g., DeepSeek API).
-   Receive and parse the LLM's response. Aim to transform it into a consistent JSON structure (e.g., `{"field_name": "filled_content",...}`) if not already in that format. [1, 2]
-   Return the structured data or appropriate error messages to the frontend.

### 5.2. API Endpoint
-   **`POST /api/v1/fill-form`**:
    -   **Request Body (JSON)**: Defined using Pydantic models for validation. [1]
        ```json
        {
          "fields": ["Field Name 1", "Field Name 2", "..."], // or "fields_text": "Field Name 1\nField Name 2..."
          "source_content": "The full text content...",
          "prompt_template_id": "default_v1" // Optional: to allow for different prompt strategies later
        }
        ```
    -   **Response Body (JSON) - Success**:
        ```json
        {
          "status": "success",
          "filled_data": {
            "Field Name 1": "Extracted content for Field 1",
            "Field Name 2": "Extracted content for Field 2"
          }
        }
        ```
    -   **Response Body (JSON) - Error**:
        ```json
        {
          "status": "error",
          "message": "A description of the error"
        }
        ```

### 5.3. LLM Integration (e.g., DeepSeek API)
-   Use an HTTP client library like `httpx` (asynchronous, recommended for FastAPI) or `requests` to interact with the external LLM API.
-   **API Key Management**: The API key for the LLM service must be stored securely, typically as an environment variable, and not hardcoded.
-   **Prompt Engineering**:
    -   A core responsibility. The backend will dynamically construct the prompt.
    -   Example prompt structure (to be adapted for the specific LLM):
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
-   **Response Parsing**:
    -   The primary goal is to get a JSON object directly from the LLM if the API supports constrained output or function calling that can produce JSON. [2]
    -   If the LLM returns a string representation of JSON, parse it.
    -   If the LLM returns unstructured text with field-value pairs, implement robust parsing logic (e.g., using regular expressions or further LLM calls for formatting, though the latter adds complexity and cost).

## 6. Data Models (Pydantic Schemas for FastAPI)

```python
# In app/models.py or app/schemas.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class FillFormRequest(BaseModel):
    fields: List[str] = Field(..., description="List of field names to be filled.")
    source_content: str = Field(..., description="The source text content for information extraction.")
    prompt_template_id: Optional[str] = Field("default_v1", description="Identifier for the prompt template to be used.")

class FilledDataResponse(BaseModel):
    field_name: str
    filled_value: str

class FillFormSuccessResponse(BaseModel):
    status: str = "success"
    filled_data: Dict[str, str] # Field name as key, filled content as value

class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
```

## 7. Deployment (Containerization)

-   **Docker**: Both the Next.js frontend and the FastAPI backend will be containerized using separate Dockerfiles.
-   **Frontend Dockerfile**: Standard Next.js multi-stage build (build stage + production server stage using Node.js).
-   **Backend Dockerfile**: Python base image, install dependencies from `requirements.txt`, run with Uvicorn.
-   **Docker Compose (`docker-compose.yml`)**:
    -   To orchestrate the frontend and backend services for local development and potentially for simple deployments.
    -   Define services for `frontend` and `backend`.
    -   Manage port mappings.
    -   Pass environment variables (especially `LLM_API_KEY`, `LLM_API_ENDPOINT` for the backend).
    -   Set up a common network for inter-service communication.

## 8. Security Considerations for Phase 1

-   **LLM API Key Security**:
    -   The API key for the external LLM service is highly sensitive.
    -   Store it as an environment variable in the backend container.
    -   Ensure it's not exposed in client-side code or version control.
-   **Input Validation**:
    -   The backend should validate inputs (e.g., length of content, number of fields) to prevent abuse or overly large requests to the LLM API, which can incur costs. Pydantic helps with this.
-   **Rate Limiting**:
    -   Consider implementing basic rate limiting on the FastAPI backend API endpoint to prevent abuse, especially if the service might be exposed publicly even in its MVP stage.
-   **PII Handling**:
    -   Users will be pasting content that may contain Personally Identifiable Information (PII).[3, 4]
    -   The data is sent to an external LLM API. It's crucial to understand and ideally inform the user about the data handling and privacy policies of the chosen LLM provider.
    -   For this MVP, the system itself does not store user data beyond the transient processing of a request.
-   **HTTPS**: Ensure all communication between the client, backend, and external LLM API uses HTTPS.
-   **CORS**: Configure Cross-Origin Resource Sharing (CORS) correctly on the FastAPI backend to allow requests from the Next.js frontend domain.

## 9. Future Considerations (Post Phase 1 MVP)

-   Transition to a privately hosted LLM (like the initially planned Qwen) for better control over data, cost, and customization.
-   Direct image upload and integrated OCR functionality.
-   Support for various input file types (PDF, DOCX).
-   Advanced prompt management and user-configurable prompts.
-   Saving and managing user profiles/common information for faster filling.
-   Integration with knowledge bases using RAG techniques. [5, 6, 7, 8]
-   Exporting filled data in various formats (e.g., filled PDF, CSV).
-   User authentication and session management.

This architecture aims to provide a clear path for developing the MVP, focusing on leveraging external services and established frameworks to achieve rapid progress.