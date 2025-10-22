# -*- coding: utf-8 -*-
import argparse
import asyncio
import json
import importlib
import os
import time
from typing import Any, Dict, Optional, Tuple, Type

from dashscope import Generation
from pydantic import BaseModel

from agentscope_bricks.base import Component

PARAM_FILL_PROMPT_SYSTEM = """你是一个工具的参数填充助手，你需要根据提供的工具及其参数描述，从用户请求中提取相关信息进行填充。

# 参数填充过程的注意事项：
- 填充的参数必须来源于用户的请求，不能包含任何非用户请求的内容；
- 必须填充所有required参数；
- 对于非required参数，如果用户请求中有与该参数相关的内容，则一定填充，如没有则不填充；
- 填充的参数必须与该参数描述内容相关，不得包含用户请求中与该参数描述无关的信息；
- 填充的参数必须与用户请求的相关内容一致，不得改写、添加或删减，请保持大小写、空格一致；
- 请严格遵循工具要求的填充格式，不要有任何注释；
- 如果无法输出参数，请输出无法输入的原因，并将原因以dict格式返回。"""


PARAM_FILL_PROMPT_USER = """# 用户的请求为：
{query}

# 你需要填充的工具信息：
## 你需要填充的工具名称为：
{name_for_model}
## 这个工具的描述是：
{description_for_model}
## 这个工具的填充参数及其描述是：
{parameters}
## 这个工具要求的填充格式是：
{args_format}

# 输出
请在本消息后直接按照工具要求的填充格式进行输出，不要输出任何其他无关内容，包括{fn_name_flag}和{fn_args_flag}"""

FN_NAME = "✿FUNCTION✿"
FN_ARGS = "✿ARGS✿"
FN_NAME_NQWN = "$$FUNCTION"
FN_ARGS_NQWN = "$$ARGS"
QWEN_MODELS_PREFIX = ["qwen2.5", "qwen", "pre_qwen", "pre-qwen", "poc-qwen"]


def is_qwen_model(model_name):
    for prefix in QWEN_MODELS_PREFIX:
        if model_name.startswith(prefix):
            return True
    return False


def get_special_token(model_name: str):
    """
    Get special tokens for raw prompt
        - For qwen, return tokens with '✿'
        - For other model, return tokens with '$'
    Args:
        model_name (str): model name
    """
    if is_qwen_model(model_name):
        return FN_NAME, FN_ARGS
    else:
        return FN_NAME_NQWN, FN_ARGS_NQWN


def get_component_info(
    component_name: str,
) -> Tuple[Type[Component], Type[BaseModel]]:
    """
    Get component class and input class by component class name
    Args:
        component_name (str): component class name
    Returns:
        Tuple[Type[Component], Type[BaseModel]]: component class and
            component input class
    """
    try:
        components_module = importlib.import_module(
            "agentscope_bricks.components",
        )
        component_class = getattr(components_module, component_name)
        component_instance = component_class()
        component_input_class = component_instance.input_type
        return component_class, component_input_class
    except (ImportError, AttributeError) as e:
        raise ValueError(
            f"Component '{component_name}' not found: {str(e)}",
        )


def build_prompt(
    component_class: Type[Component],
    model_name: str,
    query: str,
) -> str:

    system_prompt = PARAM_FILL_PROMPT_SYSTEM

    component = component_class()
    function_schema = component.get_function_schema()
    fn_name_flag, fn_args_flag = get_special_token(model_name=model_name)
    user_prompt = PARAM_FILL_PROMPT_USER.format(
        query=query,
        name_for_model=component.name,
        description_for_model=component.description,
        parameters=json.dumps(
            function_schema.parameters.model_dump(),
            ensure_ascii=False,
        ),
        args_format="此工具的参数填充应为JSON对象，JSON键名为参数名称，键值为参数内容。",
        fn_name_flag=fn_name_flag,
        fn_args_flag=fn_args_flag,
    )

    prompt = (
        system_prompt + "<|im_end|>"
        "\n"
        + "<|im_start|>user"
        + "\n"
        + user_prompt
        + "<|im_end|>\n<|im_start|>assistant\n"
    )

    print(f"prompt: {prompt}")

    return prompt


async def call_llm_for_params(
    component_class: Type[Component],
    model_name: str,
    query: str,
) -> Optional[Dict[str, Any]]:
    """
    Call LLM to generate component parameters from user query
    Args:
        component_class: component class
        model_name: model name for LLM
        query: user query for parameter filling
    Returns:
        Optional[Dict[str, Any]]: parsed parameters or None if failed
    Raises:
        Exception: if LLM call or response parsing fails
    """
    try:
        prompt = build_prompt(component_class, model_name, query)

        parameters = {
            "max_tokens": 1024,
            "temperature": 0.85,
            "result_format": "message",
            "request_timeout": 3600,
            "router": "text",
            "stop_words": [
                {"stop_str": "✿ARGS✿", "mode": "exclude"},
                {"stop_str": "✿RESULT✿", "mode": "exclude"},
                {"stop_str": "✿RETURN✿", "mode": "exclude"},
            ],
        }

        resp = Generation.call(
            model="qwen-max",
            prompt=prompt,
            use_raw_prompt=True,
            **parameters,
        )

        print(f"\n{'='*60}")
        print("Response from LLM:")
        print(f"{'='*60}")
        print(resp)

        content = resp.output.choices[0].message.content
        component_parameters = json.loads(content)
        print(f"\n{'='*60}")
        print("Parsed parameters:")
        print(f"{'='*60}")
        print(json.dumps(component_parameters, ensure_ascii=False, indent=2))
        return component_parameters
    except Exception as e:
        print(f"\n✗ Error in call_llm_for_params: {e}")
        raise e


async def execute_component(
    component_class: Type[Component],
    component_input_class: Type[BaseModel],
    component_parameters: Dict[str, Any],
) -> Optional[Any]:
    """
    Execute component with validated parameters
    Args:
        component_class: component class
        component_input_class: component input class
        component_parameters: parameters to pass to component
    Returns:
        Optional[Any]: component execution result or None if failed
    Raises:
        Exception: if validation or execution fails
    """
    print(f"\n{'='*60}")
    print("Validation with component_input_class:")
    print(f"{'='*60}")
    try:
        validated_input = component_input_class(**component_parameters)
        print("✓ Validation successful!")

        print(f"\n{'='*60}")
        print("Calling component arun method:")
        print(f"{'='*60}")

        component_instance = component_class()
        result = await component_instance.arun(validated_input)
        print("✓ Component execution successful!")
        print(f"Result: {result}")
        return result

    except Exception as e:
        print(f"✗ Error in execute_component: {e}")
        raise e


async def poll_fetch_component(
    fetch_component_class: Type[Component],
    fetch_input_class: Type[BaseModel],
    task_id: str,
    max_wait_time: int = 600,
    poll_interval: int = 5,
) -> Optional[Any]:
    """
    Poll fetch component until task completion
    Args:
        fetch_component_class: fetch component class
        fetch_input_class: fetch component input class
        task_id: task ID to poll
        max_wait_time: maximum wait time in seconds
        poll_interval: polling interval in seconds
    Returns:
        Optional[Any]: final fetch result or None if failed/timeout
    Raises:
        Exception: if polling encounters critical error
    """
    print(f"\n{'='*60}")
    print(f"🔄 Polling for task completion (task_id: {task_id})...")
    print(f"{'='*60}")

    try:
        fetch_component_instance = fetch_component_class()
        poll_start_time = time.time()

        while True:
            await asyncio.sleep(poll_interval)

            try:
                fetch_input = fetch_input_class(task_id=task_id)
                fetch_result = await fetch_component_instance.arun(fetch_input)

                task_status = fetch_result.task_status
                print(f"📊 Task status: {task_status}")

                if task_status == "SUCCEEDED":
                    print("✓ Task succeeded!")
                    print(f"Result: {fetch_result}")
                    return fetch_result
                elif task_status in ["FAILED", "CANCELED"]:
                    print(f"✗ Task failed with status: {task_status}")
                    raise Exception(
                        f"Task failed with status: {task_status}",
                    )

            except Exception as e:
                print(f"⚠️  Fetch error: {e}")
                raise e

            if time.time() - poll_start_time > max_wait_time:
                print(f"⏰ Polling timeout after {max_wait_time}s")
                raise TimeoutError(
                    f"Polling timeout after {max_wait_time}s",
                )
    except Exception as e:
        print(f"\n✗ Error in poll_fetch_component: {e}")
        raise e


async def auto_call_mcp(component_name: str, model_name: str, query: str):
    """
    Test parameter filling and component execution.
    For async submit components, also test fetch component with polling.
    Args:
        component_name (str): component class name
        model_name (str): model name for LLM
        query (str): user query for parameter filling
    Raises:
        Exception: if any step in the process fails
    """
    try:
        component_class, component_input_class = get_component_info(
            component_name,
        )

        component_parameters = await call_llm_for_params(
            component_class,
            model_name,
            query,
        )
        if not component_parameters:
            raise Exception("Failed to get component parameters from LLM")

        submit_result = await execute_component(
            component_class,
            component_input_class,
            component_parameters,
        )
        if not submit_result:
            raise Exception("Failed to execute component")

        if "Submit" in component_name:
            print(f"\n{'='*60}")
            print("🔍 Detected async submit component, testing fetch...")
            print(f"{'='*60}")

            if not hasattr(submit_result, "task_id"):
                raise Exception("Submit result does not contain task_id")

            task_id = submit_result.task_id
            print(f"📋 Task ID: {task_id}")

            fetch_component_name = component_name.replace("Submit", "Fetch")
            print(f"🔧 Fetch component: {fetch_component_name}")

            fetch_class, fetch_input_class = get_component_info(
                fetch_component_name,
            )
            fetch_result = await poll_fetch_component(
                fetch_class,
                fetch_input_class,
                task_id,
            )
            return fetch_result

        return submit_result
    except Exception as e:
        print(f"\n✗ Error in auto_call_mcp: {e}")
        raise


def parse_args():
    """
    Parse command line arguments and environment variables
    Command line arguments take precedence over environment variables
    """
    parser = argparse.ArgumentParser(
        description="Test parameter filling and component execution",
    )
    parser.add_argument(
        "--component_name",
        type=str,
        required=True if not os.getenv("COMPONENT_NAME") else False,
        default=os.getenv("COMPONENT_NAME"),
        help="Component class name (required, env: COMPONENT_NAME)",
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True if not os.getenv("QUERY") else False,
        default=os.getenv("QUERY"),
        help="User query for parameter filling (required, env: QUERY)",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default=os.getenv("MODEL_NAME", "qwen-max"),
        help="Model name for LLM (optional, env: MODEL_NAME)",
    )
    parser.add_argument(
        "--times",
        type=int,
        default=int(os.getenv("TIMES", "1")),
        help="Number of times to run the test (optional, env: TIMES)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    print(f"\n{'='*60}")
    print("Parsed arguments:")
    print(f"{'='*60}")
    print(f"component_name: {args.component_name}")
    print(f"model_name: {args.model_name}")
    print(f"query: {args.query}")
    print(f"times: {args.times}")

    async def main():
        for i in range(args.times):
            print(f"\n{'='*60}")
            print(f"Running test {i + 1}/{args.times}")
            print(f"{'='*60}")
            try:
                await auto_call_mcp(
                    args.component_name,
                    args.model_name,
                    args.query,
                )
                print(f"\n{'='*60}")
                print(f"✓ Test {i + 1}/{args.times} completed successfully")
                print(f"{'='*60}")
            except Exception as e:
                print(f"\n{'='*60}")
                print(f"✗ Test {i + 1}/{args.times} failed with error:")
                print(f"{'='*60}")
                print(f"{type(e).__name__}: {e}")
                print(f"\n{'='*60}")
                print("Test interrupted due to exception")
                print(f"{'='*60}")
                raise e

        print(f"\n{'='*60}")
        print(f"✓ All {args.times} test(s) completed successfully!")
        print(f"{'='*60}")

    asyncio.run(main())
