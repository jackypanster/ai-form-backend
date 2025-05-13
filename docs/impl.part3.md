# AI 表单填写器 - 后端实现：LLMService (MVP)

## 1. 引言

本文档详细阐述 AI 表单填写器后端服务中 `LLMService` 类的具体实现。`LLMService` 负责封装与外部大语言模型 (LLM) API 的所有通信细节，包括构建请求、发送请求、处理响应以及错误管理。其目的是将 LLM 交互逻辑与 API 端点逻辑解耦，提高代码的模块化和可测试性。

此服务将使用在《后端实现：Pydantic 模型与配置》文档中定义的 `Settings` 对象来获取 LLM API 密钥、端点 URL 和请求超时等配置。

我们将遵循先前在《AI 表单填写器 - 后端实现细节文档 (MVP)》中定义的项目结构，将此服务实现于 `app/core/llm_services.py` 文件中。

## 2. `LLMService` 类定义 (`app/core/llm_services.py`)

`LLMService` 类将包含与外部 LLM API 交互所需的方法和属性。

```python
# app/core/llm_services.py
import httpx # 异步 HTTP 客户端
import json # 用于处理 JSON 数据
import logging # 用于日志记录
from typing import Dict, Any

from app.core.config import Settings # 引入应用配置

# 获取日志记录器实例
logger = logging.getLogger(__name__)

class LLMServiceError(Exception):
    """LLMService 发生的特定错误基类。"""
    pass

class LLMAPIError(LLMServiceError):
    """当 LLM API 返回错误或非预期响应时抛出。"""
    def __init__(self, status_code: int, error_message: str):
        self.status_code = status_code
        self.error_message = error_message
        super().__init__(f"LLM API Error {status_code}: {error_message}")

class LLMConnectionError(LLMServiceError):
    """当连接到 LLM API 失败时抛出 (例如网络问题、超时)。"""
    pass

class LLMResponseParseError(LLMServiceError):
    """当解析 LLM API 响应失败时抛出。"""
    pass


class LLMService:
    """
    封装与外部大语言模型 (LLM) API 交互的服务类。
    """

    def __init__(self, settings: Settings):
        """
        初始化 LLMService。

        Args:
            settings: 应用配置对象，包含 LLM API 密钥、端点和超时等。
        """
        self.api_key: str = settings.LLM_API_KEY
        self.api_endpoint: str = settings.LLM_API_ENDPOINT
        self.request_timeout: int = settings.LLM_REQUEST_TIMEOUT
        # 根据具体的 LLM API 文档，可能还需要配置其他参数，如默认模型名称
        self.default_model: str = "deepseek-chat" # 示例，请根据实际使用的模型调整

        if not self.api_key:
            logger.error("LLM_API_KEY 未配置。LLMService 可能无法正常工作。")
            # 根据实际需求，这里也可以直接抛出异常
            # raise ValueError("LLM_API_KEY is not configured.")
        if not self.api_endpoint:
            logger.error("LLM_API_ENDPOINT 未配置。LLMService 可能无法正常工作。")
            # raise ValueError("LLM_API_ENDPOINT is not configured.")

    async def _make_llm_api_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        一个私有辅助方法，用于向 LLM API 发送实际的 HTTP 请求。

        Args:
            payload: 发送给 LLM API 的请求体。

        Returns:
            LLM API 返回的 JSON 响应体 (已解析为字典)。

        Raises:
            LLMConnectionError: 如果发生连接错误或超时。
            LLMAPIError: 如果 LLM API 返回 HTTP 错误状态码。
            LLMResponseParseError: 如果响应体不是有效的 JSON。
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            try:
                logger.debug(f"向 LLM API 发送请求: 端点='{self.api_endpoint}', 载荷='{payload}'")
                response = await client.post(
                    self.api_endpoint, headers=headers, json=payload
                )
                response.raise_for_status()  # 如果状态码是 4xx 或 5xx，则抛出 httpx.HTTPStatusError

                # 尝试解析 JSON 响应
                try:
                    response_data = response.json()
                    logger.debug(f"从 LLM API 收到响应: 数据='{response_data}'")
                    return response_data
                except json.JSONDecodeError as e:
                    logger.error(f"解析 LLM API 响应 JSON 失败: {e}. 响应文本: {response.text}")
                    raise LLMResponseParseError(f"无法解析 LLM 响应: {e}")

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"LLM API 请求失败，状态码: {e.response.status_code}. 响应: {e.response.text}"
                )
                raise LLMAPIError(
                    status_code=e.response.status_code, error_message=e.response.text
                )
            except httpx.TimeoutException as e:
                logger.error(f"LLM API 请求超时: {e}")
                raise LLMConnectionError(f"LLM API 请求超时: {e}")
            except httpx.RequestError as e: # 其他 httpx 请求相关错误 (如网络问题)
                logger.error(f"LLM API 请求发生错误: {e}")
                raise LLMConnectionError(f"LLM API 请求错误: {e}")

    async def get_structured_completion(self, prompt: str, fields_to_extract: list[str]) -> Dict[str, str]:
        """
        获取 LLM 的结构化补全，并尝试解析为特定格式 (字段名: 提取内容)。

        Args:
            prompt: 发送给 LLM 的完整提示。
            fields_to_extract: 提示 LLM 需要关注并提取的字段列表，用于辅助验证输出。

        Returns:
            一个字典，其中键是字段名，值是 LLM 提取的内容。

        Raises:
            LLMServiceError 的子类，如果发生错误。
            LLMResponseParseError: 如果 LLM 的输出不是预期的 JSON 格式或无法解析。
        """
        # 根据 LLM API 的具体要求构建请求体
        # 不同的 LLM (如 OpenAI, Anthropic, DeepSeek) 有不同的请求体结构
        # 以下是一个通用的示例，需要根据实际使用的 DeepSeek API 文档进行调整
        payload = {
            "model": self.default_model, # 使用在 __init__ 中配置的默认模型
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 2048,  # 限制生成长度，根据需要调整
            "temperature": 0.2,  # 控制生成文本的随机性，较低的值使输出更具确定性
            # "response_format": {"type": "json_object"}, # 如果 LLM 支持，强烈建议请求 JSON 输出
            # 其他特定于 LLM 的参数，例如 stream, top_p 等
        }
        
        # 检查 LLM API 是否支持强制 JSON 输出，如果支持，应在 payload 中设置
        # 例如，某些模型支持 "tool_choice" 或 "response_format" 来强制 JSON
        # if self.default_model supports json_mode:
        #    payload["response_format"] = {"type": "json_object"}

        response_data = await self._make_llm_api_request(payload)

        # 解析 LLM 响应以提取生成的文本
        # 这部分高度依赖于 LLM API 的响应结构
        try:
            # 示例：假设 DeepSeek API 的响应结构 (请查阅官方文档确认)
            if response_data.get("choices") and len(response_data["choices"]) > 0:
                message = response_data["choices"][0].get("message", {})
                llm_output_text = message.get("content")
                if llm_output_text:
                    logger.info("成功从 LLM 获取文本输出。")
                    # 尝试将 LLM 输出的文本解析为 JSON 对象
                    try:
                        extracted_data = json.loads(llm_output_text)
                        if not isinstance(extracted_data, dict):
                            logger.warning(f"LLM 输出的 JSON 不是一个字典: {llm_output_text}")
                            raise LLMResponseParseError("LLM 输出的 JSON 不是一个有效的字典对象。")
                        
                        # (可选) 验证提取的数据是否包含所有请求的字段
                        # for field_name in fields_to_extract:
                        #     if field_name not in extracted_data:
                        #         logger.warning(f"LLM 输出中缺少字段: {field_name}")
                        #         # 可以选择填充默认值或抛出错误
                        #         extracted_data[field_name] = "未找到" # 或 ""

                        return extracted_data
                    except json.JSONDecodeError as e:
                        logger.error(f"无法将 LLM 输出解析为 JSON: {e}. LLM 输出: '{llm_output_text}'")
                        raise LLMResponseParseError(f"LLM 输出不是有效的 JSON 格式: {e}")
                else:
                    logger.error("LLM API 响应中未找到 'content' 字段。")
                    raise LLMResponseParseError("LLM API 响应中缺少预期的 'content' 字段。")
            else:
                logger.error(f"LLM API 响应结构不符合预期: {response_data}")
                raise LLMResponseParseError("LLM API 响应结构不符合预期。")
        except KeyError as e:
            logger.error(f"解析 LLM 响应时发生 KeyError: {e}. 响应数据: {response_data}")
            raise LLMResponseParseError(f"解析 LLM 响应时缺少键: {e}")

3. LLMService 初始化与配置使用LLMService 的实例将在需要与 LLM 交互的地方创建，通常是通过依赖注入的方式，并将从 app.core.config.get_settings() 获取的 Settings 对象传递给构造函数。# 在 API 端点或其他服务中如何使用:
# from fastapi import Depends
# from app.core.config import Settings, get_settings
# from app.core.llm_services import LLMService, LLMServiceError

# async def some_api_endpoint(
#     request_data: SomeRequestModel,
#     settings: Settings = Depends(get_settings)
# ):
#     llm_service = LLMService(settings) # 创建 LLMService 实例
#     try:
#         prompt = f"这是一个发送给 LLM 的提示: {request_data.some_input}"
#         fields_list = ["field1", "field2"] # 假设我们期望提取这些字段
#         filled_data = await llm_service.get_structured_completion(prompt, fields_list)
#         # ... 处理 filled_data ...
#         return {"status": "success", "data": filled_data}
#     except LLMServiceError as e:
#         logger.error(f"与 LLM 服务交互时发生错误: {e}")
#         # 根据错误类型返回不同的 HTTP 错误给客户端
#         if isinstance(e, LLMConnectionError):
#             raise HTTPException(status_code=503, detail=f"无法连接到 LLM 服务: {str(e)}")
#         elif isinstance(e, LLMAPIError):
#             raise HTTPException(status_code=e.status_code, detail=f"LLM API 错误: {e.error_message}")
#         elif isinstance(e, LLMResponseParseError):
#             raise HTTPException(status_code=500, detail=f"解析 LLM 响应失败: {str(e)}")
#         else:
#             raise HTTPException(status_code=500, detail=f"处理 LLM 请求时发生未知错误: {str(e)}")
4. 核心方法 get_structured_completion 详解参数:prompt: str: 这是经过精心构造的、发送给 LLM 的完整提示文本。提示的质量直接影响 LLM 输出的准确性。提示工程本身是一个重要的环节，通常在调用此服务之前完成。fields_to_extract: list[str]: 这个列表用于告知服务我们期望从 LLM 的输出中提取哪些字段。虽然 LLM 的提示中已经包含了字段信息，但此参数可以用于在服务内部对 LLM 的输出进行二次校验或处理。请求体构建:payload 字典需要严格按照目标 LLM API (例如 DeepSeek API) 的文档来构建。关键参数包括：model: 指定要使用的 LLM 模型。messages (或 prompt，取决于 API): 包含用户角色的提示内容。max_tokens: 控制生成内容的最大长度，防止过长或不完整的响应。temperature: 控制输出的随机性。对于信息提取任务，通常设置为较低的值 (如 0.1-0.3) 以获得更稳定和可预测的结果。response_format (如果支持): 强烈建议利用此参数（如果 LLM API 支持）来请求 LLM 直接输出 JSON 对象。这可以大大简化后续的解析工作，并提高结果的可靠性。例如，OpenAI 的一些新模型支持 response_format={"type": "json_object"}。需要查阅 DeepSeek API 是否有类似功能。异步请求:使用 httpx.AsyncClient 发送异步 POST 请求，这与 FastAPI 的异步特性相符，可以提高应用的并发处理能力。设置了请求超时 (self.request_timeout)。响应处理与解析:response.raise_for_status() 会检查 HTTP 响应状态码，如果不是 2xx，则抛出 httpx.HTTPStatusError 异常。响应体 (response.json()) 被解析为 Python 字典。接着，从 LLM API 的响应结构中提取实际生成的文本内容。这部分的逻辑高度依赖于特定 LLM API 的响应格式。 示例代码假设了一个常见的 choices[0].message.content 结构，但这必须根据 DeepSeek API 的文档进行核实和调整。最关键的一步是尝试将 LLM 输出的文本 (llm_output_text) 解析为 JSON 对象 (json.loads(llm_output_text)), 因为我们的目标是获取结构化的数据。如果 LLM 被正确提示（并且支持 JSON 输出模式），它应该返回一个有效的 JSON 字符串。错误处理:自定义了 LLMServiceError 及其子类 (LLMAPIError, LLMConnectionError, LLMResponseParseError)，以便更精确地捕获和处理与 LLM 相关的各种错误。_make_llm_api_request 方法中捕获了 httpx 的各种异常，并将其转换为自定义的 LLMServiceError 类型，同时记录详细的错误日志。get_structured_completion 方法进一步处理了解析 LLM 输出文本为 JSON 时可能发生的错误。5. 安全与日志API 密钥: API 密钥通过配置加载，不会硬编码。在日志中，避免直接记录完整的 API 密钥。日志记录: 在关键步骤（如发送请求、收到响应、发生错误）添加了日志记录，有助于调试和监控。日志级别应根据环境（开发/生产）进行调整。敏感数据: 如果 prompt 或 LLM 的响应可能包含敏感信息，需要注意日志记录的内容，避免泄露。6. 小结LLMService 类为应用提供了一个集中的、可重用的组件来处理所有与外部 LLM API 的交互。通过清晰的错误处理和配置管理，它有助于构建一个更健壮和可维护的后端