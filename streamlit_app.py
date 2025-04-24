import streamlit as st
import asyncio
from app.agent.manus import Manus
from app.logger import logger
import queue
import threading
from datetime import datetime
import sys
import re
from threading import Lock
import time

# Streamlit 配置
st.set_page_config(
    page_title="旅行规划助手",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 确保应用可以被外部访问
if __name__ == "__main__":
    import os
    os.environ['STREAMLIT_SERVER_ADDRESS'] = '0.0.0.0'
    os.environ['STREAMLIT_SERVER_PORT'] = '8501'

# 创建一个队列用于存储模型的输出
output_queue = queue.Queue()
message_queue = queue.Queue()  # 用于存储需要在主线程显示的消息

# 创建一个线程锁
session_lock = Lock()

# 初始化session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'all_history' not in st.session_state:
    st.session_state.all_history = []  # 存储所有历史记录
if 'current_session' not in st.session_state:
    st.session_state.current_session = []  # 存储当前会话的记录
if 'session_count' not in st.session_state:
    st.session_state.session_count = 0
if 'current_session_id' not in st.session_state:
    st.session_state.current_session_id = 0

# 用于在线程间共享会话ID的类
class SessionManager:
    def __init__(self):
        self._session_id = 0
        self._lock = Lock()
    
    def set_session_id(self, session_id):
        with self._lock:
            self._session_id = session_id
    
    def get_session_id(self):
        with self._lock:
            return self._session_id

# 创建会话管理器实例
session_manager = SessionManager()

# 自定义loguru sink
def queue_sink(message):
    record = message.record
    msg_str = str(message)
    
    # 创建基础日志条目
    log_entry = {
        'timestamp': record['time'],
        'level': record['level'].name,
        'raw_message': msg_str,
        'type': 'log',
        'category': 'default',
        'session_id': session_manager.get_session_id()  # 使用会话管理器获取ID
    }
    
    # 处理不同类型的消息
    if "INFO | app.agent.base:run" in msg_str:
        # 捕获执行步骤信息
        step_match = re.search(r'Executing step (\d+)/(\d+)', msg_str)
        if step_match:
            log_entry['category'] = 'step_progress'
            log_entry['current_step'] = step_match.group(1)
            log_entry['total_steps'] = step_match.group(2)
            log_entry['content'] = msg_str  # 保存完整的消息
            
    elif "Activating tool" in msg_str:
        # 捕获工具激活信息
        tool_match = re.search(r"Activating tool: '([^']+)'", msg_str)
        if tool_match:
            log_entry['category'] = 'tool_activation'
            log_entry['tool_name'] = tool_match.group(1)
            log_entry['content'] = msg_str  # 保存完整的消息
            
    elif "executed:" in msg_str:
        # 捕获工具执行结果
        log_entry['category'] = 'tool_result'
        # 尝试提取工具名称
        tool_name_match = re.search(r"(\w+):execute:", msg_str)
        if tool_name_match:
            log_entry['tool_name'] = tool_name_match.group(1)
        log_entry['content'] = msg_str  # 保存完整的消息
        
    elif "✨reasoning_content-BEGIN" in msg_str:
        # 捕获推理过程
        log_entry['category'] = 'reasoning'
        log_entry['content'] = msg_str  # 保存完整的消息
            
    elif "Function-Select-BEGIN" in msg_str:
        # 捕获函数选择过程
        log_entry['category'] = 'tool_selection'
        log_entry['content'] = msg_str  # 保存完整的消息
    
    output_queue.put(log_entry)

async def process_travel_query(prompt, queue):
    agent = Manus()
    logger_id = logger.add(queue_sink, level="INFO")
    try:
        await agent.run(prompt)
    finally:
        logger.remove(logger_id)
        await agent.cleanup()

def run_async_process(prompt, queue):
    asyncio.run(process_travel_query(prompt, queue))

# 创建两列布局用于主要内容区域
left_column, right_column = st.columns([3, 1])

with left_column:
    # 主界面标题
    st.title("🌍 智能旅行规划助手")
    
    st.markdown("""
    这个应用可以帮助你规划旅行，并实时展示AI助手的思考过程。你可以：
    1. 👈 在左侧填写具体的旅行需求
    2. 🔄 或者在下方直接输入自由格式的旅行需求
    3. 💡 或者点击下方的示例查询快速开始
    """)
    
    # 添加示例查询
    example_queries = [
        "帮我生成一个从西安到川西的五日游旅游计划，我打算下周五出发",
        "帮我生成一个从西安到兰州的三日游旅游计划，我打算端午节去",
        "帮我生成一个从太原到大同的四日游旅游计划，预算3k，我不想去应县木塔",
        "计划和同事们在广州游玩5天，有哪些推荐的活动？",
        "准备去重庆游玩3天，想体验当地的夜生活",
    ]

    # 示例查询选择
    selected_example = st.selectbox(
        "💡 示例查询（点击选择）：",
        [""] + example_queries,
        index=0
    )

    # 用户输入区域
    custom_prompt = st.text_area(
        "自定义旅行需求：",
        value=selected_example if selected_example else "",
        height=100,
        placeholder="例如：帮我生成一个从上海到苏州的两日游旅游计划，我打算立夏那天出发"
    )

    # 生成按钮区域
    col1, col2 = st.columns([1, 4])
    with col1:
        generate_button = st.button("🚀 开始规划", type="primary", use_container_width=True)

# 添加CSS样式
st.markdown(
    """
    <style>
        .scrollable-container {
            max-height: 600px;
            overflow-y: auto;
            border: 1px solid #e6e6e6;
            border-radius: 8px;
            padding: 15px;
            background-color: #ffffff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .log-entry {
            padding: 8px;
            border-radius: 6px;
            margin: 4px 0;
            font-family: "SF Mono", "Roboto Mono", monospace;
            font-size: 13px;
            line-height: 1.4;
            white-space: pre-wrap;
            word-wrap: break-word;
            background-color: #f8f9fa;
            border: 1px solid #f0f0f0;
            transition: all 0.2s ease;
        }
        .log-entry:hover {
            box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        }
        .message-content {
            margin-top: 4px;
            padding: 6px;
            background-color: #ffffff;
            border-radius: 4px;
            font-size: 12px;
            color: #333;
        }
        .reasoning { 
            border-left: 3px solid #228be6; 
            background-color: #e7f5ff80;
        }
        .tool_activation { 
            border-left: 3px solid #fab005;
            background-color: #fff3bf80;
        }
        .tool_result { 
            border-left: 3px solid #40c057;
            background-color: #d3f9d880;
        }
        .tool_selection { 
            border-left: 3px solid #be4bdb;
            background-color: #f8f0fc80;
        }
        .step_progress { 
            border-left: 3px solid #495057;
            background-color: #f8f9fa80;
        }
        .timestamp { 
            color: #868e96;
            font-size: 11px;
            margin-bottom: 2px;
            font-family: system-ui, -apple-system, sans-serif;
        }
        /* 标题和图标样式 */
        .log-entry strong {
            font-size: 12px;
            color: #495057;
            font-weight: 600;
            margin-left: 4px;
        }
        /* 自定义滚动条样式 */
        .scrollable-container::-webkit-scrollbar {
            width: 6px;
        }
        .scrollable-container::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 3px;
        }
        .scrollable-container::-webkit-scrollbar-thumb {
            background: #ccc;
            border-radius: 3px;
        }
        .scrollable-container::-webkit-scrollbar-thumb:hover {
            background: #999;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# 创建侧边栏
with st.sidebar:
    st.header("✨ 快速生成旅行计划")
    
    # 出发地和目的地
    col1, col2 = st.columns(2)
    with col1:
        departure = st.text_input("出发地", placeholder="例如：上海")
    with col2:
        destination = st.text_input("目的地", placeholder="例如：苏州")
    
    # 行程天数
    days = st.slider("行程天数", 1, 15, 3)
    
    # 出行时间
    travel_time_type = st.selectbox(
        "出行时间",
        ["具体日期", "节假日", "下周", "周末"]
    )
    
    if travel_time_type == "具体日期":
        travel_date = st.date_input("选择日期")
    elif travel_time_type == "节假日":
        holiday = st.selectbox(
            "选择节假日",
            ["春节", "清明", "五一", "端午", "中秋", "国庆"]
        )
    
    # 预算
    budget = st.number_input("预算（元）", min_value=0, value=3000, step=500)
    
    # 特殊需求
    special_requirements = st.multiselect(
        "特殊需求",
        ["避开人流密集景点", "包含特色美食", "适合带孩子", "夜生活体验", "文化探索", "自然风光"],
        default=[]
    )
    
    # 其他备注
    additional_notes = st.text_area("其他备注", placeholder="例如：不想去某个景点、特别想体验的活动等")

# 在主界面下方添加实时规划进度区域
st.markdown("---")
st.header("🔄 实时规划进度")

# 创建实时更新容器
realtime_container = st.empty()

# 创建一个用于显示实时日志的容器
with st.expander("规划详细过程", expanded=True):
    # 添加可滚动容器的开始标记
    st.markdown('<div class="scrollable-container">', unsafe_allow_html=True)
    log_container = st.container()
    # 添加可滚动容器的结束标记
    st.markdown('</div>', unsafe_allow_html=True)

def update_ui(container, message):
    """在主线程中更新UI"""
    if isinstance(message, dict):
        # 定义重要的消息类型
        important_categories = ['reasoning', 'tool_selection', 'tool_activation', 'tool_result', 'step_progress']
        
        # 如果消息类型不在重要类型列表中，则不显示
        if message.get('category') not in important_categories:
            return
            
        # 显示时间戳
        container.markdown(
            f'<div class="timestamp">{message["timestamp"].strftime("%H:%M:%S")}</div>',
            unsafe_allow_html=True
        )
        
        # 根据消息类型添加不同的样式
        css_class = f"log-entry {message.get('category', 'default')}"
        content = message.get('content', message.get('raw_message', ''))
        
        # 添加图标和标题
        if message.get('category') == 'reasoning':
            icon = "💭"
            title = "思考过程"
        elif message.get('category') == 'step_progress':
            icon = "📍"
            title = f"步骤 {message.get('current_step', '?')}/{message.get('total_steps', '?')}"
        elif message.get('category') == 'tool_activation':
            icon = "⚡"
            title = f"调用: {message.get('tool_name', '未知工具')}"
        elif message.get('category') == 'tool_result':
            icon = "✓"
            title = "结果"
        elif message.get('category') == 'tool_selection':
            icon = "🎯"
            title = "选择工具"
        
        # 处理消息内容，移除不必要的技术细节
        if 'content' in message:
            # 移除日志级别和时间戳等技术信息
            content = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| \w+ \|.*?(?=\s*\w+:)', '', content)
            # 移除多余的空行
            content = re.sub(r'\n\s*\n', '\n', content)
            # 移除末尾的</div>标签
            content = re.sub(r'</div>\s*$', '', content)
            # 移除开头的空行
            content = content.lstrip()
        
        container.markdown(
            f"""
            <div class="{css_class}">
                {icon}<strong>{title}</strong>
                <div class="message-content">
                    {content}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        # 对于非字典类型的消息，也不显示
        return

# 生成按钮处理逻辑
if generate_button:
    if not custom_prompt and (not departure or not destination):
        st.warning("请输入出发地和目的地，或在下方输入自定义旅行需求")
    else:
        # 设置当前会话ID
        with session_lock:
            st.session_state.session_count += 1
            st.session_state.current_session_id = st.session_state.session_count
            session_manager.set_session_id(st.session_state.current_session_id)
        
        if custom_prompt:
            prompt_to_use = custom_prompt
        else:
            # 构建结构化的提示语
            prompt_parts = [f"帮我生成一个从{departure}到{destination}的{days}日游旅行计划"]
            
            if travel_time_type == "具体日期":
                prompt_parts.append(f"计划在{travel_date}出发")
            elif travel_time_type == "节假日":
                prompt_parts.append(f"计划在{holiday}出发")
            elif travel_time_type == "下周":
                prompt_parts.append("计划下周出发")
            elif travel_time_type == "周末":
                prompt_parts.append("计划这个周末出发")
            
            if budget > 0:
                prompt_parts.append(f"预算{budget}元")
            
            if special_requirements:
                prompt_parts.append("，".join(special_requirements))
            
            if additional_notes:
                prompt_parts.append(additional_notes)
            
            prompt_to_use = "，".join(prompt_parts) + "。"
        
        # 显示处理状态
        with st.status("🤖 AI助手正在规划您的旅程...", expanded=True) as status:
            # 清空实时日志容器
            log_container.empty()
            
            # 创建新线程处理异步任务
            thread = threading.Thread(target=run_async_process, args=(prompt_to_use, output_queue))
            thread.start()
            
            # 实时更新输出
            while thread.is_alive() or not output_queue.empty():
                try:
                    output = output_queue.get_nowait()
                    
                    # 更新进度显示
                    if output['category'] == 'step_progress':
                        status.update(label=f"🤖 步骤 {output['current_step']}/{output['total_steps']}")
                    
                    # 实时显示日志
                    with log_container:
                        update_ui(st.container(), output)
                    
                except queue.Empty:
                    pass
                
                time.sleep(0.1)  # 添加小延迟以避免过度刷新
                
            thread.join()
            status.update(label="✅ 规划完成！", state="complete") 