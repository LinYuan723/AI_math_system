import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


def score_distribution_chart(scores: list, title: str = "成绩分布图") -> go.Figure:
    """Create a histogram of score distribution."""
    fig = px.histogram(
        x=scores, nbins=20, title=title,
        labels={"x": "分数", "y": "人数"},
        color_discrete_sequence=["#4A90D9"],
    )
    fig.update_layout(
        xaxis_title="分数",
        yaxis_title="人数",
        bargap=0.05,
        template="plotly_white",
    )
    return fig


def knowledge_radar_chart(knowledge_data: list, title: str = "知识点掌握率雷达图") -> go.Figure:
    """Create a radar chart for knowledge point mastery rates.
    knowledge_data: list of dicts with 'knowledge_point' and 'mastery_rate' keys.
    """
    if not knowledge_data:
        return go.Figure()

    df = pd.DataFrame(knowledge_data)
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=df["mastery_rate"].tolist() + [df["mastery_rate"].iloc[0]],
        theta=df["knowledge_point"].tolist() + [df["knowledge_point"].iloc[0]],
        fill="toself",
        name="掌握率",
        fillcolor="rgba(74, 144, 217, 0.3)",
        line=dict(color="#4A90D9"),
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title=title,
        template="plotly_white",
    )
    return fig


def trend_chart(data: pd.DataFrame, x_col: str, y_col: str, name_col: str = None,
                title: str = "成绩趋势图") -> go.Figure:
    """Create a line chart for score trends."""
    if name_col:
        fig = px.line(data, x=x_col, y=y_col, color=name_col, title=title, markers=True)
    else:
        fig = px.line(data, x=x_col, y=y_col, title=title, markers=True)
    fig.update_layout(template="plotly_white")
    return fig


def pie_chart(labels: list, values: list, title: str = "分布图") -> go.Figure:
    """Create a pie chart."""
    fig = px.pie(
        names=labels, values=values, title=title,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


def error_type_bar(error_types: dict, title: str = "错误类型统计") -> go.Figure:
    """Create a bar chart for error type distribution."""
    fig = px.bar(
        x=list(error_types.keys()),
        y=list(error_types.values()),
        title=title,
        labels={"x": "错误类型", "y": "次数"},
        color=list(error_types.values()),
        color_continuous_scale="Reds",
    )
    fig.update_layout(template="plotly_white", showlegend=False)
    return fig
