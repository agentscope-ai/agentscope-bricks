# -*- coding: utf-8 -*-
import os
from sandbox_center.sandboxes.e2b_sandbox import (
    E2bSandBox,
)
from openai import OpenAI
from PIL import Image
import io
import re
import base64
import json


def init_output_dir(directory_format):
    run_id = 1
    while os.path.exists(directory_format(run_id)):
        run_id += 1
    os.makedirs(directory_format(run_id), exist_ok=True)
    return directory_format(run_id)


def init_sandbox():
    try:
        sandbox = E2bSandBox()
        # sandbox = Sandbox(timeout=120)
        sandbox.device.stream.start()
        return sandbox
    except Exception as e:
        print(f"Error initializing sandbox: {e}")
        # If sandbox was created but stream failed, make sure to clean up
        if "sandbox" in locals():
            try:
                if hasattr(sandbox.device, "stream") and hasattr(
                    sandbox.device.stream,
                    "stop",
                ):
                    sandbox.device.stream.stop()
                if hasattr(sandbox, "close"):
                    sandbox.close()
            except Exception as cleanup_error:
                print(f"Error during sandbox cleanup: {cleanup_error}")
        raise


def cleanup_sandbox(sandbox):
    """Properly cleanup sandbox to avoid Bad file descriptor errors"""
    if sandbox is None:
        return

    try:
        # Stop the stream first
        if hasattr(sandbox, "stream") and hasattr(sandbox.stream, "stop"):
            sandbox.stream.stop()
    except Exception as e:
        print(f"Error stopping sandbox stream: {e}")

    try:
        # Close the sandbox
        if hasattr(sandbox, "close"):
            sandbox.close()
    except Exception as e:
        print(f"Error closing sandbox: {e}")


log_template = """
<html><head><title>Log</title>
    <style>
    body {
        max-width: 1000px;
        margin: 0 auto;
        padding: 20px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                     sans-serif;
        line-height: 1.6;
        background: #f5f5f5;
    }

    h1 {
        color: #333;
        border-bottom: 2px solid #ddd;
        padding-bottom: 10px;
    }

    p {
        margin: 12px 0;
        padding: 10px;
        border-radius: 4px;
    }
    </style>
    </head><body>
    <h1>Computer Use Log</h1>
    {{content}}
    </body></html>
"""


# A logger to write to the console and a log file in color
class Logger:

    # Mapping standard color names to ANSI color codes
    color_map = {
        "black": "30",
        "red": "31",
        "green": "32",
        "yellow": "33",
        "blue": "34",
        "magenta": "35",
        "cyan": "36",
        "white": "37",
        "gray": "37;2",
    }

    # Mapping standard color names to web colors
    css_color_map = {
        "black": ("#000000", "#e3f2fd"),
        "red": ("#8B0000", "#ffebee"),
        "green": ("#006400", "#e8f5e9"),
        "yellow": ("#8B8B00", "#fff3e0"),
        "blue": ("#00008B", "#e8eaf6"),
        "magenta": ("#8B008B", "#f5f5f5"),
        "cyan": ("#008B8B", "#f5f5f5"),
        "white": ("#CCCCCC", "#f5f5f5"),
        "gray": ("#666666", "#f5f5f5"),
    }

    def __init__(self):
        self.logs = []  # Output logs
        self.log_file = None  # Output log file
        self.log_file_template = None  # Store the log file template

        # Load the HTML template when the logger is initialized
        self.log_file_template = log_template

    # Print to the terminal in color
    def print_colored(self, message, color=None):
        # Check if the color is valid and fetch its ANSI code
        color_code = self.color_map.get(color)

        if color_code:
            # Print with ANSI escape codes for color
            print(f"\033[{color_code}m{message}\033[0m")
        else:
            # Fallback: Print the message without color
            print(message)

    # Write the log file in color
    def write_log_file(self, logs, filepath):
        """Write the complete log file using the stored log entries"""
        try:
            content = ""
            for entry in logs:
                color_info = self.css_color_map.get(
                    entry["color"],
                    (entry["color"], "#f5f5f5"),
                )
                style = f"color:{color_info[0]};background:{color_info[1]}"
                content += f"<p style='{style}'>{entry['text']}</p>\n"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self.log_file_template.replace("{{content}}", content))
        except (OSError, IOError) as e:
            print(f"Error writing log file {filepath}: {e}")
        except Exception as e:
            print(f"Unexpected error writing log file {filepath}: {e}")

    # Write a line to the log file and terminal
    def log(self, text, color="black", print=True):
        # Write to the terminal
        if print:
            self.print_colored(text, color)
        # Write to the log file
        self.logs.append({"text": text, "color": color})
        if self.log_file:
            self.write_log_file(self.logs, self.log_file)
        return text


logger = Logger()


def Message(content, role="assistant"):
    return {"role": role, "content": content}


def Text(text):
    return {"type": "text", "text": text}


def parse_json(s):
    if not s:
        return None

    # 如果已经是字典类型，直接返回
    if isinstance(s, dict):
        return s

    # 如果是字符串类型，尝试解析
    if isinstance(s, str):
        try:
            # 首先尝试直接解析
            return json.loads(s)
        except json.JSONDecodeError:
            try:
                # 如果直接解析失败，尝试修复常见的JSON格式问题
                # 例如，处理单引号、尾随逗号等
                fixed_s = s.replace("'", '"')  # 将单引号替换为双引号
                fixed_s = re.sub(
                    r",(\s*[}\]])",
                    r"\1",
                    fixed_s,
                )  # 移除尾随逗号
                return json.loads(fixed_s)
            except json.JSONDecodeError:
                # 如果仍然失败，尝试处理可能的转义问题
                try:
                    # 尝试对字符串进行解码处理
                    if "\\" in s:
                        # 尝试解码转义字符
                        decoded_s = s.encode("utf-8").decode("unicode_escape")
                        return json.loads(decoded_s)
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    pass

                print(f"Error decoding JSON for tool call arguments: {s}")
                return None

    return None


class LLMProvider:
    """
    The LLM provider is used to make calls to an LLM given a provider and
    model name, with optional tool use support
    """

    # Class attributes for base URL and API key
    base_url = None
    api_key = None

    # Mapping of model aliases
    aliases = {}

    # Initialize the API client
    def __init__(self, model):
        self.model = self.aliases.get(model, model)
        print(f"Using {self.__class__.__name__} with {self.model}")
        self.client = self.create_client()

    # Convert our function schema to the provider's required format
    def create_function_schema(self, definitions):
        functions = []

        for name, details in definitions.items():
            properties = {}
            required = []

            for param_name, param_desc in details["params"].items():
                properties[param_name] = {
                    "type": "string",
                    "description": param_desc,
                }
                required.append(param_name)

            function_def = self.create_function_def(
                name,
                details,
                properties,
                required,
            )
            functions.append(function_def)

        return functions

    # Represent a tool call as an object
    def create_tool_call(self, name, parameters):
        return {
            "type": "function",
            "name": name,
            "parameters": parameters,
        }

    # Wrap a content block in a text or an image object
    def wrap_block(self, block):
        if isinstance(block, bytes):
            # Pass raw bytes so that imghdr can detect the image type properly.
            return self.create_image_block(block)
        else:
            return Text(block)

    # Wrap all blocks in a given input message
    def transform_message(self, message):
        content = message["content"]
        if isinstance(content, list):
            wrapped_content = [self.wrap_block(block) for block in content]
            return {**message, "content": wrapped_content}
        else:
            return message

    # Create a chat completion using the API client
    def completion(self, messages, **kwargs):
        # Skip the tools parameter if it's None
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        # Wrap content blocks in image or text objects if necessary
        new_messages = [
            self.transform_message(message) for message in messages
        ]
        # Call the inference provider
        completion = self.client.create(
            messages=new_messages,
            model=self.model,
            **filtered_kwargs,
        )
        # Check for errors in the response
        if hasattr(completion, "error"):
            raise Exception("Error calling model: {}".format(completion.error))
        return completion


class OpenAIBaseProvider(LLMProvider):

    def create_client(self):
        return OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        ).chat.completions

    def create_function_def(self, name, details, properties, required):
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": details["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def create_image_block(self, image_data: bytes):
        # Use Pillow to detect the image type
        image_type = "png"  # Default to PNG if detection fails
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                image_type = img.format.lower()
        except Exception as e:
            print(f"Error detecting image type: {e}")

        # Base64-encode the raw image bytes.
        encoded = base64.b64encode(image_data).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/{image_type};base64,{encoded}"},
        }

    def call(self, messages, functions=None):
        # If functions are provided, only return actions
        tools = self.create_function_schema(functions) if functions else None
        completion = self.completion(messages, tools=tools)
        message = completion.choices[0].message

        # Return response text and tool calls separately
        if functions:
            tool_calls = message.tool_calls or []
            combined_tool_calls = [
                self.create_tool_call(
                    tool_call.function.name,
                    parse_json(tool_call.function.arguments),
                )
                for tool_call in tool_calls
                if parse_json(tool_call.function.arguments) is not None
            ]

            # Sometimes, function calls are returned unparsed by the inference
            # provider. This code parses them manually.
            if message.content and not tool_calls:
                tool_call_matches = re.search(r"\{.*\}", message.content)
                if tool_call_matches:
                    tool_call = parse_json(tool_call_matches.group(0))
                    # Some models use "arguments" as the key instead of
                    # "parameters"
                    parameters = tool_call.get(
                        "parameters",
                        tool_call.get("arguments"),
                    )
                    if tool_call.get("name") and parameters:
                        combined_tool_calls.append(
                            self.create_tool_call(
                                tool_call.get("name"),
                                parameters,
                            ),
                        )
                        return None, combined_tool_calls

            return message.content, combined_tool_calls

        # Only return response text
        else:
            return message.content


class QwenProvider(OpenAIBaseProvider):
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key = os.getenv("DASHSCOPE_API_KEY")
