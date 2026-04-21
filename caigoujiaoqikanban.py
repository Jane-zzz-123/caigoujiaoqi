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
            "是否加入看板", "采购单号", "下单时间", "品名", "SKU", "采购量", "到货量",
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
# -------------------------- 逾期分析 --------------------------
# -------------------------- 厂家履约评级分析（按准时率） --------------------------
st.subheader("⚠️ 厂家履约评级分析（按准时率）")

# 计算所有厂家指标（新增：采购量、到货量）
factory_analysis = df_current.groupby("厂家").agg(
    订单总数=("采购单号", "count"),
    准时订单数=("交期状态", lambda x: (x == "提前/准时").sum()),
    逾期订单数=("交期状态", lambda x: (x == "逾期").sum()),
    平均实际交期=("实际采购交期", "mean"),
    最长实际交期=("实际采购交期", "max"),
    采购量合计=("采购量", "sum"),
    到货量合计=("到货量", "sum")
).reset_index()

# 计算整体总计（用于占比）
total_purchase = factory_analysis["采购量合计"].sum()
total_arrival = factory_analysis["到货量合计"].sum()

# 计算指标
factory_analysis["准时率"] = (factory_analysis["准时订单数"] / factory_analysis["订单总数"] * 100).round(1)
factory_analysis["订单占比"] = (factory_analysis["订单总数"] / factory_analysis["订单总数"].sum() * 100).round(1)
factory_analysis["采购量占比"] = (factory_analysis["采购量合计"] / total_purchase * 100).round(2)
factory_analysis["到货量占比"] = (factory_analysis["到货量合计"] / total_arrival * 100).round(2)

# 排序
factory_analysis = factory_analysis.sort_values("订单总数", ascending=False).reset_index(drop=True)

# 一行四列卡片展示
cols = st.columns(4)
for idx, row in factory_analysis.iterrows():
    # 评级 + 颜色
    rate = row["准时率"]
    if rate >= 90:
        level = "优质"
        bg_color = "#f0fdf4"
        border_color = "#bbf7d0"
    elif rate >= 80:
        level = "合格"
        bg_color = "#fffbeb"
        border_color = "#fed7aa"
    else:
        level = "异常"
        bg_color = "#fef2f2"
        border_color = "#fecaca"

    with cols[idx % 4]:
        st.markdown(f"""
        <div style="padding:16px; border-radius:12px; background:{bg_color}; border:2px solid {border_color}; margin-bottom:15px;">
            <div style="font-size:16px; font-weight:600; margin-bottom:6px;">
                {row['厂家']} <span style="font-size:13px;">[{level}]</span>
            </div>
            <div style="font-size:14px; line-height:1.7;">
                准时率：{rate}%<br/>
                订单数：{int(row['订单总数'])} 单（{row['订单占比']}%）<br/>
                准时：{int(row['准时订单数'])} 单｜逾期：{int(row['逾期订单数'])} 单<br/>
                采购量：{int(row['采购量合计'])}（占比：{row['采购量占比']:.2f}%）<br/>
                到货量：{int(row['到货量合计'])}（占比：{row['到货量占比']:.2f}%）<br/>
                平均交期：{row['平均实际交期']:.1f} 天<br/>
                最长交期：{row['最长实际交期']:.1f} 天
            </div>
        </div>
        """, unsafe_allow_html=True)

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
        逾期数=("交期状态", lambda x: (x == "逾期").sum()),
        平均交期=("实际采购交期", "mean"),
        最长交期=("实际采购交期", "max")
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
        elif factory_rate >= 80:
            bg_color = "#fffbeb"
            border = "#fbbf24"
            level = "⚠️ 整体合格"
        else:
            bg_color = "#fef2f2"
            border = "#f87171"
            level = "❌ 整体需整改"

        # 品类明细（自动上色 + 显示全部字段）
        cat_lines = []
        for _, row in cats.iterrows():
            c_name = row["厂家类目明细"]
            c_num = row["订单数"]
            c_on = row["准时数"]
            c_over = row["逾期数"]
            c_rate = row["准时率%"]
            c_avg = round(row["平均交期"],1)
            c_max = round(row["最长交期"],1)

            # 按你要求自动上色
            if c_rate >= 90:
                # 优质 → 绿色
                line = f"✅ <span style='color:#16a34a; font-weight:bold'>{c_name}</span>：{c_num}单｜准时{c_on}｜逾期{c_over}｜{c_rate}%｜平均交期{c_avg}天｜最长交期{c_max}天"
            elif c_rate >= 80:
                # 合格 → 橙色
                line = f"🔸 <span style='color:#f97316; font-weight:bold'>{c_name}</span>：{c_num}单｜准时{c_on}｜逾期{c_over}｜{c_rate}%｜平均交期{c_avg}天｜最长交期{c_max}天"
            else:
                # 短板 → 红色
                line = f"🔻 <span style='color:#dc2626; font-weight:bold'>{c_name}</span>：{c_num}单｜准时{c_on}｜逾期{c_over}｜{c_rate}%｜平均交期{c_avg}天｜最长交期{c_max}天"

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

# -------------------------- 最终完整版：产品分类×厂家对比表 --------------------------
st.markdown("---")
st.subheader("📊 产品分类 × 厂家 履约对比表")

# 1. 基础数据计算
compare_df = df_current.groupby(["产品分类", "厂家"], as_index=False).agg(
    订单数=("采购单号", "count"),
    准时数=("交期状态", lambda x: (x == "提前/准时").sum()),
    逾期数=("交期状态", lambda x: (x == "逾期").sum()),
    平均交期=("实际采购交期", "mean"),
    采购量=("采购量", "sum"),
)

# 准时率
compare_df["准时率%"] = (compare_df["准时数"] / compare_df["订单数"] * 100).round(1)

# 平均交期保留2位小数
compare_df["平均交期"] = compare_df["平均交期"].round(2)

# 2. 计算【分类总采购量】（用于排序）
category_sum = compare_df.groupby("产品分类")["采购量"].sum().reset_index()
category_sum.columns = ["产品分类", "分类总采购量"]
compare_df = compare_df.merge(category_sum, on="产品分类")

# 3. 计算【采购量占比%】
compare_df["采购量占比%"] = (compare_df["采购量"] / compare_df["分类总采购量"] * 100).round(2)

# 4. 履约等级
def level(rate):
    if rate >= 90:
        return "🟢 优质"
    elif rate >= 80:
        return "🟡 合格"
    else:
        return "🔴 异常"

compare_df["等级"] = compare_df["准时率%"].apply(level)

# 5. 统计厂家数量
supplier_count = compare_df.groupby("产品分类")["厂家"].nunique().reset_index()
supplier_count.columns = ["产品分类", "厂家数"]
compare_df = compare_df.merge(supplier_count, on="产品分类")

# ====================== 核心排序 ======================
# 1. 按【产品分类总采购量】从大到小
# 2. 分类内按【厂家采购量】从大到小
compare_df = compare_df.sort_values(
    by=["分类总采购量", "采购量"],
    ascending=[False, False]
).reset_index(drop=True)
# ======================================================

# 最终展示表格
final_table = compare_df[[
    "产品分类", "厂家数", "厂家", "准时率%", "等级",
    "订单数", "逾期数", "平均交期", "采购量", "采购量占比%"
]]

st.dataframe(final_table, use_container_width=True, hide_index=True)

st.info("""
履约等级文字颜色：🟢绿色=优质｜🟡黄色=合格｜🔴红色=异常高危
""")
# -------------------------- 定制字段格式 · 紧凑三列决策卡片 --------------------------
st.markdown("---")
st.subheader("💡 各品类采购下单建议")

summary_group = compare_df.groupby("产品分类", sort=False)
cate_list = list(summary_group)

# 3列循环排版
for i in range(0, len(cate_list), 3):
    batch = cate_list[i:i+3]
    cols = st.columns(3)

    for idx, (cate, group_data) in enumerate(batch):
        with cols[idx]:
            with st.container(border=True):
                # 品类标题
                st.markdown(f"**📦 {cate}**")

                # 1. 优质厂家
                good_df = group_data[group_data["等级"] == "🟢 优质"]
                if not good_df.empty:
                    st.success("✅ 优先下单")
                    for _, r in good_df.iterrows():
                        st.caption(
                            f"{r['厂家']} | 订单数：{int(r['订单数'])}单 | "
                            f"准时订单数：{int(r['准时数'])}单 | 逾期订单数：{int(r['逾期数'])}单 | "
                            f"准时率：{r['准时率%']}%"
                        )

                # 2. 合格厂家
                normal_df = group_data[group_data["等级"] == "🟡 合格"]
                if not normal_df.empty:
                    st.warning("⚠️ 适量下单")
                    for _, r in normal_df.iterrows():
                        st.caption(
                            f"{r['厂家']} | 订单数：{int(r['订单数'])}单 | "
                            f"准时订单数：{int(r['准时数'])}单 | 逾期订单数：{int(r['逾期数'])}单 | "
                            f"准时率：{r['准时率%']}%"
                        )

                # 3. 异常厂家
                bad_df = group_data[group_data["等级"] == "🔴 异常"]
                if not bad_df.empty:
                    st.error("🔴 严控订单")
                    for _, r in bad_df.iterrows():
                        st.caption(
                            f"{r['厂家']} | 订单数：{int(r['订单数'])}单 | "
                            f"准时订单数：{int(r['准时数'])}单 | 逾期订单数：{int(r['逾期数'])}单 | "
                            f"准时率：{r['准时率%']}%"
                        )

                # 底部风险提示
                if good_df.empty:
                    st.info("💡 暂无优质供方")
                if group_data["厂家数"].iloc[0] == 1:
                    st.warning("⚠️ 单一供应风险")


# ====================== 最终实用版 厂家产能分析看板 ======================
st.markdown("---")
st.header("🏭 厂家产能负载&下单承载力分析")
st.caption("核心目的：判断厂家当前能不能再接新订单，避免大面积逾期")

df_cap_final = df.copy()
# 时间标准化
df_cap_final["到货年月"] = pd.to_datetime(df_cap_final["到货年月"]).dt.to_period("M")
df_cap_final["下单年月"] = pd.to_datetime(df_cap_final["下单时间"]).dt.to_period("M")

# 1. 选择当月
all_month = sorted(df_cap_final["下单年月"].unique(), reverse=True)
selected_month = st.selectbox("选择要评估下单承载力的月份", all_month)

# 2. 计算厂家长期基准产能（近6个月正常到货水平）
recent_6_month = sorted(df_cap_final["到货年月"].unique())[-6:]
base_cap = df_cap_final[df_cap_final["到货年月"].isin(recent_6_month)]\
    .groupby(["厂家", "到货年月"])["采购量"].sum()\
    .reset_index().groupby("厂家")["采购量"].mean().reset_index()
base_cap.columns = ["厂家", "厂家月度基准产能"]

# 3. 当月实际下单负载
current_load = df_cap_final[df_cap_final["下单年月"] == selected_month]\
    .groupby("厂家")["采购量"].sum().reset_index()
current_load.columns = ["厂家", "当月下单总负载"]

# 4. 合并计算
final_df = pd.merge(base_cap, current_load, on="厂家", how="outer").fillna(0)

# 5. 产能负载率 + 状态判定
final_df = final_df[final_df["厂家月度基准产能"] > 0].reset_index(drop=True)
final_df["产能负载利用率%"] = (final_df["当月下单总负载"] / final_df["厂家月度基准产能"] * 100).round(2)

def capacity_status(rate):
    if rate <= 70:
        return "✅ 产能富余，可大量加单"
    elif rate <= 100:
        return "⚠️ 产能饱满，少量谨慎加单"
    elif rate <= 130:
        return "🔴 产能过载，严禁新增订单"
    else:
        return "🚨 严重超负荷，立刻分流订单"

final_df["产能状态&下单建议"] = final_df["产能负载利用率%"].apply(capacity_status)

# 排序：负载从高到低，高风险优先展示
final_df = final_df.sort_values("产能负载利用率%", ascending=False).reset_index(drop=True)

# 6. 主表格展示
st.subheader(f"📊 {selected_month} 厂家下单承载力总览")
st.dataframe(
    final_df.style.format({
        "厂家月度基准产能": "{:,.0f}",
        "当月下单总负载": "{:,.0f}",
        "产能负载利用率%": "{:.2f}%"
    }),
    use_container_width=True,
    height=450
)

# 7. 一行四列 决策卡片
st.markdown("---")
st.subheader("💡 分等级采购下单指引")
status_group = final_df.groupby("产能状态&下单建议")
status_order = [
    "✅ 产能富余，可大量加单",
    "⚠️ 产能饱满，少量谨慎加单",
    "🔴 产能过载，严禁新增订单",
    "🚨 严重超负荷，立刻分流订单"
]
cols = st.columns(4)

for idx, status in enumerate(status_order):
    with cols[idx]:
        st.markdown(f"**{status}**")
        if status in status_group.groups:
            g_df = status_group.get_group(status)
            for _, row in g_df.iterrows():
                st.caption(f"{row['厂家']} | 负载利用率：{row['产能负载利用率%']}%")
        else:
            st.caption("暂无该类型厂家")