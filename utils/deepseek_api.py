import os
import json
import re
import time
import streamlit as st
from openai import OpenAI, APITimeoutError, APIConnectionError, RateLimitError
from dotenv import load_dotenv

load_dotenv()


def _safe_json_loads(text: str):
    """Parse JSON with robust handling of common LLM output issues.
    Fixes unescaped backslashes in LaTeX (e.g. \\frac -> \\\\frac) and other quirks.
    """
    text = text.strip()
    # Valid JSON escapes to preserve: \\ \" \/ \n \r \t \b \f \uXXXX
    # All other \x sequences are likely LaTeX commands and need double escaping.
    VALID_ESCAPES = set('"\\/\n\r\t\b\f')

    def fix_backslashes(m):
        ch = m.group(1)
        if ch in VALID_ESCAPES:
            return m.group(0)  # valid JSON escape, keep as-is
        if ch == 'u' and len(m.group(0)) >= 6:
            hex_part = text[m.start()+2:m.start()+6]
            if len(hex_part) == 4 and all(c in '0123456789abcdefABCDEF' for c in hex_part):
                return m.group(0)  # valid \uXXXX, keep as-is
        return '\\\\' + ch  # lone \x -> \\x (double-escape for JSON)

    text = re.sub(r'\\(.)', fix_backslashes, text)
    return json.loads(text)


class DeepSeekClient:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置，请在 .env 文件中设置")
        self.client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            timeout=180.0,
        )
        self.model = st.session_state.get("ds_model", "deepseek-v4-pro")
        self.max_retries = 3

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return response.choices[0].message.content
            except (APITimeoutError, APIConnectionError, RateLimitError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
        raise last_error

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        system_prompt += "\n请严格以JSON格式返回，不要包含任何其他文字或markdown代码块标记。"
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=0.3,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                content = response.choices[0].message.content.strip()
                break
            except (APITimeoutError, APIConnectionError, RateLimitError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                continue
        else:
            raise last_error
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            if content.startswith("json"):
                content = content[4:].strip()
        return _safe_json_loads(content)

    def analyze_scores(self, score_data: dict) -> dict:
        system_prompt = (
            "你是一位经验丰富的初中数学教师和数据分析专家。"
            "请分析以下学生考试数据，给出详细的分析结果。"
            "返回JSON格式，包含以下字段：\n"
            "- class_summary: 班级整体情况总结（字符串）\n"
            "- weak_points: 薄弱知识点列表，每个元素包含knowledge_point和analysis\n"
            "- suggestions: 教学建议列表（字符串数组）\n"
            "- top_students: 优秀学生列表（字符串数组）\n"
            "- need_help: 需要关注的学生列表（字符串数组）"
        )
        return self.chat_json(system_prompt, json.dumps(score_data, ensure_ascii=False))

    def explain_error(self, question: str, wrong_answer: str, correct_answer: str, knowledge_point: str = "") -> dict:
        system_prompt = (
            "你是一位耐心的初中数学辅导老师。学生做错了以下题目，请给出详细的分析和讲解。"
            "返回JSON格式，包含以下字段：\n"
            "- error_type: 错误类型（概念混淆/计算失误/方法不当/审题不清/其他）\n"
            "- error_analysis: 错误原因分析（字符串）\n"
            "- solution_steps: 正确解题步骤（字符串数组，每步一个元素）\n"
            "- key_point: 关键知识点总结（字符串）\n"
            "- similar_tips: 避免类似错误的建议（字符串）"
        )
        user_prompt = f"题目：{question}\n学生答案：{wrong_answer}\n正确答案：{correct_answer}"
        if knowledge_point:
            user_prompt += f"\n涉及知识点：{knowledge_point}"
        return self.chat_json(system_prompt, user_prompt)

    def analyze_image(self, image_bytes: bytes) -> dict:
        """Analyze a math question image using OCR + LLM.
        Returns dict with knowledge_point, question_type, question_text, etc.
        """
        from utils.ocr import ocr_image_bytes
        ocr_text = ocr_image_bytes(image_bytes).strip()
        print(f"[OCR] 识别到 {len(ocr_text)} 个字符: {ocr_text[:200]}...")

        if not ocr_text:
            raise ValueError("未能从图片中识别出文字，请确保图片清晰、文字可辨。")

        system_prompt = (
            "你是一位经验丰富的初中数学教师。以下是一道数学题目的OCR识别文字，"
            "可能存在识别错误和排版错乱，请根据数学常识仔细修正和整理。\n\n"
            "重要：OCR文字中可能混合了题目内容、学生作答和教师批改痕迹，"
            "请仔细区分：\n"
            "- 题目原文（包含题干、选项等）\n"
            "- 学生手写的答案或解题过程\n"
            "- 教师批改的正确答案或批注（如红笔打钩、写分数、写\"正确\"等）\n\n"
            "返回JSON格式，包含以下字段（所有字段都必须填写，不能留空）：\n"
            "- knowledge_point: 涉及的知识点（必须填写，如\"一元二次方程\"、\"勾股定理\"、\"三角形全等\"等）\n"
            "- question_type: 题目类型，必须从以下4个中选一个：选择题/填空题/解答题/判断题\n"
            "- question_text: 整理后的完整题目内容（修正OCR识别错误，补全数学符号如分数、根号、平方等。选择题必须包含所有选项）\n"
            "- correct_answer: 正确答案（从OCR文字或批改痕迹中提取；如果完全无法确定则填\"未识别\"）\n"
            "- student_answer: 学生作答内容（从OCR文字或手写痕迹中提取；如果完全无法确定则填\"未识别\"）"
        )
        result = self.chat_json(system_prompt, f"以下是OCR识别出的文字内容：\n\n{ocr_text}")
        print(f"[LLM] 解析结果: knowledge_point={result.get('knowledge_point')}, "
              f"question_type={result.get('question_type')}, "
              f"question_text_len={len(result.get('question_text', ''))}")
        return result

    def generate_questions(self, topic: str, difficulty: int, q_type: str, count: int = 1) -> list:
        system_prompt = (
            "你是一位专业的初中数学命题教师。请根据要求生成数学题目。"
            "返回JSON格式，是一个数组，每个元素包含：\n"
            "- question: 题目内容\n"
            "- options: 选项数组（仅选择题需要，其他题型为空数组）\n"
            "- answer: 正确答案\n"
            "- explanation: 详细解析，分步骤说明解题过程\n"
            "- difficulty: 难度等级(1-5)\n"
            "- knowledge_point: 涉及的知识点\n\n"
            "重要规则：\n"
            "1. 选择题的options数组中，每个选项必须以A. B. C. D.开头，例如：[\"A. 选项内容\", \"B. 选项内容\", \"C. 选项内容\", \"D. 选项内容\"]\n"
            "2. 选择题的answer字段填写正确选项字母，如\"A\"或\"B\"\n"
            "3. 解析要分步骤，用句号分隔，便于阅读"
        )
        diff_desc = {1: "基础", 2: "简单", 3: "中等", 4: "较难", 5: "困难"}
        user_prompt = (
            f"请生成{count}道初中数学{q_type}题。\n"
            f"知识点/主题：{topic}\n"
            f"难度等级：{difficulty}（{diff_desc.get(difficulty, '中等')}）\n"
            f"题目要求：内容准确、表述清晰、适合初中生水平。"
        )
        return self.chat_json(system_prompt, user_prompt)

    def generate_comment(self, student_data: dict, scenario: str) -> str:
        scenario_prompts = {
            "学期评语": "请为该学生生成一份温暖、具体的学期末综合评语，既要肯定优点，也要委婉指出改进方向。",
            "成绩通知": "请生成一份成绩通知评语，客观反映学生近期学习情况，包含鼓励和建议。",
            "进步表扬": "请生成一份表扬评语，重点突出学生的进步和努力，给予积极鼓励。",
            "问题反馈": "请生成一份与家长沟通的评语，委婉反映学生存在的问题，并给出家校配合建议。",
            "假期建议": "请根据学生学情，生成一份假期学习计划和推荐练习建议。",
        }
        system_prompt = (
            "你是一位善于沟通的初中数学教师，擅长用温暖而专业的语言与家长沟通。"
            f"{scenario_prompts.get(scenario, '请生成一份个性化的学生评语。')}"
            "\n评语应该具体、有针对性，避免空话套话，字数在150-300字之间。"
        )
        return self.chat(system_prompt, json.dumps(student_data, ensure_ascii=False), temperature=0.8)

    def analyze_classroom_responses(self, question: str, responses: list) -> dict:
        system_prompt = (
            "你是一位经验丰富的初中数学教师。请分析以下课堂作答数据。"
            "返回JSON格式，包含：\n"
            "- correct_rate: 正确率（百分比数字）\n"
            "- common_errors: 共性错误列表，每个包含error_type和description\n"
            "- explanation: 针对共性错误的课堂讲解内容\n"
            "- next_step: 下一步教学建议"
        )
        user_prompt = f"课堂题目：{question}\n学生作答情况：{json.dumps(responses, ensure_ascii=False)}"
        return self.chat_json(system_prompt, user_prompt)

    def analyze_error_patterns(self, error_records: list[dict]) -> dict:
        """Analyze a student's historical error records to find patterns."""
        system_prompt = (
            "你是一位经验丰富的初中数学教师和学习分析师。请分析以下学生的错题记录，找出错误模式和规律。"
            "返回JSON格式，包含以下字段：\n"
            "- weak_points: 薄弱知识点排名，每个元素包含knowledge_point（知识点名称）、count（错误次数）、analysis（分析说明）\n"
            "- error_patterns: 错误模式列表，每个包含pattern（模式描述）、frequency（出现频率）、example（示例错题ID）\n"
            "- knowledge_relationships: 知识点关联分析，如\"因式分解薄弱会影响一元二次方程的求解\"（字符串数组）\n"
            "- priority_learning: 优先学习建议（字符串数组，按优先级排序）\n"
            "- overall_assessment: 整体评估（字符串）"
        )
        return self.chat_json(system_prompt, json.dumps(error_records, ensure_ascii=False))

    def chat_tutor(self, question: str, context: str, chat_history: list[dict], user_message: str) -> str:
        """Interactive conversational tutoring for a specific error."""
        system_prompt = (
            "你是一位耐心、善于启发的初中数学辅导老师。学生正在针对一道错题向你提问。"
            "请用通俗易懂的语言回答学生的问题，引导学生思考而不是直接给答案。"
            "如果学生问的是解题方法，先引导学生回忆相关知识点，再逐步讲解。"
            "回答要亲切自然，像面对面辅导一样。回答长度控制在100-300字。"
        )
        messages = [{"role": "system", "content": system_prompt}]
        # Add context as first assistant message
        messages.append({
            "role": "assistant",
            "content": f"我来帮你分析这道题。\n\n题目：{question}\n\n背景信息：{context}\n\n有什么问题尽管问我！"
        })
        # Add chat history
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.7,
            messages=messages,
        )
        return response.choices[0].message.content

    def generate_study_plan(self, weak_points: list[dict], student_name: str = "") -> dict:
        """Generate a personalized study plan based on weak points."""
        system_prompt = (
            "你是一位经验丰富的初中数学教师和学习规划师。请根据学生的薄弱知识点制定个性化学习计划。"
            "返回JSON格式，包含以下字段：\n"
            "- plan_title: 计划标题（字符串）\n"
            "- weekly_goals: 每周学习目标列表，每个包含week（周次）、focus（重点内容）、tasks（任务列表）、hours（建议学习时长）\n"
            "- daily_review: 每日复习安排（字符串）\n"
            "- resource_recommendations: 学习资源推荐（字符串数组）\n"
            "- milestones: 阶段性里程碑，每个包含milestone（目标描述）、target_date（建议时间）"
        )
        user_data = {"student_name": student_name, "weak_points": weak_points}
        return self.chat_json(system_prompt, json.dumps(user_data, ensure_ascii=False))


def get_client() -> DeepSeekClient:
    return DeepSeekClient()
