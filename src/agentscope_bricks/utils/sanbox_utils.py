# -*- coding: utf-8 -*-
from e2b_code_interpreter import Sandbox
from e2b_code_interpreter.models import Execution
import base64
from io import BytesIO
from PIL import Image
import os
import re
import ast


def parse_code_blobs(text: str) -> str:
    """Extract code blocs from the LLM's output.

    If a valid code block is passed, it returns it directly.

    Args:
        text (`str`): LLM's output text to parse.

    Returns:
        `str`: Extracted code block.

    Raises:
        ValueError: If no valid code block is found in the text.
    """
    pattern = r"```(?:py|python)?\s*\n(.*?)\n```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return "\n\n".join(match.strip() for match in matches)
    # Maybe the LLM outputted a code blob directly
    # Try to parse the text directly as Python code
    # If it's valid Python code, return it
    # Otherwise return empty string since no valid code block was found
    try:
        ast.parse(text.strip())
        return text.strip()
    except SyntaxError:
        return ""


class ExecutionResultHandler:
    def __init__(self) -> None:
        self.supported_formats = {
            # Images
            "jpeg": self._handle_image,
            "png": self._handle_image,
            # Other formats
            "chart": self._handle_text_based,
            "data": self._handle_data,
            "html": self._handle_text_based,
            "javascript": self._handle_text_based,
            "json": self._handle_json,
            "latex": self._handle_text_based,
            "markdown": self._handle_text_based,
            "pdf": self._handle_binary,
            "svg": self._handle_text_based,
            "text": self._handle_text_based,
        }

    def _handle_image(self, content: str, format_type: str) -> dict:
        """Process image content (jpeg/png)"""
        # decoded_bytes = base64.b64decode(content.encode("utf-8"))
        # For API response, return base64 with metadata
        return {
            "type": "image",
            "format": format_type,
            "data": content,  # Keep as base64
            "mime_type": f"image/{format_type}",
        }

    def _handle_text_based(self, content: str, format_type: str) -> dict:
        """Process text-based content (markdown, html, etc.)"""
        return {
            "type": "text",
            "format": format_type,
            "data": content,
        }

    def _handle_data(self, content: str, format_type: str) -> dict:
        """Process data (often pandas DataFrame or similar)"""
        # Try to convert to more usable format if it's tabular
        try:
            # If it's a pandas dataframe in string form, try to parse it
            if isinstance(content, str) and "<table" in content:
                return {
                    "type": "table",
                    "format": "html",
                    "data": content,
                }
            else:
                return {
                    "type": "data",
                    "format": "json",
                    "data": content,
                }
        except Exception as e:
            print(f"Error handling data: {str(e)}")
            return {
                "type": "data",
                "format": "text",
                "data": str(content),
            }

    def _handle_json(self, content: str, format_type: str) -> dict:
        """Process JSON content"""
        return {
            "type": "data",
            "format": "json",
            "data": content,
        }

    def _handle_binary(self, content: str, format_type: str) -> dict:
        """Process binary content like PDFs"""
        return {
            "type": "binary",
            "format": format_type,
            "data": content,
        }

    def process_execution_result(self, execution: Execution) -> dict:
        """
        Process the execution result from e2b_code_interpreter

        Args:
            execution: The execution result from sandbox.run_code()

        Returns:
            dict: A structured representation of the execution results
        """
        result = {
            "success": True,
            "logs": (
                "\n".join([str(log) for log in execution.logs.stdout])
                if execution.logs
                else ""
            ),
            "artifacts": [],
            "error": None,
        }

        # Handle errors
        if execution.error:
            result["success"] = False
            result["error"] = {
                "name": execution.error.name,
                "value": execution.error.value,
                "traceback": execution.error.traceback,
            }
            return result

        # Process results/artifacts
        if execution.results:
            for res in execution.results:
                # For each result, find the first non-None attribute
                for format_type, handler in self.supported_formats.items():
                    content = getattr(res, format_type, None)
                    if content is not None:
                        artifact = handler(content, format_type)
                        artifact["is_main_result"] = res.is_main_result
                        result["artifacts"].append(artifact)
                        break

        return result


class E2BExecutor:
    def __init__(self) -> None:
        # 从环境变量获取E2B API key
        api_key = os.getenv("E2B_API_KEY")
        if not api_key:
            raise ValueError("E2B_API_KEY environment variable is not set")

        self.api_key = api_key
        self.sandbox = None
        self.handler = ExecutionResultHandler()
        self.timeout = 300

    def _ensure_sandbox(self) -> bool:
        """确保sandbox存在且有效，如果不存在或已超时则创建新的"""
        try:
            if self.sandbox is None:
                self.sandbox = Sandbox(
                    api_key=self.api_key,
                    timeout=self.timeout,
                )
            return True
        except Exception as e:
            print(f"Error with existing sandbox: {str(e)}")
            self.sandbox = Sandbox(api_key=self.api_key, timeout=self.timeout)
            return True

    def upload_file(self, file_path: str, target_path: str = None) -> bool:
        """
        上传文件到沙箱环境

        Args:
            file_path (str): 本地文件路径
            target_path (str, optional): 沙箱中的目标路径。如果不指定，将使用原文件名

        Returns:
            bool: 上传是否成功
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")

            if target_path is None:
                target_path = os.path.basename(file_path)

            # 上传文件到沙箱
            with open(file_path, "rb") as file:
                self.sandbox.files.write(target_path, file)
            return True

        except Exception as e:
            print(f"Error uploading file: {str(e)}")
            return False

    def upload_file_from_memory(
        self,
        file_content: bytes,
        target_path: str,
    ) -> bool:
        """
        从内存中上传文件到沙箱环境

        Args:
            file_content (bytes): 文件内容
            target_path (str): 沙箱中的目标路径

        Returns:
            bool: 上传是否成功
        """
        try:
            self._ensure_sandbox()
            # 使用BytesIO创建文件对象
            file_obj = BytesIO(file_content)
            # 上传文件到沙箱
            self.sandbox.files.write(target_path, file_obj)
            return True
        except Exception as e:
            print(f"Error uploading file from memory: {str(e)}")
            return False

    def execute_code(
        self,
        code: str,
        return_final_answer: bool = False,
    ) -> dict:
        """
        执行代码并返回执行结果
        """
        try:
            self._ensure_sandbox()
            execution = self.sandbox.run_code(code)
            execution_result = self.handler.process_execution_result(execution)
            return execution_result
        except Exception as e:
            print(f"Error executing code: {str(e)}")
            return {}
