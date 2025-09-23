# -*- coding: utf-8 -*-
import streamlit as st
import httpx
import requests
import json
import time
import os
from typing import Dict, Any


def build_backend_url(path):
    return os.environ.get(
        "BACKEND_URL",
        "http://localhost:8002/",
    ) + path.lstrip("/")


BACKEND_SSE_URL = build_backend_url("sse/status")


def clear_frontend_state():
    """清空前端状态，重置到运行任务前的初始状态"""
    st.session_state.messages = []
    st.session_state.sandbox_url = None
    st.session_state.is_loading = False
    st.session_state.task_running = False
    st.session_state.sse_running = False
    st.session_state.step_states = {}
    st.session_state.processed_messages = set()
    st.session_state.sse_messages = []
    st.session_state.last_status_check = 0
    st.session_state.last_sse_check = 0
    st.session_state.sse_connection_id = None
    st.session_state.raw_sse_messages = ""
    print("[Frontend] All states cleared and reset")


# 页面配置
st.set_page_config(
    page_title="Computer Use Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 简化的CSS样式
st.markdown(
    """
<style>
.main { padding-top: 0.5rem; }
.stApp > header { background-color: transparent; }
.stApp { margin-top: -80px; }
.header-title {
    color: #2c3e50;
    text-align: center;
    font-weight: 600;
    margin-bottom: 1rem;
    padding-top: 0.5rem;
}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
""",
    unsafe_allow_html=True,
)

# 初始化session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "sandbox_url" not in st.session_state:
    st.session_state.sandbox_url = None
if "equipment_screenshot_url" not in st.session_state:
    st.session_state.equipment_screenshot_url = None
if "equipment_web_url" not in st.session_state:
    st.session_state.equipment_web_url = None
if "equipment_web_sdk_info" not in st.session_state:
    st.session_state.equipment_web_sdk_info = None
if "is_loading" not in st.session_state:
    st.session_state.is_loading = False
if "task_running" not in st.session_state:
    st.session_state.task_running = False
if "last_status_check" not in st.session_state:
    st.session_state.last_status_check = 0
if "raw_sse_messages" not in st.session_state:
    st.session_state.raw_sse_messages = ""

# 主标题
st.markdown(
    '<h1 class="header-title">🤖 Computer Use Agent</h1>',
    unsafe_allow_html=True,
)

# 配置选项
with st.expander("⚙️ 任务配置", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        mode = st.selectbox(
            "模式选择",
            [
                "qwen_vl",
                "pc_use",
            ],
            index=0,
        )
        sandbox_type = st.selectbox(
            "Sandbox",
            [
                "e2b-desktop",
            ],
            index=0,
        )
    with col2:
        max_steps = st.number_input(
            "最大步数",
            min_value=1,
            max_value=100,
            value=10,
        )
        pc_use_addon_info = st.text_input(
            "补充信息",
            placeholder="请输出PC_USE模型补充信息",
        )

# 创建双栏布局
left_col, right_col = st.columns([1, 1], gap="large")

# 左侧聊天界面
with left_col:
    st.markdown("### 💬 聊天界面")

    # 聊天容器
    chat_container = st.container(height=560)

    with chat_container:
        # 欢迎信息
        if not st.session_state.messages and not st.session_state.is_loading:
            st.info(
                """
            👋 **欢迎使用Computer Use Agent！**

            请在下方输入您想要执行的任务。

            **示例任务：**
            - use the web browser to get the current weather
            in Hangzhou via Bing Search
            """,
            )

        # 显示聊天历史
        for message in st.session_state.messages:
            if message["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    st.write(message["content"])
            else:
                avatar = "📊" if message.get("type") == "status" else "🤖"
                with st.chat_message("assistant", avatar=avatar):
                    st.markdown(message["content"], unsafe_allow_html=True)

                    # 如果消息包含图片路径，显示图片
                    if message.get("image_path"):
                        img_path = message["image_path"]
                        try:
                            # 直接使用 st.image 显示图片，支持 URL
                            st.image(
                                img_path,
                                caption="动作可视化",
                                width=400,  # 限制图片宽度为400像素以提高性能
                            )
                        except Exception as e:
                            st.error(f"无法显示图片: {img_path} - {e}")

        # 显示加载状态
        if st.session_state.is_loading:
            with st.chat_message("assistant", avatar="🤖"):
                st.info("🔄 正在处理任务...")

    # 输入框和按钮
    with st.form(key="chat_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            user_input = st.text_input(
                "输入您的任务...",
                placeholder="",
                label_visibility="collapsed",
            )

        with col2:
            submit_button = st.form_submit_button(
                "发送",
                use_container_width=True,
                disabled=st.session_state.is_loading
                or st.session_state.task_running,
            )
        with col3:
            clear_button = st.form_submit_button(
                "清空",
                use_container_width=True,
                disabled=st.session_state.is_loading
                or st.session_state.task_running,
            )

# 右侧预览界面
with right_col:
    st.markdown("### 🖥️ Sandbox预览")
    # Sandbox预览
    if st.session_state.sandbox_url:
        st.markdown(
            f"""
        <iframe
            src="{st.session_state.sandbox_url}"
            width="100%"
            height="560"
            frameborder="0"
            style="border-radius: 10px; border: 1px solid #e9ecef;">
        </iframe>
        """,
            unsafe_allow_html=True,
        )
    else:
        print("设备 未打开")
        st.markdown(
            """
        <div style="display: flex; align-items: center;
          justify-content: center;
          flex-direction: column; color: #6c757d; height: 560px;
          border: 1px solid #e9ecef; border-radius: 10px;
          background-color: #f8f9fa;">
            <div style="font-size: 4rem;
            margin-bottom: 1rem;">🖥️</div>
            <h3>等待Sandbox启动</h3>
            <p>请在左侧输入任务以启动Computer Use Agent</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # 控制按钮
    if st.session_state.task_running:
        if st.button("⏹️ 停止任务", use_container_width=True):
            try:
                response = requests.post(
                    f'{build_backend_url("cua/stop")}',
                    timeout=5,
                )
                if response.status_code == 200:
                    # 使用统一的清空函数
                    clear_frontend_state()
                    st.rerun()
            except Exception as e:
                st.error(f"停止任务失败: {e}")
                # 即使停止失败也清空状态
                clear_frontend_state()

# 添加SSE连接状态控制
if "sse_running" not in st.session_state:
    st.session_state.sse_running = False
if "sse_messages" not in st.session_state:
    st.session_state.sse_messages = []
# 添加步骤状态跟踪
if "step_states" not in st.session_state:
    st.session_state.step_states = {}  # 跟踪每个步骤的状态


def listen_sse(url: str):
    """
    一个生成器：持续 yield 从 SSE 收到的字典。
    只解析 'data: ...\\n' 行，忽略 event/heartbeat 等其他行。
    """
    with httpx.stream("GET", url, timeout=None) as resp:
        for raw in resp.iter_lines():
            if raw.startswith("data: "):
                try:
                    yield json.loads(raw[6:])  # 去掉前缀 b"data: "
                except json.JSONDecodeError:
                    continue


def safe_strip(value):
    """安全的字符串strip方法，处理None和非字符串类型"""
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            return str(value).strip() if str(value) else ""
        except:
            return ""
    return value.strip()


def safe_get(data, key, default=""):
    """安全获取字典值并转换为字符串"""
    if not isinstance(data, dict):
        return default
    value = data.get(key, default)
    return str(value) if value is not None else default


def format_status_message(status_data: Dict[str, Any]) -> str:
    """格式化状态消息，支持多种消息类型"""
    try:
        # 处理心跳消息
        _type = status_data.get("type", "")
        _status = status_data.get("status", "")
        if _type == "heartbeat" or _status == "idle":
            return None  # 不显示心跳消息和IDLE消息

        # 处理步骤类型消息
        if _type == "STEP":
            timestamp = status_data.get("timestamp", "")
            step_data = status_data.get("data", {})
            step_num = step_data.get("step", "?")
            observation = step_data.get("observation", "")
            action_parsed = step_data.get("action_parsed", "")
            action_executed = step_data.get("action_executed", "")
            auxiliary_info = step_data.get("auxiliary_info", {})

            # 生成步骤的唯一标识符，包含任务ID以避免冲突
            task_id = status_data.get("task_id", "unknown")
            step_key = f"task_{task_id}_step_{step_num}"

            # 安全的字符串处理函数
            def safe_strip_local(value):
                if value is None:
                    return ""
                if not isinstance(value, str):
                    try:
                        return str(value).strip() if str(value) else ""
                    except:
                        return ""
                return value.strip()

            # 获取之前的步骤状态
            previous_state = st.session_state.step_states.get(step_key, {})

            # 检查当前消息是否有新内容 - 使用安全的字符串处理
            current_state = {
                "observation": safe_strip_local(observation),
                "action_parsed": safe_strip_local(action_parsed),
                "action_executed": safe_strip_local(action_executed),
                "request_id": safe_get(auxiliary_info, "request_id", ""),
                "annotated_img_path": safe_get(auxiliary_info, "annotated_img_path", ""),
            }

            screenshot_url = step_data.get("screenshot_url", "")
            if screenshot_url:
                current_state["screenshot_url"] = str(screenshot_url)

            # 如果状态没有变化，返回None（不渲染）
            if previous_state == current_state:
                return None

            # 更新步骤状态
            st.session_state.step_states[step_key] = current_state

            # 构建完整的步骤消息
            message_parts = [f"🔍 **Step {step_num}** - {timestamp}"]

            if current_state["request_id"]:
                message_parts.append(
                    f"\n📝 **请求ID**\n\n {current_state['request_id']}",
                )

            if current_state["observation"]:
                message_parts.append(
                    f"\n🔍 **推理**\n\n {current_state['observation']}",
                )

            if current_state["action_parsed"]:
                message_parts.append(
                    f"\n⚡ **动作**\n\n {current_state['action_parsed']}",
                )

            if current_state["action_executed"]:
                message_parts.append(
                    f"\n✅ **执行**\n\n {current_state['action_executed']}",
                )

            # 检查是否有标注图片路径
            result_message = "\n".join(message_parts)

            # 如果有标注图片路径，添加到消息中
            if current_state["annotated_img_path"]:
                # 将图片路径信息返回，供上层处理
                return {
                    "content": result_message,
                    "image_path": current_state["annotated_img_path"],
                    "step_key": step_key,  # 添加步骤标识符用于消息替换
                }

            # 如果有截图 URL，返回供上层处理
            if screenshot_url:
                return {
                    "content": result_message,
                    "screenshot_url": screenshot_url,
                    "step_key": step_key,
                }

            return {
                "content": result_message,
                "step_key": step_key,  # 添加步骤标识符用于消息替换
            }

        # 处理任务类型消息
        elif _type == "TASK":
            message = safe_get(status_data.get("data", {}), "message", "")
            return f"🎯 **TASK**: {message}"

        # 处理标准状态消息
        else:
            message = status_data.get("message", "")

            # 状态图标映射
            status_icons = {
                "starting": "🔄",
                "running": "⚡",
                "completed": "✅",
                "error": "❌",
                "stopped": "⏹️",
                "idle": "⏸️",
            }

            icon = status_icons.get(_status, "📋")
            formatted_message = f"{icon} **{_status.upper()}**: {message}"

            return formatted_message

    except Exception as e:
        print(f"[ERROR] Error formatting status message: {e}")
        print(f"[ERROR] Status data: {status_data}")
        # 返回一个安全的错误消息
        return f"⚠️ **MESSAGE PARSE ERROR**: {str(e)}"


def update_or_add_step_message(status_message, msg_id):
    """更新或添加步骤消息，避免重复"""
    try:
        if isinstance(status_message, dict) and "step_key" in status_message:
            step_key = status_message["step_key"]

            # 查找是否已经存在相同步骤的消息
            message_index = None
            for i, msg in enumerate(st.session_state.messages):
                if msg.get("type") == "status" and msg.get("step_key") == step_key:
                    message_index = i
                    break

            # 构建新的消息对象
            new_message = {
                "role": "assistant",
                "content": status_message["content"],
                "type": "status",
                "step_key": step_key,
                "msg_id": msg_id,
            }

            # 如果有图片路径，添加图片路径
            if "image_path" in status_message:
                new_message["image_path"] = status_message["image_path"]

            # 如果找到了相同步骤的消息，替换它
            if message_index is not None:
                st.session_state.messages[message_index] = new_message
            else:
                # 否则添加新消息
                st.session_state.messages.append(new_message)

            # 如果包含 screenshot_url，更新 session_state
            if "screenshot_url" in status_message:
                st.session_state.equipment_screenshot_url = status_message[
                    "screenshot_url"
                ]

            if "equipment_web_url" in status_message:
                st.session_state.equipment_web_url = status_message[
                    "equipment_web_url"
                ]

        else:
            # 非步骤消息，直接添加
            if isinstance(status_message, dict):
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": status_message["content"],
                        "type": "status",
                        "image_path": status_message.get("image_path"),
                        "msg_id": msg_id,
                    },
                )
                # 如果包含 screenshot_url，更新 session_state
                if "screenshot_url" in status_message:
                    st.session_state.equipment_screenshot_url = status_message[
                        "screenshot_url"
                    ]

                if "equipment_web_url" in status_message:
                    st.session_state.equipment_web_url = status_message[
                        "equipment_web_url"
                    ]

            else:
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": str(status_message) if status_message is not None else "Unknown message",
                        "type": "status",
                        "msg_id": msg_id,
                    },
                )
    except Exception as e:
        print(f"[ERROR] Error updating step message: {e}")
        # 添加一个错误消息，避免完全失败
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"⚠️ **MESSAGE UPDATE ERROR**: {str(e)}",
                "type": "status",
                "msg_id": msg_id,
            },
        )


# 添加消息去重和连接管理
if "sse_connection_id" not in st.session_state:
    st.session_state.sse_connection_id = None
if "processed_messages" not in st.session_state:
    st.session_state.processed_messages = set()
if "last_sse_check" not in st.session_state:
    st.session_state.last_sse_check = 0

# SSE消息处理 - 优化版本，避免重复渲染
if st.session_state.sse_running:
    current_time = time.time()

    # 控制SSE检查频率，避免过于频繁的请求
    if current_time - st.session_state.last_sse_check >= 1:  # 每1秒检查一次
        st.session_state.last_sse_check = current_time

        try:
            # 使用短时间的超时来避免阻塞
            with httpx.stream("GET", BACKEND_SSE_URL, timeout=1.0) as resp:
                messages_received = 0
                max_messages_per_check = 10  # 每次最多处理10条消息

                for raw in resp.iter_lines():
                    if messages_received >= max_messages_per_check:
                        break

                    if raw.startswith("data: "):
                        try:
                            msg = json.loads(raw[6:])
                            print("SSE msg: ", msg)

                            # 使用后台提供的UUID作为消息唯一标识符
                            msg_id = msg.get("uuid")

                            # 如果没有UUID，则使用备用方案
                            if not msg_id:
                                msg_type = msg.get("type", "unknown")
                                msg_status = msg.get("status", "unknown")
                                msg_timestamp = msg.get(
                                    "timestamp",
                                    current_time,
                                )
                                msg_id = (
                                    f"{msg_type}_{msg_status}_{msg_timestamp}"
                                )
                                print(
                                    "[SSE] Warning: No UUID found in message, "
                                    f"using fallback ID: {msg_id}",
                                )

                            # 检查消息是否已处理过
                            if msg_id in st.session_state.processed_messages:
                                print(
                                    "[SSE] Skipping duplicate message"
                                    f" (UUID: {msg_id})",
                                )
                                continue

                            st.session_state.processed_messages.add(msg_id)
                            print(
                                f"[SSE] Processing new message (UUID:{msg_id},"
                                f" Type: {msg.get('type', 'unknown')})",
                            )

                            # 防止processed_messages集合过大，定期清理
                            if len(st.session_state.processed_messages) > 1000:
                                # 保留最近的500条消息ID
                                recent_messages = list(
                                    st.session_state.processed_messages,
                                )[-500:]
                                st.session_state.processed_messages = set(
                                    recent_messages,
                                )
                                print("[SSE] Cleaned up old message IDs")

                            messages_received += 1

                            status = msg.get("status")
                            message_content = msg.get("message", "")

                            # 特殊处理：如果收到IDLE状态且消息是"Ready to start"，说明任务已完成
                            if (
                                status == "idle"
                                and "ready to start" in str(message_content).lower()
                            ):
                                print(
                                    "[SSE] Task completed, "
                                    "received IDLE ready signal",
                                )

                                # 停止SSE监控
                                st.session_state.sse_running = False
                                st.session_state.task_running = False

                                # 添加任务完成消息
                                st.session_state.messages.append(
                                    {
                                        "role": "assistant",
                                        "content": "✅ 任务执行完成",
                                        "type": "status",
                                    },
                                )

                                # 重置前端状态
                                st.session_state.is_loading = False

                                print("[SSE] Frontend state reset to ready")
                                break

                            # 处理其他消息并添加到聊天记录
                            status_message = format_status_message(msg)
                            if status_message:
                                # 使用新的消息更新函数，避免重复渲染
                                update_or_add_step_message(
                                    status_message,
                                    msg_id,
                                )

                            # 收到其他结束态也停止监控
                            if status in {"completed", "error", "stopped"}:
                                st.session_state.sse_running = False
                                st.session_state.task_running = False

                                # 添加结束消息
                                end_message = (
                                    "✅ 任务已完成"
                                    if status == "completed"
                                    else f"⏹️ 任务已停止 ({status})"
                                )
                                st.session_state.messages.append(
                                    {
                                        "role": "assistant",
                                        "content": end_message,
                                        "type": "status",
                                    },
                                )
                                break

                        except json.JSONDecodeError as e:
                            print(f"[SSE] JSON decode error: {e}")
                            continue
                        except Exception as e:
                            print(f"[SSE] Error processing message: {e}")
                            continue

                # 如果有新消息，才重新渲染
                if messages_received > 0:
                    st.rerun()

        except Exception as e:
            print(f"[SSE] Connection error: {e}")
            # 不立即停止，等待下次重试

    # 显示SSE状态
    if st.session_state.sse_running:
        st.info("🔄 正在监控任务状态...")
        # 使用定时器继续检查
        time.sleep(0.1)
        st.rerun()

# 处理清空按钮
if (
    clear_button
    and not st.session_state.is_loading
    and not st.session_state.task_running
):
    try:
        response = requests.post(
            f'{build_backend_url("cua/stop")}',
            timeout=5,
        )
        if response.status_code == 200:
            # 使用统一的清空函数
            clear_frontend_state()
            st.rerun()
    except Exception as e:
        st.error(f"停止任务失败: {e}")
        # 即使停止失败也清空状态
        clear_frontend_state()
        st.rerun()
    clear_frontend_state()
    st.rerun()


# 处理用户输入
if (
    submit_button
    and user_input
    and not st.session_state.is_loading
    and not st.session_state.task_running
):
    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.is_loading = True
    st.rerun()

# 调用API处理任务
if st.session_state.is_loading:
    try:
        # 准备API请求
        messages_for_api = []
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                messages_for_api.append(
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": msg["content"]}],
                    },
                )
        static_url = os.environ.get("PUBLIC_URL", "http://localhost:8001/")
        print(f"static_url{static_url}")
        # 准备配置参数
        config = {
            "mode": mode,
            "sandbox_type": sandbox_type,
            "max_steps": max_steps,
            "pc_use_addon_info": pc_use_addon_info,
            "timeout": 360,  # 默认超时时间
            "static_url": static_url,
        }

        # 调用后端API，包含配置参数
        response = requests.post(
            f'{build_backend_url("cua/run")}',
            # f"{BACKEND_URL}cua/run",
            json={
                "messages": messages_for_api,
                "config": config,
            },
            timeout=360,
        )

        if response.status_code == 200:
            result = response.json()
            print(result)

            # 更新状态
            st.session_state.sandbox_url = result.get("sandbox_url")
            st.session_state.equipment_web_url = result.get(
                "equipment_web_url",
            )
            st.session_state.equipment_web_sdk_info = result.get(
                "equipment_web_sdk_info",
            )
            st.session_state.task_running = True
            st.session_state.sse_running = True  # 启动SSE监控

            # 重置SSE状态
            st.session_state.processed_messages = set()  # 清空已处理消息
            st.session_state.last_sse_check = 0  # 重置检查时间
            st.session_state.step_states = {}  # 重置步骤状态跟踪
            print(
                "[SSE] Reset processed messages and step states for new task",
            )

            # 添加启动消息
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "✅ 任务已启动！\n\n"
                        f"**任务ID**: {result.get('task_id', 'Unknown')}\n\n"
                        "🔗 开始监控任务状态..."
                    ),
                },
            )

            st.session_state.is_loading = False
            st.rerun()

        else:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"❌ 任务启动失败: HTTP {response.status_code}",
                },
            )
            st.session_state.is_loading = False
            st.rerun()

    except Exception as e:
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"❌ 连接错误: {str(e)}",
            },
        )
        st.session_state.is_loading = False
        st.rerun()