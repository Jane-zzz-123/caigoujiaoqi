import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO

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

    # 统一日期格式
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

# -------------------------- 核心指标（严格按两类统计） --------------------------
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


# -------------------------- 美观卡片（和你截图一致） --------------------------
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

# -------------------------- 总结 --------------------------
st.subheader("📝 月度对比总结")
if df_last.empty:
    st.info("无上月数据")
else:
    st.info(f"""
本月{selected_month}共{current_total}单，
准时率{current_on_time_rate:.1f}%，逾期{current_overdue}单，
平均交期差值{current_diff_avg:.2f}天。
""")

st.markdown("---")

# -------------------------- 图表（严格两类） --------------------------
st.subheader("📊 交期分析")
c1, c2 = st.columns(2)

with c1:
    st.markdown("#### 准时率占比")
    if current_total > 0:
        pie_df = pd.DataFrame({
            "类型": ["提前/准时", "逾期"],
            "数量": [current_on_time, current_overdue]
        })
        st.bar_chart(pie_df, x="类型", y="数量")

with c2:
    st.markdown("#### 交期差值分布")
    if current_total > 0:
        st.bar_chart(df_current["预计-实际交期的差值"].dropna())

st.markdown("---")

# -------------------------- 明细表 --------------------------
st.subheader("📋 交期明细")
table_cols = [
    "到货年月", "交期状态", "厂家", "下单时间", "采购单号", "品名", "SKU",
    "厂家类目明细", "产品分类", "采购交期", "实际采购交期", "预计-实际交期的差值"
]
df_table = df_current.copy()
df_table["sort"] = df_table["交期状态"].apply(lambda x: 0 if x == "逾期" else 1)
df_table = df_table.sort_values(["sort", "采购量"], ascending=[True, False])
st.dataframe(df_table[table_cols], use_container_width=True, height=300)

st.markdown("---")

# -------------------------- 厂家汇总 --------------------------
st.subheader("🏭 厂家交期统计")
if not df_current.empty:
    factory = df_current.groupby("厂家").agg(
        PO单数=("采购单号", "count"),
        准时=("交期状态", lambda x: (x == "提前/准时").sum()),
        逾期=("交期状态", lambda x: (x == "逾期").sum())
    )
    factory["准时率(%)"] = (factory["准时"] / factory["PO单数"] * 100).round(2)
    factory["逾期率(%)"] = (factory["逾期"] / factory["PO单数"] * 100).round(2)

    diff_agg = df_current.groupby("厂家").agg(
        平均交期差值=("预计-实际交期的差值", "mean"),
        最短交期=("实际采购交期", "min"),
        最长交期=("实际采购交期", "max")
    ).round(2)

    factory = pd.merge(factory, diff_agg, on="厂家").sort_values("PO单数", ascending=False)
    st.dataframe(factory, use_container_width=True)

st.markdown("---")

# -------------------------- 逾期分析 --------------------------
st.subheader("⚠️ 逾期厂家分析")
overdue = df_current[df_current["交期状态"] == "逾期"]
if overdue.empty:
    st.success("✅ 本月无逾期！")
else:
    st.dataframe(overdue[table_cols], use_container_width=True)