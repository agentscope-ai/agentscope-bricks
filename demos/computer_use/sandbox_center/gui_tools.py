# -*- coding: utf-8 -*-

from agentscope_bricks.base.function_tool import function_tool
from sandbox_center.sandboxes.sandbox_base import (
    SandboxBase,
)

_device: SandboxBase = None


def set_device(device: SandboxBase, execute_wait_time: int = None) -> None:
    """初始化实例

    Args:
        device: like cloud_computer ,cloud_phone, sandbox
        execute_wait_time: execute wait time ,default 5s
        wait_time: wait option cost time
    Returns:

    """

    global _device
    _device = device
    if execute_wait_time:
        _device.execute_wait_time_set(execute_wait_time)


@function_tool
def run_command(command: str) -> str:
    """Run a shell command and return the result.

    Args:
        command: Shell command to run synchronously.

    Returns:
        String containing the command output.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.run_command(command)


@function_tool
def run_background_command(command: str) -> str:
    """Run a shell command in the background.

    Args:
        command: Shell command to run asynchronously.

    Returns:
        String indicating the command has been started.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.run_command(command, background=True)


@function_tool
def send_key(name: str) -> str:
    """Send a key or combination of keys to the system.

    Args:
        name: Key or combination (e.g. 'Return', 'Ctl-C').

    Returns:
        String indicating the key has been pressed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.press_key(name)


@function_tool
def type_text(text: str) -> str:
    """Type a specified text into the system.

    Args:
        text: Text to type.

    Returns:
        String indicating the text has been typed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.type_text(text)


@function_tool
def click(query: str) -> str:
    """Click on a specified UI element.

    Args:
        query: Item or UI element on the screen to click.

    Returns:
        String indicating the mouse has clicked.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.click(query=query, action_name="click")


@function_tool
def double_click(query: str) -> str:
    """Double click on a specified UI element.

    Args:
        query: Item or UI element on the screen to double click.

    Returns:
        String indicating the mouse has double clicked.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.click(query=query, action_name="double click")


@function_tool
def right_click(query: str) -> str:
    """Right click on a specified UI element.

    Args:
        query: Item or UI element on the screen to right click.

    Returns:
        String indicating the mouse has right clicked.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.click(query=query, action_name="right click")


GUI_TOOLS = {
    tool.function_schema.name: tool
    for tool in [
        click,
        double_click,
        right_click,
        type_text,
        run_command,
        run_background_command,
        send_key,
    ]
}

ope_type_pca = "pca"


@function_tool
def pca_click(x: int, y: int, count: int = 1) -> str:
    """Click on a specified position.

    Args:
        x: X coordinate of the position to click.
        y: Y coordinate of the position to click.
        count: Number of times to click.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.click(x=x, y=y, count=count, ope_type=ope_type_pca)


@function_tool
def pca_right_click(x: int, y: int, count: int = 1) -> str:
    """Right click on a specified position.

    Args:
        x: X coordinate of the position to right click.
        y: Y coordinate of the position to right click.
        count: Number of times to right click.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.right_click(x=x, y=y, count=count, ope_type=ope_type_pca)


@function_tool
def pca_click_type(x: int, y: int, text: str) -> str:
    """Click on a specified position and type the text.

    Args:
        x: X coordinate of the position to click.
        y: Y coordinate of the position to click.
        text: Text to type.
    """

    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.click_and_type(x=x, y=y, text=text, ope_type=ope_type_pca)


@function_tool
def pca_press_key(key: str) -> str:
    """Send a key or combination of keys to the system.

    Args:
        key: The key to press (e.g. "enter", "space", "backspace", etc.).

    Returns:
        String indicating the key has been pressed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.press_key(key=key, ope_type=ope_type_pca)


@function_tool
def pca_press_key_combination(key_combination: list[str]) -> str:
    """Send a key or combination of keys to the system.

    Args:
        key_combination:
        The key combination to press (e.g. ["ctrl", "c"]).

    Returns:
        String indicating the key has been pressed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.press_key(
        key_combination=key_combination,
        ope_type=ope_type_pca,
    )


@function_tool
def pca_launch_app(app: str) -> str:
    """Launch an application.

    Args:
        app: The application to launch.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.launch_app(app=app, ope_type=ope_type_pca)


PCA_GUI_TOOLS = {
    tool.function_schema.name: tool
    for tool in [
        pca_click,
        pca_right_click,
        pca_click_type,
        pca_press_key,
        pca_launch_app,
    ]
}


@function_tool
def wy_open_app(name: str) -> str:
    """Open a specified application on the cloud computer.

    Args:
        name: The name or identifier of the application to open.

    Returns:
        String containing the result or output of the operation.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.launch_app(app=name)


@function_tool
def wy_home(action: str) -> str:
    """back desktop.

    Args:
        action: The action name

    Returns:
        String indicating the wait period has completed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.go_home(action=action)


@function_tool
def wy_click(x: int, y: int, count: int = 1) -> str:
    """Click on a specified position.

    Args:
        x: X coordinate of the position to click.
        y: Y coordinate of the position to click.
        count: Number of times to click.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.click(x=x, y=y, count=count)


@function_tool
def wy_right_click(x: int, y: int, count: int = 1) -> str:
    """Click on a specified position.

    Args:
        x: X coordinate of the position to click.
        y: Y coordinate of the position to click.
        count: Number of times to click.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.right_click(x=x, y=y, count=count)


@function_tool
def wy_click_type(x: int, y: int, text: str) -> str:
    """Click on a specified position and type the text.

    Args:
        x: X coordinate of the position to click.
        y: Y coordinate of the position to click.
        text: Text to type.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.click_and_type(x=x, y=y, text=text)


@function_tool
def wy_press_key(key: str) -> str:
    """Send a key or combination of keys to the system.

    Args:
        key: The key to press (e.g. "enter", "space", "backspace", etc.).

    Returns:
        String indicating the key has been pressed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.press_key(key=key)


@function_tool
def wy_append(x: int, y: int, text: str) -> str:
    """Append the content at position and press Enter.

    Args:
        x: X coordinate of the position to click.
        y: Y coordinate of the position to click.
        text: text for input.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.append_text(x, y, text)


WY_GUI_TOOLS = {
    tool.function_schema.name: tool
    for tool in [
        wy_open_app,
        wy_click,
        wy_right_click,
        wy_click_type,
        wy_press_key,
        wy_append,
        wy_home,
    ]
}


@function_tool
def wy_phone_run_command(command: str) -> str:
    """Run a android command and return the result.

    Args:
        command:  command to run synchronously.

    Returns:
        String containing the command output.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.run_command(command)


@function_tool
def wy_phone_click(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    width: int,
    height: int,
) -> str:
    """Click on a specified position.

    Args:
        x1: X coordinate of the position to click.
        y1: Y coordinate of the position to click.
        x2: X coordinate of the position to click.
        y2: Y coordinate of the position to click.
        width: width of the phone size
        height: height of the phone size

    Returns:
        String indicating the mouse has clicked at the given coordinates.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.click(x=x1, y=y1, x2=x2, y2=y2, width=width, height=height)


@function_tool
def wy_phone_long_press(x: int, y: int, press_time: str) -> str:
    """Press and hold a key for a specific duration.

    Args:
        x: X coordinate of the key to press.
        y: Y coordinate of the key to press.
        press_time: Duration (in seconds) to hold the key pressed.

    Returns:
        String indicating the key has been pressed and held.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.long_press(x, y, press_time)


@function_tool
def wy_phone_slide(x1: int, y1: int, x2: int, y2: int) -> str:
    """Slide from one point to another.

    Args:
        x1: Starting X coordinate of the slide.
        y1: Starting Y coordinate of the slide.
        x2: Ending X coordinate of the slide.
        y2: Ending Y coordinate of the slide.

    Returns:
        String indicating the slide action has been performed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.slide(x1, y1, x2, y2)


@function_tool
def wy_phone_type(**kwargs: dict) -> str:
    """Type a specified text using the device keyboard.

    Args:
        kwargs: text for input

    Returns:
        String indicating the text has been typed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")

    # 提取实际文本内容
    if "text" in kwargs:
        text = kwargs["text"]
    elif (
        "properties" in kwargs
        and isinstance(kwargs["properties"], dict)
        and "text" in kwargs["properties"]
    ):
        text = kwargs["properties"]["text"]
    elif "kwargs" in kwargs:
        text = kwargs["kwargs"]
    else:
        # 如果无法识别格式，使用第一个参数或抛出异常
        if kwargs:
            text = str(list(kwargs.values())[0])
        else:
            raise ValueError("No text provided for typing")

    # 如果text本身还是一个字典且包含properties，进一步解析
    if (
        isinstance(text, dict)
        and "properties" in text
        and "text" in text["properties"]
    ):
        actual_text = text["properties"]["text"]
    elif isinstance(text, dict) and "text" in text:
        actual_text = text["text"]
    else:
        actual_text = str(text)

    return _device.type_text(actual_text)


@function_tool
def wy_phone_back(action: str) -> str:
    """Perform the back navigation action.

    Args:
        action: Description of the action being performed.

    Returns:
        String indicating the back action was completed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.back(action)


@function_tool
def wy_phone_home(action: str) -> str:
    """Perform the home button action.

    Args:
        action: Description of the action being performed.

    Returns:
        String indicating the home action was completed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    print(f"Device type: {_device.__class__.__name__}")
    return _device.go_home(action)


@function_tool
def wy_phone_menu(action: str) -> str:
    """Open the device menu.

    Args:
        action: Description of the action being performed.

    Returns:
        String indicating the menu was opened.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.menu(action)


@function_tool
def wy_phone_enter(action: str) -> str:
    """Simulate pressing the Enter key.

    Args:
        action: Description of the action being performed.

    Returns:
        String indicating the enter action was completed.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.enter(action)


@function_tool
def wy_phone_kill_the_front_app(action: str) -> str:
    """Kill the currently running foreground application.

    Args:
        action: Description of the action being performed.

    Returns:
        String indicating the application was terminated.
    """
    if not _device:
        raise RuntimeError("Device instance not set. Call set_device() first.")
    return _device.kill_front_app(action)


WY_PHONE_GUI_TOOLS = {
    tool.function_schema.name: tool
    for tool in [
        wy_phone_run_command,
        wy_phone_click,
        wy_phone_long_press,
        wy_phone_slide,
        wy_phone_type,
        wy_phone_back,
        wy_phone_home,
        wy_phone_menu,
        wy_phone_enter,
        wy_phone_kill_the_front_app,
    ]
}
