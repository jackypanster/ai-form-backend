# AI 表单填写器 - 后端实现：Pydantic 模型与配置 (MVP)

## 1. 引言

本文档详细说明 AI 表单填写器后端服务中 Pydantic 模型和应用配置的具体实现。这些组件是服务稳定性和可维护性的基石，确保了数据的正确性和配置的灵活性。

* **Pydantic 模型**: 用于定义 API 请求/响应的数据结构、进行数据验证和序列化。
* **应用配置**: 用于管理敏感信息 (如 API 密钥) 和应用行为参数 (如允许的 CORS 源)。

我们将遵循先前在《AI 表单填写器 - 后端实现细节文档 (MVP)》中定义的项目结构。

## 2. Pydantic 数据模型 (`app/models/form_models.py`)

此文件将包含所有用于 API 请求和响应的数据模型。

### 2.1. `FillFormRequest` 模型

定义了 `/api/v1/fill-form` 端点预期的请求体结构。

```python
# app/models/form_models.py
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class FillFormRequest(BaseModel):
    """
    定义了表单填写请求的数据模型。
    """
    fields: List[str] = Field(
        ...,  # '...' 表示此字段是必需的
        min_length=1,
        description="需要从源内容中提取并填写的表单字段名称列表。",
        examples=[["姓名", "联系方式", "订单号"]]
    )
    source_content: str = Field(
        ...,
        min_length=1,
        description="包含待提取信息的源文本内容。",
        examples=["客户张三，电话13800138000，购买了产品A，订单号SN12345。"]
    )
    prompt_template_id: Optional[str] = Field(
        default="default_v1", # 提供一个默认值
        description="可选的提示模板ID，用于选择不同的提示工程策略。",
        examples=["default_v1", "financial_report_v2"]
    )

    # 可以添加模型级别的校验器 (validators) 如果需要更复杂的校验逻辑
    # from pydantic import validator
    # @validator('fields')
    # def check_fields_not_empty_strings(cls, value):
    #     for field_name in value:
    #         if not field_name.strip():
    #             raise ValueError("字段名称不能为空字符串。")
    #     return value
关键点:Field 函数用于为字段添加额外的元数据和验证规则 (如 min_length, description, examples)。Optional[str] 表示字段是可选的，并可以有默认值。注释和 description 有助于生成清晰的 API 文档 (FastAPI 会自动利用这些信息)。examples 字段在 OpenAPI 文档中非常有用，可以帮助前端或其他 API 消费者理解如何构造请求。2.2. FillFormSuccessResponse 模型定义了成功处理请求时的响应体结构。# app/models/form_models.py (继续)

class FillFormSuccessResponse(BaseModel):
    """
    定义了成功填写表单后的响应数据模型。
    """
    status: str = Field(default="success", description="操作状态，成功时为 'success'。")
    filled_data: Dict[str, str] = Field(
        ...,
        description="一个字典，键是表单字段名，值是LLM提取并填充的内容。",
        examples=[{"姓名": "张三", "联系方式": "13800138000", "订单号": "SN12345"}]
    )
2.3. ErrorResponse 模型定义了发生错误时的通用响应体结构。# app/models/form_models.py (继续)

class ErrorResponse(BaseModel):
    """
    定义了API发生错误时的标准响应数据模型。
    """
    status: str = Field(default="error", description="操作状态，发生错误时为 'error'。")
    message: str = Field(..., description="关于错误的描述性信息。", examples=["LLM 服务请求失败：连接超时。"])
这些模型将由 FastAPI 在请求处理流程中自动用于：请求体解析与验证: 将传入的 JSON 转换为 FillFormRequest 对象，并根据模型定义进行验证。如果验证失败，FastAPI 会自动返回 422 Unprocessable Entity 错误。响应体序列化与验证: 将端点返回的 Python 对象 (例如 FillFormSuccessResponse 实例) 转换为 JSON，并确保其符合模型定义。3. 应用配置 (app/core/config.py)此文件负责加载和管理应用配置，特别是从环境变量中读取。我们将使用 pydantic-settings。# app/core/config.py
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache # 用于缓存配置实例

class Settings(BaseSettings):
    """
    应用配置类，从环境变量加载配置项。
    """
    # LLM 服务相关配置
    LLM_API_KEY: str = Field(..., description="用于访问外部 LLM 服务的 API 密钥。")
    LLM_API_ENDPOINT: str = Field(
        "[https://api.deepseek.com/v1/chat/completions](https://api.deepseek.com/v1/chat/completions)", # 提供一个合理的默认值或使其必需
        description="外部 LLM 服务的 API 端点 URL。"
    )
    LLM_REQUEST_TIMEOUT: int = Field(default=30, description="调用 LLM API 的请求超时时间（秒）。")

    # 应用行为配置
    APP_NAME: str = Field(default="AI Form Filler Backend", description="应用名称。")
    API_V1_STR: str = Field(default="/api/v1", description="API 版本1的前缀。")
    LOG_LEVEL: str = Field(default="INFO", description="应用日志级别 (例如 DEBUG, INFO, WARNING, ERROR)。")

    # CORS 配置
    # pydantic-settings 可以自动将环境变量中的字符串（如 "http://localhost:3000,[http://127.0.0.1:3000](http://127.0.0.1:3000)"）
    # 转换为 List[str]，如果类型提示是 List[str] 且环境变量是逗号分隔的字符串。
    # 或者，环境变量可以是一个 JSON 字符串列表。
    CORS_ORIGINS: Union[str, List[str]] = Field(
        default=["http://localhost:3000"], # 开发环境默认值
        description="允许跨源请求的源列表 (逗号分隔的字符串或JSON字符串列表)。"
    )

    # Pydantic-settings 配置
    model_config = SettingsConfigDict(
        env_file=".env",                # 指定 .env 文件名
        env_file_encoding='utf-8',      # .env 文件编码
        extra='ignore',                 # 忽略 .env 文件中多余的变量
        case_sensitive=False            # 环境变量名不区分大小写 (通常环境变量是大写的)
    )

# 使用 lru_cache 装饰器确保 Settings 类只被实例化一次，配置只加载一次
@lru_cache
def get_settings() -> Settings:
    """
    返回应用配置的单例实例。
    """
    return Settings()

# 可以在这里添加一个小的测试，以验证配置是否能正确加载
# if __name__ == "__main__":
#     settings = get_settings()
#     print("成功加载配置:")
#     print(f"  LLM API Key: {'*' * len(settings.LLM_API_KEY) if settings.LLM_API_KEY else 'Not Set'}")
#     print(f"  LLM API Endpoint: {settings.LLM_API_ENDPOINT}")
#     print(f"  CORS Origins: {settings.CORS_ORIGINS}")
#     print(f"  Log Level: {settings.LOG_LEVEL}")

3.1. .env 文件示例在项目根目录下创建 .env 文件来存储敏感信息和环境特定配置 (此文件不应提交到版本控制系统)。# .env

# LLM 服务配置 (请替换为您的实际值)
LLM_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
LLM_API_ENDPOINT="[https://api.deepseek.com/v1/chat/completions](https://api.deepseek.com/v1/chat/completions)" # 或其他 LLM 服务商的端点
LLM_REQUEST_TIMEOUT=45

# 应用行为配置
APP_NAME="AI Form Filler - Development"
LOG_LEVEL="DEBUG" # 开发时使用 DEBUG，生产环境建议 INFO 或 WARNING

# CORS 配置
# 可以是逗号分隔的字符串
# CORS_ORIGINS="http://localhost:3000,http://localhost:3001,[https://your-frontend.com](https://your-frontend.com)"
# 或者是一个 JSON 字符串列表 (注意单引号和双引号的使用)
CORS_ORIGINS='["http://localhost:3000", "[http://127.0.0.1:3000](http://127.0.0.1:3000)", "[https://your-dev-frontend.example.com](https://your-dev-frontend.example.com)"]'
3.2. 配置的使用在应用的其他部分 (例如 API 端点或服务类中)，通过依赖注入来获取配置实例：from fastapi import Depends
from app.core.config import Settings, get_settings

# 在端点函数中:
# async def some_endpoint(settings: Settings = Depends(get_settings)):
#     api_key = settings.LLM_API_KEY
#     # ... 使用配置 ...
4. 小结通过精心设计的 Pydantic 模型，我们确保了 API 接口数据的健壮性和明确性。通过 pydantic-settings 管理的应用配置，我们实现了配置与代码的分离，提高了应用的灵活性和安全性。下一步将是实现 LLMService，