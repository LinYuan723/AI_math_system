"""Generate sample student score data for testing.
试卷结构回归基础，每种题型内部难度结构 7:2:1（基础:中档:难题）
"""
import pandas as pd
import random
import os

random.seed(42)

exam_name = "2025-2026学年第二学期期中考试"
class_name = "九年级（3）班"

# 40 students (mix of two-char and three-char names)
students = [
    "张伟", "李娜", "王芳", "刘洋", "陈静", "杨帆", "赵磊", "黄丽", "周强", "吴敏",
    "徐明杰", "孙红", "马超", "朱琳", "胡军", "郭敏", "林峰", "何雪梅", "高阳", "罗婷",
    "王浩然", "刘婷", "陈杰", "杨梅", "赵鹏飞", "黄磊", "周雪", "吴刚", "徐丽华", "孙强",
    "马琳", "朱军", "胡敏", "郭峰", "林雪", "何阳", "高明辉", "罗超", "王静怡", "李强"
]

# 24 questions: (number, type, max_score, knowledge_point)
questions = [
    (1, "选择题", 3, "正负数的实际意义（收入与支出）"),
    (2, "选择题", 3, "判断简单组合体的三视图"),
    (3, "选择题", 3, "计算单项式乘单项式"),
    (4, "选择题", 3, "平行线的性质（同旁内角）"),
    (5, "选择题", 3, "不等式解集在数轴上的表示"),
    (6, "选择题", 3, "事件类型的判断（必然事件）"),
    (7, "选择题", 3, "根据实际问题列二元一次方程组"),
    (8, "选择题", 3, "尺规作图（角平分线）与圆周角定理"),
    (9, "选择题", 3, "图形旋转与坐标变化"),
    (10, "选择题", 3, "二次函数图象与性质"),
    (11, "填空题", 3, "有理数的大小比较"),
    (12, "填空题", 3, "概率计算（古典概型）"),
    (13, "填空题", 3, "同分母分式加减法"),
    (14, "填空题", 3, "正比例函数的函数值计算"),
    (15, "填空题", 3, "等边三角形、勾股定理、相似三角形综合"),
    (16, "解答题", 6, "实数混合运算（含零指数幂）"),
    (17, "解答题", 6, "利用平行四边形的性质证明"),
    (18, "解答题", 6, "相似三角形应用（解直角三角形）"),
    (19, "解答题", 8, "统计综合（补图、估计、统计量分析）"),
    (20, "解答题", 8, "一次函数与反比例函数综合"),
    (21, "解答题", 8, "圆切线判定、弧长计算"),
    (22, "解答题", 10, "二次函数的实际应用（面积最值）"),
    (23, "解答题", 11, "图形变换与相似综合（矩形折叠）"),
    (24, "解答题", 12, "二次函数综合（平移、新定义区域）"),
]

TOTAL_MAX = sum(q[2] for q in questions)  # 120

# 每种题型内部 7:2:1 分布难度
# 选择题 10题: 7基础(1-7) + 2中档(8-9) + 1难题(10)  → 7:2:1
# 填空题  5题: 3基础(11-13) + 1中档(14) + 1难题(15)  → 3:1:1 ≈ 6:2:2
# 解答题  9题: 6基础(16-19,20-21) + 2中档(22-23) + 1难题(24)  → 6:2:1 ≈ 7:2:1
difficulty = {
    # 选择题 — 基础
    1: 0.92, 2: 0.88, 3: 0.90, 4: 0.85, 5: 0.86, 6: 0.92, 7: 0.84,
    # 选择题 — 中档
    8: 0.70, 9: 0.68,
    # 选择题 — 难题
    10: 0.48,
    # 填空题 — 基础
    11: 0.90, 12: 0.85, 13: 0.88,
    # 填空题 — 中档
    14: 0.72,
    # 填空题 — 难题
    15: 0.45,
    # 解答题 — 基础
    16: 0.88, 17: 0.82, 18: 0.80, 19: 0.80, 20: 0.80, 21: 0.80,
    # 解答题 — 中档
    22: 0.62, 23: 0.60,
    # 解答题 — 难题
    24: 0.30,
}

# 难度标签
level_map = {}
for q in questions:
    qn = q[0]
    p = difficulty[qn]
    level_map[qn] = "基础" if p >= 0.80 else ("中档" if p >= 0.60 else "难题")

# Student ability modifier
student_ability = {}
for s in students:
    student_ability[s] = random.gauss(0, 0.12)


def generate_score(q_num, q_type, max_score, student):
    base_prob = difficulty[q_num]
    ability = student_ability[student]
    prob = max(0.05, min(0.98, base_prob + ability))

    if q_type in ("选择题", "填空题"):
        return max_score if random.random() < prob else 0
    else:
        alpha = prob * 5
        beta_param = (1 - prob) * 5
        ratio = random.betavariate(max(alpha, 0.5), max(beta_param, 0.5))
        raw = ratio * max_score
        return min(max_score, max(0, round(raw)))


# Build data
rows: list[dict[str, int | str]] = []
for student in students:
    row: dict[str, int | str] = {"姓名": student}
    total = 0
    for q_num, q_type, max_score, kp in questions:
        score = generate_score(q_num, q_type, max_score, student)
        row[f"第{q_num}题"] = score
        total += score
    row["总分"] = total
    rows.append(row)

# Metadata sheet
meta_rows = []
for q_num, q_type, max_score, kp in questions:
    meta_rows.append({
        "题号": q_num,
        "题型": q_type,
        "分值": max_score,
        "难度": level_map[q_num],
        "考查知识点": kp,
    })
df_meta = pd.DataFrame(meta_rows)

# Score sheet
df = pd.DataFrame(rows)
col_order = ["姓名"] + [f"第{i}题" for i in range(1, 25)] + ["总分"]
df = df[col_order]

# Exam info sheet
df_info = pd.DataFrame([
    {"项目": "考试名称", "内容": exam_name},
    {"项目": "班级", "内容": class_name},
    {"项目": "学生人数", "内容": len(students)},
    {"项目": "满分", "内容": TOTAL_MAX},
])

# Write Excel
output_path = os.path.join(os.path.dirname(__file__), "sample_scores.xlsx")
with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
    df_info.to_excel(writer, sheet_name="考试信息", index=False)
    df_meta.to_excel(writer, sheet_name="题目信息", index=False)
    df.to_excel(writer, sheet_name="学生成绩", index=False)

print(f"Sample data saved to {output_path}")
print(f"\n=== 题目信息 ===")
print(df_meta.to_string(index=False))
print(f"\n总分范围: {df['总分'].min()} ~ {df['总分'].max()}（满分 {TOTAL_MAX}）")
print(f"平均总分: {df['总分'].mean():.1f}")
