# -*- coding: utf-8 -*-
from e2b_desktop import Sandbox
from agentscope_bricks.utils.grounding_utils import (
    perform_gui_grounding_with_api,
)
from typing import Callable
from .sandbox_base import (
    SandboxBase,
    OperationStatus,
)

execute_wait_time_: int = 5


class E2bSandBox(SandboxBase):
    """
    统一控制类，支持 Sandbox、CloudComputer 和 CloudPhone。
    根据传入的设备类型自动选择合适的操作方式。
    """

    def __init__(self, sandbox: Sandbox = None, timeout: int = 120):
        if sandbox:
            self.device = sandbox
        else:
            self.device = Sandbox.create(timeout=timeout)

    def run_command(
        self,
        command: str,
        background: bool = False,
        timeout: int = 5,
        ope_type: str = None,
    ) -> str:
        if background:
            self.device.commands.run(command, background=True)
            return "The command has been started."
        else:
            result = self.device.commands.run(command, timeout=timeout)
            stdout, stderr = result.stdout, result.stderr
            if stdout and stderr:
                return stdout + "\n" + stderr
            elif stdout or stderr:
                return stdout + stderr
            else:
                return "The command finished running."

    def press_key(
        self,
        key: str = None,
        key_combination: list[str] = None,
        ope_type: str = None,
    ) -> str:
        if ope_type == "pca":
            if key and not key_combination:
                self.device.press(key)
                return f"The key {key} has been pressed."
            elif key_combination and not key:
                self.device.press(key_combination)
                return (
                    f"The key combination {key_combination} has been pressed."
                )
            else:
                raise ValueError("Invalid key or key combination")
        else:
            return "The operation have not finished"

    def long_press(self, x: int, y: int, press_time: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    def type_text(self, text: str, ope_type: str = None) -> str:
        self.device.write(
            text,
            chunk_size=50,
            delay_in_ms=12,
        )
        return "The text has been typed."

    def click_element(
        self,
        query: str,
        click_command: Callable,
        action_name: str = "click",
    ) -> str:
        img_bytes = self.device.screenshot()
        position = perform_gui_grounding_with_api(
            min_pixels=4096,
            screenshot=img_bytes,
            user_query=query,
        )
        x, y = position
        self.device.move_mouse(x, y)
        click_command()
        return f"The mouse has {action_name}ed."

    def click(
        self,
        x: int = 0,
        y: int = 0,
        count: int = 1,
        query: str = "",
        action_name: str = "click",
        ope_type: str = None,
        x2: int = 0,
        y2: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> str:
        if ope_type == "pca":
            self.device.move_mouse(x, y)
            if count == 1:
                self.device.left_click()
            elif count == 2:
                self.device.double_click()
            else:
                raise ValueError(
                    f"Invalid count: {count}, only support 1 or 2",
                )

            return f"The mouse has clicked {count} times at ({x}, {y})."
        else:
            if action_name == "click":
                return self.click_element(
                    query,
                    self.device.left_click,
                    action_name,
                )
            elif action_name == "double click":
                return self.click_element(
                    query,
                    self.device.double_click,
                    action_name,
                )
            elif action_name == "right click":
                return self.click_element(
                    query,
                    self.device.right_click,
                    action_name,
                )
            else:
                return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    def right_click(
        self,
        x: int,
        y: int,
        count: int = 1,
        ope_type: str = None,
    ) -> str:
        if ope_type == "pca":
            self.device.move_mouse(x, y)
            self.device.right_click()
            return f"The mouse has right clicked at ({x}, {y})."
        else:
            return "The operation have not finished"

    def click_and_type(
        self,
        x: int,
        y: int,
        text: str,
        ope_type: str = None,
    ) -> str:
        if ope_type == "pca":
            self.device.move_mouse(x, y)
            self.device.left_click()
            self.device.write(text)
            return f"The mouse has clicked and typed the text at ({x}, {y})."
        else:
            return "The operation have not finished"

    def append_text(
        self,
        x: int,
        y: int,
        text: str,
        ope_type: str = None,
    ) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    def launch_app(self, app: str, ope_type: str = None) -> str:
        if ope_type == "pca":
            self.device.launch(app)
            return f"The application {app} has been launched."
        else:
            return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    def go_home(self, action: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    def slide(self, x1: int, y1: int, x2: int, y2: int) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    def back(self, action: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    def menu(self, action: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    def enter(self, action: str) -> str:
        self.device.press("enter")
        return "Enter key has been pressed."

    def kill_front_app(self, action: str) -> str:
        return OperationStatus.DEVICE_UN_SUPPORTED_OPERATION.value

    def execute_wait_time_set(self, execute_wait_time: int = 5) -> str:
        global execute_wait_time_
        execute_wait_time_ = execute_wait_time
        print("set slot time to " + str(execute_wait_time_))
        return "The execute wait time has been set."
