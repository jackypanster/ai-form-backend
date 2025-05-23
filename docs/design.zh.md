# AI 表单填写器 - 后端设计文档 (Phase 1 MVP)

## 1. 引言

本文档概述了 AI 表单填写器项目第一阶段 (MVP) 的后端设计。后端将采用 FastAPI (Python) 实现，作为 Next.js 前端与外部大语言模型 (LLM) API 之间的核心桥梁。其主要职责包括接收前端发送的表单字段信息和源文本内容，构建合适的提示 (Prompt) 并调用外部 LLM API，最后将 LLM 返回的结构化数据处理后返还给前端。

本设计明确指出，在 MVP 阶段，后端服务将是无状态的，并且暂时不考虑数据的持久化存储。

## 2. 后端指导原则与假设

* **快速 MVP 开发**: 优先保证核心功能的快速开发和交付。
* **无状态操作**: 后端服务将是无状态的，每个 API 请求都将被独立处理，不依赖于先前请求的会话数据。
* **外部 LLM API 集成**: 后端将负责管理与一个公开的外部 LLM API (例如 DeepSeek API 或类似服务) 的所有交互。
* **基于文本的数据处理**: 后端主要处理文本类型的输入 (如表单字段名称列表、源文本内容)，并致力于输出结构化的 JSON 数据。

## 3. Python 虚拟环境管理

* **工具**: `uv` 将被用作后端 Python 项目的虚拟环境管理工具。
* **用途**:
    * 创建和管理项目的独立 Python 虚拟环境。
    * 高效管理项目依赖包 (记录于 `requirements.txt` 或 `pyproject.toml` 中)。

## 4. 后端架构 (FastAPI)

### 4.1. 核心职责

* **API 端点提供**: 暴露一个安全的 API 端点，用于接收前端发送的表单字段名称、源文本内容以及可选的提示模板标识符。
* **输入验证**: 使用 Pydantic 模型对所有传入的请求数据进行严格验证，以确保数据完整性、类型正确性，并防止潜在的注入或格式错误。
* **提示工程 (Prompt Engineering)**: 根据接收到的用户输入（字段名、源内容）和预定义的提示模板，动态构建精确、高效的提示，以引导 LLM 生成期望的输出。
* **LLM API 编排**:
    * 安全管理和使用所选外部 LLM 服务的 API 密钥。
    * 使用异步 HTTP 客户端 (如 `httpx`) 向外部 LLM 服务发起认证后的 API 调用。
* **响应处理**:
    * 接收来自 LLM API 的响应。
    * 解析 LLM 的响应数据，并将其转换为统一的、结构化的 JSON 格式 (例如，一个将字段名映射到提取内容的字典)。这是确保前端能够一致地处理数据的关键步骤。
* **数据序列化与返回**: 将处理后的结构化 JSON 数据或适当的错误信息返回给前端。

### 4.2. API 端点定义

* **端点**: `POST /api/v1/fill-form`
* **请求体 (JSON)**:
    * 将通过 Pydantic 模型进行定义和验证。
    * 预期字段:
        * `fields: List[str]`：一个包含表单字段名称的字符串列表 (例如: `["姓名", "邮箱地址", "联系电话"]`)。或者，可以考虑 `fields_text: str`，允许用户粘贴多行文本，每行一个字段名。
        * `source_content: str`：一个包含用于信息提取的完整源文本内容的字符串。
        * `prompt_template_id: Optional[str]` (可选)：一个字符串标识符，用于指定使用的提示模板，默认为 `"default_v1"`。这为未来扩展不同提示策略提供了灵活性。
    ```json
    // 请求体示例
    {
      "fields": ["客户名称", "订单号", "产品名称"],
      "source_content": "张三的公司订购了100件A产品，订单号是SN20240513001。",
      "prompt_template_id": "default_v1"
    }
    ```
* **成功响应体 (JSON)**:
    * 一个包含处理状态和提取数据的 JSON 对象。
    ```json
    // 成功响应体示例
    {
      "status": "success",
      "filled_data": {
        "客户名称": "张三的公司",
        "订单号": "SN20240513001",
        "产品名称": "A产品"
      }
    }
    ```
* **错误响应体 (JSON)**:
    * 一个包含错误状态和描述性错误信息的 JSON 对象。
    ```json
    // 错误响应体示例
    {
      "status": "error",
      "message": "处理请求时发生错误：无法连接到 LLM API。"
    }
    ```

### 4.3. LLM 集成详情

* **HTTP 客户端**: 推荐使用 `httpx` 库。它支持异步操作，与 FastAPI 的异步特性完美契合，能提供更好的性能。
* **API 密钥管理**: LLM 服务的 API 密钥是敏感信息，必须作为环境变量 (例如 `LLM_API_KEY`) 存储，并在后端应用运行时读取。严禁将 API 密钥硬编码到代码中。
* **提示工程策略**:
    * 后端将动态构建提示。一个通用的模板结构可能如下（具体措辞需根据选用的 LLM API 进行调整优化）：
        ```text
        你是一个负责填写表单的AI助手。
        以下是表单中的字段：
        --- 字段开始 ---
        {用户提供的字段列表}
        --- 字段结束 ---

        这是用于提取信息的源内容：
        --- 内容开始 ---
        {用户提供的源内容}
        --- 内容结束 ---

        请从“内容”中提取相关信息，并填写“字段”列表中的每一个字段。
        请将输出结果格式化为一个 JSON 对象，其中每个键是“字段”列表中的字段名，对应的值是提取到的内容。
        如果某个字段的信息在“内容”中未找到，请使用空字符串 "" 或 "未找到" 作为其值。
        请确保输出的仅仅是这个 JSON 对象本身，不包含任何额外的解释或标记。
        ```
    * 此模板将使用 API 请求中提供的 `fields` 和 `source_content` 进行填充。
* **响应解析**:
    * 最理想的情况是 LLM API 支持通过参数配置直接返回 JSON 对象格式的输出。
    * 如果 LLM API 返回的是 JSON 字符串，后端需要将其解析为 Python 字典。
    * 如果 LLM 返回的是包含字段-值对的非结构化文本，则需要实现更健壮的解析逻辑 (例如，使用正则表达式，或在极端情况下，再次调用 LLM 进行格式化，但这会增加复杂性和成本)。MVP 阶段应优先争取 LLM 直接输出 JSON。

### 4.4. 数据模型 (Pydantic Schemas)

Pydantic 模型将用于请求体验证、响应体序列化以及内部数据结构定义。

* **`FillFormRequest(BaseModel)`**:
    * `fields: List[str] = Field(..., description="需要填写的字段名称列表。")`
    * `source_content: str = Field(..., description="用于信息提取的源文本内容。")`
    * `prompt_template_id: Optional[str] = Field("default_v1", description="用于指定提示模板的标识符。")`

* **`FillFormSuccessResponse(BaseModel)`**:
    * `status: str = "success"`
    * `filled_data: Dict[str, str]` (字段名称作为键，提取到的内容作为值)

* **`ErrorResponse(BaseModel)`**:
    * `status: str = "error"`
    * `message: str`

(这些 Pydantic 模型定义将直接在 FastAPI 应用的代码中使用。)

## 5. 部署考量 (后端)

* **容器化**: FastAPI 后端应用将被容器化，使用 Docker 进行构建和管理。
* **后端 Dockerfile**:
    * 基于合适的 Python 官方基础镜像 (例如 `python:3.10-slim`)。
    * 通过 `uv` 安装 `requirements.txt` 或 `pyproject.toml` 中定义的依赖。
    * 使用 ASGI 服务器 (如 Uvicorn) 运行 FastAPI 应用。
* **环境变量**:
    * `LLM_API_KEY`: (必需) 用于认证外部 LLM 服务的 API 密钥。
    * `LLM_API_ENDPOINT`: (必需) 外部 LLM 服务的 API 端点 URL。
    * 其他可选配置，如 `LOG_LEVEL`, `APP_PORT` 等。

## 6. 安全考量 (后端)

* **LLM API 密钥安全**: 严格通过环境变量管理 LLM API 密钥，避免在代码库或日志中泄露。
* **输入验证**: 利用 Pydantic 对所有输入数据进行严格验证，防止恶意输入、超长内容等可能导致服务异常或成本超支的请求。
* **速率限制**: 考虑在 `/api/v1/fill-form` 端点实施基本的速率限制策略，以防止滥用，特别是在 MVP 阶段 API 可能暴露于公网的情况下。可以使用如 `slowapi` 等库。
* **PII (个人可识别信息) 处理**:
    * 后端将瞬时处理用户提供的可能包含 PII 的内容。
    * 在此 MVP 阶段，后端本身**不会存储**任何用户数据或 PII。
    * 数据会被发送到外部 LLM API，因此理解并告知用户所选 LLM 提供商的数据处理和隐私政策至关重要。
* **HTTPS**: 在生产环境中，确保 FastAPI 应用通过 HTTPS 提供服务。这通常由部署在前端的反向代理 (如 Nginx) 或云服务提供商的负载均衡器处理。
* **CORS (跨源资源共享)**: 在 FastAPI 应用中正确配置 CORS 中间件，以明确允许来自 Next.js 前端域的请求。

## 7. 数据持久化

* 根据 MVP 的范围定义，此阶段的后端设计**不包括**任何形式的数据持久化 (例如，保存用户的表单填写请求、结果或用户账户信息)。后端将以无状态方式运行。

## 8. 未来考量 (MVP 后后端增强)

* 实现用户认证和授权机制。
* 开发更高级的提示管理功能，允许用户自定义或选择不同的提示模板。
* 如果业务需求发展，集成数据库以实现数据持久化。
* 探索集成和管理私有化部署的 LLM 的可能性，以增强数据控制、降低成本和实现模型定制。
* 增加对处理文件上传（如 PDF、图片中的表单）和集成 OCR 功能的支持。
