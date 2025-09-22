# -*- coding: utf-8 -*-
import json
import json5


def process_json_str(s: str) -> dict:
    """Process a JSON string with fallback parsing strategies.

    Args:
        s (str): The JSON string to parse.

    Returns:
        dict: The parsed JSON object.

    Raises:
        Exception: If both json5 and json parsing fail.
    """
    try:
        return json5.loads(s)
    except Exception:
        # json库对一些特殊unicode字符有支持, 同时设置 strict 可以绕过无法解析的字符，增加容错性
        return json.loads(s, strict=False)


def json_loads(s: str) -> dict:
    """Load JSON from a string, handling code block formatting.

    Args:
        s (str): The JSON string to parse, potentially wrapped in code blocks.

    Returns:
        dict: The parsed JSON object.
    """
    s = s.strip("\n")
    if s.startswith("```") and s.endswith("\n```"):
        s = "\n".join(s.split("\n")[1:-1])
    return process_json_str(s)
