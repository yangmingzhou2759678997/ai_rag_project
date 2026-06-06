# 文件路径: web_ui.py
import streamlit as st
import httpx
from httpx_sse import EventSource
import json
import uuid
import time

# ====================== 全局配置 ======================
BACKEND_BASE_URL = "http://localhost:8000"
st.set_page_config(
    page_title="AI RAG 智能助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ====================== 会话名称缓存工具 ======================
def get_session_name(session_id: str) -> str:
    """从本地缓存获取会话友好名称（纯文本，无ID后缀）"""
    cache_key = f"session_name_{session_id}"
    return st.session_state.get(cache_key, "新会话")


def save_session_name(session_id: str, name: str):
    """将会话友好名称保存到本地缓存"""
    cache_key = f"session_name_{session_id}"
    st.session_state[cache_key] = name


# ====================== 会话状态初始化 ======================
if "token" not in st.session_state:
    st.session_state.token = None
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "sessions" not in st.session_state:
    st.session_state.sessions = []
if "username" not in st.session_state:
    st.session_state.username = None
if "is_streaming" not in st.session_state:
    st.session_state.is_streaming = False


# ====================== API 调用函数 ======================
def login(username: str, password: str) -> bool:
    try:
        response = httpx.post(
            f"{BACKEND_BASE_URL}/api/auth/login",
            data={"username": username, "password": password},
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        st.session_state.token = data["access_token"]
        st.session_state.username = username
        get_sessions()
        return True
    except Exception as e:
        st.error(f"登录失败: {str(e)}")
        return False


def register(username: str, password: str) -> bool:
    try:
        response = httpx.post(
            f"{BACKEND_BASE_URL}/api/auth/register",
            json={"username": username, "password": password},
            timeout=10.0
        )
        response.raise_for_status()
        st.success("注册成功！请登录")
        return True
    except Exception as e:
        st.error(f"注册失败: {str(e)}")
        return False


def get_sessions() -> list:
    if not st.session_state.token:
        return []
    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = httpx.get(
            f"{BACKEND_BASE_URL}/api/chat/sessions",
            headers=headers,
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        st.session_state.sessions = data["data"]
        return data["data"]
    except Exception as e:
        st.error(f"获取会话列表失败: {str(e)}")
        return []


def get_chat_history(session_id: str) -> list:
    if not st.session_state.token:
        return []
    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = httpx.get(
            f"{BACKEND_BASE_URL}/api/chat/history/{session_id}",
            headers=headers,
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        st.session_state.chat_history = data["data"]

        # 自动生成并缓存会话名称（纯文本，无ID后缀）
        if data["data"]:
            first_user_msg = next((msg["content"][:12] for msg in data["data"] if msg["role"] == "user"), "新会话")
            # 超过12字加省略号
            session_name = first_user_msg + "..." if len(first_user_msg) >= 12 else first_user_msg
            save_session_name(session_id, session_name)

        return data["data"]
    except Exception as e:
        st.error(f"获取历史记录失败: {str(e)}")
        return []


# 新增：删除会话API
def delete_session(session_id: str) -> bool:
    if not st.session_state.token:
        return False
    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = httpx.delete(
            f"{BACKEND_BASE_URL}/api/chat/sessions/{session_id}",
            headers=headers,
            timeout=10.0
        )
        response.raise_for_status()
        # 删除本地缓存的会话名称
        cache_key = f"session_name_{session_id}"
        if cache_key in st.session_state:
            del st.session_state[cache_key]
        st.success("会话删除成功")
        return True
    except Exception as e:
        st.error(f"删除会话失败: {str(e)}")
        return False


def send_message_stream(query: str, session_id: str, temperature: float = 0.1):
    """工业级防崩溃流式响应函数"""
    headers = {
        "Authorization": f"Bearer {st.session_state.token}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
        "session_id": session_id,
        "temperature": temperature
    }

    try:
        with httpx.Client(timeout=None) as client:
            with client.stream("POST", f"{BACKEND_BASE_URL}/api/chat/completions", headers=headers,
                               json=payload) as response:

                # 先检查状态码，非200直接返回错误
                if response.status_code != 200:
                    response.read()
                    try:
                        err_msg = response.json().get("msg", response.text)
                    except:
                        err_msg = response.text
                    yield f"❌ **后端错误 (状态码 {response.status_code})**：\n\n{err_msg}"
                    return

                # 确认是200后再解析SSE流
                event_source = EventSource(response)
                buffer = ""
                last_update = time.time()
                update_interval = 0.1  # 100ms更新一次，平衡流畅度和稳定性

                for event in event_source.iter_sse():
                    if event.data == "[DONE]":
                        break
                    try:
                        data = json.loads(event.data)
                        if "content" in data:
                            buffer += data["content"]
                            current_time = time.time()
                            if current_time - last_update >= update_interval:
                                yield buffer
                                last_update = current_time
                    except json.JSONDecodeError:
                        continue

                # 最后发送剩余内容
                if buffer:
                    yield buffer

    except httpx.ConnectError:
        yield "❌ **无法连接到后端服务器**\n\n请确认后端服务已启动：`uvicorn main:app --reload`"
    except Exception as e:
        yield f"❌ **前端异常**：\n\n{str(e)}"


# ====================== 侧边栏：登录与会话管理 ======================
with st.sidebar:
    st.title("🤖 AI RAG 智能助手")

    if not st.session_state.token:
        tab1, tab2 = st.tabs(["登录", "注册"])

        with tab1:
            login_username = st.text_input("用户名", key="login_username")
            login_password = st.text_input("密码", type="password", key="login_password")
            if st.button("登录", type="primary", use_container_width=True):
                if login(login_username, login_password):
                    st.rerun()

        with tab2:
            reg_username = st.text_input("用户名", key="reg_username")
            reg_password = st.text_input("密码", type="password", key="reg_password")
            reg_confirm = st.text_input("确认密码", type="password", key="reg_confirm")
            if st.button("注册", use_container_width=True):
                if reg_password != reg_confirm:
                    st.error("两次输入的密码不一致")
                elif len(reg_password) < 6:
                    st.error("密码长度至少6位")
                else:
                    register(reg_username, reg_password)
    else:
        st.success(f"已登录: {st.session_state.username}")

        if st.button("➕ 新建会话", type="primary", use_container_width=True):
            new_session_id = str(uuid.uuid4())
            st.session_state.current_session_id = new_session_id
            st.session_state.chat_history = []
            save_session_name(new_session_id, "新会话")
            st.rerun()

        st.divider()
        st.subheader("历史会话")

        if st.button("🔄 刷新会话列表", use_container_width=True):
            get_sessions()
            st.rerun()

        # 🚨 核心修改：会话列表带删除按钮，纯文本名称
        for session_id in st.session_state.sessions:
            col1, col2 = st.columns([0.85, 0.15])
            session_label = get_session_name(session_id)

            with col1:
                # 会话名称按钮（点击切换会话）
                if st.button(
                        session_label,
                        key=f"goto_{session_id}",
                        use_container_width=True,
                        # 高亮当前会话
                        type="primary" if session_id == st.session_state.current_session_id else "secondary"
                ):
                    st.session_state.current_session_id = session_id
                    get_chat_history(session_id)
                    st.rerun()

            with col2:
                # 删除按钮
                if st.button(
                        "🗑️",
                        key=f"del_{session_id}",
                        use_container_width=True,
                        help="删除此会话"
                ):
                    if delete_session(session_id):
                        # 如果删除的是当前会话，自动创建新会话
                        if session_id == st.session_state.current_session_id:
                            st.session_state.current_session_id = str(uuid.uuid4())
                            st.session_state.chat_history = []
                            save_session_name(st.session_state.current_session_id, "新会话")
                        # 刷新会话列表
                        get_sessions()
                        st.rerun()

        st.divider()
        if st.button("🚪 退出登录", use_container_width=True):
            # 清空所有会话状态，但保留会话名称缓存
            for key in list(st.session_state.keys()):
                if not key.startswith("session_name_"):
                    del st.session_state[key]
            st.rerun()

# ====================== 主界面：聊天窗口 ======================
if not st.session_state.token:
    st.info("👈 请先在左侧登录或注册账号，开始使用AI助手")
    st.image("https://picsum.photos/800/400", use_column_width=True)
else:
    if not st.session_state.current_session_id:
        st.session_state.current_session_id = str(uuid.uuid4())
        st.session_state.chat_history = []
        save_session_name(st.session_state.current_session_id, "新会话")

    st.header(f"💬 当前会话: {get_session_name(st.session_state.current_session_id)}")

    # 固定聊天容器，避免DOM树频繁变化
    chat_container = st.container()

    # 渲染所有历史消息
    with chat_container:
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # 只有在非流式输出状态下才显示输入框
    if not st.session_state.is_streaming:
        if prompt := st.chat_input("输入你的问题..."):
            # 标记为正在流式输出
            st.session_state.is_streaming = True

            # 添加用户消息到历史
            st.session_state.chat_history.append({"role": "user", "content": prompt})

            # 如果是新会话的第一条消息，自动更新会话名称（纯文本）
            if len(st.session_state.chat_history) == 1:
                # 取前12字，超过加省略号
                session_name = prompt[:12] + "..." if len(prompt) >= 12 else prompt
                save_session_name(st.session_state.current_session_id, session_name)

            # 立即渲染用户消息
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

            # 渲染AI回复
            with chat_container:
                with st.chat_message("assistant"):
                    full_response = ""
                    response_placeholder = st.empty()

                    # 流式接收响应
                    for chunk in send_message_stream(
                            prompt,
                            st.session_state.current_session_id,
                            temperature=0.1
                    ):
                        full_response = chunk
                        response_placeholder.markdown(full_response + "▌")

                    # 最终更新（移除光标）
                    response_placeholder.markdown(full_response)

            # 添加AI回复到历史
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})

            # 重置流式状态
            st.session_state.is_streaming = False

            # 温和重绘
            st.rerun()

st.divider()
st.caption("© 2026 AI RAG 智能助手 | 基于 FastAPI + PGVector + Agentic RAG 架构")