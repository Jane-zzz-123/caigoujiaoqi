import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO
import plotly.express as px

# -------------------------- 页面设置 --------------------------
st.set_page_config(page_title="采购交期监控看板", page_icon="📊", layout="wide")
st.title("📦 采购交期监控可视化看板")
st.markdown("---")

# -------------------------- 加载数据（已修复正确链接） --------------------------
@st.cache_data(ttl=3600)
def load_data():
    try:
        # ✅ 正确的 raw 链接
        url = "https://github.com/Jane-zzz-123/caigoujiaoqi/raw/main/caigoushuju.xlsx"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        excel_file = BytesIO(response.content)

        df = pd.read_excel(excel_file, sheet_name="源数据")

        need_cols = [
            "是否加入看板", "采购单号", "下单时间", "品名", "SKU", "采购量", "待到货量",
            "到货年月", "采购交期", "预计到货时间修改", "异常数据", "厂家",
            "厂家类目明细", "产品分类", "实际采购交期", "交期状态", "预计-实际交期的差值"
        ]
        df = df[need_cols]
        df = df[df["是否加入看板"] == "是"].reset_index(drop=True)

        df["到货年月"] = pd.to_datetime(df["到货年月"], errors="coerce").dt.to_period("M").astype(str)
        df["实际采购交期"] = pd.to_numeric(df["实际采购交期"], errors="coerce")
        df["预计-实际交期的差值"] = pd.to_numeric(df["预计-实际交期的差值"], errors="coerce")

        return df
    except Exception as e:
        st.error(f"数据加载失败：{str(e)}")
        return pd.DataFrame()

df = load_data()
if df.empty:
    st.stop()

# -------------------------- 筛选器：年月 + 厂家 --------------------------
col1, col2 = st.columns(2)
with col1:
    year_month_list = sorted(df["到货年月"].dropna().unique())
    selected_month = st.selectbox("📅 选择到货年月", year_month_list, index=len(year_month_list)-1)

with col2:
    factory_list = sorted(df["厂家"].dropna().unique())
    selected_factory = st.multiselect("🏭 筛选厂家（默认全部）", factory_list, default=[])

# 应用筛选
df_current = df[df["到货年月"] == selected_month].copy()
if selected_factory:
    df_current = df_current[df_current["厂家"].isin(selected_factory)]

# -------------------------- 上月数据 --------------------------
def get_last_month(ym):
    try:
        current_dt = datetime.strptime(ym, "%Y-%m")
        last_dt = current_dt - pd.DateOffset(months=1)
        return last_dt.strftime("%Y-%m")
    except:
        return None

last_month = get_last_month(selected_month)
df_last = df[df["到货年月"] == last_month].copy() if last_month else pd.DataFrame()
if selected_factory and not df_last.empty:
    df_last = df_last[df_last["厂家"].isin(selected_factory)]

st.markdown("---")

# -------------------------- 核心指标 --------------------------
current_total = len(df_current)
current_on_time = len(df_current[df_current["交期状态"] == "提前/准时"])
current_overdue = len(df_current[df_current["交期状态"] == "逾期"])
current_on_time_rate = (current_on_time / current_total * 100) if current_total > 0 else 0.0
current_diff_avg = df_current["预计-实际交期的差值"].mean() if current_total > 0 else 0.0

last_total = len(df_last) if not df_last.empty else 0
last_on_time = len(df_last[df_last["交期状态"] == "提前/准时"]) if not df_last.empty else 0
last_overdue = len(df_last[df_last["交期状态"] == "逾期"]) if not df_last.empty else 0
last_on_time_rate = (last_on_time / last_total * 100) if last_total > 0 else 0.0
last_diff_avg = df_last["预计-实际交期的差值"].mean() if (not df_last.empty and last_total > 0) else 0.0

# -------------------------- 卡片组件 --------------------------
def card(col, title, current, last, suffix="", is_good_up=True, bg_color="#fafbfc", is_int=False):
    if last == 0:
        pct = "新数据"
    else:
        pct = (current - last) / last * 100
        pct = f"{pct:+.2f}%"

    if is_good_up:
        color = "#28a745" if current >= last else "#dc3545"
    else:
        color = "#dc3545" if current >= last else "#28a745"

    if is_int:
        current_str = f"{int(current)}"
        last_str = f"{int(last)}"
    else:
        current_str = f"{current:.2f}"
        last_str = f"{last:.2f}"

    with col:
        st.markdown(f"""
        <div style="padding:18px; border-radius:12px; background:{bg_color}; border:1px solid #e5e7eb;">
          <div style="font-size:15px; color:#555; margin-bottom:8px;">{title}</div>
          <div style="font-size:30px; font-weight:600;">{current_str}{suffix}</div>
          <div style="font-size:13px; color:{color}; margin-top:6px;">
            环比 {pct}（上月：{last_str}{suffix}）
          </div>
        </div>
        """, unsafe_allow_html=True)

st.subheader(f"📆 {selected_month} 整体分析")
col1, col2, col3, col4, col5 = st.columns(5)

card(col1, "PO单数", current_total, last_total, "", is_good_up=False, is_int=True)
card(col2, "提前/准时", current_on_time, last_on_time, "", is_good_up=True, bg_color="#f0fdf4", is_int=True)
card(col3, "逾期", current_overdue, last_overdue, "", is_good_up=False, bg_color="#fef2f2", is_int=True)
card(col4, "准时率", current_on_time_rate, last_on_time_rate, "%", is_good_up=True, bg_color="#eff6ff")
card(col5, "平均交期差值", current_diff_avg, last_diff_avg, "天", is_good_up=False)

st.markdown("---")

# -------------------------- 月度总结 --------------------------
st.subheader("📝 月度对比总结")
if df_last.empty:
    st.info("无上月数据，无法环比对比")
else:
    po_trend = "上升" if current_total > last_total else "下降"
    rate_trend = "提升" if current_on_time_rate > last_on_time_rate else "下降"
    overdue_trend = "增加" if current_overdue > last_overdue else "减少"
    diff_trend = "延长" if (current_diff_avg or 0) > (last_diff_avg or 0) else "缩短"

    txt = f"""
    本月{selected_month}共{current_total}单，较上月{po_trend}；
    准时率{current_on_time_rate:.1f}%，较上月{rate_trend}；
    逾期订单{current_overdue}单，较上月{overdue_trend}；
    平均交期差值{current_diff_avg:.2f}天，较上月{diff_trend}。
    """
    st.info(txt)

st.markdown("---")

# -------------------------- 饼图 & 交期分布 --------------------------
st.subheader("📊 准时率与时效偏差分布")
c1, c2 = st.columns(2)

with c1:
    st.markdown(f"#### {selected_month} 准时率分布")
    if current_total > 0:
        pie_data = pd.DataFrame({
            "状态": ["提前/准时", "逾期"],
            "数量": [current_on_time, current_overdue]
        })
        fig = px.pie(
            pie_data,
            values="数量",
            names="状态",
            color="状态",
            # 这里强制设置颜色：提前/准时用绿色，逾期用红色
            color_discrete_map={"提前/准时": "#28a745", "逾期": "#dc3545"},
            hole=0.3,
            labels={"数量": "订单数"}
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

with c2:
    st.markdown("#### 交期差值区间分布")
    if current_total > 0:
        df_diff = df_current.copy()
        df_diff["差值(天)"] = df_diff["预计-实际交期的差值"].round(0).astype(int)
        diff_counts = df_diff["差值(天)"].value_counts().sort_index(ascending=False)
        on_time_diff = diff_counts[diff_counts.index >= 0]
        overdue_diff = diff_counts[diff_counts.index < 0]

        st.markdown("✅ **提前/准时**")
        for day, cnt in on_time_diff.items():
            bar = "🟩" * min(cnt, 20)
            st.markdown(f"- +{day}天: {bar} ({cnt}单)")

        st.markdown("❌ **延迟**")
        for day, cnt in overdue_diff.items():
            bar = "🟥" * min(cnt, 20)
            st.markdown(f"- {day}天: {bar} ({cnt}单)")

st.markdown("---")

# -------------------------- 明细 --------------------------
st.subheader("📋 交期数据明细")
table_cols = [
    "到货年月", "交期状态", "厂家", "下单时间", "采购单号", "品名", "SKU",
    "厂家类目明细", "产品分类", "采购交期", "实际采购交期", "预计-实际交期的差值"
]
df_table = df_current.copy()
df_table["排序标识"] = df_table["交期状态"].apply(lambda x: 0 if x == "逾期" else 1)
df_table = df_table.sort_values(["排序标识", "采购量"], ascending=[True, False])
st.dataframe(df_table[table_cols], use_container_width=True, height=300)

st.markdown("---")

# -------------------------- 厂家汇总 --------------------------
st.subheader("🏭 各厂家交期统计汇总")
if not df_current.empty:
    factory_df = df_current.groupby("厂家").agg(
        PO单数=("采购单号", "count"),
        提前准时订单=("交期状态", lambda x: (x == "提前/准时").sum()),
        逾期订单=("交期状态", lambda x: (x == "逾期").sum())
    ).reset_index()

    factory_df["准时率(%)"] = (factory_df["提前准时订单"] / factory_df["PO单数"] * 100).round(2)
    jq_df = df_current.groupby("厂家").agg(
        平均交期差值=("预计-实际交期的差值", "mean"),
        最短实际交期=("实际采购交期", "min"),
        最长实际交期=("实际采购交期", "max")
    ).round(2).reset_index()

    final = pd.merge(factory_df, jq_df, on="厂家")
    final = final.sort_values("PO单数", ascending=False)
    st.dataframe(final, use_container_width=True, height=300)

st.markdown("---")
# -------------------------- 厂家订单数+准时率 组合分析 --------------------------
st.subheader("📊 厂家订单数 & 准时率 组合分析")
if not df_current.empty:
    factory_chart = df_current.groupby("厂家").agg(
        订单数=("采购单号","count"),
        准时订单数=("交期状态",lambda x: (x=="提前/准时").sum())
    ).reset_index()
    factory_chart["准时率(%)"] = (factory_chart["准时订单数"]/factory_chart["订单数"]*100).round(1)
    factory_chart = factory_chart.sort_values("订单数", ascending=False)

    import plotly.graph_objects as go
    fig = go.Figure()

    # 柱状图 + 显示订单数
    fig.add_trace(go.Bar(
        x=factory_chart["厂家"],
        y=factory_chart["订单数"],
        name="订单数",
        marker_color="#5dade2",
        text=factory_chart["订单数"],  # 显示数值
        textposition="outside",        # 显示在柱子顶部
        textfont=dict(size=12)
    ))

    # 折线图 + 显示准时率
    fig.add_trace(go.Scatter(
        x=factory_chart["厂家"],
        y=factory_chart["准时率(%)"],
        name="准时率(%)",
        mode="lines+markers+text",     #  lines + 点 + 文字
        text=factory_chart["准时率(%)"].astype(str)+"%",  # 显示百分比
        textposition="top center",
        marker=dict(size=8, color="#e74c3c"),
        line=dict(width=3),
        yaxis="y2"
    ))

    fig.update_layout(
        xaxis_title="厂家",
        yaxis=dict(title="订单数", side="left"),
        yaxis2=dict(title="准时率(%)", overlaying="y", side="right", range=[0,100]),
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("🏷️ 厂家 - 全品类明细履约分析（按准时率自动评级上色）")

df_category = df_current[
    (df_current["厂家"].notna()) &
    (df_current["厂家类目明细"].notna())
].copy()

if df_category.empty:
    st.warning("当前筛选条件下无厂家类目明细数据")
else:
    # 1. 统计每个厂家 + 每个品类 的数据
    category_stats = df_category.groupby(["厂家", "厂家类目明细"]).agg(
        订单数=("采购单号", "count"),
        准时数=("交期状态", lambda x: (x == "提前/准时").sum()),
    ).reset_index()

    category_stats["准时率%"] = round(
        category_stats["准时数"] / category_stats["订单数"] * 100, 1
    )

    # 2. 厂家整体数据（总订单、整体准时率）
    factory_total = df_category.groupby("厂家").agg(
        总订单=("采购单号", "count"),
        总准时=("交期状态", lambda x: (x == "提前/准时").sum())
    ).reset_index()
    factory_total["整体准时率%"] = round(
        factory_total["总准时"] / factory_total["总订单"] * 100, 1
    )

    # 3. 开始生成卡片（3列布局）
    st.markdown("#### 📌 各厂家全品类明细卡片")
    factory_list = factory_total["厂家"].unique()
    cols = st.columns(3)

    for idx, factory_name in enumerate(factory_list):
        # 厂家基础信息
        f_data = factory_total[factory_total["厂家"] == factory_name].iloc[0]
        total_order = f_data["总订单"]
        factory_rate = f_data["整体准时率%"]

        # 该厂家所有品类
        cats = category_stats[category_stats["厂家"] == factory_name]

        # 整体评级
        if factory_rate >= 90:
            bg_color = "#f0fdf4"
            border = "#4ade80"
            level = "✅ 整体优质"
        elif factory_rate >= 70:
            bg_color = "#fffbeb"
            border = "#fbbf24"
            level = "⚠️ 整体合格"
        else:
            bg_color = "#fef2f2"
            border = "#f87171"
            level = "❌ 整体需整改"

        # 品类明细（自动上色）
        cat_lines = []
        for _, row in cats.iterrows():
            c_name = row["厂家类目明细"]
            c_num = row["订单数"]
            c_rate = row["准时率%"]

            # 按你要求自动上色
            if c_rate >= 90:
                # 优质 → 绿色
                line = f"✅ <span style='color:#16a34a; font-weight:bold'>{c_name}</span>：{c_num}单 | {c_rate}%"
            elif c_rate >= 70:
                # 合格 → 橙色
                line = f"🔸 <span style='color:#f97316; font-weight:bold'>{c_name}</span>：{c_num}单 | {c_rate}%"
            else:
                # 短板 → 红色
                line = f"🔻 <span style='color:#dc2626; font-weight:bold'>{c_name}</span>：{c_num}单 | {c_rate}%"

            cat_lines.append(line)

        cat_html = "<br>".join(cat_lines)

        # 输出卡片
        with cols[idx % 3]:
            st.markdown(f"""
            <div style="padding:16px; border-radius:12px; background:{bg_color}; border:2px solid {border}; margin-bottom:15px;">
                <div style="font-size:17px; font-weight:bold; margin-bottom:8px;">🏭 {factory_name}</div>
                <div style="font-size:14px; line-height:1.8;">
                    总订单：{total_order} 单<br>
                    整体准时率：<b>{factory_rate}%</b><br>
                    综合评级：{level}<br>
                    <hr style="margin:8px 0;">
                    <b>📂 全部品类明细：</b><br>
                    {cat_html}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 底部说明
    st.markdown("---")
    st.info("""
    💡 颜色说明：
    ✅ **绿色（≥90%）** = 优质品类
    🔸 **橙色（70%~89%）** = 合格品类
    🔻 **红色（＜70%）** = 短板品类
    """)