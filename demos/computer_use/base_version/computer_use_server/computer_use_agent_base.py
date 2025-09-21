# -*- coding: utf-8 -*-
import os
from PIL import Image
import json
import datetime
import asyncio
import threading
import requests
from demos.computer_use.sandbox_center.gui_tools import (
    GUI_TOOLS,
    PCA_GUI_TOOLS,
    set_device,
)
from agentscope_bricks.utils.grounding_utils import draw_point, encode_image
from cua_utils_base import logger, Message, parse_json, QwenProvider
from demos.computer_use.sandbox_center.utils.oss_client import OSSClient
from demos.computer_use.sandbox_center.sandboxes.e2b_sandbox import (
    E2bSandBox,
)
from demos.computer_use.agents.gui_agent_app_v2 import (
    GuiAgent,
)

TYPING_DELAY_MS = 12
TYPING_GROUP_SIZE = 50
HUMAN_HELP_ACTION = "human_help"
vision_model = QwenProvider("qwen-vl-max")
action_model = QwenProvider("qwen-max")
gui_agent = GuiAgent()


def register_tools(equipment: E2bSandBox, tool_functions: dict):
    set_device(equipment)
    tools = {
        "stop": {
            "description": "Indicate that the task has been completed.",
            "params": {},
        },
        HUMAN_HELP_ACTION: {
            "description": (
                "Wait for the given amount of time for human to do the task."
            ),
            "params": {
                "time": {
                    "type": "integer",
                    "description": (
                        "The estimated time to do the task in seconds. "
                        "Estimate conservatively - it's better to estimate "
                        "less time and retry if needed."
                    ),
                },
                "task": {
                    "type": "string",
                    "description": (
                        "The task for human to do while the system is waiting."
                    ),
                },
            },
        },
    }
    for name, tool in tool_functions.items():
        tools[name] = {
            "description": tool.function_schema.description,
            "params": tool.function_schema.parameters.model_dump(),
        }
    return tools


class ComputerUseAgent:
    def __init__(
        self,
        equipment,
        output_dir=".",
        mode="qwen_vl",
        sandbox_type="e2b-desktop",
        save_logs=True,
        status_callback=None,
        pc_use_add_info: str = "",
        max_steps: int = 10,
    ):
        super().__init__()
        self.messages = []  # Agent memory
        # self.sandbox = sandbox  # E2B sandbox
        self.latest_screenshot = None  # Most recent PNG of the scren
        self.image_counter = 0  # Current screenshot number
        self.tmp_dir = output_dir  # Folder to store screenshots
        self.mode = mode
        self.sandbox_type = sandbox_type
        self.status_callback = status_callback  # 状态回调函数
        self.max_steps = max_steps
        self.equipment = equipment
        # 修改设备处理逻辑
        if hasattr(equipment, "device") and equipment.device:
            self.sandbox = equipment.device
        else:
            # 如果equipment本身就是设备对象，则直接使用
            self.sandbox = equipment

        if mode == "qwen_vl":
            self.tool_functions = GUI_TOOLS
            self.tools = register_tools(equipment, self.tool_functions)
        elif mode == "pc_use":
            self.session_id = ""
            self.add_info = pc_use_add_info
            if self.sandbox_type == "e2b-desktop":
                self.tool_functions = PCA_GUI_TOOLS
                self.tools = register_tools(equipment, self.tool_functions)
        else:
            raise ValueError(
                f"Invalid mode: {mode}, must be one "
                f"of: [qwen_vl, pc_use, wy_pc_use]",
            )

        # Set the log file location
        if save_logs:
            logger.log_file = f"{output_dir}/log.html"

        log_str = "The agent will use the following actions:\n"
        for action, details in self.tools.items():
            param_str = ", ".join(
                details.get("params").get("properties", {}).keys(),
            )
            log_str += f"- {action}({param_str})\n"
        logger.log(log_str.rstrip(), "gray")
        self.emit_status("TASK", {"message": log_str.rstrip()})
        self._is_cancelled = False
        self._interrupted = False

    def stop(self):
        self._is_cancelled = True
        print("Agent stopped by user request.")
        # 发送状态更新到前端
        self.emit_status(
            "SYSTEM",
            {
                "message": "Stop request received, "
                "waiting for current step to complete...",
                "status": "running",
            },
        )

    def interrupt_wait(self):
        """
        由前端调用，用于中断当前的等待状态
        """
        self._interrupted = True
        print("Agent wait stopped by user request.")
        # 发送状态更新到前端
        self.emit_status(
            "SYSTEM",
            {
                "message": "Stop wait request received, "
                "waiting for current step to complete...",
                "status": "running",
            },
        )

    def close_equipment(self, session_id: str):
        """
        由前端调用，用于中断当前的等待状态
        """

        print("Agent wait close equipment by user request.")
        status, res = self.equipment.agent_bay_instance.close_session(
            session_id=session_id,
        )
        # 发送状态更新到前端
        if status == "success":
            self.emit_status(
                "SYSTEM",
                {
                    "message": "Close equipment success",
                    "status": "running",
                },
            )
        else:
            self.emit_status(
                "SYSTEM",
                {
                    "message": "Close equipment failed",
                    "status": "running",
                },
            )

    def emit_status(self, status_type: str, data: dict):
        """发射状态更新 - 支持同步和异步回调"""
        status_data = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": status_type,
            "status": "running",
            "data": data,
        }

        if self.status_callback:
            try:
                if asyncio.iscoroutinefunction(self.status_callback):
                    # 异步回调函数
                    self._run_async_callback(status_data)
                else:
                    # 同步回调函数
                    self.status_callback(status_data)
            except Exception as e:
                logger.log(f"Error in status callback: {e}", "red")

    def annotate_image(
        self,
        point: list,
        is_save: bool = False,
    ):
        annotated_img = draw_point(Image.open(self.latest_screenshot), point)
        screenshot_filename = os.path.basename(self.latest_screenshot)
        img_path = None
        if is_save:
            img_path = self.save_image(
                annotated_img,
                f"{screenshot_filename[:-4]}_annotated",
            )
        # 上传到oss
        oss_url = self.equipment.upload_file_and_sign(
            img_path,
            screenshot_filename,
        )
        return encode_image(annotated_img), oss_url

    def _run_async_callback(self, status_data):
        """在后台线程中运行异步回调"""

        def run_callback():
            try:
                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.status_callback(status_data))
                loop.close()
            except Exception as e:
                logger.log(f"Error running async callback: {e}", "red")

        # 在后台线程中运行
        thread = threading.Thread(target=run_callback)
        thread.daemon = True
        thread.start()

    def call_function(self, name, arguments):
        func_impl = (
            self.tool_functions.get(name.lower())
            if name.lower() in self.tools
            else None
        )
        if func_impl:
            try:
                # Ensure arguments is a dictionary
                if isinstance(arguments, str):
                    arguments = parse_json(arguments) or {}
                elif arguments is None:
                    arguments = {}
                # 处理传入的是 JSON Schema 格式的情况
                if isinstance(arguments, dict) and "properties" in arguments:
                    # 提取实际的参数值
                    arguments = arguments.get("properties", {})

                result = func_impl(**arguments) if arguments else func_impl()
                return result
            except Exception as e:
                return (
                    f"Error executing function: {str(e)}, "
                    f"when calling function: {name} "
                    f"with arguments: {arguments}"
                )
        else:
            return "Function not implemented."

    def save_image(self, image, prefix="image"):
        self.image_counter += 1
        filename = f"{prefix}_{self.image_counter}.png"
        filepath = os.path.join(self.tmp_dir, filename)
        if isinstance(image, Image.Image):
            image.save(filepath)
        else:
            with open(filepath, "wb") as f:
                f.write(image)

        return filepath

    def screenshot(self):
        file = self.sandbox.screenshot()
        filename = self.save_image(file, "screenshot")
        logger.log(f"screenshot {filename}", "gray")
        self.latest_screenshot = filename
        with open(filename, "rb") as image_file:
            return image_file.read(), filename

    def screenshot_base64_save_local_wy(self, prefix="image"):
        self.image_counter += 1
        filename = f"{prefix}_{self.image_counter}.png"
        filename_ = f"{prefix}_{self.image_counter}"
        filepath = os.path.join(self.tmp_dir, filename)
        file_base64 = self.equipment.get_screenshot_base64_save_local(
            filename_,
            filepath,
        )
        logger.log(f"screenshot {filename}", "gray")
        self.latest_screenshot = filepath
        with open(filepath, "rb") as image_file:
            return image_file.read(), file_base64.split(",")[1], filename

    def screenshot_save_local_wy(self, prefix="image"):
        self.image_counter += 1
        filename = f"{prefix}_{self.image_counter}.png"
        filename_ = f"{prefix}_{self.image_counter}"
        filepath = os.path.join(self.tmp_dir, filename)
        file_os_url = self.equipment.get_screenshot_oss_save_local(
            filename_,
            filepath,
        )
        logger.log(f"file_os_url {file_os_url}")
        self.latest_screenshot = filepath
        with open(filepath, "rb") as image_file:
            return image_file.read(), file_os_url, filename

    def screenshot_save_oss(self, data: bytes, file_name: str):
        oss_client = OSSClient()
        return oss_client.oss_upload_data_and_sign(data, file_name)

    def screenshot_base64_save_local_phone_wy(self, prefix="image"):
        self.image_counter += 1
        filename = f"{prefix}_{self.image_counter}.png"
        filepath = os.path.join(self.tmp_dir, filename)
        file_oss = self.equipment.get_screenshot_oss_phone()  # 获取 OSS URL
        # 下载远程图片并保存到本地
        response = requests.get(file_oss, stream=True)
        if response.status_code == 200:
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
        else:
            raise Exception(f"Failed to download image from {file_oss}")

        self.latest_screenshot = filepath

        # 读取图像二进制数据
        with open(filepath, "rb") as image_file:
            return image_file.read(), file_oss, filename

    def screenshot_base64_save_local_agent_bay_wy(self, prefix="image"):
        self.image_counter += 1
        filename = f"{prefix}_{self.image_counter}.png"
        filepath = os.path.join(self.tmp_dir, filename)
        file_oss = self.equipment.get_screenshot_oss_url()  # 获取 OSS URL
        # 下载远程图片并保存到本地
        response = requests.get(file_oss, stream=True)
        if response.status_code == 200:
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
        else:
            raise Exception(f"Failed to download image from {file_oss}")

        self.latest_screenshot = filepath

        # 读取图像二进制数据
        with open(filepath, "rb") as image_file:
            return image_file.read(), file_oss, filename

    def analyse_screenshot(self, is_debug=False, debug_file_path=None):
        screenshot_img, screenshot_filename = self.screenshot()
        screenshot_oss_url = self.screenshot_save_oss(
            screenshot_img,
            screenshot_filename,
        )
        auxiliary_info = {}
        result = ""
        if self.mode == "qwen_vl":
            system_prompt = (
                "You are an intelligent computer-use "
                "agent that helps users "
                "accomplish tasks by interpreting desktop "
                "screenshots and "
                "generating the next UI action.\n\n"
                "For each screenshot, follow these steps "
                "and respond in the "
                "exact format below. Only use visual "
                "evidence — do not assume "
                "hidden or off-screen information.\n\n"
                f"### Objective:\n{self.user_instruction}\n\n"
                "### Response Format:\n```\n"
                "Screen analysis: [Describe relevant "
                "visible elements such as "
                "windows, apps, icons, buttons, menus]\n"
                "Objective status: [complete | not complete]\n"
                "(If the objective is not complete:)\n"
                "Next action: [click|type|run command] "
                "[describe the action "
                "clearly]\nExpected outcome: [What "
                "result do you expect this "
                "action to achieve?]\n```\n\n"
                "### Guidelines:\n"
                '* Be specific (e.g., "click the '
                'Chrome icon in the taskbar" '
                'not just "click Chrome").\n'
                "* Do **not** speculate about invisible UI.\n"
                "* Only suggest **one next action** at a time.\n"
                "* Use the screenshot to ground all decisions."
            )

            vl_messages = [
                Message(system_prompt, role="system"),
                Message(
                    [
                        screenshot_img,
                        "The image shows the current display of the computer.",
                    ],
                    role="user",
                ),
            ]

            # Debug: save vision_model request
            if is_debug and debug_file_path:
                with open(debug_file_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{'=' * 50}\n")
                    f.write(
                        f"VISION_MODEL REQUEST - {datetime.datetime.now()}\n",
                    )
                    f.write(f"{'=' * 50}\n")
                    # Save the text content of messages (excluding image data)
                    for i, msg in enumerate(vl_messages):
                        role = msg.get("role", "user")
                        f.write(f"Message {i + 1} (role: {role}):\n")
                        content = msg.get("content", msg)
                        if isinstance(content, list):
                            for j, content_item in enumerate(content):
                                if isinstance(content_item, bytes):
                                    img_info = (
                                        f"[Screenshot saved as "
                                        f"{screenshot_filename}]"
                                    )
                                    f.write(
                                        f"  Image part {j + 1}: "
                                        f"{img_info}\n",
                                    )
                                elif isinstance(content_item, str):
                                    f.write(
                                        f"  Text part {j + 1}: "
                                        f"{content_item}\n",
                                    )
                                else:
                                    f.write(
                                        f"  Content part {j + 1}: "
                                        f"{str(content_item)}\n",
                                    )
                        else:
                            if content == screenshot_img:
                                img_info = (
                                    "[Screenshot saved as"
                                    f"{screenshot_filename}]"
                                )
                                f.write(f"  Content: {img_info}\n")
                            else:
                                f.write(f"  Content: {str(content)}\n")
                    f.write("\n")

            result = "THOUGHT: " + vision_model.call(vl_messages)

        elif self.mode == "pc_use":
            try:
                m_name = "pre-gui_owl_7b"
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "data",
                                "data": {
                                    "messages": [
                                        {"image": screenshot_oss_url},
                                        {"instruction": self.user_instruction},
                                        {"session_id": self.session_id},
                                        {
                                            "device_type": "pc",
                                        },
                                        {
                                            "pipeline_type": "agent",
                                        },
                                        {
                                            "model_name": m_name,
                                        },
                                        {"thought_language": "chinese"},
                                        {
                                            "param_list": [
                                                {"add_info": self.add_info},
                                                {"a11y": ""},
                                                {"use_a11y": -1},
                                                {"enable_reflector": True},
                                                {"enable_notetaker": True},
                                                {"worker_model": m_name},
                                                {"manager_model": m_name},
                                                {
                                                    "reflector_model": m_name,
                                                },
                                                {
                                                    "notetaker_model": m_name,
                                                },
                                            ],
                                        },
                                    ],
                                },
                            },
                        ],
                    },
                ]

                mode_response = asyncio.run(gui_agent.arun(messages, "pc_use"))

                action = mode_response.action
                action_params = mode_response.action_params
                result = (
                    "Thought: "
                    + mode_response.thought
                    + "\n\nAction: "
                    + action
                    + "\n\nAction Params: "
                    + str(action_params)
                )
                self.session_id = mode_response.session_id
                auxiliary_info["request_id"] = mode_response.request_id

                # 为click类型的动作生成标注图片
                if action in ["click", "right click"]:
                    try:
                        if "position" in action_params:
                            point_x = action_params["position"][0]
                            point_y = action_params["position"][1]
                            _, img_path = self.annotate_image(
                                [point_x, point_y],
                                is_save=True,
                            )
                            auxiliary_info["annotated_img_path"] = img_path
                    except Exception as e:
                        logger.log(
                            f"Error generating annotated image: {e}",
                            "red",
                        )

            except Exception as e:
                logger.log(f"Error querying PC use model: {e}", "red")
                raise RuntimeError(f"Error querying PC use model: {e}")
        else:
            raise ValueError(
                f"Invalid mode: {self.mode},"
                "must be one of: [qwen_vl, pc_use]",
            )

        # Debug: save vision_model response
        if is_debug and debug_file_path:
            with open(debug_file_path, "a", encoding="utf-8") as f:
                f.write("VISION_MODEL RESPONSE:\n")
                f.write(f"{result}\n")
                f.write("=" * 50 + "\n\n")

        return result, auxiliary_info

    def run(self, instruction: str, is_debug=False):
        try:
            while not self._is_cancelled:
                self.messages.append(Message(f"OBJECTIVE: {instruction}"))
                self.user_instruction = instruction
                logger.log(f"USER: {instruction}", print=False)

                if self.mode == "pc_use":
                    self.session_id = ""

                # 发射任务开始状态
                self.emit_status(
                    "TASK",
                    {"message": "task=" + instruction + ", mode=" + self.mode},
                )

                # Setup debug file path if debug mode is enabled
                debug_file_path = None
                if is_debug:
                    debug_file_path = os.path.join(self.tmp_dir, "debug.txt")
                    # Create or clear the debug file
                    with open(debug_file_path, "w", encoding="utf-8") as f:
                        f.write(
                            f"DEBUG LOG - Started at "
                            f"{datetime.datetime.now()}\n",
                        )
                        f.write(f"OBJECTIVE: {instruction}\n")
                        f.write("=" * 80 + "\n\n")

                should_continue = True
                step_count = 0
                while should_continue and step_count < self.max_steps:
                    if self._is_cancelled:
                        break
                    step_count += 1
                    step_info = {
                        "step": step_count,
                        "auxiliary_info": {},
                        "observation": "",
                        "action_parsed": "",
                        "action_executed": "",
                    }
                    self.emit_status("STEP", step_info)

                    action_system_prompt = (
                        "You are an intelligent computer-use "
                        "agent that helps users "
                        "accomplish the objective. Every turn"
                        ", user will provide a "
                        "natural-language description of the "
                        "current screen and next "
                        "action to take. Your task is to use "
                        "tool calls to take "
                        "these actions, or use the stop command"
                        " if the objective is "
                        "complete. You are an assistant "
                        "that **must use tools** to "
                        "answer questions when possible. "
                        "Do not answer directly "
                        "unless no tools are available."
                    )

                    screenshot_analysis, auxiliary_info = (
                        self.analyse_screenshot(
                            is_debug,
                            debug_file_path,
                        )
                    )
                    step_info["observation"] = screenshot_analysis
                    if auxiliary_info:
                        step_info["auxiliary_info"].update(auxiliary_info)
                    self.emit_status("STEP", step_info)

                    action_messages = [
                        Message(action_system_prompt, role="system"),
                        *self.messages,
                        Message(
                            logger.log(
                                f"{screenshot_analysis}",
                                "green",
                            ),
                            role="user",
                        ),
                    ]

                    # Debug: save action_model request
                    if is_debug and debug_file_path:
                        with open(debug_file_path, "a", encoding="utf-8") as f:
                            f.write(f"\n{'=' * 50}\n")
                            f.write(
                                f"ACTION_MODEL REQUEST - "
                                f"{datetime.datetime.now()}\n",
                            )
                            f.write("=" * 50 + "\n")
                            for i, msg in enumerate(action_messages):
                                role = msg.get("role", "user")
                                f.write(f"Message {i + 1} (role: {role}):\n")
                                content = msg.get("content", msg)
                                content_str = str(content)
                                truncated = (
                                    content_str[:1000] + "..."
                                    if len(content_str) > 1000
                                    else content_str
                                )
                                f.write(f"  Content: {truncated}\n")
                            tools_list = list(self.tools.keys())
                            f.write(f"\nTools available: {tools_list}\n\n")

                    content, tool_calls = action_model.call(
                        action_messages,
                        self.tools,
                    )

                    # Debug: save action_model response
                    if is_debug and debug_file_path:
                        with open(debug_file_path, "a", encoding="utf-8") as f:
                            f.write("ACTION_MODEL RESPONSE:\n")
                            f.write(f"Content: {content}\n")
                            f.write(f"Tool calls: {tool_calls}\n")
                            f.write("=" * 50 + "\n\n")

                    if content:
                        self.messages.append(
                            Message(logger.log(f"THOUGHT: {content}", "blue")),
                        )

                    should_continue = False
                    for tool_call in tool_calls:
                        if self._is_cancelled:
                            break
                        name, parameters = tool_call.get(
                            "name",
                        ), tool_call.get(
                            "parameters",
                        )
                        should_continue = name != "stop"
                        if not should_continue:
                            # 发射任务完成状态
                            self.emit_status(
                                "TASK",
                                {
                                    "total_steps": step_count,
                                    "instruction": instruction,
                                },
                            )
                            break

                        # 发射动作执行开始状态
                        step_info["action_parsed"] = (
                            f"Action: {name} Params: {str(parameters)}"
                        )

                        self.emit_status("STEP", step_info)

                        # Print the tool-call in an easily readable format
                        logger.log(f"ACTION: {name} {str(parameters)}", "red")
                        # format used by the model
                        self.messages.append(Message(json.dumps(tool_call)))
                        step_info["human_help_status"] = False
                        if name == HUMAN_HELP_ACTION:
                            import time

                            time_to_sleep = os.getenv("HUMAN_WAIT_TIME", 15)
                            task = parameters.get("task", "")
                            logger.log(
                                "HUMAN_HELP: The system will waited "
                                f"for {time_to_sleep} "
                                f"seconds for human to do the task: {task}",
                            )
                            step_info["action_executed"] = (
                                f"The system will waited for {time_to_sleep} "
                                f"seconds for human to do the task:\n\n {task}"
                            )
                            if not self._interrupted:
                                step_info["human_help_status"] = True
                            self.emit_status("STEP", step_info)
                            # 可中断等待
                            start_time = time.time()
                            waited_time = 0
                            sleep_interval = min(
                                5,
                                time_to_sleep,
                            )  # 每次最多等待5秒

                            # 重置中断标志
                            self._interrupted = False

                            # 可中断的等待循环
                            while (
                                waited_time < time_to_sleep
                                and not self._interrupted
                            ):
                                time.sleep(
                                    min(
                                        sleep_interval,
                                        time_to_sleep - waited_time,
                                    ),
                                )
                                waited_time = time.time() - start_time

                            if self._interrupted:
                                logger.log(
                                    "Human help wait was interrupted by user.",
                                    "yellow",
                                )
                                self._interrupted = False  # 重置标志

                            else:
                                logger.log(
                                    "Human help wait completed.",
                                    "yellow",
                                )

                            break
                        try:
                            result = self.call_function(name, parameters)
                        except Exception as e:
                            result = ""
                            logger.log(
                                f"Error executing function:{e},{result}",
                                "red",
                            )
                            continue

                        # 发射动作执行完成状态
                        step_info["action_executed"] = result

                        self.emit_status("STEP", step_info)

                        self.messages.append(
                            Message(
                                logger.log(f"OBSERVATION: {result}", "yellow"),
                            ),
                        )
                if self._is_cancelled:
                    print("✅ Task canceled")
                    break
                elif not should_continue:
                    print("✅ Task completed")
                    break
                elif step_count >= self.max_steps:
                    print("✅ Task out max step, stop")
                    break

        except Exception as e:
            logger.log(f"Error in agent run: {e}")
        finally:
            logger.log("Agent run loop exited.")
