# AI 表单填写器 - 后端实现：API 端点 (MVP)

## 1. 引言

本文档详细说明 AI 表单填写器后端服务中 API 端点 (`/api/v1/fill-form`) 的具体实现。此端点是前端与后端服务交互的入口，负责接收用户输入的表单字段和源文本，调用 `LLMService` 进行处理，并最终将结构化的表单填写结果或错误信息返回给前端。

此实现将整合先前文档中定义的 Pydantic 模型 (`FillFormRequest`, `FillFormSuccessResponse`, `ErrorResponse`)、应用配置 (`Settings`) 以及 `LLMService`。

代码将位于项目结构中的 `app/api/v1/endpoints/form_filler.py`。

## 2. API 路由和端点设置

### 2.1. API 路由器 (`app/api/v1/api.py` - 如果采用模块化路由)

为了更好地组织路由，特别是在未来可能有更多端点时，通常会为每个 API 版本创建一个主路由器，然后将各个功能模块的子路由器包含进去。

```python
# app/api/v1/api.py
from fastapi import APIRouter
from app.api.v1.endpoints import form_filler

# 创建 v1 版本的主 API 路由器
api_router_v1 = APIRouter()

# 包含 form_filler 模块中定义的路由
api_router_v1.include_router(form_filler.router, prefix="/forms", tags=["Form Filling"])

# 可以在这里包含其他 v1 版本的端点模块...
```

### 2.2. 在主应用中挂载 API 路由器 (app/main.py)

主 FastAPI 应用实例需要挂载上面定义的版本化路由器。

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import get_settings, Settings
from app.api.v1.api import api_router_v1 # 引入 v1 版本的 API 路由器

# 初始化日志配置 (可以更复杂，例如从配置加载)
logging.basicConfig(level=get_settings().LOG_LEVEL.upper(), format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 获取配置实例
settings: Settings = get_settings()

# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" # API 文档路径
)

# 配置 CORS 中间件
if settings.CORS_ORIGINS:
    origins = []
    if isinstance(settings.CORS_ORIGINS, str):
        origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]
    elif isinstance(settings.CORS_ORIGINS, list):
        origins = settings.CORS_ORIGINS
    
    if origins: # 确保 origins 列表不为空
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"], # 允许所有标准方法
            allow_headers=["*"], # 允许所有请求头
        )
        logger.info(f"CORS 中间件已配置，允许的源: {origins}")
    else:
        logger.warning("CORS_ORIGINS 配置为空或格式不正确，未配置 CORS 中间件。")


# 挂载 v1 API 路由
app.include_router(api_router_v1, prefix=settings.API_V1_STR)

@app.on_event("startup")
async def startup_event():
    logger.info(f"应用 '{settings.APP_NAME}' 启动...")
    logger.info(f"LLM API Endpoint: {settings.LLM_API_ENDPOINT}")
    logger.info(f"LLM API Key Loaded: {'Yes' if settings.LLM_API_KEY else 'No'}")


@app.get("/", tags=["Root"])
async def read_root():
    """
    根路径，返回应用基本信息。
    """
    return {"message": f"欢迎使用 {settings.APP_NAME}!"}

# 其他全局配置或事件处理器...

```


## 3. /fill-form 端点实现 (app/api/v1/endpoints/form_filler.py)
此文件包含核心的表单填写逻辑。

```python
# app/api/v1/endpoints/form_filler.py
import logging
from fastapi import APIRouter, HTTPException, Depends, Body

from app.models.form_models import FillFormRequest, FillFormSuccessResponse, ErrorResponse
from app.core.config import Settings, get_settings
from app.core.llm_services import (
    LLMService,
    LLMServiceError,
    LLMAPIError,
    LLMConnectionError,
    LLMResponseParseError
)

# 获取日志记录器实例
logger = logging.getLogger(__name__)

# 创建此端点模块的路由器
router = APIRouter()

# 依赖项：获取 LLMService 实例
# 这种方式可以使得 LLMService 的创建和配置更灵活，例如未来可以加入缓存或连接池
async def get_llm_service(settings: Settings = Depends(get_settings)) -> LLMService:
    """
    依赖项函数，用于创建和返回 LLMService 的实例。
    """
    return LLMService(settings)


def construct_prompt(fields: list[str], source_content: str, template_id: str) -> str:
    """
    根据输入数据和模板ID构建发送给 LLM 的提示。
    未来可以从配置或数据库加载不同的提示模板。
    """
    # MVP 阶段，我们使用一个硬编码的默认模板 (template_id 暂时未使用)
    # TODO: 根据 template_id 实现不同的提示模板加载逻辑
    
    fields_str = "\n".join([f"- {field}" for field in fields])
    
    # 核心提示内容，要求 LLM 返回 JSON 对象
    prompt = f"""你是一个AI助手，负责从提供的"源内容"中提取信息来填写给定的"表单字段"。
请严格按照以下要求操作：
1.  仔细阅读"源内容"和"表单字段"列表。
2.  对于"表单字段"中的每一个字段，从"源内容"中找到最相关的信息并填写。
3.  如果某个字段在"源内容"中找不到对应信息，请将该字段的值设为 \"未找到\" 或空字符串 \"\"。
4.  **输出格式要求**：请将结果组织成一个单一的、结构化的 JSON 对象。该 JSON 对象的键必须是"表单字段"列表中的字段名，值是对应的提取内容。
5.  **确保输出的只有这个 JSON 对象本身**，不要添加任何额外的解释、介绍、Markdown标记或其他非 JSON 内容。

--- 表单字段开始 ---
{fields_str}
--- 表单字段结束 ---

--- 源内容开始 ---
{source_content}
--- 源内容结束 ---

请生成填充后的 JSON 对象：
"""
    logger.debug(f"构建的提示 (模板ID: {template_id}):\n{prompt}")
    return prompt


@router.post(
    "/fill", # 端点路径相对于其父路由器的 prefix (即 /api/v1/forms/fill)
    response_model=FillFormSuccessResponse,
    summary="填写表单字段",
    description="接收表单字段列表和源文本内容，使用 LLM 提取信息并返回结构化的填充结果。",
    responses={
        400: {"model": ErrorResponse, "description": "无效的请求数据 (例如，字段列表为空)"},
        422: {"model": ErrorResponse, "description": "请求体验证失败 (由 FastAPI 自动处理)"},
        500: {"model": ErrorResponse, "description": "服务器内部错误或解析 LLM 响应失败"},
        503: {"model": ErrorResponse, "description": "LLM 服务不可用或请求失败"}
    }
)
async def fill_form_fields(
    # 使用 Body(..., embed=True) 可以让请求体在 OpenAPI 文档中作为一个命名对象显示，
    # 但对于单个模型作为请求体，通常不需要 embed=True。
    # request_data: FillFormRequest = Body(..., embed=True, alias="formData"), 
    request_data: FillFormRequest,
    llm_service: LLMService = Depends(get_llm_service) # 依赖注入 LLMService
):
    """
    处理表单填写请求的核心逻辑。
    """
    logger.info(f"收到表单填写请求: {len(request_data.fields)} 个字段, prompt_template_id='{request_data.prompt_template_id}'")
    
    # 1. (可选) 额外的业务逻辑校验 (Pydantic 已完成基础类型和结构校验)
    if not request_data.fields:
        logger.warning("请求中的字段列表为空。")
        raise HTTPException(status_code=400, detail="请求中的字段列表 (fields) 不能为空。")
    if not request_data.source_content.strip():
        logger.warning("请求中的源内容为空。")
        raise HTTPException(status_code=400, detail="请求中的源内容 (source_content) 不能为空。")

    # 2. 构建 Prompt
    try:
        prompt_text = construct_prompt(
            fields=request_data.fields,
            source_content=request_data.source_content,
            template_id=request_data.prompt_template_id
        )
    except Exception as e: # 更具体的提示构建错误
        logger.error(f"构建提示时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"构建提示时发生内部错误: {str(e)}")

    # 3. 调用 LLM 服务
    try:
        logger.info("正在调用 LLM 服务进行信息提取...")
        filled_data_dict = await llm_service.get_structured_completion(
            prompt=prompt_text,
            fields_to_extract=request_data.fields # 传递字段列表用于可能的后处理或验证
        )
        logger.info(f"LLM 服务成功返回结构化数据，包含 {len(filled_data_dict)} 个字段。")

    except LLMConnectionError as e:
        logger.error(f"LLM 连接错误: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"无法连接到 LLM 服务: {str(e)}")
    except LLMAPIError as e:
        logger.error(f"LLM API 错误 (状态码 {e.status_code}): {e.error_message}", exc_info=True)
        # 可以根据 e.status_code 决定是否返回 503 或其他特定错误码
        detail_message = f"LLM API 返回错误 (状态码 {e.status_code})。"
        if e.status_code == 401: # Unauthorized
            detail_message = "LLM API 认证失败，请检查 API 密钥。"
        elif e.status_code == 429: # Too Many Requests
            detail_message = "LLM API 请求过于频繁，请稍后再试。"
        # 对于其他 4xx 错误，可能表示请求内容有问题
        # 对于 5xx 错误，表示 LLM 服务端问题
        raise HTTPException(status_code=503, detail=detail_message) # 通常归为服务不可用
    except LLMResponseParseError as e:
        logger.error(f"解析 LLM 响应失败: {e}. Prompt: '{prompt_text[:500]}...'", exc_info=True) # 日志中记录部分prompt
        raise HTTPException(status_code=500, detail=f"解析 LLM 响应失败: {str(e)}")
    except LLMServiceError as e: # 捕获其他 LLMService 自定义错误
        logger.error(f"LLM 服务发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"LLM 服务发生错误: {str(e)}")
    except Exception as e: # 捕获其他意外错误
        logger.error(f"处理表单填写请求时发生未知内部错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理请求时发生未知内部错误。")

    # 4. 返回成功响应
    logger.info(f"成功处理表单填写请求。返回数据: {filled_data_dict}")
    return FillFormSuccessResponse(filled_data=filled_data_dict)

```

## 4. 关键逻辑说明

### 4.1. 依赖注入 (Depends)
get_settings: 用于获取应用配置 (Settings 实例)。FastAPI 会自动调用此函数并将其结果注入到需要它的地方。
get_llm_service: 这是一个自定义的依赖项，用于创建和提供 LLMService 的实例。这样做的好处是，如果 LLMService 的初始化变得更复杂（例如，需要连接池、缓存等），这些逻辑可以封装在 get_llm_service 中，而端点函数保持简洁。

### 4.2. Prompt 构建 (construct_prompt)
此函数负责根据用户输入（字段、源内容）和可选的模板ID来动态生成发送给 LLM 的提示。核心目标：清晰地指示 LLM 的任务，并强烈要求其输出为 JSON 格式。这是获取结构化数据的关键。在 MVP 阶段，我们使用了一个硬编码的模板。未来可以扩展为从配置文件、数据库或特定模板管理系统中加载不同的提示模板，以适应不同的表单类型或提取需求。

### 4.3. 错误处理
Pydantic 验证错误: FastAPI 自动处理请求体验证。如果 FillFormRequest 模型验证失败，FastAPI 会返回 422 Unprocessable Entity 错误，其中包含详细的错误信息。
业务逻辑校验: 在 Pydantic 验证之后，可以添加额外的业务规则校验（例如，字段列表不能为空）。如果校验失败，则主动抛出 HTTPException (例如，状态码 400)。
LLMService 错误:
LLMService 中定义的各种自定义异常 (LLMConnectionError, LLMAPIError, LLMResponseParseError) 会在端点中被捕获。根据捕获到的具体错误类型，将其映射为合适的 HTTPException，并返回给客户端相应的 HTTP 状态码和错误信息。
LLMConnectionError 通常映射为 503 Service Unavailable。
LLMAPIError 可以根据其内部的 status_code 进一步细化，但通常也归为 503，因为这表示依赖的外部服务有问题。特定的状态码如 401（认证失败）或 429（速率限制）可以提供更具体的错误信息。
LLMResponseParseError 通常映射为 500 Internal Server Error，因为它表示后端在处理有效（或无效）的 LLM 响应时出现问题。
未知错误: 使用通用的 except Exception 来捕获任何未预料到的错误，记录详细日志，并返回 500 Internal Server Error。

### 4.4. 日志记录
在端点的关键步骤（接收请求、构建提示、调用服务、处理错误、返回响应）都添加了日志记录。使用 logger.error(..., exc_info=True)可以在日志中记录完整的异常堆栈信息，非常有助于调试。注意在记录日志时避免泄露过多敏感信息，例如完整的源文本内容或 API 密钥。

## 5. 小结
API 端点是连接前端请求和后端核心逻辑的桥梁。通过清晰的职责分离（配置、服务、模型、端点）、健壮的错误处理和详细的日志记录，我们可以构建一个可靠且易于维护的后端 API。至此，后端 MVP 的核心组件（模型、配置、服务、端点）的实现细节文档已经完成。