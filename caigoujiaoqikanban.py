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


# -------------------------- 加载数据 --------------------------
@st.cache_data(ttl=3600)
def load_data():
    url = "https://github.com/Jane-zzz-123/streamlit-dashboard/raw/main/caigoushuju.xlsx"
    response = requests.get(url)
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


df = load_data()

# -------------------------- 筛选器：默认最新月份 --------------------------
year_month_list = sorted(df["到货年月"].dropna().unique())
selected_month = st.selectbox("📅 选择到货年月", year_month_list, index=len(year_month_list) - 1)
df_current = df[df["到货年月"] == selected_month].copy()


# 获取上月
def get_last_month(ym):
    try:
        current_dt = datetime.strptime(ym, "%Y-%m")
        last_dt = current_dt - pd.DateOffset(months=1)
        return last_dt.strftime("%Y-%m")
    except:
        return None


last_month = get_last_month(selected_month)
df_last = df[df["到货年月"] == last_month].copy() if last_month else pd.DataFrame()

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


# -------------------------- 美观卡片 --------------------------
def card(col, title, current, last, suffix="", is_good_up=True):
    if last == 0:
        pct = "新数据"
    else:
        pct = (current - last) / last * 100
        pct = f"{pct:+.2f}%"

    if is_good_up:
        color = "#28a745" if current >= last else "#dc3545"
    else:
        color = "#dc3545" if current >= last else "#28a745"

    with col:
        st.markdown(f"""
        <div style="padding:18px; border-radius:12px; background:#fafbfc; border:1px solid #e5e7eb;">
          <div style="font-size:15px; color:#555; margin-bottom:8px;">{title}</div>
          <div style="font-size:30px; font-weight:600;">{current:.2f}{suffix}</div>
          <div style="font-size:13px; color:{color}; margin-top:6px;">
            环比 {pct}（上月：{last:.2f}）
          </div>
        </div>
        """, unsafe_allow_html=True)


st.subheader(f"📆 {selected_month} 整体分析")
col1, col2, col3, col4, col5 = st.columns(5)
card(col1, "PO单数", current_total, last_total, "", is_good_up=False)
card(col2, "提前/准时", current_on_time, last_on_time, "", is_good_up=True)
card(col3, "逾期", current_overdue, last_overdue, "", is_good_up=False)
card(col4, "准时率", current_on_time_rate, last_on_time_rate, "%", is_good_up=True)
card(col5, "平均交期差值", current_diff_avg, last_diff_avg, "天", is_good_up=False)

st.markdown("---")

# -------------------------- 月度对比总结 --------------------------
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

# -------------------------- ✨ 交期分析（和你参考图1:1还原） --------------------------
st.subheader("📊 准时率与时效偏差分布")
c1, c2 = st.columns(2)

with c1:
    st.markdown(f"#### {selected_month} 准时率分布")
    if current_total > 0:
        # 真正的饼图，绿/红两色，带百分比标签
        pie_data = pd.DataFrame({
            "状态": ["提前/准时", "逾期"],
            "数量": [current_on_time, current_overdue]
        })
        fig = px.pie(
            pie_data,
            values="数量",
            names="状态",
            color="状态",
            color_discrete_map={"提前/准时": "#28a745", "逾期": "#dc3545"},
            hole=0.3,
            labels={"数量": "订单数"}
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

with c2:
    st.markdown("#### 交期差值区间分布")
    if current_total > 0:
        # 处理差值数据，取整数并统计
        df_diff = df_current.copy()
        df_diff["差值(天)"] = df_diff["预计-实际交期的差值"].round(0).astype(int)
        diff_counts = df_diff["差值(天)"].value_counts().sort_index(ascending=False)

        # 分提前/准时和延迟
        on_time_diff = diff_counts[diff_counts.index >= 0]
        overdue_diff = diff_counts[diff_counts.index < 0]

        # 提前/准时部分
        st.markdown("✅ **提前/准时区间分布**")
        for day, cnt in on_time_diff.items():
            # 用绿色方块模拟条形，和参考图效果一致
            bar = "🟩" * min(cnt, 20)
            st.markdown(f"- +{day}天: {bar} ({cnt}单)")

        # 延迟部分
        st.markdown("❌ **延迟区间分布**")
        for day, cnt in overdue_diff.items():
            bar = "🟥" * min(cnt, 20)
            st.markdown(f"- {day}天: {bar} ({cnt}单)")

st.markdown("---")

# -------------------------- 明细表 --------------------------
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

    factory_df["总订单"] = factory_df["PO单数"]
    factory_df["准时率(%)"] = (factory_df["提前准时订单"] / factory_df["总订单"] * 100).round(2)
    factory_df["逾期率(%)"] = (factory_df["逾期订单"] / factory_df["总订单"] * 100).round(2)

    jq_df = df_current.groupby("厂家").agg(
        平均交期差值=("预计-实际交期的差值", "mean"),
        最短实际交期=("实际采购交期", "min"),
        最长实际交期=("实际采购交期", "max")
    ).round(2).reset_index()

    final = pd.merge(factory_df, jq_df, on="厂家")
    final = final.sort_values("PO单数", ascending=False)
    st.dataframe(final, use_container_width=True, height=300)

st.markdown("---")

# -------------------------- 逾期分析 --------------------------
st.subheader("⚠️ 逾期厂家专项分析")
overdue_df = df_current[df_current["交期状态"] == "逾期"]
if overdue_df.empty:
    st.success("✅ 本月无逾期订单！")
else:
    analyze_df = overdue_df.groupby("厂家").agg(
        逾期订单数=("采购单号", "count"),
        平均逾期差值=("预计-实际交期的差值", "mean"),
        涉及SKU数=("SKU", "nunique")
    ).round(2).sort_values("逾期订单数", ascending=False).reset_index()
    st.dataframe(analyze_df, use_container_width=True)
    st.dataframe(overdue_df[table_cols], use_container_width=True)

st.markdown("---")
st.success("✅ 看板已按参考图效果1:1还原！")