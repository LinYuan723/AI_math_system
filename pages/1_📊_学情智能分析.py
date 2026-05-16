import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.deepseek_api import get_client
from utils.database import (
    add_exam, add_score, get_exams, get_scores_by_exam,
    get_or_create_student, get_students, get_scores_by_student,
    delete_exam, exam_exists,
)
from utils.data_processor import (
    parse_score_excel, export_to_word, export_to_pdf,
)
from utils.visualizations import (
    score_distribution_chart, knowledge_radar_chart,
    trend_chart,
)
from utils.sidebar import render_shared_sidebar, inject_sidebar_css

st.set_page_config(page_title="学情智能分析", page_icon="📊", layout="wide")

inject_sidebar_css()

# 侧边栏
with st.sidebar:
    render_shared_sidebar()

st.title("📊 学情智能分析")
st.markdown("上传学生考试成绩，AI自动分析知识点掌握情况，生成可视化图表和教学建议。")

# Tabs
tab_upload, tab_analysis, tab_history, tab_student = st.tabs(["📤 上传成绩", "🤖 AI分析", "📋 历史考试", "👤 个人学情"])

# --- Tab 1: Upload scores ---
with tab_upload:
    st.subheader("上传考试成绩")

    uploaded_files = st.file_uploader(
        "上传成绩文件",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help='支持Excel格式（.xlsx/.xls），可同时选择多个文件。每个文件需包含"考试信息"、"题目信息"、"学生成绩"三个Sheet。'
    )

    if uploaded_files:
        success_count = 0
        fail_count = 0

        for uploaded_file in uploaded_files:
            st.markdown("---")
            st.markdown(f"### 📄 {uploaded_file.name}")

            try:
                # Validate sheet names before parsing
                xls_check = pd.ExcelFile(uploaded_file)
                required_sheets = ["考试信息", "题目信息", "学生成绩"]
                missing_sheets = [s for s in required_sheets if s not in xls_check.sheet_names]
                if missing_sheets:
                    st.error(f"❌ 缺少必要的Sheet：{', '.join(missing_sheets)}")
                    st.info(f"当前文件包含的Sheet：{', '.join(xls_check.sheet_names)}")
                    fail_count += 1
                    continue

                data = parse_score_excel(uploaded_file)
                exam_info = data["exam_info"]
                question_info = data["question_info"]
                scores_df = data["scores_df"]

                st.success(f"成功读取文件！")

                # 使用卡片样式显示考试信息
                st.markdown(f"""
                <div style="background:#f0f2f6;padding:1rem;border-radius:0.5rem;margin:1rem 0;">
                    <strong>考试名称：</strong>{exam_info.get("考试名称", "N/A")}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                    <strong>班级：</strong>{exam_info.get("班级", "N/A")}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                    <strong>学生人数：</strong>{exam_info.get("学生人数", "N/A")}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                    <strong>满分：</strong>{exam_info.get("满分", "N/A")}
                </div>
                """, unsafe_allow_html=True)

                st.subheader("题目信息")
                st.dataframe(question_info, use_container_width=True)

                st.subheader("学生成绩预览")
                st.dataframe(scores_df, use_container_width=True)

                # Save button
                if st.button("💾 保存成绩", type="primary", key=f"save_{uploaded_file.name}"):
                    exam_name = str(exam_info.get("考试名称", "未命名考试"))
                    class_name = str(exam_info.get("班级", "未命名班级"))
                    total_score = float(exam_info.get("满分", 100))

                    # 检查是否已存在同名考试
                    if exam_exists(exam_name, class_name):
                        st.warning(f"⚠️ 已存在同名考试：「{exam_name}」（{class_name}），跳过保存。如需重新上传，请先在历史考试中删除该考试。")
                    else:
                        # 校验分数是否超过满分
                        score_cols = [col for col in scores_df.columns if col.startswith("第") and col.endswith("题")]
                        score_errors = []
                        for _, row in scores_df.iterrows():
                            student_name = str(row["姓名"]).strip()
                            for col in score_cols:
                                q_num = int(col.replace("第", "").replace("题", ""))
                                q_info_row = question_info[question_info["题号"] == q_num]
                                max_score = float(q_info_row["分值"].values[0]) if len(q_info_row) > 0 else total_score
                                if float(row[col]) > max_score:
                                    score_errors.append(f"学生「{student_name}」第{q_num}题得分 {row[col]} 超过满分 {max_score}")

                        if score_errors:
                            st.error(f"❌ 发现 {len(score_errors)} 处分数异常，已中止保存：")
                            for err in score_errors[:20]:
                                st.error(f"  - {err}")
                            if len(score_errors) > 20:
                                st.error(f"  ... 还有 {len(score_errors) - 20} 处异常")
                        else:
                            exam_id = add_exam(exam_name, class_name, total_score=total_score)

                            # Build knowledge map from question info
                            knowledge_map = {}
                            for _, row in question_info.iterrows():
                                q_num = int(row["题号"])
                                col_name = f"第{q_num}题"
                                knowledge_map[col_name] = str(row["考查知识点"])

                            progress = st.progress(0)
                            total_students = len(scores_df)

                            for idx, row in scores_df.iterrows():
                                student_name = str(row["姓名"]).strip()
                                student_id = get_or_create_student(student_name, class_name)

                                for col in score_cols:
                                    q_num = int(col.replace("第", "").replace("题", ""))
                                    q_info_row = question_info[question_info["题号"] == q_num]
                                    max_score = float(q_info_row["分值"].values[0]) if len(q_info_row) > 0 else total_score

                                    add_score(
                                        student_id, exam_id,
                                        question_no=q_num,
                                        knowledge_point=knowledge_map.get(col, col),
                                        score=float(row[col]),
                                        max_score=max_score,
                                    )
                                progress.progress((idx + 1) / total_students)

                            st.success(f"成绩保存成功！考试ID：{exam_id}，共录入 {total_students} 名学生成绩。")
                            success_count += 1

            except Exception as e:
                fail_count += 1
                st.error(f"❌ 文件解析失败：{e}")
                st.info("""
                **正确格式要求：**
                - 文件格式：`.xlsx` 或 `.xls`
                - 必须包含以下三个Sheet：
                  1. **考试信息**：包含"项目"和"内容"两列，需有"考试名称"、"班级"、"学生人数"、"满分"等行
                  2. **题目信息**：包含"题号"、"题型"、"分值"、"考查知识点"等列
                  3. **学生成绩**：包含"姓名"列和"第1题"、"第2题"...等得分列
                """)

        # 汇总结果
        if len(uploaded_files) > 1:
            st.markdown("---")
            st.info(f"批量上传完成：成功 {success_count} 个，失败 {fail_count} 个，共 {len(uploaded_files)} 个文件。")

# --- Tab 2: AI Analysis ---
with tab_analysis:
    st.subheader("AI智能分析")

    exams = get_exams()
    if not exams:
        st.info("暂无考试数据，请先上传成绩。")
    else:
        exam_options = {f"{e['name']} ({e['date']}) - {e['class_name']}": e['id'] for e in exams}
        selected = st.selectbox("选择考试", list(exam_options.keys()))
        exam_id = exam_options[selected]

        scores = get_scores_by_exam(exam_id)
        if scores:
            df = pd.DataFrame(scores)

            # Summary stats
            total_scores = df.groupby("student_name")["score"].sum().sort_values(ascending=False)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("平均分", f"{total_scores.mean():.1f}")
            with col2:
                st.metric("最高分", f"{total_scores.max():.1f}")
            with col3:
                st.metric("最低分", f"{total_scores.min():.1f}")

            # Charts
            col_left, col_right = st.columns(2)
            with col_left:
                fig = score_distribution_chart(total_scores.tolist(), "班级成绩分布")
                st.plotly_chart(fig, use_container_width=True)

            with col_right:
                knowledge_stats = df.groupby("knowledge_point").agg(
                    avg_score=("score", "mean"),
                    max_score=("max_score", "first"),
                ).reset_index()
                knowledge_stats["mastery_rate"] = (knowledge_stats["avg_score"] / knowledge_stats["max_score"] * 100).round(1)
                fig = knowledge_radar_chart(knowledge_stats.to_dict("records"), "知识点掌握率")
                st.plotly_chart(fig, use_container_width=True)

            # Knowledge point detail
            st.subheader("各知识点详细数据")
            st.dataframe(
                knowledge_stats.rename(columns={
                    "knowledge_point": "知识点", "avg_score": "平均得分",
                    "max_score": "满分", "mastery_rate": "掌握率(%)"
                }),
                use_container_width=True,
            )

            # AI Analysis - 使用session_state持久化结果
            if st.button("🤖 启动AI深度分析", type="primary"):
                with st.spinner("AI正在分析中，请稍候..."):
                    try:
                        client = get_client()
                        exam_info = [e for e in exams if e['id'] == exam_id][0]

                        # Build summary from long-format database data
                        students_data = []
                        for name, group in df.groupby("student_name"):
                            students_data.append({
                                "name": name,
                                "total_score": round(group["score"].sum(), 2),
                                "details": [
                                    {"knowledge_point": row["knowledge_point"], "score": row["score"], "max_score": row["max_score"]}
                                    for _, row in group.iterrows()
                                ],
                            })

                        kp_summary = df.groupby("knowledge_point").agg(
                            avg_score=("score", "mean"),
                            max_score=("max_score", "first"),
                        ).reset_index()
                        kp_summary["mastery_rate"] = (kp_summary["avg_score"] / kp_summary["max_score"] * 100).round(1)

                        summary = {
                            "exam_name": exam_info["name"],
                            "class_name": exam_info["class_name"],
                            "total_students": len(students_data),
                            "class_avg": round(total_scores.mean(), 2),
                            "class_max": round(total_scores.max(), 2),
                            "class_min": round(total_scores.min(), 2),
                            "knowledge_points": kp_summary.to_dict("records"),
                            "students": sorted(students_data, key=lambda x: x["total_score"], reverse=True),
                        }

                        result = client.analyze_scores(summary)

                        # 存入session_state，避免导出时丢失
                        st.session_state["ai_analysis"] = {
                            "exam_id": exam_id,
                            "exam_name": exam_info["name"],
                            "class_name": exam_info["class_name"],
                            "total_students": len(students_data),
                            "avg_score": round(total_scores.mean(), 1),
                            "max_score": round(total_scores.max(), 1),
                            "min_score": round(total_scores.min(), 1),
                            "result": result,
                            "kp_summary_rows": [
                                {"knowledge_point": row["knowledge_point"], "avg_score": row["avg_score"],
                                 "max_score": row["max_score"], "mastery_rate": row["mastery_rate"]}
                                for _, row in kp_summary.iterrows()
                            ],
                        }
                        st.rerun()

                    except Exception as e:
                        st.error(f"AI分析失败：{type(e).__name__}: {e}")

            # 如果session_state中有分析结果且匹配当前考试，直接显示
            cached = st.session_state.get("ai_analysis")
            if cached and cached["exam_id"] == exam_id:
                result = cached["result"]
                kp_rows = cached["kp_summary_rows"]

                st.subheader("📋 AI分析报告")
                st.markdown(f"**班级整体情况：** {result.get('class_summary', '')}")

                st.markdown("**薄弱知识点：**")
                for wp in result.get("weak_points", []):
                    st.markdown(f"- **{wp.get('knowledge_point', '')}**：{wp.get('analysis', '')}")

                st.markdown("**教学建议：**")
                for s in result.get("suggestions", []):
                    st.markdown(f"- {s}")

                col_t, col_h = st.columns(2)
                with col_t:
                    top_students = result.get("top_students", [])
                    if top_students:
                        st.markdown("**优秀学生：** " + "、".join(f"⭐ {s}" for s in top_students))
                with col_h:
                    need_help = result.get("need_help", [])
                    if need_help:
                        st.markdown("**需要关注：** " + "、".join(f"⚠️ {s}" for s in need_help))

                # AI disclaimer
                st.markdown("---")
                st.markdown("""
                <div style="background:#fff3cd;padding:1rem;border-radius:0.5rem;border-left:4px solid #ffc107;margin:1rem 0;">
                    <strong>⚠️ AI生成内容声明</strong><br>
                    本分析报告由人工智能模型（DeepSeek）自动生成，仅供参考。AI分析结果可能存在局限性，具体教学决策请结合专业判断。
                </div>
                """, unsafe_allow_html=True)

                # Export buttons
                st.markdown("---")
                st.subheader("📥 导出报告")
                col_export1, col_export2 = st.columns(2)

                report_sections = [
                    {"heading": "班级整体情况", "content": result.get('class_summary', '')},
                    {"heading": "薄弱知识点分析", "content": "\n".join(f"- {wp.get('knowledge_point', '')}：{wp.get('analysis', '')}" for wp in result.get("weak_points", []))},
                    {"heading": "教学建议", "content": "\n".join(f"- {s}" for s in result.get("suggestions", []))},
                    {"heading": "优秀学生", "content": "\n".join(f"- {s}" for s in result.get("top_students", []))},
                    {"heading": "需要关注的学生", "content": "\n".join(f"- {s}" for s in result.get("need_help", []))},
                    {"heading": "知识点掌握详情", "table": {
                        "headers": ["知识点", "平均得分", "满分", "掌握率"],
                        "rows": [[r["knowledge_point"], f"{r['avg_score']:.1f}", f"{r['max_score']:.1f}", f"{r['mastery_rate']}%"] for r in kp_rows]
                    }},
                    {"heading": "重要声明", "content": "本报告由AI自动生成，仅供参考。\n1. 本分析报告基于学生考试成绩数据，由人工智能模型（DeepSeek）自动生成，仅供教师和家长参考使用。\n2. AI分析结果可能存在局限性，不能完全替代专业教师的判断和评估。\n3. 报告中的教学建议和学生评价仅供参考，具体教学决策请结合实际情况和专业判断。\n4. 本系统不对因使用AI分析结果而产生的任何后果承担责任。\n5. 学生个人信息和成绩数据受到保护，请勿将报告随意传播给无关人员。"},
                ]
                report_title = f"{cached['exam_name']} - AI智能分析报告"

                with col_export1:
                    word_buffer = export_to_word(report_title, report_sections)
                    st.download_button(
                        label="📄 导出为Word文件",
                        data=word_buffer,
                        file_name=f"AI分析报告_{cached['exam_name']}_{datetime.now().strftime('%Y%m%d')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        help="将报告导出为Word文档格式"
                    )

                with col_export2:
                    pdf_buffer = export_to_pdf(report_title, report_sections)
                    st.download_button(
                        label="📑 导出为PDF文件",
                        data=pdf_buffer,
                        file_name=f"AI分析报告_{cached['exam_name']}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        help="将报告导出为PDF格式文件"
                    )

# --- Tab 3: History ---
with tab_history:
    st.subheader("历史考试记录")
    exams = get_exams()
    if not exams:
        st.info("暂无考试记录。")
    else:
        for exam in exams:
            with st.expander(f"{exam['name']} - {exam['class_name']} ({exam['date']})"):
                scores = get_scores_by_exam(exam['id'])
                if scores:
                    df = pd.DataFrame(scores)
                    total_scores = df.groupby("student_name")["score"].sum().sort_values(ascending=False)
                    st.write(f"参考人数：{len(total_scores)} | 平均分：{total_scores.mean():.1f} | 最高分：{total_scores.max():.1f}")
                    st.dataframe(
                        total_scores.reset_index().rename(columns={"student_name": "姓名", "score": "总分"}),
                        use_container_width=True,
                    )

                # 删除按钮
                st.markdown("---")
                col_del, col_spacer = st.columns([1, 3])
                with col_del:
                    if st.button("🗑️ 删除此考试", key=f"del_{exam['id']}", type="secondary"):
                        delete_exam(exam['id'])
                        st.success(f"已删除考试：{exam['name']}")
                        st.rerun()

# --- Tab 4: Individual student ---
with tab_student:
    st.subheader("个人学情分析")
    students = get_students()
    if not students:
        st.info("暂无学生数据。")
    else:
        student_options = {f"{s['name']} ({s['class_name']})": s['id'] for s in students}
        selected = st.selectbox("选择学生", list(student_options.keys()))
        student_id = student_options[selected]
        student_info = [s for s in students if s['id'] == student_id][0]

        scores = get_scores_by_student(student_id)
        if scores:
            df = pd.DataFrame(scores)

            # Total scores per exam
            exam_totals = df.groupby(["exam_name", "exam_date"]).agg(
                total=("score", "sum"),
            ).reset_index().sort_values("exam_date")

            # ========== 子标签：总分析 / 单次分析 ==========
            sub_tab_overview, sub_tab_single = st.tabs(["📊 多次考试总分析", "📝 单次考试分析"])

            # ====== 多次考试总分析 ======
            with sub_tab_overview:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("考试次数", f"{len(exam_totals)}次")
                with col2:
                    st.metric("平均分", f"{exam_totals['total'].mean():.1f}")
                with col3:
                    st.metric("最高分", f"{exam_totals['total'].max():.1f}")
                with col4:
                    st.metric("最低分", f"{exam_totals['total'].min():.1f}")

                # Trend chart
                if len(exam_totals) >= 2:
                    fig = trend_chart(exam_totals, "exam_name", "total", title="成绩趋势")
                    st.plotly_chart(fig, use_container_width=True)

                # Knowledge mastery across all exams
                knowledge_stats = df.groupby("knowledge_point").agg(
                    avg_score=("score", "mean"),
                    max_score=("max_score", "first"),
                ).reset_index()
                knowledge_stats["mastery_rate"] = (knowledge_stats["avg_score"] / knowledge_stats["max_score"] * 100).round(1)

                col_radar, col_table = st.columns(2)
                with col_radar:
                    fig = knowledge_radar_chart(knowledge_stats.to_dict("records"), "个人知识点掌握率")
                    st.plotly_chart(fig, use_container_width=True)
                with col_table:
                    st.markdown("**各知识点掌握情况**")
                    st.dataframe(
                        knowledge_stats.rename(columns={
                            "knowledge_point": "知识点", "avg_score": "平均得分",
                            "max_score": "满分", "mastery_rate": "掌握率(%)"
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )

                # AI综合评语 - 使用session_state持久化
                overview_key = f"student_overview_comment_{student_id}"
                if st.button("🤖 生成AI综合评语", type="primary", key="ai_comment_overview"):
                    with st.spinner("AI正在生成综合评语..."):
                        try:
                            client = get_client()
                            student_data = {
                                "name": student_info["name"],
                                "class_name": student_info["class_name"],
                                "exam_count": len(exam_totals),
                                "avg_score": round(exam_totals["total"].mean(), 2),
                                "max_score": round(exam_totals["total"].max(), 2),
                                "min_score": round(exam_totals["total"].min(), 2),
                                "recent_score": round(exam_totals.iloc[-1]["total"], 2),
                                "score_trend": [round(t, 2) for t in exam_totals["total"].tolist()],
                                "knowledge_mastery": knowledge_stats.to_dict("records"),
                            }
                            st.session_state[overview_key] = client.generate_comment(student_data, "学期评语")
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI评语生成失败：{e}")

                # 显示已缓存的AI评语
                overview_comment = st.session_state.get(overview_key)
                if overview_comment:
                    st.markdown("---")
                    st.markdown("### 📋 AI综合评语")
                    st.markdown(overview_comment)
                    st.markdown("""
                    <div style="background:#fff3cd;padding:0.8rem;border-radius:0.5rem;border-left:4px solid #ffc107;margin:1rem 0;font-size:0.9em;">
                        <strong>⚠️ 声明：</strong>本评语由AI自动生成，仅供参考。具体评价请结合学生实际表现和专业判断。
                    </div>
                    """, unsafe_allow_html=True)

                # 导出总分析报告
                st.markdown("---")
                st.subheader("📥 导出总分析报告")
                overview_sections = [
                    {"heading": "基本信息", "content": f"学生姓名：{student_info['name']}\n班级：{student_info['class_name']}\n考试次数：{len(exam_totals)}次\n平均分：{exam_totals['total'].mean():.1f}\n最高分：{exam_totals['total'].max():.1f}\n最低分：{exam_totals['total'].min():.1f}"},
                    {"heading": "成绩趋势", "content": "\n".join(f"- {row['exam_name']}：{row['total']:.1f}分" for _, row in exam_totals.iterrows())},
                ]
                # AI评语（如果有）
                if overview_comment:
                    overview_sections.append({"heading": "AI综合评语", "content": overview_comment})
                overview_sections.extend([
                    {"heading": "知识点掌握情况", "table": {
                        "headers": ["知识点", "平均得分", "满分", "掌握率"],
                        "rows": [[r["knowledge_point"], f"{r['avg_score']:.1f}", f"{r['max_score']:.1f}", f"{r['mastery_rate']}%"] for _, r in knowledge_stats.iterrows()]
                    }},
                    {"heading": "声明", "content": "本报告由AI自动生成，仅供参考。具体评价请结合学生实际表现和专业判断。"},
                ])
                col_w, col_p = st.columns(2)
                with col_w:
                    word_buf = export_to_word(f"{student_info['name']} - 个人学情总分析报告", overview_sections)
                    st.download_button("📄 导出Word", data=word_buf,
                                       file_name=f"个人学情总分析_{student_info['name']}_{datetime.now().strftime('%Y%m%d')}.docx",
                                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                with col_p:
                    pdf_buf = export_to_pdf(f"{student_info['name']} - 个人学情总分析报告", overview_sections)
                    st.download_button("📑 导出PDF", data=pdf_buf,
                                       file_name=f"个人学情总分析_{student_info['name']}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                       mime="application/pdf")

            # ====== 单次考试分析 ======
            with sub_tab_single:
                exam_list = df["exam_name"].unique().tolist()
                selected_exam = st.selectbox("选择考试", exam_list)
                exam_df = df[df["exam_name"] == selected_exam].copy()
                exam_total = exam_df["score"].sum()

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("本次总分", f"{exam_total:.1f}")
                with col_b:
                    st.metric("题目数", f"{len(exam_df)}")
                with col_c:
                    mastery_rate = (exam_df["score"].sum() / exam_df["max_score"].sum() * 100)
                    st.metric("总得分率", f"{mastery_rate:.1f}%")

                # 各题得分详情
                st.markdown("**各题得分详情**")
                detail_df = exam_df[["question_no", "knowledge_point", "score", "max_score"]].copy()
                detail_df["得分率"] = (detail_df["score"] / detail_df["max_score"] * 100).round(1)
                detail_df = detail_df.rename(columns={
                    "question_no": "题号", "knowledge_point": "知识点",
                    "score": "得分", "max_score": "满分"
                })
                st.dataframe(detail_df, use_container_width=True, hide_index=True)

                # 知识点掌握雷达图
                kp_stats = exam_df.groupby("knowledge_point").agg(
                    avg_score=("score", "mean"),
                    max_score=("max_score", "first"),
                ).reset_index()
                kp_stats["mastery_rate"] = (kp_stats["avg_score"] / kp_stats["max_score"] * 100).round(1)
                fig = knowledge_radar_chart(kp_stats.to_dict("records"), f"{selected_exam} - 知识点掌握率")
                st.plotly_chart(fig, use_container_width=True)

                # AI单次考试分析 - 使用session_state持久化
                single_key = f"student_single_comment_{student_id}_{selected_exam}"
                if st.button("🤖 生成AI分析", type="primary", key="ai_single_exam"):
                    with st.spinner("AI正在分析本次考试..."):
                        try:
                            client = get_client()
                            exam_data = {
                                "student_name": student_info["name"],
                                "exam_name": selected_exam,
                                "total_score": round(exam_total, 2),
                                "mastery_rate": round(mastery_rate, 1),
                                "questions": [
                                    {"question_no": int(r["question_no"]), "knowledge_point": r["knowledge_point"],
                                     "score": r["score"], "max_score": r["max_score"]}
                                    for _, r in exam_df.iterrows()
                                ],
                                "knowledge_mastery": kp_stats.to_dict("records"),
                            }
                            st.session_state[single_key] = client.generate_comment(exam_data, "成绩通知")
                            st.rerun()
                        except Exception as e:
                            st.error(f"AI分析失败：{e}")

                # 显示已缓存的AI评语
                single_comment = st.session_state.get(single_key)
                if single_comment:
                    st.markdown("---")
                    st.markdown("### 📋 AI考试分析")
                    st.markdown(single_comment)
                    st.markdown("""
                    <div style="background:#fff3cd;padding:0.8rem;border-radius:0.5rem;border-left:4px solid #ffc107;margin:1rem 0;font-size:0.9em;">
                        <strong>⚠️ 声明：</strong>本分析由AI自动生成，仅供参考。具体评价请结合学生实际表现和专业判断。
                    </div>
                    """, unsafe_allow_html=True)

                # 导出单次分析报告
                st.markdown("---")
                st.subheader("📥 导出单次考试报告")
                single_sections = [
                    {"heading": "基本信息", "content": f"学生姓名：{student_info['name']}\n班级：{student_info['class_name']}\n考试名称：{selected_exam}\n总分：{exam_total:.1f}\n得分率：{mastery_rate:.1f}%"},
                    {"heading": "各题得分详情", "table": {
                        "headers": ["题号", "知识点", "得分", "满分", "得分率"],
                        "rows": [[int(r["question_no"]), r["knowledge_point"], r["score"], r["max_score"], f"{r['score']/r['max_score']*100:.1f}%"] for _, r in exam_df.iterrows()]
                    }},
                    {"heading": "知识点掌握情况", "table": {
                        "headers": ["知识点", "平均得分", "满分", "掌握率"],
                        "rows": [[r["knowledge_point"], f"{r['avg_score']:.1f}", f"{r['max_score']:.1f}", f"{r['mastery_rate']}%"] for _, r in kp_stats.iterrows()]
                    }},
                ]
                # AI评语（如果有）
                if single_comment:
                    single_sections.append({"heading": "AI考试分析", "content": single_comment})
                single_sections.append({"heading": "声明", "content": "本报告由AI自动生成，仅供参考。具体评价请结合学生实际表现和专业判断。"})

                col_w2, col_p2 = st.columns(2)
                with col_w2:
                    word_buf2 = export_to_word(f"{student_info['name']} - {selected_exam} 考试分析报告", single_sections)
                    st.download_button("📄 导出Word", data=word_buf2,
                                       file_name=f"单次考试分析_{student_info['name']}_{selected_exam}_{datetime.now().strftime('%Y%m%d')}.docx",
                                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                       key="word_single")
                with col_p2:
                    pdf_buf2 = export_to_pdf(f"{student_info['name']} - {selected_exam} 考试分析报告", single_sections)
                    st.download_button("📑 导出PDF", data=pdf_buf2,
                                       file_name=f"单次考试分析_{student_info['name']}_{selected_exam}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                       mime="application/pdf",
                                       key="pdf_single")
        else:
            st.info("该学生暂无成绩记录。")
