# AI 表单填写器 - 后端实现细节文档 (Phase 1 MVP)

## 1. 引言

本文档基于《AI 表单填写器 - 后端设计文档 (Phase 1 MVP)》，旨在进一步明确 FastAPI 后端服务的具体实现细节。它将涵盖项目结构、关键 Python 包的选择、API 端点的详细逻辑流程、错误处理机制、配置管理以及日志记录策略。目标是为后续的编码工作提供一个清晰、可操作的指南。

## 2. 项目结构 (建议)

为了保持代码的组织性和可维护性，建议采用如下的项目结构：

```
./
├── app/                             # 应用核心代码目录
│   ├── __init__.py
│   ├── main.py                      # FastAPI 应用实例和全局配置
│   ├── api/                         # API 路由模块
│   │   ├── __init__.py
│   │   └── v1/                      # API 版本 v1
│   │       ├── __init__.py
│   │       └── endpoints/           # 端点具体实现
│   │           ├── __init__.py
│   │           └── form_filler.py   # /fill-form 端点的逻辑
│   ├── core/                        # 核心业务逻辑与配置
│   │   ├── __init__.py
│   │   ├── config.py                # 应用配置 (环境变量读取等)
│   │   └── llm_services.py          # 与外部 LLM API 交互的服务
│   ├── models/                      # Pydantic 数据模型 (请求与响应)
│   │   ├── __init__.py
│   │   └── form_models.py
│   └── schemas/                     # (可选) 如果模型复杂，可分离 Pydantic schema
│       └── __init__.py
├── tests/                           # 单元测试和集成测试
│   ├── __init__.py
│   └── api/
│       └── v1/
│           └── test_form_filler.py
├── .env                             # 环境变量文件 (开发时，不提交到版本库)
├── .gitignore
├── Dockerfile                       # 后端 Docker 镜像构建文件
├── pyproject.toml                   # 项目元数据和依赖 (推荐使用 uv 管理)
├── README.md
└── scripts/                         # (可选) 辅助脚本 (如启动脚本)
```

**主要目录和文件说明:**

* **`app/main.py`**: 创建 FastAPI 应用实例，挂载 API 路由器，配置全局中间件 (如 CORS)。
* **`app/api/v1/endpoints/form_filler.py`**: 包含 `/api/v1/fill-form` 端点的具体实现函数。
* **`app/core/config.py`**: 使用 Pydantic 的 `BaseSettings` 来加载和管理环境变量，如 `LLM_API_KEY`, `LLM_API_ENDPOINT`。
* **`app/core/llm_services.py`**: 封装与外部 LLM API 通信的逻辑，包括构建请求、发送请求、处理原始响应。
* **`app/models/form_models.py`**: 定义 `FillFormRequest`, `FillFormSuccessResponse`, `ErrorResponse` 等 Pydantic 模型。

## 3. 关键 Python 包

* **`fastapi`**: Web 框架本身。
* **`uvicorn[standard]`**: ASGI 服务器，用于运行 FastAPI 应用。
* **`pydantic`**: 用于数据验证和设置管理。
* **`pydantic-settings`**: Pydantic V2 中用于设置管理的推荐方式 (替代旧版的 `pydantic.BaseSettings` 直接用法)。
* **`httpx`**: 异步 HTTP 客户端，用于与外部 LLM API 通信。
* **`python-dotenv`**: (开发时) 用于从 `.env` 文件加载环境变量。
* **`uv`**: 用于项目环境和依赖管理。

`pyproject.toml` (或 `requirements.txt` 若不使用 `poetry` 或 `pdm` 等构建工具) 中应包含这些依赖。

## 4. API 端点 (`/api/v1/fill-form`) 实现细节

文件: `app/api/v1/endpoints/form_filler.py`

```python
# 伪代码，仅作逻辑演示
from fastapi import APIRouter, HTTPException, Depends
from app.models.form_models import FillFormRequest, FillFormSuccessResponse, ErrorResponse
from app.core.llm_services import LLMService
from app.core.config import Settings, get_settings # 假设 Settings 和 get_settings 在 config.py 中

router = APIRouter()

@router.post(
    "/fill-form",
    response_model=FillFormSuccessResponse, # 成功时的响应模型
    responses={ # 定义可能的其他响应
        400: {"model": ErrorResponse, "description": "请求数据校验失败"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
        503: {"model": ErrorResponse, "description": "LLM 服务不可用或请求失败"}
    }
)
async def fill_form_endpoint(
    request_data: FillFormRequest,
    settings: Settings = Depends(get_settings) # 依赖注入配置
):
    # 1. (Pydantic 已自动完成) 输入验证: FastAPI 会自动使用 FillFormRequest 模型验证请求体。
    #    如果验证失败，FastAPI 会自动返回 422 Unprocessable Entity 错误。
    #    我们可以在这里添加更细致的业务逻辑校验，如果需要的话。

    # 2. 准备 LLM 服务
    llm_service = LLMService(api_key=settings.llm_api_key, api_endpoint=settings.llm_api_endpoint)

    # 3. 构建 Prompt
    #    从 request_data.fields 和 request_data.source_content 构建。
    #    可以考虑将 prompt 模板存储在配置或单独的模块中。
    #    示例：
    fields_str = "\n".join([f"- {field}" for field in request_data.fields])
    prompt = f"""你是一个负责填写表单的AI助手。
以下是表单中的字段：
--- 字段开始 ---
{fields_str}
--- 字段结束 ---

这是用于提取信息的源内容：
--- 内容开始 ---
{request_data.source_content}
--- 内容结束 ---

请从"内容"中提取相关信息，并填写"字段"列表中的每一个字段。
请将输出结果格式化为一个 JSON 对象，其中每个键是"字段"列表中的字段名，对应的值是提取到的内容。
如果某个字段的信息在"内容"中未找到，请使用空字符串 "" 或 "未找到" 作为其值。
请确保输出的仅仅是这个 JSON 对象本身，不包含任何额外的解释或标记。
"""
    #    如果 request_data.prompt_template_id 有值，则可以根据 ID 选择不同的模板。

    # 4. 调用 LLM 服务
    try:
        llm_response_text = await llm_service.get_completion(prompt)
    except Exception as e: # 更具体的异常捕获，例如 httpx.RequestError
        # 日志记录错误详情
        # logger.error(f"LLM service request failed: {e}")
        raise HTTPException(status_code=503, detail=f"LLM 服务请求失败: {str(e)}")

    # 5. 解析 LLM 响应
    #    目标是将 llm_response_text (通常是字符串) 解析为 Dict[str, str]
    try:
        # 假设 LLM 返回的是一个 JSON 字符串
        import json
        filled_data = json.loads(llm_response_text)
        # (可选) 进一步验证 filled_data 的结构是否符合预期
        if not isinstance(filled_data, dict):
            raise ValueError("LLM 返回的不是一个有效的 JSON 对象。")
        # (可选) 检查返回的字段是否与请求的字段匹配或部分匹配

    except (json.JSONDecodeError, ValueError) as e:
        # 日志记录解析错误
        # logger.error(f"Failed to parse LLM response: {e}. Response was: {llm_response_text}")
        raise HTTPException(status_code=500, detail=f"解析 LLM 响应失败: {str(e)}")

    # 6. 返回成功响应
    return FillFormSuccessResponse(filled_data=filled_data)

5. LLMService 实现细节 (app/core/llm_services.py)# 伪代码，仅作逻辑演示
import httpx
import json

class LLMService:
    def __init__(self, api_key: str, api_endpoint: str):
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.timeout = 30  # 设置请求超时时间 (秒)

    async def get_completion(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}", # 根据实际 LLM API 的认证方式调整
            "Content-Type": "application/json"
        }
        # 根据 LLM API 的具体要求构建请求体
        payload = {
            "model": "deepseek-coder", # 示例模型，需替换为实际模型
            "prompt": prompt,
            "max_tokens": 1500, # 限制生成长度
            "temperature": 0.1, # 控制生成文本的随机性，低一些更稳定
            # 其他 LLM API 可能需要的参数，例如 stream, top_p 等
            # "response_format": {"type": "json_object"} # 如果 LLM 支持，请求 JSON 输出
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.api_endpoint, headers=headers, json=payload)
                response.raise_for_status() # 如果 HTTP 状态码是 4xx 或 5xx，则抛出异常
                
                # 解析响应，不同 LLM API 返回结构可能不同
                # 假设返回的 JSON 中有一个 'choices' 列表，其中包含 'text' 或 'message.content'
                response_data = response.json()
                
                # 示例：DeepSeek API 可能的返回结构 (需要查阅具体文档)
                # if response_data.get("choices") and len(response_data["choices"]) > 0:
                #    content = response_data["choices"][0].get("message", {}).get("content")
                #    if content:
                #        return content
                #    text_content = response_data["choices"][0].get("text")
                #    if text_content:
                #        return text_content
                # raise ValueError("LLM API 响应中未找到预期的文本内容。")

                # **重要**: 这里的响应解析逻辑需要根据你选择的 LLM API 文档来精确实现。
                # 目标是提取出包含表单填充结果的文本（最好是 JSON 字符串）。
                # 假设 LLM 直接返回了包含 JSON 的文本
                # 例如，如果 LLM 返回的 JSON 直接在 'data' 字段或根对象
                # return response.text # 或者 response_data.get("generated_text") 等

                # 临时的简化处理，假设 LLM 直接返回了我们需要的 JSON 字符串
                # 实际项目中，这里需要严格按照 LLM API 文档处理
                # 假设 LLM 返回的 JSON 在 'choices'[0]['message']['content']
                if "choices" in response_data and response_data["choices"]:
                    message = response_data["choices"][0].get("message", {})
                    if "content" in message:
                        return message["content"]
                raise ValueError("从 LLM 响应中未能提取有效内容。")


            except httpx.HTTPStatusError as e:
                # logger.error(f"LLM API request failed with status {e.response.status_code}: {e.response.text}")
                raise  # 重新抛出，由上层处理
            except httpx.RequestError as e:
                # logger.error(f"LLM API request failed due to network issue or timeout: {e}")
                raise  # 重新抛出
            except (json.JSONDecodeError, KeyError, ValueError) as e: # 解析 LLM 返回的 JSON 可能出错
                # logger.error(f"Failed to parse LLM API JSON response: {e}. Response: {response.text if 'response' in locals() else 'No response object'}")
                raise ValueError(f"解析 LLM API 响应失败: {str(e)}") # 转换为 ValueError 或自定义异常

6. 配置管理 (app/core/config.py)使用 pydantic-settings 来管理配置。# 伪代码，仅作逻辑演示
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    llm_api_key: str
    llm_api_endpoint: str
    # 可以添加其他配置，如 LOG_LEVEL, APP_HOST, APP_PORT
    app_name: str = "AI Form Filler Backend"
    cors_origins: list[str] = ["http://localhost:3000"] # 前端地址

    # model_config 用于配置 Pydantic 如何加载设置
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-f8', extra='ignore')

@lru_cache() # 缓存配置实例，避免重复加载
def get_settings() -> Settings:
    return Settings()
在 .env 文件中 (开发环境):LLM_API_KEY="your_actual_llm_api_key"
LLM_API_ENDPOINT="[https://api.deepseek.com/v1/chat/completions](https://api.deepseek.com/v1/chat/completions)" # 示例，替换为实际端点
CORS_ORIGINS='["http://localhost:3000", "[https://your-frontend-domain.com](https://your-frontend-domain.com)"]' # JSON 格式的列表
7. 错误处理与 HTTPExceptionsPydantic 验证错误: FastAPI 自动处理，返回 422 Unprocessable Entity。业务逻辑错误/自定义校验:如果请求数据通过了 Pydantic 验证，但在业务逻辑层面不合法 (例如，字段列表为空但源内容也为空)，可以主动抛出 HTTPException(status_code=400, detail="错误描述")。LLM 服务调用失败:网络问题、超时、LLM API 返回错误状态码 (4xx, 5xx) 等，应捕获 httpx 的相关异常，记录日志，并向上抛出或转换为 HTTPException(status_code=503, detail="LLM 服务暂时不可用或请求失败")。LLM 响应解析失败:如果 LLM 返回的不是预期的 JSON 格式或无法解析，记录日志，并返回 HTTPException(status_code=500, detail="解析 LLM 响应失败")。其他内部服务器错误:使用全局异常处理器 (FastAPI Middleware) 来捕获未被特定处理的异常，记录日志，并返回通用的 HTTPException(status_code=500, detail="服务器内部错误")。8. 日志记录使用 Python 内置的 logging 模块。在 app/main.py 中配置日志级别、格式和处理器 (例如，输出到控制台，未来可以输出到文件或日志服务)。关键日志点:应用启动和关闭。接收到的请求 (可以记录部分关键信息，注意不要记录敏感数据如完整的 source_content，除非明确需要且已脱敏)。调用外部 LLM API 的请求参数 (同样注意敏感信息)。外部 LLM API 的响应 (原始响应或关键部分)。所有捕获到的异常及其堆栈信息。成功处理请求并返回结果。示例日志配置 (简化版，在 main.py 或单独的日志配置文件中):import logging

logging.basicConfig(
    level=logging.INFO, # 从配置读取，例如 settings.log_level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler() # 输出到控制台
    ]
)
logger = logging.getLogger(__name__)

# 在其他模块中获取 logger:
# import logging
# logger = logging.getLogger(__name__)
# logger.info("This is an info message.")
9. CORS (跨源资源共享)在 app/main.py 中配置 FastAPI 的 CORSMiddleware。# 伪代码，仅作逻辑演示
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings

settings = get_settings() # 加载配置

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins, # 从配置中读取允许的源
    allow_credentials=True,
    allow_methods=["*"], # 允许所有标准方法
    allow_headers=["*"], # 允许所有请求头
)

# ... 挂载 API 路由 ...
# from app.api.v1 import api_router as api_v1_router
# app.include_router(api_v1_router, prefix="/api/v1")
10. uv 环境与依赖管理安装 uv:pip install uv
创建虚拟环境:uv venv .venv  # 在项目根目录创建名为 .venv 的虚拟环境
source .venv/bin/activate # 激活环境 (Linux/macOS)
# .venv\Scripts\activate (Windows)
安装依赖:在 pyproject.toml 中定义依赖，然后运行：uv pip install -r requirements.txt # 如果使用 requirements.txt
# 或者，如果 pyproject.toml 中有 [project.dependencies]
uv pip install . # 安装当前项目的依赖
uv pip install fastapi uvicorn[standard] pydantic pydantic-settings httpx python-dotenv
生成 requirements.txt (如果需要):uv pip freeze > requirements.txt