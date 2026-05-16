"""共享侧边栏组件"""
import streamlit as st
import os
from utils.database import get_students, get_exams, get_error_records

# 可选模型
MODELS = {
    "DeepSeek V4 Pro（推荐）": "deepseek-v4-pro",
    "DeepSeek V4 Flash（经济）": "deepseek-v4-flash",
}


SIDEBAR_CSS = """
<style>
    [data-testid="stSidebar"] > div:first-child { padding-top: 0.8rem !important; }
    [data-testid="stSidebar"] .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    [data-testid="stSidebar"] nav ul { padding-left: 0.5rem !important; }
    [data-testid="stSidebar"] nav li a, [data-testid="stSidebar"] nav li span { padding-left: 0.5rem !important; }
    [data-testid="stSidebar"] [data-testid="stPageLink"] a, [data-testid="stSidebar"] [data-testid="stPageLink"] span { padding-left: 0.5rem !important; }
    [data-testid="stSidebar"] h4 { margin: 0.2rem 0 0.1rem 0 !important; line-height: 1.3 !important; }
    [data-testid="stSidebar"] hr { margin: 0.25rem 0 !important; }
    [data-testid="stSidebar"] .stAlert { padding: 0.2rem 0.5rem !important; margin: 0.15rem 0 !important; }
    [data-testid="stSidebar"] .stSelectbox { margin: 0.1rem 0 !important; }
</style>
"""


def inject_sidebar_css():
    """在页面早期注入侧边栏CSS"""
    st.html(SIDEBAR_CSS)


def render_shared_sidebar():
    """渲染共享的侧边栏信息"""

    # 模型选择
    st.markdown("#### ⚙️ 模型设置")
    st.markdown("AI模型")
    labels = list(MODELS.keys())
    current_model = st.session_state.get("ds_model", "deepseek-v4-pro")
    default_idx = 0
    for i, label in enumerate(labels):
        if MODELS[label] == current_model:
            default_idx = i
            break
    selected_label = st.selectbox("AI模型", labels, index=default_idx, key="ds_model_select", label_visibility="collapsed")
    st.session_state["ds_model"] = MODELS[selected_label]
    st.markdown("---")

    # 系统信息
    students = get_students()
    exams = get_exams()
    errors = get_error_records()
    st.markdown(f"#### 系统信息")
    st.markdown(f"- 学生 {len(students)} 人 | 考试 {len(exams)} 条 | 错题 {len(errors)} 条")
    st.markdown("---")

    # 技术栈
    st.markdown(f"#### 技术栈")
    st.markdown(f"- Python + Streamlit + SQLite + Plotly")
    st.markdown(f"- DeepSeek API")

    # API 状态
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if api_key:
        st.success("DeepSeek API 已配置")
    else:
        st.error("DeepSeek API 未配置")
    st.markdown("---")

    # 开发者
    st.markdown("#### 开发者")
    st.markdown("初中数学智能信息系统 v1.0")
    st.caption("基于DeepSeek大模型的智能教学辅助平台")
    st.markdown("---")

    # 免责声明
    st.markdown("#### ⚠️ 免责声明")
    st.markdown("""
    <div style="background:#fff3cd;padding:0.5rem;border-radius:0.4rem;font-size:0.9rem;line-height:1.3;">
        本系统AI生成内容仅供参考，教学决策请结合专业判断。
    </div>
    """, unsafe_allow_html=True)
