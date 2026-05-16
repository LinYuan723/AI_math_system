import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from utils.database import get_students, get_exams, get_error_records
from utils.sidebar import render_shared_sidebar, inject_sidebar_css

st.set_page_config(
    page_title="初中数学智能信息系统",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 提前注入侧边栏CSS，减少页面切换闪烁
inject_sidebar_css()

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #1E3A5F;
        text-align: center;
        padding: 1rem 0;
    }
    .feature-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.8rem;
        border-left: 4px solid #4A90D9;
        margin-bottom: 1rem;
    }
    .feature-card h4 { font-size: 1.1rem; margin-bottom: 0.5rem; }
    .feature-card p { font-size: 0.95rem; line-height: 1.5; color: #555; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">初中数学智能信息系统</div>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center;color:#666;font-size:1.2rem;">基于DeepSeek大模型的智能教学辅助平台</p>', unsafe_allow_html=True)

# Load stats
students = get_students()
exams = get_exams()
errors = get_error_records()

# Metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("学生总数", len(students))
with col2:
    st.metric("考试记录", len(exams))
with col3:
    st.metric("错题记录", len(errors))

st.divider()

# Feature overview
st.subheader("系统功能模块")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="feature-card">
        <h4>📊 学情智能分析</h4>
        <p>上传考试成绩，AI自动分析班级和个人的知识点掌握情况，生成可视化图表和个性化提升建议。</p>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/1_📊_学情智能分析.py", label="进入学情分析", icon="📊")

with col2:
    st.markdown("""
    <div class="feature-card">
        <h4>📝 错题智能辅导</h4>
        <p>录入错题，AI分析错误原因，给出详细解题思路和同类练习题推荐，帮助学生精准提升。</p>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/2_📝_错题智能辅导.py", label="进入错题辅导", icon="📝")

with col3:
    st.markdown("""
    <div class="feature-card">
        <h4>📄 智能出题组卷</h4>
        <p>灵活配置知识点、难度、题型和数量，AI自动生成试卷并支持一键导出Word文档。</p>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/3_📄_智能出题组卷.py", label="进入出题组卷", icon="📄")

st.divider()

# Quick start guide
st.subheader("快速开始")
st.markdown("""
1. **配置API Key**：在 `.env` 文件中填入你的 DeepSeek API Key
2. **上传数据**：进入「学情智能分析」模块，上传学生成绩Excel文件
3. **查看分析**：系统自动调用AI进行分析，生成可视化图表和建议
4. **探索其他功能**：错题辅导、出题组卷等模块均可独立使用
""")

# Sidebar info
with st.sidebar:
    render_shared_sidebar()
