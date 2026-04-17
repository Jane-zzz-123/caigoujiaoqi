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
    url = "https://github.com/Jane-zzz-123/caigoujiaoqi/raw/main/caigoushuju.xlsx"
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

    df["到货年月"] = df["到货年月"].astype(str).str.strip()
    df["实际采购交期"] = pd.to_numeric(df["实际采购交期"], errors="coerce")
    df["预计-实际交期的差值"] = pd.to_numeric(df["预计-实际交期的差值"], errors="coerce")

    return df


df = load_data()

# -------------------------- 筛选器 --------------------------
year_month_list = sorted(df["到货年月"].dropna().unique())
selected_month = st.selectbox("📅 选择到货年月", year_month_list)
df_current = df[df["到货年月"] == selected_month].copy()


def get_last_month(ym):
    try:
        current_dt = datetime.strptime(ym, "%Y%m")
        last_dt = current_dt - pd.DateOffset(months=1)
        return last_dt.strftime("%Y%m")
    except:
        return None


last_month = get_last_month(selected_month)
df_last = df[df["到货年月"] == last_month].copy() if last_month else pd.DataFrame()

st.markdown("---")

# -------------------------- 指标卡片 --------------------------
st.subheader(f"📆 {selected_month} 月度整体分析")

current_po = df_current["采购单号"].nunique()
current_on_time = df_current[df_current["交期状态"].isin(["提前", "准时"])].shape[0]
current_overdue = df_current[df_current["交期状态"] == "逾期"].shape[0]
current_total = current_on_time + current_overdue
current_on_time_rate = current_on_time / current_total * 100 if current_total > 0 else 0
current_diff_avg = df_current["预计-实际交期的差值"].mean()

last_po = df_last["采购单号"].nunique() if not df_last.empty else 0
last_on_time = df_last[df_last["交期状态"].isin(["提前", "准时"])].shape[0] if not df_last.empty else 0
last_overdue = df_last[df_last["交期状态"] == "逾期"].shape[0] if not df_last.empty else 0
last_on_time_rate = last_on_time / (last_on_time + last_overdue) * 100 if (last_on_time + last_overdue) > 0 else 0
last_diff_avg = df_last["预计-实际交期的差值"].mean() if not df_last.empty else 0

col1, col2, col3, col4, col5 = st.columns(5)
with col1: st.metric("PO单数", current_po, f"{current_po - last_po}")
with col2: st.metric("提前/准时订单", current_on_time, f"{current_on_time - last_on_time}")
with col3: st.metric("逾期订单", current_overdue, f"{current_overdue - last_overdue}")
with col4: st.metric("准时率(%)", round(current_on_time_rate, 1),
                     f"{round(current_on_time_rate - last_on_time_rate, 1)}%")
with col5: st.metric("平均交期差值(天)", round(current_diff_avg, 1) if current_diff_avg else 0,
                     f"{round((current_diff_avg or 0) - (last_diff_avg or 0), 1)}")

st.markdown("---")

# -------------------------- 总结 --------------------------
st.subheader("📝 月度对比总结")
if df_last.empty:
    st.info("⚠️ 无上月数据，无法环比")
else:
    po_trend = "上升" if current_po > last_po else "下降"
    rate_trend = "提升" if current_on_time_rate > last_on_time_rate else "下降"
    overdue_trend = "增加" if current_overdue > last_overdue else "减少"
    diff_trend = "延长" if (current_diff_avg or 0) > (last_diff_avg or 0) else "缩短"

    txt = f"""
    本月{selected_month}共{current_po}单，较上月{po_trend}；
    准时率{current_on_time_rate:.1f}%，较上月{rate_trend}；
    逾期订单{current_overdue}单，较上月{overdue_trend}；
    平均交期差值{current_diff_avg:.1f}天，较上月{diff_trend}。
    """
    st.info(txt)

st.markdown("---")

# -------------------------- 图表（原生 streamlit 图表，无需 matplotlib） --------------------------
st.subheader("📊 交期状态分析")

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### 准时率占比")
    if current_total > 0:
        pie_df = pd.DataFrame({
            "状态": ["提前/准时", "逾期"],
            "数量": [current_on_time, current_overdue]
        })
        st.dataframe(pie_df, use_container_width=True)
        st.bar_chart(pie_df, x="状态", y="数量")

with c2:
    st.markdown("#### 交期状态分布")
    if current_total > 0:
        status_df = df_current["交期状态"].value_counts().reindex(["提前", "准时", "逾期"], fill_value=0)
        st.bar_chart(status_df)

st.markdown("#### 预计-实际交期差值分布")
if not df_current["预计-实际交期的差值"].dropna().empty:
    st.bar_chart(df_current["预计-实际交期的差值"].dropna())

st.markdown("---")

# -------------------------- 交期明细表 --------------------------
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

# -------------------------- 厂家统计表 --------------------------
st.subheader("🏭 厂家交期统计汇总")
if not df_current.empty:
    factory_df = df_current.groupby("厂家").agg(
        PO单数=("采购单号", "nunique"),
        提前准时订单=("交期状态", lambda x: x.isin(["提前", "准时"]).sum()),
        逾期订单=("交期状态", lambda x: (x == "逾期").sum())
    ).reset_index()

    factory_df["总订单"] = factory_df["提前准时订单"] + factory_df["逾期订单"]
    factory_df["准时率(%)"] = (factory_df["提前准时订单"] / factory_df["总订单"] * 100).round(1)
    factory_df["逾期率(%)"] = (factory_df["逾期订单"] / factory_df["总订单"] * 100).round(1)

    jq_df = df_current.groupby("厂家").agg(
        平均交期差值=("预计-实际交期的差值", "mean"),
        最短实际交期=("实际采购交期", "min"),
        最长实际交期=("实际采购交期", "max")
    ).round(1).reset_index()

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
        逾期订单数=("采购单号", "nunique"),
        平均逾期差值=("预计-实际交期的差值", "mean"),
        涉及SKU数=("SKU", "nunique")
    ).round(1).sort_values("逾期订单数", ascending=False).reset_index()
    st.dataframe(analyze_df, use_container_width=True)
    st.dataframe(overdue_df[table_cols], use_container_width=True)

st.markdown("---")
st.success("✅ 看板加载完成！")