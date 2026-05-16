import streamlit as st
import re
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.deepseek_api import get_client
from utils.data_processor import export_to_word, latex_to_text
from utils.sidebar import render_shared_sidebar, inject_sidebar_css

st.set_page_config(page_title="智能出题组卷", page_icon="📄", layout="wide")

inject_sidebar_css()

# 侧边栏
with st.sidebar:
    render_shared_sidebar()

st.title("📄 智能出题与组卷")
st.markdown("根据知识点、难度、题型要求，AI自动生成数学题目并组装试卷。")

# 全局紧凑排版
st.markdown("""<style>
    /* 减少题目区域的段落间距 */
    .compact-q p { margin: 0.1rem 0 !important; line-height: 1.4 !important; }
    .compact-q p+p { margin-top: 0.05rem !important; }
</style>""", unsafe_allow_html=True)

# 湖北省天门市中考数学知识点分类
KP_CATEGORIES = {
    "数与代数": [
        "有理数运算", "实数运算", "科学记数法", "数轴与绝对值",
        "整式运算", "因式分解", "分式运算", "根式运算",
        "一元一次方程", "二元一次方程组", "一元二次方程",
        "分式方程", "不等式与不等式组",
        "一次函数", "反比例函数", "二次函数",
        "函数与图像综合", "函数应用题",
    ],
    "空间与图形": [
        "相交线与平行线", "三角形", "全等三角形", "相似三角形",
        "等腰三角形", "直角三角形", "勾股定理",
        "平行四边形", "矩形", "菱形", "正方形", "梯形",
        "四边形综合", "圆的基本性质", "直线与圆的位置关系",
        "圆与圆的位置关系", "弧长与扇形面积",
        "锐角三角函数", "解直角三角形",
        "图形的平移", "图形的旋转", "轴对称", "中心对称",
        "平面直角坐标系", "图形与坐标",
    ],
    "统计与概率": [
        "数据的收集与整理", "平均数中位数众数", "方差与标准差",
        "频率与概率", "统计图表分析",
    ],
    "综合与实践": [
        "规律探究", "阅读理解题", "方案设计题",
        "动态几何问题", "存在性问题", "最值问题",
    ],
}

# --- Paper assembly (组卷导出) ---
st.subheader("智能组卷")

paper_title = st.text_input("试卷标题", value="初中数学测试卷")

if "paper_questions" not in st.session_state:
    st.session_state.paper_questions = []
if "paper_result" not in st.session_state:
    st.session_state.paper_result = None

# 切换类别时重置知识点为该类别第一项
def _on_cat_change():
    st.session_state.paper_topic = KP_CATEGORIES[st.session_state.paper_cat][0]

st.markdown("### 设置题目要求")
col_cat, col_kp = st.columns(2)
with col_cat:
    category = st.selectbox(
        "知识类别", list(KP_CATEGORIES.keys()),
        key="paper_cat", on_change=_on_cat_change,
    )
with col_kp:
    topic = st.selectbox("知识点", KP_CATEGORIES[category], key="paper_topic")

with st.form("paper_form"):
    col2, col3, col4 = st.columns(3)
    with col2:
        difficulty = st.slider("难度", 1, 5, 3, key="paper_diff")
    with col3:
        q_type = st.selectbox("题型", ["选择题", "填空题", "解答题"], key="paper_type")
    with col4:
        count = st.number_input("数量", 1, 5, 1, key="paper_count")

    submitted = st.form_submit_button("➕ 添加到试卷")
    if submitted:
        st.session_state.paper_questions.append({
            "topic": topic, "difficulty": difficulty,
            "q_type": q_type, "count": count,
        })
        st.session_state.paper_result = None
        st.success(f"已添加：{count}道{difficulty}星难度的{q_type}（{topic}）")

if st.session_state.paper_questions:
    st.markdown("### 当前试卷配置")

    # Card-style display for each configuration
    for i, pq in enumerate(st.session_state.paper_questions):
        stars = "⭐" * pq["difficulty"]
        card_html = f"""
        <div style="
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 0.6rem;
            padding: 0.8rem 1.2rem;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.95rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.6rem;">
                <span style="
                    background: #4A90D9;
                    color: white;
                    border-radius: 50%;
                    width: 28px;
                    height: 28px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    font-size: 0.85rem;
                    flex-shrink: 0;
                ">{i+1}</span>
                <span style="font-weight: 600; color: #333;">{pq['topic']}</span>
                <span style="color: #f5a623;">{stars}</span>
                <span style="
                    background: #e8f0fe;
                    color: #4A90D9;
                    padding: 0.15rem 0.6rem;
                    border-radius: 0.3rem;
                    font-size: 0.85rem;
                ">{pq['q_type']}</span>
                <span style="color: #666;">×{pq['count']}道</span>
            </div>
        </div>
        """
        col_card, col_up, col_down, col_del = st.columns([8, 1, 1, 1])
        with col_card:
            st.markdown(card_html, unsafe_allow_html=True)
        with col_up:
            if st.button("⬆️", key=f"up_{i}", help="上移"):
                if i == 0:
                    st.toast("已经是第一题了")
                else:
                    st.session_state.paper_questions[i-1], st.session_state.paper_questions[i] = \
                        st.session_state.paper_questions[i], st.session_state.paper_questions[i-1]
                    st.session_state.paper_result = None
                    st.rerun()
        with col_down:
            if st.button("⬇️", key=f"down_{i}", help="下移"):
                if i == len(st.session_state.paper_questions) - 1:
                    st.toast("已经是最后一题了")
                else:
                    st.session_state.paper_questions[i], st.session_state.paper_questions[i+1] = \
                        st.session_state.paper_questions[i+1], st.session_state.paper_questions[i]
                    st.session_state.paper_result = None
                    st.rerun()
        with col_del:
            if st.button("🗑️", key=f"del_{i}", help="删除此配置"):
                st.session_state.paper_questions.pop(i)
                st.session_state.paper_result = None
                st.rerun()

    def _finalize_paper(gs, title):
        """将已生成的题目构建为最终结果"""
        all_qs = gs["all_questions"]
        type_order = []
        for q in all_qs:
            t = q.get("type", "其他")
            if t not in type_order:
                type_order.append(t)
        sections = []
        for t in type_order:
            tqs = [q for q in all_qs if q.get("type") == t]
            sections.append({"heading": t, "questions": tqs})
        st.session_state.paper_result = {
            "title": title,
            "all_questions": all_qs,
            "type_order": type_order,
            "sections": sections,
        }

    # 初始化生成状态
    if "paper_gen_state" not in st.session_state:
        st.session_state.paper_gen_state = None

    # 判断是否有未完成的生成任务
    gen_state = st.session_state.paper_gen_state
    is_generating = gen_state is not None and not gen_state.get("finished", False)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("🗑️ 清空配置", disabled=is_generating):
            st.session_state.paper_questions = []
            st.session_state.paper_result = None
            st.session_state.paper_gen_state = None
            st.rerun()
    with col_b:
        if is_generating:
            st.button("⏳ AI正在生成试卷...", type="primary", disabled=True)
        else:
            start_gen = st.button("🤖 AI生成试卷", type="primary")
    with col_c:
        if is_generating:
            if st.button("⏹️ 终止"):
                if gen_state["all_questions"]:
                    _finalize_paper(gen_state, paper_title)
                st.session_state.paper_gen_state = None
                st.rerun()

    if not is_generating and start_gen:
        total_questions = sum(pq["count"] for pq in st.session_state.paper_questions)
        if total_questions > 20:
            st.error(f"❌ 总题目数（{total_questions}道）超过上限20道，请减少题目数量。")
        elif total_questions == 0:
            st.error("❌ 请先添加题目要求。")
        else:
            st.session_state.paper_gen_state = {
                "all_questions": [],
                "done_count": 0,
                "total": total_questions,
                "start_time": time.time(),
                "task_queue": list(st.session_state.paper_questions),
                "current_task_idx": 0,
                "current_task_done": 0,
                "finished": False,
                "error": None,
            }
            st.session_state.paper_result = None
            st.rerun()

    # 执行生成（每次rerun生成一道题）
    gen_state = st.session_state.paper_gen_state
    if gen_state and not gen_state.get("finished", False):
        gs = gen_state
        total = gs["total"]
        done = gs["done_count"]
        start_ts = gs["start_time"]
        elapsed = time.time() - start_ts

        # 显示进度
        progress_bar = st.progress(done / total)
        status_placeholder = st.empty()
        status_placeholder.markdown(f"**进度：{done}/{total}** | 已用时：{elapsed:.0f}秒")

        # JS实时计时器（用 components 执行）
        import streamlit.components.v1 as components
        timer_html = f"""
        <div id="gen_timer" style="font-size:1rem;font-weight:bold;color:#4A90D9;padding:4px 0;"></div>
        <script>
        (function() {{
            var start = {start_ts * 1000};
            function tick() {{
                var sec = Math.floor((Date.now() - start) / 1000);
                var el = document.getElementById('gen_timer');
                if (el) {{ el.innerText = "⏱ 实时计时：" + sec + "秒"; }}
                setTimeout(tick, 1000);
            }}
            tick();
        }})();
        </script>
        """
        components.html(timer_html, height=30)

        # 逐题生成
        try:
            client = get_client()
            while gs["current_task_idx"] < len(gs["task_queue"]):
                pq = gs["task_queue"][gs["current_task_idx"]]
                remain = pq["count"] - gs["current_task_done"]
                if remain <= 0:
                    gs["current_task_idx"] += 1
                    gs["current_task_done"] = 0
                    continue

                qs = client.generate_questions(
                    pq["topic"], pq["difficulty"], pq["q_type"], 1
                )
                if isinstance(qs, list) and qs:
                    for q in qs:
                        q["type"] = pq["q_type"]
                    gs["all_questions"].extend(qs)

                gs["current_task_done"] += 1
                gs["done_count"] += 1
                done = gs["done_count"]

                # 更新进度和文字
                progress_bar.progress(done / total)
                elapsed = time.time() - start_ts
                status_placeholder.markdown(f"**进度：{done}/{total}** | 已用时：{elapsed:.0f}秒")

                # 已完成全部
                if done >= total:
                    gs["finished"] = True
                    _finalize_paper(gs, paper_title)
                    progress_bar.progress(1.0)
                    status_placeholder.markdown(f"**进度：{done}/{total}** | 已用时：{elapsed:.0f}秒")
                    st.session_state.paper_gen_state = None
                    st.session_state["paper_gen_elapsed"] = elapsed
                    st.rerun()
                    break

            # 如果循环结束但未完成（异常情况）
            gs["finished"] = True
            _finalize_paper(gs, paper_title)
            st.session_state.paper_gen_state = None
            st.rerun()

        except Exception as e:
            elapsed = time.time() - start_ts
            st.warning(f"⚠️ 生成中断（{done}/{total}），已用时 {elapsed:.0f} 秒。可点击「继续生成」补全剩余题目。")
            st.error(f"错误：{e}")

        # 中断后显示已生成的题目
        if gs["all_questions"]:
            st.markdown("### 已生成的题目")
            _display_questions(gs["all_questions"])


def _strip_option_prefix(opt: str) -> str:
    """去除选项已有的字母前缀，如 'A. xxx' -> 'xxx'"""
    return re.sub(r'^[A-Fa-f][.、．]\s*', '', opt.strip())


def _nl_to_br(text: str) -> str:
    """将换行符转为HTML换行，便于Streamlit markdown渲染"""
    return text.replace("\n", "  \n")


def _display_questions(questions: list):
    """左题右解析布局展示题目（紧凑排版）"""
    option_labels = ["A", "B", "C", "D", "E", "F"]

    # 紧凑排版 CSS
    st.markdown("""<style>
    .compact-q p { margin: 0.1rem 0 !important; line-height: 1.4 !important; }
    .compact-q .stAlert { padding: 0.3rem 0.6rem !important; }
    </style>""", unsafe_allow_html=True)

    for i, q in enumerate(questions, 1):
        qtype = q.get("type", "其他")
        col_q, col_a = st.columns([1, 1])
        with col_q:
            # 题目内容拼成一段HTML，减少多层markdown嵌套
            q_html = f'<div class="compact-q">'
            q_html += f'<p><strong>第{i}题（{qtype}）</strong></p>'
            q_html += f'<p>{_nl_to_br(latex_to_text(q.get("question", "")))}</p>'
            if q.get('options'):
                for j, opt in enumerate(q['options']):
                    label = option_labels[j] if j < len(option_labels) else str(j+1)
                    clean_opt = _strip_option_prefix(opt)
                    q_html += f'<p style="padding-left:1rem;"><strong>{label}.</strong> {_nl_to_br(latex_to_text(clean_opt))}</p>'
            q_html += '</div>'
            st.markdown(q_html, unsafe_allow_html=True)
        with col_a:
            kp = q.get('knowledge_point', '')
            answer = q.get('answer', '')
            explanation = q.get('explanation', '')
            a_html = '<div class="compact-q">'
            if kp:
                a_html += f'<p><strong>知识点：</strong>{kp}</p>'
            a_html += f'<p style="color:green;font-weight:bold;">✅ {answer}</p>'
            if explanation:
                a_html += '<p><strong>解析：</strong></p>'
                for seg in re.split(r'(?<=[。；])\s*', explanation):
                    if seg.strip():
                        a_html += f'<p style="padding-left:0.5rem;">• {_nl_to_br(seg.strip())}</p>'
            a_html += '</div>'
            st.markdown(a_html, unsafe_allow_html=True)

        # 用细线分隔代替 st.divider()
        st.markdown('<hr style="margin:0.3rem 0;border:none;border-top:1px solid #e0e0e0;">', unsafe_allow_html=True)


# --- Display final result ---
if st.session_state.get("paper_result"):
    result = st.session_state.paper_result
    all_questions = result["all_questions"]
    paper_title_display = result["title"]

    st.divider()
    st.subheader(paper_title_display)

    # 显示生成用时
    if st.session_state.get("paper_gen_elapsed"):
        elapsed = st.session_state["paper_gen_elapsed"]
        st.success(f"✅ 试卷生成完成，共 {len(all_questions)} 道题，最终用时 **{elapsed:.0f}秒**")
        del st.session_state["paper_gen_elapsed"]

    _display_questions(all_questions)

    # Export buttons
    st.markdown("### 导出试卷")
    col_export1, col_export2 = st.columns(2)
    with col_export1:
        buffer_student = export_to_word(
            paper_title_display, result["sections"], include_answers=False
        )
        st.download_button(
            "📥 下载试卷版（学生用）",
            data=buffer_student,
            file_name=f"{paper_title_display}_试卷版.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    with col_export2:
        buffer_teacher = export_to_word(
            paper_title_display, result["sections"], include_answers=True
        )
        st.download_button(
            "📥 下载解析版（教师用）",
            data=buffer_teacher,
            file_name=f"{paper_title_display}_解析版.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    # AI disclaimer
    st.markdown("---")
    st.markdown("""
    <div style="background:#fff3cd;padding:1rem;border-radius:0.5rem;border-left:4px solid #ffc107;margin:1rem 0;">
        <strong>⚠️ AI生成内容声明</strong><br>
        本试卷题目由人工智能模型（DeepSeek）自动生成，仅供参考。题目内容可能存在不准确之处，请教师在使用前进行审核和调整。
    </div>
    """, unsafe_allow_html=True)
