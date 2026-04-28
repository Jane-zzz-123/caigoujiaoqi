import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO
import plotly.express as px
import numpy as np
# -------------------------- 页面设置 --------------------------
st.set_page_config(page_title="采购交期监控看板", page_icon="📊", layout="wide")
st.title("📦 采购交期监控可视化看板")
st.markdown("---")

# -------------------------- 加载数据（已修复正确链接） --------------------------
@st.cache_data(ttl=3600)
def load_data():
    try:
        url = "https://github.com/Jane-zzz-123/caigoujiaoqi/raw/main/caigoushuju.xlsx"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        excel_file = BytesIO(response.content)

        # 一次性读取所有sheet
        all_sheets = pd.read_excel(excel_file, sheet_name=None)

        # 读取两个表
        df = all_sheets["源数据"]
        df_product = all_sheets["产品分类"]  # 产品表

        # 清洗主表
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

        # 🔥 关键：同时返回 主表df + 产品表df_product
        return df, df_product

    except Exception as e:
        st.error(f"数据加载失败：{str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# 🔥 关键：同时接收两个表
df, df_product_info = load_data()

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

# -------------------------- 核心指标（订单数 + 采购量 双统计） --------------------------
# === 1. 当前月 ===
current_total = len(df_current)
current_on_time = len(df_current[df_current["交期状态"] == "提前/准时"])
current_overdue = len(df_current[df_current["交期状态"] == "逾期"])
current_on_time_rate = (current_on_time / current_total * 100) if (current_total > 0 and not pd.isna(current_total)) else 0.0
current_diff_avg = df_current["预计-实际交期的差值"].mean() if current_total > 0 else 0.0

current_qty = df_current["采购量"].sum()
current_on_time_qty = df_current[df_current["交期状态"] == "提前/准时"]["采购量"].sum()
current_overdue_qty = df_current[df_current["交期状态"] == "逾期"]["采购量"].sum()

# ✅ 新增：采购量准时率
current_qty_on_time_rate = (current_on_time_qty / current_qty * 100) if current_qty > 0 else 0.0

# === 2. 上月 ===
last_total = len(df_last) if not df_last.empty else 0
last_on_time = len(df_last[df_last["交期状态"] == "提前/准时"]) if not df_last.empty else 0
last_overdue = len(df_last[df_last["交期状态"] == "逾期"]) if not df_last.empty else 0
last_on_time_rate = (last_on_time / last_total * 100) if last_total > 0 else 0.0
last_diff_avg = df_last["预计-实际交期的差值"].mean() if (not df_last.empty and last_total > 0) else 0.0

last_qty = df_last["采购量"].sum() if not df_last.empty else 0
last_on_time_qty = df_last[df_last["交期状态"] == "提前/准时"]["采购量"].sum() if not df_last.empty else 0
last_overdue_qty = df_last[df_last["交期状态"] == "逾期"]["采购量"].sum() if not df_last.empty else 0

# ✅ 新增：上月采购量准时率
last_qty_on_time_rate = (last_on_time_qty / last_qty * 100) if last_qty > 0 else 0.0


# -------------------------- 双指标卡片组件（订单数 + 采购量） --------------------------
def double_card(col, title,
                current_cnt, last_cnt,
                current_qty, last_qty,
                suffix="", is_good_up=True, bg_color="#fafbfc", is_int=True):
    # 订单数环比
    if last_cnt == 0:
        pct_cnt = "新数据"
    else:
        pct_cnt = (current_cnt - last_cnt) / last_cnt * 100
        pct_cnt = f"{pct_cnt:+.2f}%"

    # 采购量环比
    if last_qty == 0:
        pct_qty = "新数据"
    else:
        pct_qty = (current_qty - last_qty) / last_qty * 100
        pct_qty = f"{pct_qty:+.2f}%"

    # 颜色
    if is_good_up:
        color_cnt = "#28a745" if current_cnt >= last_cnt else "#dc3545"
        color_qty = "#28a745" if current_qty >= last_qty else "#dc3545"
    else:
        color_cnt = "#dc3545" if current_cnt >= last_cnt else "#28a745"
        color_qty = "#dc3545" if current_qty >= last_qty else "#28a745"

    # 显示格式
    current_cnt_str = f"{int(current_cnt)}" if is_int else f"{current_cnt:.2f}"
    last_cnt_str = f"{int(last_cnt)}" if is_int else f"{last_cnt:.2f}"

    current_qty_str = f"{int(current_qty)}"
    last_qty_str = f"{int(last_qty)}"

    # 卡片HTML
    with col:
        st.markdown(f"""
        <div style="padding:18px; border-radius:12px; background:{bg_color}; border:1px solid #e5e7eb;">
          <div style="font-size:15px; color:#555; margin-bottom:8px;">{title}</div>

          <div style="font-size:22px; font-weight:600;">{current_cnt_str} 单</div>
          <div style="font-size:12px; color:{color_cnt}; margin-top:2px;">
            环比 {pct_cnt}（上月：{last_cnt_str}）
          </div>

          <div style="height:10px;"></div>

          <div style="font-size:18px; font-weight:600; color:#333;">{current_qty_str} 件</div>
          <div style="font-size:12px; color:{color_qty}; margin-top:2px;">
            环比 {pct_qty}（上月：{last_qty_str}）
          </div>
        </div>
        """, unsafe_allow_html=True)


# -------------------------- 准时率双口径卡片 --------------------------
def rate_card(col, order_curr, order_last, qty_curr, qty_last, bg_color="#eff6ff"):
    # 订单
    if order_last == 0:
        op = "新数据"
    else:
        op = f"{(order_curr - order_last)/order_last*100:+.2f}%"
    oc = "#28a745" if order_curr >= order_last else "#dc3545"

    # 采购量
    if qty_last == 0:
        qp = "新数据"
    else:
        qp = f"{(qty_curr - qty_last)/qty_last*100:+.2f}%"
    qc = "#28a745" if qty_curr >= qty_last else "#dc3545"

    with col:
        st.markdown(f"""
        <div style="padding:18px; border-radius:12px; background:{bg_color}; border:1px solid #e5e7eb;">
          <div style="font-size:15px; color:#555; margin-bottom:8px;">准时率</div>
          <div style="font-size:18px; font-weight:600;">订单：{order_curr:.1f}%</div>
          <div style="font-size:12px; color:{oc}; margin-bottom:6px;">环比 {op}（上月：{order_last:.1f}%）</div>
          <div style="font-size:18px; font-weight:600;">采购量：{qty_curr:.1f}%</div>
          <div style="font-size:12px; color:{qc};">环比 {qp}（上月：{qty_last:.1f}%）</div>
        </div>
        """, unsafe_allow_html=True)


# -------------------------- 普通卡片 --------------------------
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

    current_str = f"{int(current)}" if is_int else f"{current:.2f}"
    last_str = f"{int(last)}" if is_int else f"{last:.2f}"

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


# -------------------------- 绘制卡片 --------------------------
st.subheader(f"📆 {selected_month} 整体分析")
col1, col2, col3, col4, col5 = st.columns(5)

double_card(col1, "PO单数",
            current_total, last_total,
            current_qty, last_qty,
            "", is_good_up=False, bg_color="#fafbfc", is_int=True)

double_card(col2, "提前/准时",
            current_on_time, last_on_time,
            current_on_time_qty, last_on_time_qty,
            "", is_good_up=True, bg_color="#f0fdf4", is_int=True)

double_card(col3, "逾期",
            current_overdue, last_overdue,
            current_overdue_qty, last_overdue_qty,
            "", is_good_up=False, bg_color="#fef2f2", is_int=True)

# ✅ 准时率（双口径）
rate_card(col4, current_on_time_rate, last_on_time_rate, current_qty_on_time_rate, last_qty_on_time_rate)

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
    "到货年月", "交期状态", "厂家", "下单时间", "预计到货时间修改","采购单号", "品名", "SKU","采购量",
    "厂家类目明细", "产品分类", "采购交期", "实际采购交期", "预计-实际交期的差值"
]
df_table = df_current.copy()

# ====================== 【加这一行！】解决重复列报错 ======================
df_table = df_table.loc[:, ~df_table.columns.duplicated()]

df_table["排序标识"] = df_table["交期状态"].apply(lambda x: 0 if x == "逾期" else 1)
df_table = df_table.sort_values(["排序标识", "采购量"], ascending=[True, False])
st.dataframe(df_table[table_cols], use_container_width=True, height=300)

st.markdown("---")

# -------------------------- 逾期深度分析（严格按你指定区间） --------------------------
st.markdown("---")
st.subheader("⚠️ 逾期深度分析（按逾期严重程度）")

import numpy as np
import plotly.express as px

# 只保留逾期数据（差值 >=1 才算逾期）
overdue_df = df_current[df_current["预计-实际交期的差值"] <= -1].copy()

if overdue_df.empty:
    st.info("当前筛选条件下无逾期订单")
else:
    # 字段简写，方便计算
    diff = -overdue_df["预计-实际交期的差值"]

    # 严格按你的规则分层
    def get_level(x):
        if 1 <= x <= 3:
            return "轻度(1-3天)"
        elif 4 <= x <= 7:
            return "中度(4-7天)"
        elif 8 <= x <= 15:
            return "重度(8-15天)"
        elif x > 15:
            return "极度(>15天)"
        else:
            return "正常"

    overdue_df["逾期等级"] = diff.apply(get_level)

    # ==========================================
    # 1️⃣ 整体逾期分布（环形图 + 彩色卡片）
    # ==========================================
    st.markdown("#### 1. 整体逾期分布")
    col1, col2 = st.columns([1, 1.5])

    level_cnt = overdue_df.groupby("逾期等级").agg(
        订单数=("采购单号", "count"),
        采购量=("采购量", sum),
        平均逾期天数=("预计-实际交期的差值", np.mean)
    ).reset_index()
    level_cnt["平均逾期天数"] = level_cnt["平均逾期天数"].round(1)

    # ====================== 核心修改：固定排序 ======================
    level_order = ["轻度(1-3天)", "中度(4-7天)", "重度(8-15天)", "极度(>15天)"]
    level_cnt["逾期等级"] = pd.Categorical(level_cnt["逾期等级"], categories=level_order, ordered=True)
    level_cnt = level_cnt.sort_values("逾期等级")
    # ================================================================

    with col1:
        color_map = {
            "轻度(1-3天)": "#10b981",
            "中度(4-7天)": "#f59e0b",
            "重度(8-15天)": "#ef4444",
            "极度(>15天)": "#7f1d1d"
        }
        fig = px.pie(level_cnt, names="逾期等级", values="采购量",
                     color="逾期等级", color_discrete_map=color_map, hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        for _, row in level_cnt.iterrows():
            level = row["逾期等级"]
            color = color_map[level]
            st.markdown(f"""
            <div style="border-left:4px solid {color}; padding:10px 14px; background:#f9fafb; border-radius:8px; margin-bottom:8px;">
                <b>{level}</b>｜{row['订单数']}单｜{row['采购量']}件｜平均{row['平均逾期天数']}天
            </div>
            """, unsafe_allow_html=True)

    # ==========================================
    # 2️⃣ 厂家逾期卡片（一行3列，高颜值）
    # ====================== 2️⃣ 厂家逾期卡片 + 内嵌采购量热力分布图 ======================
    # ====================== 厂家逾期详情 终极优化版 ======================
    st.markdown("#### 2. 各厂家逾期详情（高风险优先）")

    # 预处理转正逾期天数
    overdue_df["逾期正数天数"] = -overdue_df["预计-实际交期的差值"]

    # 全局分层统计
    factory_detail = overdue_df.groupby(["厂家", "逾期等级"]).agg(
        订单数=("采购单号", "count"),
        采购量=("采购量", "sum"),
        平均逾期原始=("预计-实际交期的差值", "mean")
    ).reset_index()
    factory_detail["平均逾期显示"] = (-factory_detail["平均逾期原始"]).round(1)

    # 全局总逾期采购量，用于计算占比
    total_all_purchase = overdue_df["采购量"].sum()

    # 按最长逾期风险排序
    factory_order = overdue_df.groupby("厂家")["逾期正数天数"].max().sort_values(ascending=False).index

    cols = st.columns(3)
    idx = 0


    # 分区间专属渐变色卡
    def get_heat_color(days):
        if 1 <= days <= 3:
            # 轻度 绿色渐变
            return f"rgba(22, 163, 74, {0.4 + days * 0.15})"
        elif 4 <= days <= 7:
            # 中度 橙色渐变
            return f"rgba(245, 158, 11, {0.4 + (days - 3) * 0.15})"
        elif 8 <= days <= 15:
            # 重度 橙红渐变
            return f"rgba(239, 68, 68, {0.4 + (days - 7) * 0.08})"
        else:
            # 极度 深红渐变
            return f"rgba(127, 29, 29, {0.7 + min(days - 16, 0.3)})"


    # ===================== 固定等级顺序（你要的排序） =====================
    level_order = ["轻度(1-3天)", "中度(4-7天)", "重度(8-15天)", "极度(>15天)"]

    # 遍历厂家渲染卡片
    for fac in factory_order:
        fac_data_all = overdue_df[overdue_df["厂家"] == fac].copy()
        fac_sub = factory_detail[factory_detail["厂家"] == fac]

        # 厂家基础数据
        total_order = len(fac_data_all)
        max_day = fac_data_all["逾期正数天数"].max()
        fac_total_pur = fac_data_all["采购量"].sum()

        # 卡片整体底色
        if max_day > 15:
            bg, bd = "#fee2e2", "#fecaca"
        elif max_day > 7:
            bg, bd = "#ffedd5", "#fed7aa"
        elif max_day > 3:
            bg, bd = "#fef9c3", "#fde047"
        else:
            bg, bd = "#dcfce7", "#bbf7d0"

        with cols[idx % 3]:
            # 卡片头部
            st.markdown(f"""
                <div style="padding:16px; border-radius:12px; background:{bg}; border:1px solid {bd}; margin-bottom:14px;">
                <div style="font-weight:bold; font-size:15px; margin-bottom:6px;">🏭 {fac}</div>
                <div style="font-size:13px;">逾期订单：{total_order}单｜最长逾期：{max_day}天</div>
                """, unsafe_allow_html=True)

            # 1. 分层明细 + 新增采购量+占比
            color_lv = {
                "轻度(1-3天)": "#16a34a",
                "中度(4-7天)": "#f59e0b",
                "重度(8-15天)": "#ea580c",
                "极度(>15天)": "#dc2626"
            }

            # ===================== 按固定顺序显示 =====================
            for lv in level_order:
                row = fac_sub[fac_sub["逾期等级"] == lv]
                if not row.empty:
                    cnt = row.iloc[0]["订单数"]
                    avg = row.iloc[0]["平均逾期显示"]
                    pur = row.iloc[0]["采购量"]
                    pct = (pur / fac_total_pur * 100).round(2)
                    c = color_lv[lv]

                    st.markdown(f"""
                        <div style="font-size:13px; margin:4px 0; color:{c};">
                        {lv}｜{cnt}单｜平均{avg}天（逾期采购量：{pur}，占比{pct}%）
                        </div>
                        """, unsafe_allow_html=True)

            # 2. 定制渐变色热力条形图
            st.caption("📈 逾期天数-采购量热力分布")
            heat_df = fac_data_all.groupby("逾期正数天数")["采购量"].sum().reset_index()
            heat_df.columns = ["逾期天数", "逾期采购量"]
            heat_df = heat_df.sort_values("逾期天数")
            # 为每一天匹配专属渐变色
            heat_df["条形颜色"] = heat_df["逾期天数"].apply(get_heat_color)

            import plotly.express as px

            fig = px.bar(
                heat_df,
                x="逾期天数",
                y="逾期采购量",
                color="条形颜色",
                color_discrete_map="identity",
                height=150
            )
            # 图表极简适配卡片
            fig.update_layout(
                margin=dict(l=0, r=0, t=8, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                showlegend=False
            )
            fig.update_yaxes(showticklabels=False, title="")
            fig.update_xaxes(title="逾期天数")
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("</div>", unsafe_allow_html=True)
        idx += 1

# -------------------------- 厂家汇总 --------------------------
st.subheader("🏭 各厂家交期统计汇总")
if not df_current.empty:
    factory_df = df_current.groupby("厂家").agg(
        PO单数=("采购单号", "count"),
        提前准时订单=("交期状态", lambda x: (x == "提前/准时").sum()),
        逾期订单=("交期状态", lambda x: (x == "逾期").sum())
    ).reset_index()

    factory_df["准时率(%)"] = (
        (factory_df["提前准时订单"].astype(np.float64) /
         factory_df["PO单数"].replace(0, np.nan).astype(np.float64) * 100)
    ).round(2).fillna(0.0)
    jq_df = df_current.groupby("厂家").agg(
        平均交期=("实际采购交期", "mean"),
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
# 新增：过滤空值 + 仅保留有效数据行
df_valid = df_current[
    df_current["厂家"].notna() &  # 过滤空厂家
    df_current["采购单号"].notna()  # 过滤空订单号
].copy()
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
# 修复：处理除数为0 + 转换为numpy数组避免Arrow类型问题
factory_analysis["准时率"] = (
    (factory_analysis["准时订单数"].astype(np.float64) /
     factory_analysis["订单总数"].replace(0, np.nan).astype(np.float64) * 100)
).round(1).fillna(0.0)  # 0值替换为NaN再计算，最后填充0
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




st.subheader("🎯 厂家+类目明细 采购交期分位数分析 & 修改建议")
st.markdown("### ⏱ 订单时间筛选设置")

# 只保留单列多选布局
all_valid_months = sorted(df["到货年月"].dropna().unique(), reverse=True)

# 🔍 自动定位最近有有效采购交期的月份（兜底防空）
latest_arrival_month = None
for month_candidate in all_valid_months:
    temp_data = df[df["到货年月"] == month_candidate]
    if not temp_data.empty and temp_data["采购交期"].notna().sum() > 0:
        latest_arrival_month = month_candidate
        break

# 极端无数据兜底拦截
if latest_arrival_month is None:
    st.error("⚠️ 暂无任何有效采购交期数据，无法进行分析")
    st.stop()

# 仅保留多选月份控件
eval_months = st.multiselect(
    "选择履约统计的历史月份（可多选，默认全选）",
    options=all_valid_months,
    default=all_valid_months
)

if not eval_months:
    st.warning("⚠️ 请至少勾选1个月份用于履约统计")
    st.stop()

# 口径定义（极简清晰）
# 1. 实际履约数据 = 勾选的全部月份
df_actual = df[df["到货年月"].isin(eval_months)].copy()
start_str = min(eval_months)
end_str = max(eval_months)

# 2. 当前基准交期 = 固定最新有效月份（永远不变）
df_latest = df[df["到货年月"] == latest_arrival_month].copy()

# 提示文案同步简化
st.success(f"""
✅ 当前采购交期基准：固定取自【最新有效月份 {latest_arrival_month}】
✅ 历史履约统计区间：{start_str} ~ {end_str}（已选{len(eval_months)}个月）
""")

# -------------------------- 下方原有全部业务逻辑 100% 保留无需改动 --------------------------
st.markdown("---")

# 清洗有效数据
df_actual = df_actual[
    df_actual["厂家"].notna() &
    df_actual["厂家类目明细"].notna() &
    df_actual["实际采购交期"].notna()
].copy()

df_latest = df_latest[
    df_latest["厂家"].notna() &
    df_latest["厂家类目明细"].notna() &
    df_latest["采购交期"].notna()
].copy()

# 最新月基准交期均值
latest_mean = df_latest.groupby(["厂家", "厂家类目明细"]).agg(
    当前采购交期均值=("采购交期", "mean")
).reset_index()

# 业务自定义分位算法
def biz_quantile(series, q):
    s = series.dropna().sort_values().reset_index(drop=True)
    if len(s) == 0:
        return None
    idx = int((len(s) * q) - 1e-9)
    idx = max(0, min(idx, len(s)-1))
    return s.iloc[idx]

# 历史履约分位&准时率计算
actual_stats = df_actual.groupby(["厂家", "厂家类目明细"]).agg(
    实际交期80分位=("实际采购交期", lambda x: biz_quantile(x, 0.8)),
    实际交期85分位=("实际采购交期", lambda x: biz_quantile(x, 0.85)),
    实际交期90分位=("实际采购交期", lambda x: biz_quantile(x, 0.9)),
    实际交期95分位=("实际采购交期", lambda x: biz_quantile(x, 0.95)),
    实际交期100分位=("实际采购交期", lambda x: biz_quantile(x, 1.0)),
    样本订单数=("采购单号", "count"),
    准时率=("交期状态", lambda x: (x == "提前/准时").sum() / len(x) * 100)
).reset_index()

# 合并数据
quantile_stats = pd.merge(
    latest_mean,
    actual_stats,
    on=["厂家", "厂家类目明细"],
    how="inner"
)

# 数值格式规整
cols_round = [
    "当前采购交期均值",
    "实际交期80分位", "实际交期85分位",
    "实际交期90分位", "实际交期95分位", "实际交期100分位"
]
for c in cols_round:
    quantile_stats[c] = quantile_stats[c].round(2)
quantile_stats["准时率"] = quantile_stats["准时率"].round(1)

# 交期优化建议逻辑
def get_delivery_advice(row):
    current = row["当前采购交期均值"]
    q80 = row["实际交期80分位"]
    q85 = row["实际交期85分位"]
    q90 = row["实际交期90分位"]
    rate = row["准时率"]
    sample = row["样本订单数"]

    min_sample = 5
    if sample < min_sample:
        return "⚠️ 样本数据太少，暂不提出修改建议"

    if rate < 80:
        ref_q = q80
    elif 80 <= rate < 90:
        ref_q = q85
    else:
        ref_q = q90

    diff = abs(current - ref_q)
    if diff <= 2:
        return "✅ 偏差不大，现有交期合理，可继续保持"

    if rate >= 90:
        if current > ref_q:
            return f"✅ 履约优秀，可适度下调至{ref_q}天，提升整体周转效率"
        else:
            return f"🟡 交期略偏紧张，建议小幅上调至{ref_q}天规避风险"

    elif 80 <= rate < 90:
        if current < ref_q:
            return f"🟡 履约整体稳定，建议上调至{ref_q}天，减少逾期波动"
        else:
            return f"🟡 交期存在压缩空间，可下调至{ref_q}天优化交付"

    else:
        if current < ref_q:
            return f"🟠 履约偏弱，建议上调至{ref_q}天，大幅降低逾期风险"
        else:
            return "🟡 当前交期较为宽松，可根据放量需求适度收紧"


quantile_stats["采购交期修改建议"] = quantile_stats.apply(get_delivery_advice, axis=1)

# 渲染分析卡片
st.markdown("#### 📋 各厂家+类目明细交期分析卡片")
cols = st.columns(4)
card_idx = 0

for _, row in quantile_stats.iterrows():
    factory = row["厂家"]
    cat = row["厂家类目明细"]
    current_day = row["当前采购交期均值"]
    sample = int(row["样本订单数"])
    rate = row["准时率"]
    q80 = row["实际交期80分位"]
    q85 = row["实际交期85分位"]
    q90 = row["实际交期90分位"]
    q95 = row["实际交期95分位"]
    q100 = row["实际交期100分位"]
    advice = row["采购交期修改建议"]

    if rate >= 90:
        bg = "#f0fdf4"
        border = "#22c55e"
    elif rate >= 80:
        bg = "#fffbeb"
        border = "#f59e0b"
    else:
        bg = "#fef2f2"
        border = "#ef4444"

    with cols[card_idx % 4]:
        st.markdown(f"""
<div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:18px; margin-bottom:16px;">

**🏭 {factory}**  

{cat}

<p style="font-size:14px; margin:8px 0 4px 0;">
最新采购交期：{current_day}天（准时率{rate}%）
</p>

<p style="font-size:12px; color:#555; margin:4px 0 12px 0;">
统计样本：{sample} 单
</p>

<p style="font-size:12px; color:#71717a; line-height:1.6; margin:8px 0;">
<span style="display:inline-block; width:48%;">80% 订单达成：{q80}天</span>
<span style="display:inline-block; width:48%;">85% 订单达成：{q85}天</span><br>
<span style="display:inline-block; width:48%;">90% 订单达成：{q90}天</span>
<span style="display:inline-block; width:48%;">95% 订单达成：{q95}天</span><br>
<span style="font-size:11px; color:#999;">100% 订单达成：{q100}天</span>
</p>

<hr style="margin:12px 0; border:none; border-top:1px solid #ddd;">

<div style="font-size:14px; line-height:1.5;">
💡 <b>建议：</b>{advice}
</div>

</div>
""", unsafe_allow_html=True)
    card_idx += 1

# 明细数据表格
st.markdown("#### 📊 交期分位数分析明细表格")
st.dataframe(quantile_stats, use_container_width=True, hide_index=True)


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
# 修复：处理除数为0 + Arrow 数据类型兼容问题
compare_df["准时率%"] = (
    (compare_df["准时数"].astype(float) / compare_df["订单数"].replace(0, np.nan).astype(float)) * 100
).round(1).fillna(0)

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

# ===================== 统计在售产品数量（绝对不报错版） =====================
df_on_sale = df_product_info[df_product_info["是否在售"] == "是"].copy()
prod_count_map = df_on_sale.groupby("产品类型（新）").size().to_dict()

summary_group = compare_df.groupby("产品分类", sort=False)
cate_list = list(summary_group)

# 3列循环排版
for i in range(0, len(cate_list), 3):
    batch = cate_list[i:i+3]
    cols = st.columns(3)

    for idx, (cate, group_data) in enumerate(batch):
        with cols[idx]:
            with st.container(border=True):
                # 品类标题 + 在售数量
                prod_num = prod_count_map.get(cate, 0)
                st.markdown(f"**📦 {cate}（在售产品：{prod_num} 款）**")

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

                # 风险提示（带产品数量，优先级清晰）
                if good_df.empty:
                    st.info(f"💡 暂无优质供方｜在售 {prod_num} 款需开发新厂家")
                if group_data["厂家数"].iloc[0] == 1:
                    st.warning(f"⚠️ 单一供应风险｜在售 {prod_num} 款仅 1 家供货")

# ===================== 结束 =====================

# ====================== 科学优化版：近半年平均产能为基准 ======================
# -------------------------- 厂家产能&准时率综合分析（月度复盘版） --------------------------
st.markdown("---")
st.header("🏭 厂家产能&准时率综合分析")

df_final = df.copy()

# 时间格式化
df_final["下单年月"] = pd.to_datetime(df_final["下单时间"]).dt.to_period("M")
df_final["到货年月"] = pd.to_datetime(df_final["到货年月"]).dt.to_period("M")

# 选择评估月份
order_months = sorted(df_final["到货年月"].unique(), reverse=True)
selected_month = st.selectbox("选择统计截止月份", order_months)

# 周期区间（以所选月份为终点倒推）
end_month = selected_month
end_p = pd.Period(end_month, freq='M')
p3  = pd.period_range(end_p - 2, end_p, freq='M')
p6  = pd.period_range(end_p - 5, end_p, freq='M')
p12 = pd.period_range(end_p - 11, end_p, freq='M')

# 按到货年月计算历史产能（用于基准）
def get_cap(df, period):
    dfp = df[df["到货年月"].isin(period)]
    if dfp.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    monthly = dfp.groupby(["厂家", "到货年月"])["采购量"].sum()
    avg_cap = monthly.groupby(level=0).mean().round(0)
    max_cap = monthly.groupby(level=0).max()
    return avg_cap, max_cap

# 多口径产能
cap_3m, _        = get_cap(df_final, p3)
cap_6m, cap_max  = get_cap(df_final, p6)
cap_12m, _       = get_cap(df_final, p12)

# 重命名列
cap_3m    = cap_3m.rename("近3个月平均产能")
cap_6m    = cap_6m.rename("近半年平均产能（基准）")
cap_12m   = cap_12m.rename("近一年平均产能")
cap_max   = cap_max.rename("历史最高单月产能")

# 近半年准时率
df_p6 = df_final[df_final["到货年月"].isin(p6)].copy()
if not df_p6.empty:
    df_p6["准时标记"] = (df_p6["交期状态"] == "提前/准时").astype(int)
    on_time_rate = df_p6.groupby("厂家")["准时标记"].mean() * 100
    on_time_rate = on_time_rate.round(1).rename("近半年准时率%")
else:
    on_time_rate = pd.Series(dtype=float)

# 合并所有数据
result = pd.concat([
    cap_3m, cap_6m, cap_12m, cap_max,
    on_time_rate
], axis=1).fillna(0).reset_index()

# 安全可放量产能（保留！）
result["安全可放量产能"] = (result["近半年平均产能（基准）"] * result["近半年准时率%"] / 100).round(0)

# 展示列（精简版，只留月度复盘有用字段）
show_cols = [
    "厂家",
    "近3个月平均产能",
    "近半年平均产能（基准）",
    "近一年平均产能",
    "历史最高单月产能",
    "近半年准时率%",
    "安全可放量产能"
]

# 确保只展示存在的列
show_cols = [c for c in show_cols if c in result.columns]

st.dataframe(
    result[show_cols].style.format({
        "近3个月平均产能": "{:,.0f}",
        "近半年平均产能（基准）": "{:,.0f}",
        "近一年平均产能": "{:,.0f}",
        "历史最高单月产能": "{:,.0f}",
        "近半年准时率%": "{:.1f}%",
        "安全可放量产能": "{:,.0f}"
    }), use_container_width=True, height=600
)


# =========================================================
# 🌟 多月趋势分析：订单数堆叠柱状图 + 准时率折线图（中文坐标+数值标签版）
# =========================================================
st.markdown("---")
# =========================================================
# 🌟 多月趋势分析：订单数堆叠柱状图 + 准时率折线图（无筛选器·整体版）
# =========================================================
st.header("📈 整体的多月履约趋势分析")

# 数据准备
df_trend = df.copy()
df_trend["到货年月"] = pd.to_datetime(df_trend["到货年月"]).dt.to_period("M")
df_trend["到货年月_str"] = df_trend["到货年月"].astype(str)

# =========================================================
# 直接全量统计，不做任何筛选
# =========================================================
df_filter = df_trend.copy()

# =========================================================
# 按月统计
# =========================================================
df_stat = df_filter.groupby("到货年月_str").agg(
    总订单数=("采购单号", "count"),
    准时订单数=("交期状态", lambda x: (x == "提前/准时").sum()),
    逾期订单数=("交期状态", lambda x: (x == "逾期").sum())
).reset_index()

df_stat["准时率%"] = (df_stat["准时订单数"] / df_stat["总订单数"] * 100).round(1)
df_stat = df_stat.sort_values("到货年月_str")

# ===================== 横坐标转为中文日期 =====================
df_stat["到货月份_中文"] = pd.to_datetime(df_stat["到货年月_str"]).dt.strftime("%Y年%m月")

# =========================================================
# 📊 绘制组合图（中文坐标 + 全部数值直接显示在图上）
# =========================================================
import plotly.graph_objects as go
from plotly.subplots import make_subplots

fig = make_subplots(specs=[[{"secondary_y": True}]])

# 1. 准时订单数（绿色柱子 + 显示数值）
fig.add_trace(go.Bar(
    x=df_stat["到货月份_中文"], y=df_stat["准时订单数"],
    name="准时/提前订单数", marker_color="#27AE60",
    text=df_stat["准时订单数"], textposition="auto"
), secondary_y=False)

# 2. 逾期订单数（红色柱子 + 显示数值）
fig.add_trace(go.Bar(
    x=df_stat["到货月份_中文"], y=df_stat["逾期订单数"],
    name="逾期订单数", marker_color="#E74C3C",
    text=df_stat["逾期订单数"], textposition="auto"
), secondary_y=False)

# 3. 准时率折线（蓝色+数值标签）
fig.add_trace(go.Scatter(
    x=df_stat["到货月份_中文"], y=df_stat["准时率%"],
    name="准时率%", mode="lines+markers+text",
    text=[f"{v}%" for v in df_stat["准时率%"]],
    textposition="top center",
    marker_color="#3498DB", line=dict(width=3)
), secondary_y=True)

# 图表样式
fig.update_layout(
    barmode="stack",
    height=500,
    title_text="整体履约趋势（全厂家）",
    template="plotly_white",
    legend_orientation="h",
    legend_y=-0.2,
    xaxis_title="到货月份",
    yaxis_title="订单数"
)

# 右Y轴：准时率
fig.update_yaxes(title_text="准时率 (%)", secondary_y=True, range=[0, 105])

st.plotly_chart(fig, use_container_width=True)

# =========================================================
# 数据核对表格
# =========================================================
with st.expander("📄 查看统计数据"):
    st.dataframe(df_stat.rename(columns={
        "到货月份_中文":"到货月份", "准时订单数":"准时数", "逾期订单数":"逾期数",
        "总订单数":"总订单", "准时率%":"准时率"
    })[["到货月份","总订单","准时数","逾期数","准时率"]],
    use_container_width=True, hide_index=True)

# =========================================================
# 🌟 逾期深度趋势分析（柱形：逾期订单数 + 折线：平均/最长逾期天数）
# 适配列名：预计-实际交期的差值（负数=逾期）
# =========================================================
st.subheader("📅 逾期深度趋势（逾期订单量 + 天数）")

# 统计逾期深度
df_delay_stat = df_filter.groupby("到货年月_str").agg(
    总订单数=("采购单号", "count"),
    逾期订单数=("交期状态", lambda x: (x == "逾期").sum()),
    平均逾期天数=("预计-实际交期的差值", lambda x: abs(x[x < 0]).mean().round(1) if (x < 0).any() else 0),
    最长逾期天数=("预计-实际交期的差值", lambda x: abs(x[x < 0]).max() if (x < 0).any() else 0)
).reset_index()

df_delay_stat = df_delay_stat.sort_values("到货年月_str")
df_delay_stat["到货月份_中文"] = pd.to_datetime(df_delay_stat["到货年月_str"]).dt.strftime("%Y年%m月")

# ==================== 绘图：柱形 + 双折线 ====================
import plotly.graph_objects as go
fig_delay = go.Figure()

# 👇 柱形图：逾期订单数
fig_delay.add_trace(go.Bar(
    x=df_delay_stat["到货月份_中文"],
    y=df_delay_stat["逾期订单数"],
    name="逾期订单数",
    marker_color="#FF9900",
    opacity=0.8
))

# 👇 折线：平均逾期天数
fig_delay.add_trace(go.Scatter(
    x=df_delay_stat["到货月份_中文"],
    y=df_delay_stat["平均逾期天数"],
    name="平均逾期天数",
    mode="lines+markers+text",
    text=df_delay_stat["平均逾期天数"],
    textposition="top center",
    line=dict(color="#E64A19", width=3),
    marker=dict(size=6),
    yaxis="y2"
))

# 👇 折线：最长逾期天数
fig_delay.add_trace(go.Scatter(
    x=df_delay_stat["到货月份_中文"],
    y=df_delay_stat["最长逾期天数"],
    name="最长逾期天数",
    mode="lines+markers+text",
    text=df_delay_stat["最长逾期天数"],
    textposition="bottom center",
    line=dict(color="#C0392B", width=3, dash="dot"),
    marker=dict(size=6),
    yaxis="y2"
))

# 双轴设置（左：订单数，右：逾期天数）
fig_delay.update_layout(
    height=420,
    title_text="整体逾期趋势：订单量 + 逾期天数",
    template="plotly_white",
    legend_orientation="h",
    legend_y=-0.2,
    xaxis_title="到货月份",
    yaxis=dict(title="逾期订单数"),
    yaxis2=dict(title="逾期天数", overlaying="y", side="right"),
)

st.plotly_chart(fig_delay, use_container_width=True)

# 数据核对
with st.expander("📄 查看逾期深度数据"):
    st.dataframe(
        df_delay_stat[["到货月份_中文", "总订单数", "逾期订单数", "平均逾期天数", "最长逾期天数"]]
        .rename(columns={"到货月份_中文":"到货月份"}),
        use_container_width=True, hide_index=True
    )


st.header("📈 厂家多月履约趋势分析（准时率 + 订单数结构）")

# 数据准备
df_trend = df.copy()
df_trend["到货年月"] = pd.to_datetime(df_trend["到货年月"]).dt.to_period("M")
df_trend["到货年月_str"] = df_trend["到货年月"].astype(str)

# ========================================================================
# 🌟 筛选区移到最顶部（时间多选 + 厂家筛选）
# ========================================================================
st.subheader("🔍 筛选条件")

# 1. 月份多选框（默认全选）
all_months = sorted(df_trend["到货年月_str"].unique())
selected_months = st.multiselect("🗓️ 选择月份（可多选）", all_months, default=all_months)

# 2. 厂家单选筛选器
supplier_list = ["全部厂家"] + sorted(df_trend["厂家"].dropna().unique().tolist())
selected_supplier = st.selectbox("🏭 选择要分析的厂家", supplier_list)

st.markdown("---")

# ========================================================================
# 数据过滤（统一过滤，全局生效）
# ========================================================================
df_filter = df_trend.copy()
df_filter = df_filter[df_filter["到货年月_str"].isin(selected_months)]  # 多选月份过滤

if selected_supplier != "全部厂家":
    df_filter = df_filter[df_filter["厂家"] == selected_supplier]

# ========================================================================
# 🌟 所有厂家 总结卡片（现在在筛选器下方）
# ========================================================================
st.subheader("🏭 全厂家履约总结卡片")

# 基于已筛选数据统计卡片
df_factory_summary = df_filter.groupby("厂家").agg(
    总订单数=("采购单号", "count"),
    准时订单数=("交期状态", lambda x: (x == "提前/准时").sum()),
    逾期订单数=("交期状态", lambda x: (x == "逾期").sum()),
    平均交期=("实际采购交期", "mean"),
    总采购量=("采购量", "sum")
).reset_index()

df_factory_summary["准时率%"] = (
    df_factory_summary["准时订单数"] / df_factory_summary["总订单数"] * 100
).round(1)

# 评级
def get_level(rate):
    if rate >= 90:
        return "✅ 优质", "#f0fdf4", "#22c55e"
    elif rate >= 80:
        return "⚠️ 合格", "#fffbeb", "#f59e0b"
    else:
        return "🔴 异常", "#fef2f2", "#ef4444"

# 一行4列卡片
cols = st.columns(4)
card_idx = 0
for _, row in df_factory_summary.iterrows():
    level_name, bg, bd = get_level(row["准时率%"])
    with cols[card_idx % 4]:
        st.markdown(f"""
<div style="background:{bg}; border:2px solid {bd}; border-radius:12px; padding:16px; margin-bottom:14px;">
<b>{row['厂家']}</b><br>
准时率：{row['准时率%']}% {level_name}<br>
订单：{int(row['总订单数'])} 单<br>
准时：{int(row['准时订单数'])} 单｜逾期：{int(row['逾期订单数'])} 单<br>
总采购量：{int(row['总采购量'])} 件
</div>
""", unsafe_allow_html=True)
    card_idx += 1

st.markdown("---")

# ========================================================================
# 1. 履约趋势图（准时率+订单）
# ========================================================================
st.subheader("📊 履约趋势：订单结构 + 准时率")
df_stat = df_filter.groupby("到货年月_str").agg(
    总订单数=("采购单号", "count"),
    准时订单数=("交期状态", lambda x: (x == "提前/准时").sum()),
    逾期订单数=("交期状态", lambda x: (x == "逾期").sum())
).reset_index()

df_stat["准时率%"] = (df_stat["准时订单数"] / df_stat["总订单数"] * 100).round(1)
df_stat = df_stat.sort_values("到货年月_str")
df_stat["到货月份_中文"] = pd.to_datetime(df_stat["到货年月_str"]).dt.strftime("%Y年%m月")

fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Bar(x=df_stat["到货月份_中文"], y=df_stat["准时订单数"], name="准时/提前", marker_color="#27AE60", text=df_stat["准时订单数"]), secondary_y=False)
fig.add_trace(go.Bar(x=df_stat["到货月份_中文"], y=df_stat["逾期订单数"], name="逾期", marker_color="#E74C3C", text=df_stat["逾期订单数"]), secondary_y=False)
fig.add_trace(go.Scatter(x=df_stat["到货月份_中文"], y=df_stat["准时率%"], name="准时率%", mode="lines+markers+text", text=[f"{v}%" for v in df_stat["准时率%"]], marker_color="#3498DB", line=dict(width=3)), secondary_y=True)

fig.update_layout(barmode="stack", height=460, title=f"{selected_supplier} 履约趋势", template="plotly_white", legend_orientation="h", legend_y=-0.2, xaxis_title="到货月份", yaxis_title="订单数")
fig.update_yaxes(title_text="准时率 (%)", secondary_y=True, range=[0, 105])
st.plotly_chart(fig, use_container_width=True)

# ========================================================================
# 2. 逾期深度趋势
# ========================================================================
st.subheader("📅 逾期深度趋势（订单量 + 天数）")
df_delay_stat = df_filter.groupby("到货年月_str").agg(
    总订单数=("采购单号", "count"),
    逾期订单数=("交期状态", lambda x: (x == "逾期").sum()),
    平均逾期天数=("预计-实际交期的差值", lambda x: abs(x[x < 0]).mean().round(1) if (x < 0).any() else 0),
    最长逾期天数=("预计-实际交期的差值", lambda x: abs(x[x < 0]).max() if (x < 0).any() else 0)
).reset_index()
df_delay_stat = df_delay_stat.sort_values("到货年月_str")
df_delay_stat["到货月份_中文"] = pd.to_datetime(df_delay_stat["到货年月_str"]).dt.strftime("%Y年%m月")

fig_delay = go.Figure()
fig_delay.add_trace(go.Bar(x=df_delay_stat["到货月份_中文"], y=df_delay_stat["逾期订单数"], name="逾期订单数", marker_color="#FF9900", opacity=0.8))
fig_delay.add_trace(go.Scatter(x=df_delay_stat["到货月份_中文"], y=df_delay_stat["平均逾期天数"], name="平均逾期天数", mode="lines+markers+text", text=df_delay_stat["平均逾期天数"], line=dict(color="#E64A19", width=3), yaxis="y2"))
fig_delay.add_trace(go.Scatter(x=df_delay_stat["到货月份_中文"], y=df_delay_stat["最长逾期天数"], name="最长逾期天数", mode="lines+markers+text", text=df_delay_stat["最长逾期天数"], line=dict(color="#C0392B", width=3, dash="dot"), yaxis="y2"))

fig_delay.update_layout(height=420, title=f"{selected_supplier} 逾期趋势", template="plotly_white", legend_orientation="h", legend_y=-0.2, xaxis_title="到货月份", yaxis=dict(title="逾期订单数"), yaxis2=dict(title="逾期天数", overlaying="y", side="right"))
st.plotly_chart(fig_delay, use_container_width=True)

# ========================================================================
# 3. 订单量 + 采购量趋势（合作深度）
# ========================================================================
st.subheader("📦 订单量 & 采购量趋势（合作深度）")
df_volume = df_filter.groupby("到货年月_str").agg(
    总订单数=("采购单号", "count"),
    总采购量=("采购量", "sum")
).reset_index()
df_volume = df_volume.sort_values("到货年月_str")
df_volume["到货月份_中文"] = pd.to_datetime(df_volume["到货年月_str"]).dt.strftime("%Y年%m月")

fig_vol = make_subplots(specs=[[{"secondary_y": True}]])
fig_vol.add_trace(go.Bar(x=df_volume["到货月份_中文"], y=df_volume["总订单数"], name="总订单数", marker_color="#2980B9"), secondary_y=False)
fig_vol.add_trace(go.Scatter(x=df_volume["到货月份_中文"], y=df_volume["总采购量"], name="总采购量", mode="lines+markers+text", text=df_volume["总采购量"], line=dict(color="#8E44AD", width=3)), secondary_y=True)

fig_vol.update_layout(height=420, title=f"{selected_supplier} 订单&采购量趋势", template="plotly_white", legend_orientation="h", legend_y=-0.2, xaxis_title="月份")
fig_vol.update_yaxes(title_text="订单数", secondary_y=False)
fig_vol.update_yaxes(title_text="采购量", secondary_y=True)
st.plotly_chart(fig_vol, use_container_width=True)

# ========================================================================
# 🌟 每月真实产能趋势（你想要的：每个月产能多少、区间多少）
# 不再算百分比！只看真实产能！
# ========================================================================
st.subheader("📦 每月真实产能趋势（件）")

# 1. 按月统计真实产能 = 每月【准时到货量】（逾期不算）
df_on_time = df_filter[df_filter["交期状态"] == "提前/准时"].copy()

df_monthly_cap = df_on_time.groupby(["到货年月_str"], as_index=False).agg(
    当月产能=("采购量", "sum")  # 真实产能 = 仅准时交付的量
).sort_values("到货年月_str")

df_monthly_cap["到货月份_中文"] = pd.to_datetime(
    df_monthly_cap["到货年月_str"]
).dt.strftime("%Y年%m月")

# 2. 计算产能波动区间（用来判断稳定度）
min_cap = df_monthly_cap["当月产能"].min()
max_cap = df_monthly_cap["当月产能"].max()
avg_cap = df_monthly_cap["当月产能"].mean()

# 3. 画真实产能折线图
fig_cap = go.Figure()

fig_cap.add_trace(go.Scatter(
    x=df_monthly_cap["到货月份_中文"],
    y=df_monthly_cap["当月产能"],
    mode="lines+markers+text",
    text=df_monthly_cap["当月产能"],
    textposition="top center",
    line=dict(width=3, color="#3498db"),
    name="每月真实产能（准时交付）"
))

# 平均产能线（参考基准）
fig_cap.add_trace(go.Scatter(
    x=df_monthly_cap["到货月份_中文"],
    y=[avg_cap] * len(df_monthly_cap),
    mode="lines",
    line=dict(color="#2ecc71", dash="dash"),
    name=f"平均产能 {avg_cap:.0f} 件"
))

fig_cap.update_layout(
    height=400,
    title=f"{selected_supplier} | 每月真实产能（件）",
    xaxis_title="月份",
    yaxis_title="产能（件）",
    template="plotly_white"
)

st.plotly_chart(fig_cap, use_container_width=True)

# 4. 直接告诉你产能范围（你要的结论）
st.success(f"""
📊 产能区间总结：
• 平均月真实产能（准时交付）：**{avg_cap:.0f} 件**
• 真实产能波动范围：**{min_cap:.0f} ~ {max_cap:.0f} 件**
""")

# ========================================================================
# 新增：逐月滑动半年产能&准时率明细表格（和单月面板算法完全统一）
# ========================================================================
st.markdown("---")
st.subheader("📋 逐月滑动半年产能明细")

# 定义滑动半年计算函数
def get_rolling_half_year_data(df, current_month_str):
    current_p = pd.Period(current_month_str, freq='M')
    # 滑动窗口：截止当月，往前追溯最多6个月（不足6月则取全部）
    start_p = current_p - 5
    window_periods = pd.period_range(start_p, current_p, freq='M')
    window_list = [str(p) for p in window_periods]

    # 筛选窗口周期内全部数据
    df_window = df[df["到货年月_str"].isin(window_list)].copy()
    if df_window.empty:
        return 0, 0, 0

    # ===================== 核心修改 =====================
    # 1. 近半年平均【真实产能】= 仅准时交付的月度平均值
    df_ontime_window = df_window[df_window["交期状态"] == "提前/准时"].copy()
    monthly_total = df_ontime_window.groupby("到货年月_str")["采购量"].sum()
    half_year_avg_cap = monthly_total.mean().round(0)

    # 2. 近半年准时率（不变，正确）
    total_order = len(df_window)
    ontime_order = (df_window["交期状态"] == "提前/准时").sum()
    half_year_on_time = (ontime_order / total_order * 100).round(1) if total_order > 0 else 0

    return half_year_avg_cap, half_year_on_time, total_order

# 逐月计算所有指标
table_data = []
for idx, row in df_volume.iterrows():
    month = row["到货年月_str"]
    month_cn = row["到货月份_中文"]

    # ===================== 当月真实产能 = 准时到货量 =====================
    current_cap = df_filter[
        (df_filter["到货年月_str"] == month) &
        (df_filter["交期状态"] == "提前/准时")
    ]["采购量"].sum()

    # 调用滑动计算
    avg_6m_cap, rate_6m, _ = get_rolling_half_year_data(df_filter, month)

    # 统一标准公式计算
    safe_cap = (avg_6m_cap * rate_6m / 100).round(0)
    load_rate = 0.0
    if safe_cap > 0:
        load_rate = (current_cap / safe_cap * 100).round(1)

    # 组装表格行
    table_data.append({
        "到货月份": month_cn,
        "当月真实产能(件)": int(current_cap),  # 已修改为准时
        "滑动近半年平均产能(件)": int(avg_6m_cap),
        "滑动近半年准时率": f"{rate_6m}%",
        "当月安全可放量产能(件)": int(safe_cap),
        "当月产能负载利用率": f"{load_rate}%"
    })

# 转为DataFrame展示
df_table = pd.DataFrame(table_data)

st.dataframe(
    df_table,
    use_container_width=True,
    hide_index=True,
    height=500
)

# 补充提示说明
st.info("""
💡 计算规则说明：
1. 滑动窗口：以当月为终点，往前追溯最多6个月，历史不足6个月则取全部已有数据
2. 真实产能 = 仅统计【准时/提前交付】的到货量，逾期交付不计入产能
3. 安全产能 = 滑动近半年平均真实产能 × 滑动近半年准时率
4. 负载利用率 = 当月真实产能 ÷ 当月安全可放量产能
""")


# ========================================================================
# 5. 履约等级变化趋势
# ========================================================================
st.subheader("🏅 履约等级月度变化")
df_stat["履约等级"] = df_stat["准时率%"].apply(lambda x: "优质" if x>=90 else "合格" if x>=80 else "异常")
fig_level = go.Figure()
fig_level.add_trace(go.Scatter(
    x=df_stat["到货月份_中文"], y=df_stat["准时率%"],
    mode="lines+markers+text", text=df_stat["履约等级"],
    textposition="top center", line=dict(color="#27AE60", width=3)
))
fig_level.update_layout(height=420, title=f"{selected_supplier} 履约等级变化", template="plotly_white", yaxis_range=[0, 105], yaxis_title="准时率 %", xaxis_title="月份")
st.plotly_chart(fig_level, use_container_width=True)