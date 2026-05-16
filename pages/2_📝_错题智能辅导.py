import streamlit as st
import json
import re
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.deepseek_api import get_client
from utils.database import (
    add_error_record, get_error_records, get_students, get_or_create_student,
    save_upload_file,
    find_duplicate_error, increment_error_count, delete_error_record,
)
from utils.visualizations import pie_chart, error_type_bar
from utils.sidebar import render_shared_sidebar, inject_sidebar_css

st.set_page_config(page_title="错题智能辅导", page_icon="📝", layout="wide")

inject_sidebar_css()

# 侧边栏
with st.sidebar:
    render_shared_sidebar()

st.title("📝 错题智能辅导")


# ===== Helper functions =====

def normalize_latex(text: str) -> str:
    r"""Convert LaTeX delimiters to Streamlit/MathJax compatible format.
    \(...)  -> $...$     (inline math)
    \[...\]  -> $$...$$   (display math)
    """
    if not text:
        return text
    # Display math: \[...\] -> $$...$$
    text = re.sub(r'\\\[(.+?)\\\]', r'$$\1$$', text, flags=re.DOTALL)
    # Inline math: \(...\) -> $...$
    text = re.sub(r'\\\((.+?)\\\)', r'$\1$', text, flags=re.DOTALL)
    return text


def render_math_text(text: str, label: str = ""):
    """Render text with LaTeX math expressions using Streamlit Markdown (MathJax)."""
    if not text:
        return
    if label:
        st.markdown(f"**{label}**")
    normalized = normalize_latex(text)
    st.markdown(normalized)


# ===== Student selector at the top =====

students = get_students()
if students:
    student_options = {f"{s['name']} ({s['class_name']})": s for s in students}
    student_options["── 手动输入新学生 ──"] = None
    selected_label = st.selectbox("👤 选择学生", list(student_options.keys()), key="global_student")
    if selected_label == "── 手动输入新学生 ──":
        col_sn, col_cn = st.columns(2)
        with col_sn:
            manual_name = st.text_input("学生姓名", key="global_sname")
        with col_cn:
            manual_class = st.text_input("班级", key="global_cname")
        STUDENT_ID = None
        STUDENT_NAME = manual_name
        STUDENT_CLASS = manual_class
    else:
        s = student_options[selected_label]
        STUDENT_ID = s["id"]
        STUDENT_NAME = s["name"]
        STUDENT_CLASS = s["class_name"]
else:
    col_sn, col_cn = st.columns(2)
    with col_sn:
        manual_name = st.text_input("学生姓名", key="global_sname")
    with col_cn:
        manual_class = st.text_input("班级", key="global_cname")
    STUDENT_ID = None
    STUDENT_NAME = manual_name
    STUDENT_CLASS = manual_class

if STUDENT_ID is None and STUDENT_NAME and STUDENT_CLASS:
    STUDENT_ID = get_or_create_student(STUDENT_NAME, STUDENT_CLASS)

if STUDENT_ID:
    st.info(f"当前学生：**{STUDENT_NAME}**（{STUDENT_CLASS}）")

st.divider()

# ===== Tabs =====

tab_add, tab_book, tab_diagnosis = st.tabs(["➕ 录入错题", "📖 错题本", "📊 学习诊断"])


# ==================== Tab 1: 录入错题 ====================

with tab_add:
    st.subheader("录入错题")

    st.markdown("#### 上传错题图片，AI自动识别")

    # 上传图片
    uploaded_image = st.file_uploader(
        "上传错题照片（支持 JPG、PNG 格式）",
        type=["jpg", "jpeg", "png"],
        key="photo_upload",
    )

    # 检查文件大小
    if uploaded_image and uploaded_image.size > 10 * 1024 * 1024:
        st.error("图片文件过大，请上传小于10MB的图片。")
        uploaded_image = None

    # 没有上传图片时清除之前的识别结果，防止页面切换后残留数据
    if not uploaded_image:
        st.session_state.pop("photo_ai_result", None)

    # 初始化识别状态
    if "photo_ai_running" not in st.session_state:
        st.session_state["photo_ai_running"] = False
    if "photo_ai_start_time" not in st.session_state:
        st.session_state["photo_ai_start_time"] = 0.0
    if "photo_ai_elapsed" not in st.session_state:
        st.session_state["photo_ai_elapsed"] = 0.0

    if uploaded_image:
        st.image(uploaded_image, caption="上传的错题照片", use_container_width=True)

        # AI识别按钮和停止按钮
        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            recognize_btn = st.button(
                "🤖 AI识别题目" if not st.session_state["photo_ai_running"] else "⏳ AI识别中...",
                type="primary",
                key="ai_recognize",
                disabled=st.session_state["photo_ai_running"],
            )
        with col_btn2:
            stop_btn = st.button(
                "⏹️ 停止识别",
                key="ai_stop",
                disabled=not st.session_state["photo_ai_running"],
            )

        if stop_btn:
            st.session_state["photo_ai_running"] = False
            st.warning("已终止识别。")
            st.rerun()

        if recognize_btn:
            st.session_state["photo_ai_running"] = True
            st.session_state["photo_ai_start_time"] = time.time()
            st.rerun()

        # 执行识别
        if st.session_state["photo_ai_running"]:
            start_ms = int(st.session_state["photo_ai_start_time"] * 1000)

            # JS实时计时器
            import streamlit.components.v1 as components
            timer_html = f"""
            <div id="ocr-timer" style="font-size:1rem;padding:8px 12px;background:#e8f0fe;border-radius:6px;color:#1a73e8;font-weight:bold;margin:4px 0;">
                ⏱ 正在识别... 已耗时 <span id="ocr-elapsed">0.0</span> 秒
            </div>
            <script>
            (function() {{
                var start = {start_ms};
                var el = document.getElementById('ocr-elapsed');
                var timer = setInterval(function() {{
                    var sec = (Date.now() - start) / 1000;
                    if (el) el.textContent = sec.toFixed(1);
                }}, 100);
            }})();
            </script>
            """
            components.html(timer_html, height=45)

            try:
                client = get_client()
                result = client.analyze_image(uploaded_image.getbuffer())
                elapsed = time.time() - st.session_state["photo_ai_start_time"]
                st.session_state["photo_ai_result"] = result
                st.session_state["photo_ai_elapsed"] = elapsed
                st.session_state["photo_kp"] = result.get("knowledge_point", "")
                st.session_state["photo_q"] = result.get("question_text", "")
                st.session_state["photo_sa"] = result.get("student_answer", "")
                st.session_state["photo_ca"] = result.get("correct_answer", "")
                valid_types = ["选择题", "填空题", "解答题", "判断题"]
                ai_qt = result.get("question_type", "解答题")
                st.session_state["photo_qt"] = valid_types.index(ai_qt) if ai_qt in valid_types else 2
                st.session_state["photo_ai_running"] = False
                st.success(f"✅ AI识别完成！耗时 {elapsed:.1f} 秒")
                st.rerun()
            except Exception as e:
                elapsed = time.time() - st.session_state["photo_ai_start_time"]
                st.session_state["photo_ai_running"] = False
                st.session_state["photo_ai_elapsed"] = elapsed
                st.error(f"❌ AI识别失败（耗时 {elapsed:.1f} 秒）：{e}")
                st.rerun()

        # 显示上次识别耗时
        if st.session_state.get("photo_ai_elapsed") > 0 and not st.session_state["photo_ai_running"]:
            st.caption(f"上次识别耗时：{st.session_state['photo_ai_elapsed']:.1f} 秒")

    # AI识别结果或手动填写
    ai_result = st.session_state.get("photo_ai_result", {})

    col1, col2 = st.columns(2)
    with col1:
        kp = st.text_input("涉及知识点", key="photo_kp",
                           value=ai_result.get("knowledge_point", ""),
                           placeholder="如：一元二次方程")
    with col2:
        valid_types = ["选择题", "填空题", "解答题", "判断题"]
        ai_qt = ai_result.get("question_type", "解答题")
        qt_idx = valid_types.index(ai_qt) if ai_qt in valid_types else 2
        qt = st.selectbox("题目类型", valid_types, index=qt_idx, key="photo_qt")

    q_text = st.text_area("题目内容", height=120, key="photo_q",
                          value=ai_result.get("question_text", ""),
                          placeholder="请输入题目内容...")
    col3, col4 = st.columns(2)
    with col3:
        sa = st.text_area("学生答案", height=80, key="photo_sa",
                          value=ai_result.get("student_answer", ""),
                          placeholder="学生的错误答案")
    with col4:
        ca = st.text_area("正确答案", height=80, key="photo_ca",
                          value=ai_result.get("correct_answer", ""),
                          placeholder="题目的正确答案")

    if st.button("💾 保存错题", type="primary", key="save_photo"):
        if not q_text:
            st.error("题目内容不能为空")
        elif not STUDENT_ID:
            st.error("请先选择或输入学生信息")
        else:
            dup = find_duplicate_error(STUDENT_ID, q_text)
            if dup:
                increment_error_count(dup["id"], sa)
                st.success(f"该错题已存在（ID: {dup['id']}），错误次数已+1（当前：{dup.get('error_count', 1) + 1}次）。")
            else:
                file_path = save_upload_file(uploaded_image, prefix="photo") if uploaded_image else None
                record_id = add_error_record(
                    student_id=STUDENT_ID, question_text=q_text, student_answer=sa,
                    correct_answer=ca, knowledge_point=kp, source_type="photo", image_path=file_path,
                )
                st.success(f"错题已保存（ID: {record_id}）。")
                st.session_state["photo_ai_result"] = {}


# ==================== Tab 2: 错题本 ====================

with tab_book:
    st.subheader("错题本")

    if not STUDENT_ID:
        st.info("请先在页面顶部选择学生。")
    else:
        records = get_error_records(student_id=STUDENT_ID)
        if not records:
            st.info("该学生暂无错题记录。")
        else:
            # Filters
            knowledge_points = list(set(r['knowledge_point'] for r in records if r.get('knowledge_point')))
            kp_filter = st.selectbox("按知识点筛选", ["全部"] + sorted(knowledge_points), key="book_kp")

            filtered = records
            if kp_filter != "全部":
                filtered = [r for r in filtered if r.get('knowledge_point') == kp_filter]

            total_errors = sum(r.get('error_count', 1) for r in filtered)
            st.markdown(f"共 **{len(filtered)}** 条错题记录（累计错误 **{total_errors}** 次）")

            if filtered:
                col_a, col_b = st.columns(2)
                with col_a:
                    kp_counts = {}
                    for r in filtered:
                        kp = r.get('knowledge_point') or '未分类'
                        kp_counts[kp] = kp_counts.get(kp, 0) + r.get('error_count', 1)
                    fig = pie_chart(list(kp_counts.keys()), list(kp_counts.values()), "知识点分布")
                    st.plotly_chart(fig, use_container_width=True)

                with col_b:
                    error_types = {}
                    for r in filtered:
                        et = r.get('error_type') or '未分析'
                        error_types[et] = error_types.get(et, 0) + r.get('error_count', 1)
                    if error_types:
                        fig = error_type_bar(error_types, "错误类型分布")
                        st.plotly_chart(fig, use_container_width=True)

            for r in filtered:
                source_tag = {"manual": "✏️ 手动", "photo": "📷 拍照", "exam": "📋 考试"}.get(r.get('source_type', 'manual'), "✏️")
                count_tag = f" ×{r.get('error_count', 1)}" if r.get('error_count', 1) > 1 else ""
                with st.expander(f"[{r['id']}] {r['question_text'][:60]}... | {source_tag}{count_tag}"):
                    render_math_text(r['question_text'], "题目：")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**学生答案：** {r.get('student_answer', '')}")
                    with col2:
                        st.markdown(f"**正确答案：** {r.get('correct_answer', '')}")
                    if r.get('knowledge_point'):
                        st.markdown(f"**知识点：** {r['knowledge_point']}")
                    if r.get('error_type'):
                        st.markdown(f"**错误类型：** {r['error_type']}")
                    if r.get('error_count', 1) > 1:
                        st.warning(f"错误次数：{r['error_count']} 次")
                    if r.get('created_at'):
                        st.caption(f"录入时间：{r['created_at']}")
                    col_d1, col_d2 = st.columns([4, 1])
                    with col_d2:
                        if st.button("🗑️ 删除", key=f"book_del_{r['id']}", type="secondary"):
                            delete_error_record(r["id"])
                            st.success("已删除")
                            st.rerun()


# ==================== Tab 3: 学习诊断 ====================

with tab_diagnosis:
    st.subheader("📊 学习诊断与个性化辅导")

    if not STUDENT_ID:
        st.info("请先在页面顶部选择学生。")
    else:
        student_records = get_error_records(student_id=STUDENT_ID)

        if not student_records:
            st.info(f"该学生暂无错题记录，无法生成学习诊断。")
        else:
            total_errors = sum(r.get('error_count', 1) for r in student_records)
            st.markdown(f"共有 **{len(student_records)}** 条错题记录（累计错误 **{total_errors}** 次）")

            kp_data = {}
            for r in student_records:
                kp = r.get('knowledge_point') or '未分类'
                if kp not in kp_data:
                    kp_data[kp] = {"count": 0, "errors": []}
                kp_data[kp]["count"] += r.get('error_count', 1)
                kp_data[kp]["errors"].append(r)

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("#### 知识点错误分布")
                if kp_data:
                    fig = pie_chart(list(kp_data.keys()), [v["count"] for v in kp_data.values()], "错题分布")
                    st.plotly_chart(fig, use_container_width=True)

            with col_b:
                st.markdown("#### 知识点错误次数")
                sorted_kp = sorted(kp_data.items(), key=lambda x: x[1]["count"], reverse=True)
                for kp, data in sorted_kp[:5]:
                    st.markdown(f"- **{kp}**：{data['count']} 次")

            st.divider()

            if st.button("📋 AI生成学习计划", type="primary", key="diag_plan"):
                with st.spinner("AI正在生成个性化学习计划..."):
                    try:
                        client = get_client()
                        weak_points = [{"knowledge_point": kp, "count": data["count"]} for kp, data in sorted_kp]
                        result = client.generate_study_plan(weak_points, STUDENT_NAME)

                        st.divider()
                        st.subheader("📋 个性化学习计划")

                        st.markdown(f"**{result.get('plan_title', '学习计划')}**")

                        st.markdown("#### 每周学习目标")
                        for goal in result.get('weekly_goals', []):
                            with st.expander(f"第{goal.get('week', '?')}周：{goal.get('focus', '')}（建议{goal.get('hours', '?')}小时）"):
                                for task in goal.get('tasks', []):
                                    st.markdown(f"- {task}")

                        st.markdown("#### 每日复习安排")
                        st.markdown(result.get('daily_review', ''))

                        st.markdown("#### 学习资源推荐")
                        for res in result.get('resource_recommendations', []):
                            st.markdown(f"- {res}")

                        st.markdown("#### 阶段性里程碑")
                        for ms in result.get('milestones', []):
                            st.markdown(f"- **{ms.get('milestone', '')}** — 目标时间：{ms.get('target_date', '待定')}")

                    except Exception as e:
                        st.error(f"生成学习计划失败：{e}")

            st.divider()
            st.subheader("🔁 智能复习提醒")

            from datetime import datetime

            for r in student_records:
                try:
                    created = datetime.strptime(r.get('created_at', '')[:10], '%Y-%m-%d')
                    days_passed = (datetime.now() - created).days
                except (ValueError, TypeError):
                    days_passed = 0

                review_days = [1, 3, 7, 14, 30]
                next_review = None
                for rd in review_days:
                    if days_passed <= rd:
                        next_review = rd - days_passed
                        break

                if next_review is not None:
                    if next_review <= 1:
                        urgency = "🔴"
                        status = "需要立即复习"
                    elif next_review <= 3:
                        urgency = "🟡"
                        status = f"即将到期（{next_review}天后）"
                    else:
                        urgency = "🟢"
                        status = f"距离下次复习还有{next_review}天"
                else:
                    urgency = "🟢"
                    status = "已完成所有周期复习"

                with st.expander(f"{urgency} [{r['id']}] {r['question_text'][:50]}... — {status}"):
                    render_math_text(r['question_text'], "题目：")
                    st.markdown(f"**正确答案：** {r.get('correct_answer', '')}")
                    st.markdown(f"**知识点：** {r.get('knowledge_point', '未知')}")
                    if r.get('error_count', 1) > 1:
                        st.warning(f"错误次数：{r['error_count']} 次")
                    st.caption(f"录入时间：{r.get('created_at', '')} | 已过 {days_passed} 天")

            if st.button("📝 生成今日复习任务清单", key="gen_review_list"):
                with st.spinner("AI正在生成复习任务..."):
                    try:
                        client = get_client()
                        review_data = []
                        for r in student_records:
                            try:
                                created = datetime.strptime(r.get('created_at', '')[:10], '%Y-%m-%d')
                                days = (datetime.now() - created).days
                            except (ValueError, TypeError):
                                days = 0
                            review_data.append({
                                "id": r["id"],
                                "question": r["question_text"][:100],
                                "knowledge_point": r.get("knowledge_point", ""),
                                "days_since": days,
                            })

                        system_prompt = (
                            "你是一位初中数学辅导老师。请根据以下错题数据，生成一份今日复习任务清单。"
                            "优先安排录入时间较早的错题，以及知识点关联性强的错题归类复习。"
                            "返回JSON格式，包含：\n"
                            "- tasks: 复习任务列表，每项包含错题ID、题目摘要、建议复习方式、预计时间（分钟）\n"
                            "- total_time: 总预计时间（分钟）\n"
                            "- tips: 复习建议（字符串）"
                        )
                        result = client.chat_json(system_prompt, json.dumps(review_data, ensure_ascii=False))

                        st.markdown(f"**总预计时间：{result.get('total_time', 0)} 分钟**")
                        for task in result.get('tasks', []):
                            st.markdown(f"- 📝 错题 #{task.get('id', '')}：{task.get('question', '')[:60]}...")
                            st.markdown(f"  复习方式：{task.get('建议复习方式', task.get('review_method', ''))} | 预计 {task.get('预计时间', task.get('time', '?'))} 分钟")
                        st.info(f"**复习建议：** {result.get('tips', '')}")

                    except Exception as e:
                        st.error(f"生成复习清单失败：{e}")
