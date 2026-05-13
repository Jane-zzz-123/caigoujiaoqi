import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from io import BytesIO
import base64
import math

# 页面配置（完全保留）
st.set_page_config(
    page_title="FBA海运物流交期分析看板",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------- 工具函数（完全保留你的原有代码） ----------------------
def get_prev_month(current_month):
    """获取上个月的年月字符串（格式：YYYY-MM）"""
    try:
        current = datetime.strptime(current_month, "%Y-%m")
        prev_month = current.replace(day=1) - pd.Timedelta(days=1)
        return prev_month.strftime("%Y-%m")
    except:
        return ""

def calculate_percent_change(current, prev):
    """计算环比变化百分比"""
    try:
        if prev == 0:
            return 0 if current == 0 else 100
        return ((current - prev) / prev) * 100
    except:
        return 0

def highlight_large_cells(val, avg, col_name):
    """高亮大于平均值的单元格"""
    try:
        if pd.isna(val) or val == "-" or str(val) == "平均值":
            return ""
        val_num = float(val)
        if val_num > avg:
            return "background-color: #ffcccc"  # 浅红色
    except:
        pass
    return ""

def highlight_change(val):
    """高亮环比变化（红升绿降）"""
    try:
        if pd.isna(val) or val == "-" or str(val).strip() == "":
            return ""
        val_str = str(val).replace('%', '').strip()
        val_num = float(val_str)
        if val_num > 0:
            return "color: red"
        elif val_num < 0:
            return "color: green"
    except:
        pass
    return ""

def get_table_download_link(df, filename, text):
    """生成表格下载链接"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='FBA海运明细')
    output.seek(0)
    b64 = base64.b64encode(output.read()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">{text}</a>'
    return href

# ---------------------- 数据加载函数（两份数据逻辑） ----------------------
@st.cache_data
def load_data():
    url = "https://github.com/Jane-zzz-123/Logistics/raw/main/Logisticsdata.xlsx"
    try:
        df_all = pd.read_excel(url, sheet_name="上架完成-海运（FBA号）")  # 全部数据
    except Exception as e:
        st.error(f"读取数据失败：{str(e)}")
        return pd.DataFrame(), pd.DataFrame()

    # 处理「是否为异常数据」列
    abnormal_col = "是否为异常数据"
    if abnormal_col in df_all.columns:
        df_all[abnormal_col] = df_all[abnormal_col].str.strip().fillna("否")
        df_all[abnormal_col] = df_all[abnormal_col].replace({
            "异常数据": "是", "正常数据": "否", "异常": "是", "正常": "否"
        })
        df_clean = df_all[df_all[abnormal_col] == "否"].copy()  # 纯净数据
    else:
        df_all[abnormal_col] = "否"
        df_clean = df_all.copy()
        st.warning(f"未找到「{abnormal_col}」列，已默认全部为正常数据（否）")

    # ===================== 新增：处理 是否查验 列 =====================
    check_col = "是否查验"
    if check_col in df_all.columns:
        df_all[check_col] = df_all[check_col].astype(str).str.strip().fillna("否")
        df_all[check_col] = df_all[check_col].replace({"是": "是", "否": "否", "nan": "否"})
    else:
        df_all[check_col] = "否"
        st.warning(f"未找到「{check_col}」列，已默认全部为否")
    # =================================================================

    # 核心列筛选
    core_columns = [
        "FBA号", "区域", "物流方式", "店铺", "仓库", "货代", "异常备注","货件单号",
        "发货-开船", "开船-到港", "到港-提柜", "提柜-签收", "签收-完成上架","开船-提柜",
        "到货年月", "签收-发货时间", "上架完成-发货时间","开船-签收","开船-完成上架",
        "预计物流时效-实际物流时效差值(绝对值)",
        "预计物流时效-实际物流时效差值", "提前/延期(整体)",
        "预计物流时效-实际物流时效差值（货代）",
        "提前/延期（货代）", "提前/延期（仓库）", abnormal_col, "是否查验"  # <-- 加入是否查验
    ]
    existing_columns = [col for col in core_columns if col in df_all.columns]
    missing_columns = [col for col in core_columns if col not in df_all.columns]
    if missing_columns:
        st.warning(f"以下列不存在，已忽略：{missing_columns}")
    df_all = df_all[existing_columns]
    df_clean = df_clean[existing_columns]

    # 统一到货年月格式
    df_all["到货年月"] = pd.to_datetime(df_all["到货年月"], errors='coerce').dt.strftime("%Y-%m")
    df_clean["到货年月"] = pd.to_datetime(df_clean["到货年月"], errors='coerce').dt.strftime("%Y-%m")
    df_all = df_all.dropna(subset=["到货年月"])
    df_clean = df_clean.dropna(subset=["到货年月"])

    # 清洗数值列
    abs_diff_col = "预计物流时效-实际物流时效差值(绝对值)"
    real_diff_col = "预计物流时效-实际物流时效差值"
    if abs_diff_col in df_all.columns:
        df_all[abs_diff_col] = pd.to_numeric(df_all[abs_diff_col], errors='coerce').fillna(0)
        df_clean[abs_diff_col] = pd.to_numeric(df_clean[abs_diff_col], errors='coerce').fillna(0)
    if real_diff_col in df_all.columns:
        df_all[real_diff_col] = pd.to_numeric(df_all[real_diff_col], errors='coerce').fillna(0)
        df_clean[real_diff_col] = pd.to_numeric(df_clean[real_diff_col], errors='coerce').fillna(0)

    return df_all, df_clean

# ---------------------- 主程序逻辑 ----------------------
# 1. 加载两份基础数据
df_all, df_clean = load_data()
if df_all.empty:
    st.error("暂无可用数据，请检查数据源或列名！")
    st.stop()

# 2. 顶部筛选按钮
st.header("FBA海运物流交期分析看板")
data_filter = st.radio(
    "📊 选择数据范围：",
    options=["全部数据", "纯净数据（剔除异常）"],
    index=0,
    horizontal=True,
    key="data_filter"
)

# 3. 核心：生成两套数据（完全满足你的需求）
if data_filter == "纯净数据（剔除异常）":
    df_selected_FBA = df_clean.copy()
    df_selected = df_clean.drop_duplicates(subset=["货件单号"], keep="first").copy()

    # ===================== 纯净模式：剔除的异常统计（货件 + FBA + 查验） =====================
    # 全局被剔除的异常数据（来自 df_all）
    df_excluded = df_all[df_all["是否为异常数据"] == "是"]

    # 货件维度（去重）
    excluded_shipment = df_excluded.drop_duplicates(subset=["货件单号"], keep="first")
    excluded_shipment_count = len(excluded_shipment)
    excluded_shipment_check = len(excluded_shipment[excluded_shipment["是否查验"] == "是"])
    excluded_shipment_nocheck = excluded_shipment_count - excluded_shipment_check

    # FBA维度（不去重）
    excluded_fba_count = len(df_excluded)
    excluded_fba_check = len(df_excluded[df_excluded["是否查验"] == "是"])
    excluded_fba_nocheck = excluded_fba_count - excluded_fba_check

    st.success(
        f"✅ 已筛选为纯净数据（全局），\n"
        f"已剔除 {excluded_shipment_count} 条货件异常数据（查验导致 {excluded_shipment_check} 条，非查验 {excluded_shipment_nocheck} 条），\n"
        f"已剔除 {excluded_fba_count} 条FBA异常数据（查验导致 {excluded_fba_check} 条，非查验 {excluded_fba_nocheck} 条），\n"
        f"当前共 {len(df_selected)} 条货件记录 | {len(df_selected_FBA)} 条FBA记录"
    )
else:
    df_selected_FBA = df_all.copy()
    df_selected = df_all.drop_duplicates(subset=["货件单号"], keep="first").copy()

    # ===================== 【核心修改】查验统计 =====================
    # 货件维度（去重后）
    total_shipment = len(df_selected)
    abnormal_shipment = len(df_selected[df_selected["是否为异常数据"] == "是"])
    abnormal_shipment_check = len(df_selected[(df_selected["是否为异常数据"] == "是") & (df_selected["是否查验"] == "是")])
    abnormal_shipment_nocheck = abnormal_shipment - abnormal_shipment_check

    # FBA维度（不去重）
    total_fba = len(df_selected_FBA)
    abnormal_fba = len(df_selected_FBA[df_selected_FBA["是否为异常数据"] == "是"])
    abnormal_fba_check = len(df_selected_FBA[(df_selected_FBA["是否为异常数据"] == "是") & (df_selected_FBA["是否查验"] == "是")])
    abnormal_fba_nocheck = abnormal_fba - abnormal_fba_check

    # 输出你要的格式
    st.info(
        f"ℹ️ 当前展示全部数据（全局），共 {total_shipment} 条货件记录，"
        f"其中异常 {abnormal_shipment} 条，查验导致 {abnormal_shipment_check} 条，非查验 {abnormal_shipment_nocheck} 条 | "
        f"共 {total_fba} 条FBA记录，其中异常 {abnormal_fba} 条，查验导致 {abnormal_fba_check} 条，非查验 {abnormal_fba_nocheck} 条"
    )
# 5. 主看板区域
st.title("🚢 FBA海运分析看板区域")
st.divider()

# 6. 当月数据筛选（基于 df_selected，不会丢数据）
st.subheader("🔍 当月海运分析")
month_options = sorted(df_selected["到货年月"].unique(), reverse=True)
if not month_options:
    st.warning("⚠️ 暂无可用的到货年月数据")
    st.stop()

selected_month = st.selectbox(
    "选择到货年月",
    options=month_options,
    index=0,
    key="month_selector_current"
)
st.subheader("")  # 空行分隔，优化排版
# 获取所有物流方式选项（去重），并添加“全部”选项
logistics_methods = ['全部'] + list(df_selected['物流方式'].dropna().unique())
# 创建下拉筛选器，默认选中“全部”
selected_logistics = st.selectbox(
    "选择物流方式",
    options=logistics_methods,
    index=0,  # 默认选中第一个选项（全部）
    key="logistics_filter"  # 唯一key，避免streamlit缓存冲突
)

# -------------------------------------------
# 7. 当月数据【两套同步筛选】
# -------------------------------------------
# A. 货件去重（非仓库用）
df_current = df_selected[df_selected["到货年月"] == selected_month].copy()
if selected_logistics != '全部':
    df_current = df_current[df_current['物流方式'] == selected_logistics].copy()

# B. FBA不去重（仓库分析用）→ 新增
df_current_FBA = df_selected_FBA[df_selected_FBA["到货年月"] == selected_month].copy()
if selected_logistics != '全部':
    df_current_FBA = df_current_FBA[df_current_FBA['物流方式'] == selected_logistics].copy()

# -------------------------------------------
# 8. 上月数据【两套同步筛选】
# -------------------------------------------
prev_month = get_prev_month(selected_month)

# A. 货件去重（非仓库用）
df_prev = df_selected[df_selected["到货年月"] == prev_month].copy() if prev_month and prev_month in month_options else pd.DataFrame()
if selected_logistics != '全部' and not df_prev.empty:
    df_prev = df_prev[df_prev['物流方式'] == selected_logistics].copy()

# B. FBA不去重（仓库分析用）→ 新增
df_prev_FBA = df_selected_FBA[df_selected_FBA["到货年月"] == prev_month].copy() if prev_month and prev_month in month_options else pd.DataFrame()
if selected_logistics != '全部' and not df_prev.empty:
    df_prev_FBA = df_prev_FBA[df_prev_FBA['物流方式'] == selected_logistics].copy()

# -------------------------------------------
# -------------------------------------------
# 9. 【最终版】当月异常数据统计 + 查验区分（纯净数据模式也支持）
# -------------------------------------------
logistics_tip = f"，筛选物流方式：{selected_logistics}" if selected_logistics != "全部" else ""

# 先统一计算当月异常总数（修复报错）
abnormal_filter = (df_all["到货年月"] == selected_month) & (df_all["是否为异常数据"] == "是")
if selected_logistics != '全部':
    abnormal_filter = abnormal_filter & (df_all["物流方式"] == selected_logistics)
abnormal_current_month = len(df_all[abnormal_filter])

# 纯净数据模式下，我们也需要统计「被剔除的异常数据」中查验/非查验的数量
if data_filter == "纯净数据（剔除异常）":
    # 1. 货件维度：被剔除的异常货件（去重）
    # 先筛选出当月、对应物流方式的所有数据，再去重货件
    temp_all_shipment = df_all[
        (df_all["到货年月"] == selected_month) &
        (df_all["物流方式"] == selected_logistics if selected_logistics != "全部" else True)
        ].drop_duplicates(subset=["货件单号"], keep="first")

    excluded_shipment = len(temp_all_shipment[temp_all_shipment["是否为异常数据"] == "是"])
    excluded_shipment_check = len(temp_all_shipment[
                                      (temp_all_shipment["是否为异常数据"] == "是") &
                                      (temp_all_shipment["是否查验"] == "是")
                                      ])
    excluded_shipment_nocheck = excluded_shipment - excluded_shipment_check

    # 2. FBA维度：被剔除的异常FBA记录（不去重）
    temp_all_fba = df_all[
        (df_all["到货年月"] == selected_month) &
        (df_all["物流方式"] == selected_logistics if selected_logistics != "全部" else True)
        ]

    excluded_fba = len(temp_all_fba[temp_all_fba["是否为异常数据"] == "是"])
    excluded_fba_check = len(temp_all_fba[
                                 (temp_all_fba["是否为异常数据"] == "是") &
                                 (temp_all_fba["是否查验"] == "是")
                                 ])
    excluded_fba_nocheck = excluded_fba - excluded_fba_check

    # 3. 按你要的格式输出
    st.info(f"📌 【{selected_month}】已筛选为纯净数据{logistics_tip}，"
            f"已剔除 {excluded_shipment} 条货件异常数据（查验导致 {excluded_shipment_check} 条，非查验 {excluded_shipment_nocheck} 条），"
            f"已剔除 {excluded_fba} 条FBA记录异常数据（查验导致 {excluded_fba_check} 条，非查验 {excluded_fba_nocheck} 条），"
            f"当前共 {len(df_current)} 条货件记录 | {len(df_current_FBA)} 条FBA记录")
else:
    # 全部数据模式：保持之前的统计逻辑
    # 货件维度（去重）
    total_current_shipment = len(df_current)
    abnormal_current_shipment = len(df_current[df_current["是否为异常数据"] == "是"])
    abnormal_shipment_check = len(df_current[(df_current["是否为异常数据"] == "是") & (df_current["是否查验"] == "是")])
    abnormal_shipment_nocheck = abnormal_current_shipment - abnormal_shipment_check

    # FBA维度（不去重）
    total_current_fba = len(df_current_FBA)
    abnormal_current_fba = len(df_current_FBA[df_current_FBA["是否为异常数据"] == "是"])
    abnormal_fba_check = len(
        df_current_FBA[(df_current_FBA["是否为异常数据"] == "是") & (df_current_FBA["是否查验"] == "是")])
    abnormal_fba_nocheck = abnormal_current_fba - abnormal_fba_check

    st.info(f"📌 【{selected_month}】当前显示全部数据{logistics_tip}，"
            f"共 {total_current_shipment} 条货件记录，其中异常 {abnormal_current_shipment} 条（查验导致 {abnormal_shipment_check} 条，非查验 {abnormal_shipment_nocheck} 条） | "
            f"共 {total_current_fba} 条FBA记录，其中异常 {abnormal_current_fba} 条（查验导致 {abnormal_fba_check} 条，非查验 {abnormal_fba_nocheck} 条）")
# ---------------------- 你的核心指标/可视化/表格代码（仅改数据源引用） ----------------------
# ---------------------- ① 核心指标卡片 ----------------------
st.markdown("### 核心指标")

# 计算核心指标
# 1. FBA单数
current_fba = len(df_current)
prev_fba = len(df_prev) if not df_prev.empty else 0
fba_change = current_fba - prev_fba
fba_change_text = f"{'↑' if fba_change > 0 else '↓' if fba_change < 0 else '—'} {abs(fba_change)} (上月: {prev_fba})"
fba_change_color = "red" if fba_change > 0 else "green" if fba_change < 0 else "gray"

# 2. 提前/准时数（修复：匹配实际数据中的值，比如可能是"提前"或"准时"分开存储）
# 兼容处理：如果数据中是"提前"和"准时"分开，合并统计
if "提前/延期(整体)" in df_current.columns:
    # 适配不同的数据值：支持"提前/准时"、"提前"、"准时"三种情况
    current_on_time = len(df_current[df_current["提前/延期(整体)"].isin(["提前/准时", "提前", "准时"])])
else:
    current_on_time = 0

if not df_prev.empty and "提前/延期(整体)" in df_prev.columns:
    prev_on_time = len(df_prev[df_prev["提前/延期(整体)"].isin(["提前/准时", "提前", "准时"])])
else:
    prev_on_time = 0

on_time_change = current_on_time - prev_on_time
on_time_change_text = f"{'↑' if on_time_change > 0 else '↓' if on_time_change < 0 else '—'} {abs(on_time_change)} (上月: {prev_on_time})"
on_time_change_color = "red" if on_time_change > 0 else "green" if on_time_change < 0 else "gray"

# 3. 延期数
current_delay = len(df_current[df_current["提前/延期(整体)"] == "延期"]) if "提前/延期(整体)" in df_current.columns else 0
prev_delay = len(
    df_prev[df_prev["提前/延期(整体)"] == "延期"]) if not df_prev.empty and "提前/延期(整体)" in df_prev.columns else 0
delay_change = current_delay - prev_delay
delay_change_text = f"{'↑' if delay_change > 0 else '↓' if delay_change < 0 else '—'} {abs(delay_change)} (上月: {prev_delay})"
delay_change_color = "red" if delay_change > 0 else "green" if delay_change < 0 else "gray"

# 4. 绝对值差值平均值（将百分比改为差值）
abs_col = "预计物流时效-实际物流时效差值(绝对值)"
current_abs_avg = df_current[abs_col].mean() if abs_col in df_current.columns and len(df_current) > 0 else 0
prev_abs_avg = df_prev[abs_col].mean() if not df_prev.empty and abs_col in df_prev.columns and len(
    df_prev) > 0 else 0
abs_change = current_abs_avg - prev_abs_avg  # 差值计算（替换百分比）
abs_change_text = f"{'↑' if abs_change > 0 else '↓' if abs_change < 0 else '—'} {abs(abs_change):.2f} (上月: {prev_abs_avg:.2f})"
abs_change_color = "red" if abs_change > 0 else "green" if abs_change < 0 else "gray"

# 5. 实际差值平均值
diff_col = "预计物流时效-实际物流时效差值"
current_diff_avg = df_current[diff_col].mean() if diff_col in df_current.columns and len(df_current) > 0 else 0
prev_diff_avg = df_prev[diff_col].mean() if not df_prev.empty and diff_col in df_prev.columns and len(
    df_prev) > 0 else 0
diff_change = current_diff_avg - prev_diff_avg
diff_change_text = f"{'↑' if diff_change > 0 else '↓' if diff_change < 0 else '—'} {abs(diff_change):.2f} (上月: {prev_diff_avg:.2f})"
diff_change_color = "red" if diff_change > 0 else "green" if diff_change < 0 else "gray"

# ========== 新增：6. 准时率（核心修改1） ==========
# 当月准时率（提前/准时数 ÷ 总FBA数 × 100%）
current_on_time_rate = (current_on_time / current_fba * 100) if current_fba > 0 else 0.0
# 上月准时率
prev_on_time_rate = (prev_on_time / prev_fba * 100) if prev_fba > 0 else 0.0
# 准时率环比变化（百分点）
on_time_rate_change = current_on_time_rate - prev_on_time_rate
# 准时率变化文本（和其他指标样式统一）
on_time_rate_change_text = f"{'↑' if on_time_rate_change > 0 else '↓' if on_time_rate_change < 0 else '—'} {abs(on_time_rate_change):.1f}% (上月: {prev_on_time_rate:.1f}%)"
# 准时率变化颜色（红升绿降）
on_time_rate_change_color = "red" if on_time_rate_change > 0 else "green" if on_time_rate_change < 0 else "gray"

# 显示卡片（一行六列）- 改用HTML自定义样式（核心修改2：从5列改为6列）
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.markdown(f"""
    <div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;'>
        <h5 style='margin: 0; color: #333;'>FBA单</h5>
        <p style='font-size: 24px; margin: 8px 0; font-weight: bold;'>{current_fba}</p>
        <p style='font-size: 14px; color: {fba_change_color}; margin: 0;'>{fba_change_text}</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div style='background-color: #f0f8f0; padding: 15px; border-radius: 8px; text-align: center;'>
        <h5 style='margin: 0; color: green;'>提前/准时数</h5>
        <p style='font-size: 24px; margin: 8px 0; font-weight: bold;'>{current_on_time}</p>
        <p style='font-size: 14px; color: {on_time_change_color}; margin: 0;'>{on_time_change_text}</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div style='background-color: #fff0f0; padding: 15px; border-radius: 8px; text-align: center;'>
        <h5 style='margin: 0; color: red;'>延期数</h5>
        <p style='font-size: 24px; margin: 8px 0; font-weight: bold;'>{current_delay}</p>
        <p style='font-size: 14px; color: {delay_change_color}; margin: 0;'>{delay_change_text}</p>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;'>
        <h5 style='margin: 0; color: #333;'>绝对值差值均值</h5>
        <p style='font-size: 24px; margin: 8px 0; font-weight: bold;'>{current_abs_avg:.2f}</p>
        <p style='font-size: 14px; color: {abs_change_color}; margin: 0;'>{abs_change_text}</p>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;'>
        <h5 style='margin: 0; color: #333;'>实际差值均值</h5>
        <p style='font-size: 24px; margin: 8px 0; font-weight: bold;'>{current_diff_avg:.2f}</p>
        <p style='font-size: 14px; color: {diff_change_color}; margin: 0;'>{diff_change_text}</p>
    </div>
    """, unsafe_allow_html=True)

# ========== 新增：第6列 准时率卡片（核心修改3） ==========
with col6:
    st.markdown(f"""
    <div style='background-color: #e8f4f8; padding: 15px; border-radius: 8px; text-align: center;'>
        <h5 style='margin: 0; color: #2196f3;'>准时率</h5>
        <p style='font-size: 24px; margin: 8px 0; font-weight: bold;'>{current_on_time_rate:.1f}%</p>
        <p style='font-size: 14px; color: {on_time_rate_change_color}; margin: 0;'>{on_time_rate_change_text}</p>
    </div>
    """, unsafe_allow_html=True)

# 计算辅助指标（业务视角）
total_orders = current_fba
on_time_rate = (current_on_time / total_orders * 100) if total_orders > 0 else 0  # 准时率
delay_rate = (current_delay / total_orders * 100) if total_orders > 0 else 0  # 延期率
prev_on_time_rate = (prev_on_time / prev_fba * 100) if prev_fba > 0 else 0  # 上月准时率
on_time_rate_change = on_time_rate - prev_on_time_rate  # 准时率变化

# 核心结论（先给定性判断）
if on_time_rate >= 90:
    core_conclusion = f"{selected_month}海运物流整体表现优秀，准时率达{on_time_rate:.1f}%，远高于行业基准"
elif on_time_rate >= 80:
    core_conclusion = f"{selected_month}海运物流表现良好，准时率{on_time_rate:.1f}%，整体可控"
elif on_time_rate >= 70:
    core_conclusion = f"{selected_month}海运物流表现一般，准时率{on_time_rate:.1f}%，需关注延期问题"
else:
    core_conclusion = f"{selected_month}海运物流表现较差，准时率仅{on_time_rate:.1f}%，延期风险显著"

# 关键数据支撑（精简+业务化）
data_support = f"""
本月共处理订单{current_fba}单（环比{'+' if fba_change > 0 else ''}{fba_change}单）：
✅ 提前/准时单{current_on_time}单（准时率{on_time_rate:.1f}%，环比{'↑' if on_time_rate_change > 0 else '↓'}{abs(on_time_rate_change):.1f}个百分点）；
❌ 延期单{current_delay}单（延期率{delay_rate:.1f}%）；
📊 实际物流时效与预计的偏差均值为{current_diff_avg:.2f}天（绝对值均值{current_abs_avg:.2f}天），环比{'扩大' if abs_change > 0 else '收窄'}{abs(abs_change):.2f}天。
"""

# 风险/亮点提示（针对性分析）
tips = ""
# 1. 准时率大幅波动提示
if abs(on_time_rate_change) >= 5:
    if on_time_rate_change > 0:
        tips += f"💡 亮点：本月准时率环比提升{on_time_rate_change:.1f}个百分点，物流效率显著改善；"
    else:
        tips += f"⚠️ 风险：本月准时率环比下降{abs(on_time_rate_change):.1f}个百分点，需排查延期原因；"
# 2. 延期单占比过高提示
if delay_rate >= 30:
    tips += f"⚠️ 风险：延期单占比超30%，建议优先核查高频延期的货代/仓库；"
# 3. 时效偏差扩大提示
if abs_change >= 2:
    tips += f"⚠️ 风险：时效偏差绝对值环比扩大{abs_change:.2f}天，预计时效的准确性需优化；"
# 4. 无明显风险的正向提示
if not tips:
    tips = "💡 本月物流时效无显著异常，各维度表现稳定。"

# 整合最终总结
summary_text = f"""
### {selected_month}海运物流核心分析
{core_conclusion}

{data_support}

{tips}
"""

# 渲染总结（用markdown美化）
st.markdown(summary_text)

# ---------------------- ② 当月准时率与时效偏差 ----------------------
st.markdown("### 准时率与时效偏差分布")
col1, col2 = st.columns(2)

# 左：饼图（提前/准时 vs 延期）
with col1:
    if "提前/延期(整体)" in df_current.columns and len(df_current) > 0:
        # 兼容数据值：合并"提前/准时"、"提前"、"准时"为同一类别
        df_current["提前/延期(整体)_分类"] = df_current["提前/延期(整体)"].apply(
            lambda x: "提前/准时" if x in ["提前/准时", "提前", "准时"] else "延期" if x == "延期" else "其他"
        )
        pie_data = df_current["提前/延期(整体)_分类"].value_counts()

        # 确保颜色映射严格生效（显式指定颜色列表）
        categories = pie_data.index.tolist()
        colors = []
        for cat in categories:
            if cat == "提前/准时":
                colors.append("green")
            elif cat == "延期":
                colors.append("red")
            else:
                colors.append("gray")  # 处理意外类别

        fig_pie = px.pie(
            values=pie_data.values,
            names=pie_data.index,
            title=f"{selected_month} 海运准时率分布",
            color=pie_data.index,  # 显式指定颜色依据
            color_discrete_sequence=colors  # 使用顺序颜色列表确保对应关系
        )
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.write("⚠️ 暂无准时率数据")

# 右：文本直方图（提前/准时 和 延期）
with col2:
    if diff_col in df_current.columns and len(df_current) > 0:
        # 提取并处理数据
        diff_data = df_current[diff_col].dropna()
        diff_data = diff_data.round().astype(int)  # 转换为整数天数

        # 分离提前/准时（>=0）和延期（<0）数据
        early_data = diff_data[diff_data >= 0]  # 包含0天（准时）
        delay_data = diff_data[diff_data < 0]  # 延期数据

        # 统计各天数出现次数
        early_counts = early_data.value_counts().sort_index(ascending=False)  # 从大到小排序
        delay_counts = delay_data.value_counts().sort_index()  # 从小到大排序（-7, -6...）

        # 计算最大计数（用于归一化显示长度）
        max_count = max(
            early_counts.max() if not early_counts.empty else 0,
            delay_counts.max() if not delay_counts.empty else 0
        )
        max_display_length = 20  # 最大显示字符数

        # 生成文本直方图（使用HTML设置颜色，与饼图保持一致）
        st.markdown("#### 提前/准时区间分布")
        if not early_counts.empty:
            for day, count in early_counts.items():
                # 计算显示长度（按比例缩放）
                display_length = int((count / max_count) * max_display_length) if max_count > 0 else 0
                bar = "█" * display_length
                day_label = f"+{day}天" if day > 0 else "0天"  # 0天特殊处理
                # 绿色显示（与饼图提前/准时颜色一致）
                st.markdown(
                    f"<div style='font-family: monospace;'><span style='display: inline-block; width: 60px;'>{day_label}</span>"
                    f"<span style='color: green;'>{bar}</span> <span> ({count})</span></div>",
                    unsafe_allow_html=True
                )
        else:
            st.text("暂无提前/准时数据")

        st.markdown("#### 延迟区间分布")
        if not delay_counts.empty:
            for day, count in delay_counts.items():
                display_length = int((count / max_count) * max_display_length) if max_count > 0 else 0
                bar = "█" * display_length
                # 红色显示（与饼图延期颜色一致）
                st.markdown(
                    f"<div style='font-family: monospace;'><span style='display: inline-block; width: 60px;'>{day}天</span>"
                    f"<span style='color: red;'>{bar}</span> <span> ({count})</span></div>",
                    unsafe_allow_html=True
                )
        else:
            st.text("暂无延迟数据")
    else:
        st.write("⚠️ 暂无时效偏差数据")

st.divider()
# ---------------------- ③ 当月FBA海运明细表格 ----------------------
st.markdown("### 海运明细（含平均值）")

# 准备明细数据
detail_cols = [
    "到货年月", "提前/延期(整体)", "FBA号", "区域","物流方式", "店铺", "仓库", "货代",
    # 新增的物流阶段列（加在货代右边）
    "发货-开船", "开船-到港", "到港-提柜", "开船-提柜","提柜-签收","开船-签收", "开船-完成上架","签收-完成上架",
    "签收-发货时间", "上架完成-发货时间", "提前/延期（货代）",
    "提前/延期（仓库）",
    abs_col, diff_col
]
# 过滤存在的列
detail_cols = [col for col in detail_cols if col in df_current.columns]
df_detail = df_current[detail_cols].copy() if len(detail_cols) > 0 else pd.DataFrame()

if len(df_detail) > 0:
    # 按时效差值升序排序
    if diff_col in df_detail.columns:
        df_detail = df_detail.sort_values(diff_col, ascending=True)

    # 定义需要显示为整数的列
    int_cols = [
        "发货-开船", "开船-到港", "到港-提柜","开船-提柜", "提柜-签收", "开船-签收","开船-完成上架","签收-完成上架",
        "签收-发货时间", "上架完成-发货时间"
    ]
    # 过滤存在的整数列
    int_cols = [col for col in int_cols if col in df_detail.columns]

    # 将整数列转换为无小数点格式（空值填充为0）
    for col in int_cols:
        df_detail[col] = pd.to_numeric(df_detail[col], errors='coerce').fillna(0).astype(int)

    # 计算平均值行
    avg_row = {}
    for col in detail_cols:
        if col in ["到货年月"]:
            avg_row[col] = "平均值"
        elif col in ["提前/延期(整体)", "FBA号", "店铺","区域", "仓库", "货代", "物流方式", "提前/延期（货代）",
                     "提前/延期（仓库）"]:
            avg_row[col] = "-"
        elif col in int_cols:
            # 整数列的平均值保留两位小数
            avg_val = df_detail[col].mean()
            avg_row[col] = round(avg_val, 2)
        else:
            # 其他数值列保留两位小数
            avg_val = df_detail[col].mean() if len(df_detail) > 0 else 0
            avg_row[col] = round(avg_val, 2)


    # 格式化函数
    def format_value(val, col):
        """格式化单元格值"""
        try:
            if val == "平均值" or val == "-":
                return val
            if col in int_cols:
                if isinstance(val, (int, float)):
                    if val == int(val):
                        return f"{int(val)}"
                    else:
                        return f"{val:.2f}"
            elif col in [abs_col, diff_col]:
                return f"{val:.2f}"
            return str(val)
        except:
            return str(val)


    # === 1. 解决列名不完整：换行/自适应宽度 ===
    # 处理长列名（换行显示）
    def format_colname(col):
        """列名换行处理，避免截断"""
        if len(col) > 8:
            # 按特殊字符拆分长列名
            if "-" in col:
                return col.replace("-", "<br>-")
            elif "（" in col:
                return col.replace("（", "<br>（")
            else:
                # 手动换行
                return col[:8] + "<br>" + col[8:]
        return col


    # === 2. 生成带固定行的表格（列名完整） ===
    html_content = f"""
    <style>
    /* 容器样式 */
    .table-container {{
        height: 400px;
        overflow-y: auto;
        overflow-x: auto;  /* 横向滚动，避免列名截断 */
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        margin: 10px 0;
    }}

    /* 核心：单表格 + sticky固定行 */
    .data-table {{
        width: 100%;
        min-width: max-content;  /* 确保列名完整显示 */
        border-collapse: collapse;
    }}

    /* 表头固定 + 列名完整显示 */
    .data-table thead th {{
        position: sticky;
        top: 0;
        background-color: #f8f9fa;
        font-weight: bold;
        z-index: 2;
        padding: 8px 4px;  /* 减小内边距，增加显示空间 */
        white-space: normal;  /* 允许列名换行 */
        line-height: 1.2;     /* 行高适配换行 */
        text-align: center;   /* 列名居中，更易读 */
    }}

    /* 平均值行固定（紧跟表头） */
    .avg-row td {{
        position: sticky;
        top: 60px; /* 适配换行后的表头高度 */
        background-color: #fff3cd;
        font-weight: 500;
        z-index: 1;
        text-align: center;
    }}

    /* 通用单元格样式 */
    .data-table th, .data-table td {{
        padding: 8px;
        border: 1px solid #e0e0e0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    /* 数据行左对齐 */
    .data-table tbody tr td {{
        text-align: left;
    }}

    /* 高亮样式 */
    .highlight {{
        background-color: #ffcccc !important;
    }}
    </style>

    <div class="table-container">
        <table class="data-table">
            <!-- 表头（列名换行处理） -->
            <thead>
                <tr>
                    {''.join([f'<th>{format_colname(col)}</th>' for col in detail_cols])}
                </tr>
            </thead>
            <tbody>
                <!-- 平均值行 -->
                <tr class="avg-row">
                    {''.join([f'<td>{format_value(avg_row[col], col)}</td>' for col in detail_cols])}
                </tr>
                <!-- 数据行 -->
                {''.join([
        '<tr>' + ''.join([
            f'<td class={"highlight" if (
                    col in (int_cols + [abs_col, diff_col])
                    and avg_row[col] not in ["-", "平均值"]
                    and pd.notna(row[col])
                    and float(row[col]) > float(avg_row[col])
            ) else ""}>{format_value(row[col], col)}</td>'
            for col in detail_cols
        ]) + '</tr>'
        for _, row in df_detail.iterrows()
    ])}
            </tbody>
        </table>
    </div>
    """

    # 渲染表格
    st.markdown(html_content, unsafe_allow_html=True)

    # === 3. 添加表格下载功能 ===
    # 构建带平均值的完整数据（用于下载）
    df_download = pd.concat([pd.DataFrame([avg_row]), df_detail], ignore_index=True)

    # 显示下载按钮
    st.markdown(
        get_table_download_link(
            df_download,
            f"海运明细_{selected_month}.xlsx",
            "📥 下载海运明细表格（Excel格式）"
        ),
        unsafe_allow_html=True
    )

else:
    st.write("⚠️ 暂无明细数据")

st.divider()
# --------------------------
# 1. 数据预处理 & 字段定义（核心：匹配你的业务逻辑）
# --------------------------
st.subheader("📝 延期订单深度归因分析")

# 请确认以下字段名与你的数据完全一致！
main_delay_col = "提前/延期(整体)"  # 总提前/延期列
forwarder_delay_col = "提前/延期（货代）"  # 货代延期分类列
warehouse_delay_col = "提前/延期（仓库）"  # 仓库延期分类列
region_col = "区域"  # 区域列名（请确认与数据一致）
ship_method_col = "物流方式"  # 物流方式列名（请确认与数据一致）

# 环节字段定义（货代负责环节：开船-到港、到港-提柜、提柜-签收）
forwarder_stage_cols = [
    "开船-到港",
    "到港-提柜",
    "提柜-签收"
]
warehouse_stage_col = "签收-完成上架"  # 仓库负责的环节（单独列）
all_stage_cols = forwarder_stage_cols + [warehouse_stage_col]  # 所有环节
signoff_stage = "提柜-签收"  # 重点细分区域的环节

# 核心规则：区域正常标准（自动适配以星转火车）
# 常规物流（非以星转火车）标准
NORMAL_REGION_THRESHOLD = {
    "美西": 6,  # 美西≤6天正常
    "美中": 10,  # 美中≤10天正常
    "美东": 11,  # 美东≤11天正常
    "未知区域": 6  # 无区域信息时默认阈值
}
# 以星转火车 专属规则（仅美东≤4天）
YIXING_SPECIAL_NAME = "以星转火车"
YIXING_REGION_THRESHOLD = {
    "美东": 4,
    "未知区域": 4  # 以星转火车若出现未知区域，仍按4天标准
}

# 1.1 基础字段清洗（统一格式，避免筛选错误）
df_current[main_delay_col] = df_current[main_delay_col].fillna("未知").apply(
    lambda x: x.strip() if isinstance(x, str) else "未知")
df_current[forwarder_delay_col] = df_current[forwarder_delay_col].fillna("未知").apply(
    lambda x: x.strip() if isinstance(x, str) else "未知")
df_current[warehouse_delay_col] = df_current[warehouse_delay_col].fillna("未知").apply(
    lambda x: x.strip() if isinstance(x, str) else "未知")
# 区域字段清洗（统一名称，匹配阈值字典）
df_current[region_col] = df_current[region_col].fillna("未知区域").apply(
    lambda x: x.strip() if isinstance(x, str) else "未知区域")
# 区域名称校准（确保与阈值字典匹配，如数据中是“美国东部”自动转为“美东”）
df_current[region_col] = df_current[region_col].replace({
    "美国东部": "美东",
    "美国西部": "美西",
    "美国中部": "美中",
    "东部": "美东",
    "西部": "美西",
    "中部": "美中"
})
# 物流方式字段清洗
df_current[ship_method_col] = df_current[ship_method_col].fillna("其他").apply(
    lambda x: x.strip() if isinstance(x, str) else "其他")

# 1.2 环节字段数值化（确保均值计算准确）
for col in all_stage_cols:
    df_current[col] = pd.to_numeric(df_current[col], errors="coerce").fillna(0.0)

# --------------------------
# 2. 严格按业务逻辑筛选数据集
# --------------------------
# 2.1 正常订单集：总状态=提前/准时
df_normal = df_current[df_current[main_delay_col] == "提前/准时"].copy()
# 2.2 货代延期订单集：总状态=延期 + 货代状态=延期
df_forwarder_delay = df_current[
    (df_current[main_delay_col] == "延期") &
    (df_current[forwarder_delay_col] == "延期")
    ].copy()
# 2.3 仓库延期订单集：总状态=延期 + 仓库状态=延期
df_warehouse_delay = df_current[
    (df_current[main_delay_col] == "延期") &
    (df_current[warehouse_delay_col] == "延期")
    ].copy()
# 2.4 总延期订单数（用于占比计算）
df_total_delay = df_current[df_current[main_delay_col] == "延期"].copy()
total_delay = len(df_total_delay)
total_normal = len(df_normal)
total_current = len(df_current)

# --------------------------
# 3. 无延期订单时的展示
# --------------------------
if total_delay == 0:
    st.success("✅ 本月无延期订单，各物流环节时效均符合预期！")
    # 仅展示正常订单的各环节均值（按区域+物流方式细分，含标准标注）
    st.markdown("### 📈 各环节耗时均值（仅正常订单，含物流标准）")
    # 按物流方式+区域分组计算正常订单各环节均值
    normal_mean_by_method_region = df_normal.groupby([ship_method_col, region_col])[all_stage_cols].mean().round(
        2).reset_index()
    for _, row in normal_mean_by_method_region.iterrows():
        method = row[ship_method_col]
        region = row[region_col]
        # 确定当前物流方式+区域的标准
        if method == YIXING_SPECIAL_NAME:
            signoff_std = YIXING_REGION_THRESHOLD.get(region, 4)
            method_prefix = "🚆"
        else:
            signoff_std = NORMAL_REGION_THRESHOLD.get(region, 6)
            method_prefix = "🚛"
        # 展示该物流方式+区域的均值
        st.markdown(f"#### {method_prefix} {method} - {region}")
        st.markdown(f"- **{signoff_stage}**：{float(row[signoff_stage])} 天（物流标准≤{signoff_std}天）")
        # 展示其他货代环节
        for stage in forwarder_stage_cols:
            if stage != signoff_stage:
                st.markdown(f"- **{stage}**：{float(row[stage])} 天")
        # 展示仓库环节
        st.markdown(f"- **{warehouse_stage_col}**：{float(row[warehouse_stage_col])} 天（标准≤3天）")
else:
    # --------------------------
    # 4. 统计核心数据（含物流方式+区域细分）
    # --------------------------
    forwarder_count = int(len(df_forwarder_delay))
    warehouse_count = int(len(df_warehouse_delay))

    # 计算占比（纯Python原生计算，防错）
    forwarder_pct = round((forwarder_count / total_delay) * 100, 1) if total_delay > 0 else 0.0
    warehouse_pct = round((warehouse_count / total_delay) * 100, 1) if total_delay > 0 else 0.0
    normal_pct = round((total_normal / total_current) * 100, 1) if total_current > 0 else 0.0
    delay_pct = round((total_delay / total_current) * 100, 1) if total_current > 0 else 0.0

    # 重点统计：提柜-签收环节（按物流方式+区域细分）
    # 筛选提柜-签收环节有数据的货代延期订单
    df_forwarder_signoff = df_forwarder_delay[df_forwarder_delay[signoff_stage] > 0].copy()
    # 按物流方式+区域分组统计
    signoff_stats = []
    if not df_forwarder_signoff.empty:
        for method in df_forwarder_signoff[ship_method_col].unique():
            df_method = df_forwarder_signoff[df_forwarder_signoff[ship_method_col] == method]
            for region in df_method[region_col].unique():
                df_region = df_method[df_method[region_col] == region]
                total_region = len(df_region)
                if total_region == 0:
                    continue
                # 确定当前物流方式+区域的正常标准
                if method == YIXING_SPECIAL_NAME:
                    std = YIXING_REGION_THRESHOLD.get(region, 4)
                else:
                    std = NORMAL_REGION_THRESHOLD.get(region, 6)
                # 计算该组的核心指标
                avg_days = round(df_region[signoff_stage].mean(), 2)
                max_days = round(df_region[signoff_stage].max(), 2)
                # 统计超时情况（按物流标准判断）
                over_threshold = len(df_region[df_region[signoff_stage] > std])
                over_rate = round((over_threshold / total_region) * 100, 1) if total_region > 0 else 0.0
                over_days = round(avg_days - std, 1) if std != 999 else None
                # 加入统计结果
                signoff_stats.append({
                    "物流方式": method,
                    "区域": region,
                    "延期订单数": total_region,
                    "物流标准（提柜-签收）": f"≤{std}天",
                    "平均耗时": avg_days,
                    "最大耗时": max_days,
                    "超时订单数": over_threshold,
                    "超时率": f"{over_rate}%",
                    "超时时长（平均）": f"{over_days}天" if over_days is not None else "无标准"
                })
    # 转为DataFrame用于展示
    signoff_stats_df = pd.DataFrame(signoff_stats)

    # --------------------------
    # 5. 基础数据汇总（含物流标准说明）
    # --------------------------
    st.markdown(f"""
        ### 📊 基础数据
        - 当月总订单数：{total_current} 单
        - 正常订单数：{total_normal} 单（占比 {normal_pct}%）
        - 延期订单数：{total_delay} 单（占比 {delay_pct}%）
        - 货代原因延期：{forwarder_count} 单（占延期订单的 {forwarder_pct}%）
        - 仓库原因延期：{warehouse_count} 单（占延期订单的 {warehouse_pct}%）

        #### 📌 提柜-签收环节物流标准
        - 常规物流：美西≤6天 | 美中≤10天 | 美东≤11天
        - 以星转火车（专属）：美东≤4天

        #### 📌 仓库环节物流标准
        - 签收-完成上架：≤3天
        """)

    # --------------------------
    # 6. 提柜-签收环节细分统计（物流方式+区域，统一表格展示）
    # --------------------------
    # --------------------------
    # 6. 提柜-签收环节延期细分统计（物流方式+区域）
    # 【已修复：只统计真正超时的订单】
    # --------------------------
    st.markdown("### 🗺️ 提柜-签收环节延期细分统计（物流方式+区域）")

    # 只统计【真正超时】的订单（货代延期 + 大于区域标准天数）
    df_real_overdue = []
    for idx, row in df_forwarder_delay.iterrows():
        method = row[ship_method_col]
        region = row[region_col]
        days = row[signoff_stage]

        # 获取当前标准
        if method == YIXING_SPECIAL_NAME:
            std = YIXING_REGION_THRESHOLD.get(region, 4)
        else:
            std = NORMAL_REGION_THRESHOLD.get(region, 6)

        # 只保留真正超时
        if days > std:
            df_real_overdue.append(row)

    df_real_overdue = pd.DataFrame(df_real_overdue)

    # 开始分组统计
    signoff_stats = []
    if not df_real_overdue.empty:
        for method in df_real_overdue[ship_method_col].unique():
            df_method = df_real_overdue[df_real_overdue[ship_method_col] == method]
            for region in df_method[region_col].unique():
                df_region = df_method[df_method[region_col] == region]
                total_region = len(df_region)
                if total_region == 0:
                    continue

                if method == YIXING_SPECIAL_NAME:
                    std = YIXING_REGION_THRESHOLD.get(region, 4)
                else:
                    std = NORMAL_REGION_THRESHOLD.get(region, 6)

                avg_days = round(df_region[signoff_stage].mean(), 2)
                max_days = round(df_region[signoff_stage].max(), 2)
                over_threshold = len(df_region[df_region[signoff_stage] > std])
                over_rate = round((over_threshold / total_region) * 100, 1) if total_region > 0 else 0.0
                over_days = round(avg_days - std, 1)

                signoff_stats.append({
                    "物流方式": method,
                    "区域": region,
                    "延期订单数": total_region,  # 现在这个 = 真正超时数
                    "物流标准（提柜-签收）": f"≤{std}天",
                    "平均耗时": avg_days,
                    "最大耗时": max_days,
                    "超时订单数": over_threshold,
                    "超时率": f"{over_rate}%",
                    "超时时长（平均）": f"{over_days}天"
                })

    signoff_stats_df = pd.DataFrame(signoff_stats)

    if not signoff_stats_df.empty:
        st.dataframe(
            signoff_stats_df,
            use_container_width=True,
            column_config={
                "物流方式": st.column_config.TextColumn("物流方式"),
                "区域": st.column_config.TextColumn("区域"),
                "延期订单数": st.column_config.NumberColumn("超时订单数（真正超时）"),
                "物流标准（提柜-签收）": st.column_config.TextColumn("物流标准"),
                "平均耗时": st.column_config.NumberColumn("平均耗时（天）", format="%.2f"),
                "最大耗时": st.column_config.NumberColumn("最大耗时（天）", format="%.2f"),
                "超时订单数": st.column_config.NumberColumn("超时订单数"),
                "超时率": st.column_config.TextColumn("超时率"),
                "超时时长（平均）": st.column_config.TextColumn("超时时长（平均）")
            }
        )
    else:
        st.markdown("- 暂无真正超时数据")

    # --------------------------
    # 7. 各环节耗时均值对比（正常 vs 延期，按物流方式+区域）
    # --------------------------
    st.markdown("### 📈 各环节耗时均值对比（正常 vs 延期）")
    # 预计算正常订单的各环节均值（按物流方式+区域）
    normal_mean_by_method_region = df_normal.groupby([ship_method_col, region_col])[all_stage_cols].mean().round(2)
    # 预计算货代延期订单的各环节均值（按物流方式+区域）
    forwarder_delay_mean_by_method_region = df_forwarder_delay.groupby([ship_method_col, region_col])[
        forwarder_stage_cols].mean().round(2) if forwarder_count > 0 else None
    warehouse_delay_mean = df_warehouse_delay[warehouse_stage_col].mean().round(2) if warehouse_count > 0 else None
    abnormal_threshold_days = 3  # 其他环节超时判断阈值
    WAREHOUSE_STANDARD = 3  # 仓库标准

    # 7.1 货代环节展示（按物流方式+区域分组）
    st.markdown("#### 🔹 货代负责环节（开船-到港 → 提柜-签收）")
    if forwarder_count > 0 and forwarder_delay_mean_by_method_region is not None:
        # 遍历所有有延期数据的物流方式+区域组合
        for (method, region), delay_means in forwarder_delay_mean_by_method_region.iterrows():
            # 获取该物流方式+区域的正常均值（无则用全局正常均值）
            if (method, region) in normal_mean_by_method_region.index:
                normal_means = normal_mean_by_method_region.loc[(method, region)]
            else:
                normal_means = df_normal[forwarder_stage_cols].mean().round(2)
            # 确定物流方式前缀和提柜-签收标准
            if method == YIXING_SPECIAL_NAME:
                method_prefix = "🚆"
                signoff_std = YIXING_REGION_THRESHOLD.get(region, 4)
            else:
                method_prefix = "🚛"
                signoff_std = NORMAL_REGION_THRESHOLD.get(region, 6)
            # 展示该物流方式+区域的对比数据
            st.markdown(f"##### {method_prefix} {method} - {region}")
            for stage in forwarder_stage_cols:
                n_mean = float(normal_means[stage]) if stage in normal_means.index else 0.0
                d_mean = float(delay_means[stage]) if stage in delay_means.index else 0.0
                diff_days = round(d_mean - n_mean, 1)  # 与正常均值的差值

                # 提柜-签收环节：按物流标准判断，其他环节按差值判断
                if stage == signoff_stage:
                    # 提柜-签收：用物流标准判断
                    std_diff = round(d_mean - signoff_std, 1)
                    if std_diff >= 1:
                        st.markdown(
                            f"- **{stage}**：正常标准≤{signoff_std}天 | 延期均值 **:red[{d_mean} 天]** | **:red[超时 {std_diff} 天]**")
                    elif std_diff < 0:
                        faster_days = round(abs(std_diff), 1)
                        st.markdown(
                            f"- **{stage}**：正常标准≤{signoff_std}天 | 延期均值 {d_mean} 天 | ✅ 符合标准（快于标准 {faster_days} 天）")
                    else:
                        st.markdown(f"- **{stage}**：正常标准≤{signoff_std}天 | 延期均值 {d_mean} 天 | ✅ 符合标准")
                else:
                    # 其他货代环节：用与正常均值的差值判断
                    if diff_days >= abnormal_threshold_days:
                        st.markdown(
                            f"- **{stage}**：正常均值 {n_mean} 天 | 延期均值 **:red[{d_mean} 天]** | **:red[严重超时，慢了 {diff_days} 天]**")
                    elif diff_days > 0:
                        st.markdown(f"- **{stage}**：正常均值 {n_mean} 天 | 延期均值 {d_mean} 天 | 慢了 {diff_days} 天")
                    else:
                        faster_days = round(abs(diff_days), 1)
                        st.markdown(
                            f"- **{stage}**：正常均值 {n_mean} 天 | 延期均值 {d_mean} 天 | ✅ 比正常还快 {faster_days} 天")
    else:
        st.markdown("- 无货代延期订单数据")

    # 7.2 仓库环节展示（整体）- 已修改：与3天标准对比
    st.markdown("#### 🔹 仓库负责环节（签收-完成上架）")
    n_mean = df_normal[warehouse_stage_col].mean().round(2) if len(df_normal) > 0 else 0.0
    if warehouse_count > 0 and warehouse_delay_mean is not None:
        d_mean = float(warehouse_delay_mean)
        std_diff = round(d_mean - WAREHOUSE_STANDARD, 1)

        if std_diff >= 1:
            st.markdown(
                f"- **{warehouse_stage_col}**：标准≤{WAREHOUSE_STANDARD}天 | 延期均值 **:red[{d_mean} 天]** | **:red[超时 {std_diff} 天]**")
        elif std_diff < 0:
            faster_days = round(abs(std_diff), 1)
            st.markdown(
                f"- **{warehouse_stage_col}**：标准≤{WAREHOUSE_STANDARD}天 | 延期均值 {d_mean} 天 | ✅ 符合标准（快于标准 {faster_days} 天）")
        else:
            st.markdown(
                f"- **{warehouse_stage_col}**：标准≤{WAREHOUSE_STANDARD}天 | 延期均值 {d_mean} 天 | ✅ 符合标准")
    else:
        st.markdown(
            f"- **{warehouse_stage_col}**：标准≤{WAREHOUSE_STANDARD}天 | 无仓库延期订单")

    # --------------------------
    # 8. 针对性优化建议
    # --------------------------
    st.markdown("### 💡 优化建议")
    suggestions = []
    # 货代环节建议（含物流方式+区域）
    if not signoff_stats_df.empty:
        for _, row in signoff_stats_df.iterrows():
            method = row["物流方式"]
            region = row["区域"]
            over_days = row["超时时长（平均）"]
            over_rate = row["超时率"]
            if over_days and isinstance(over_days, str) and over_days.replace("天", "").strip() != "" and float(
                    over_days.replace("天", "")) >= 1:
                suggestions.append(
                    f"⚠️ {method} - {region}：提柜-签收环节超时{over_days}，超时率{over_rate}，需按标准（{row['物流标准（提柜-签收）']}）优化。")
    # 其他货代环节建议
    if forwarder_count > 0 and forwarder_delay_mean_by_method_region is not None:
        for (method, region), delay_means in forwarder_delay_mean_by_method_region.iterrows():
            if (method, region) in normal_mean_by_method_region.index:
                normal_means = normal_mean_by_method_region.loc[(method, region)]
            else:
                normal_means = df_normal[forwarder_stage_cols].mean().round(2)
            for stage in forwarder_stage_cols:
                if stage == signoff_stage:
                    continue
                n_mean = float(normal_means[stage]) if stage in normal_means.index else 0.0
                d_mean = float(delay_means[stage]) if stage in delay_means.index else 0.0
                diff_days = round(d_mean - n_mean, 1)
                if diff_days >= abnormal_threshold_days:
                    suggestions.append(f"⚠️ {method} - {region}：{stage}环节严重超时{diff_days}天，需重点优化。")
    # 仓库环节建议 - 已修改：按3天标准判断
    if warehouse_count > 0 and warehouse_delay_mean is not None:
        d_mean = float(warehouse_delay_mean)
        std_diff = round(d_mean - WAREHOUSE_STANDARD, 1)
        if std_diff >= abnormal_threshold_days:
            suggestions.append(
                f"⚠️ 仓库环节：{warehouse_stage_col}标准≤{WAREHOUSE_STANDARD}天，实际延期均值{d_mean}天，严重超时{std_diff}天，需紧急优化仓内操作流程。")
    # 无异常时的正向建议
    if not suggestions:
        suggestions.append("💡 各环节均符合物流标准或无严重超时，整体表现稳定。")
    # 展示建议
    for idx, suggestion in enumerate(suggestions, 1):
        st.markdown(f"{idx}. {suggestion}")

# ---------------------- 货代准时情况分析（独立版：发货-签收环节，无仓库关联） ----------------------
st.markdown("### 货代准时情况分析（开船-签收环节）")

# ========== 列名映射字典（根据你的实际列名修改！）==========
COLUMN_MAPPING = {
    "货代列名": "货代",  # 改成你数据中实际的货代列名
    "货代提前延期列名": "提前/延期（货代）",  # 改成你实际的货代提前/延期列名
    "货代时效差值列名": "预计物流时效-实际物流时效差值（货代）"  # 改成你实际的货代时效差值列名
}

# 筛选有效数据（仅保留有货代信息的行）
df_freight_valid = df_current[
    df_current[COLUMN_MAPPING["货代列名"]].notna() &
    (df_current[COLUMN_MAPPING["货代列名"]] != "")
    ].copy()

if len(df_freight_valid) == 0:
    st.warning(f"{selected_month}月暂无货代相关数据")
else:
    # ===== 列名校验：避免KeyError =====
    required_cols = [COLUMN_MAPPING["货代列名"], COLUMN_MAPPING["货代提前延期列名"],
                     COLUMN_MAPPING["货代时效差值列名"]]
    missing_cols = [col for col in required_cols if col not in df_freight_valid.columns]
    if missing_cols:
        st.error(f"缺少货代分析必要列：{missing_cols}，请检查列名是否正确！")
        st.stop()

    # ===== 1. 货代核心指标计算 =====
    freight_stats = df_freight_valid.groupby(COLUMN_MAPPING["货代列名"]).agg(
        总订单数=(COLUMN_MAPPING["货代列名"], "count"),
        提前准时订单数=(COLUMN_MAPPING["货代提前延期列名"], lambda x: len(x[x == "提前/准时"])),
        延期订单数=(COLUMN_MAPPING["货代提前延期列名"], lambda x: len(x[x == "延期"])),
        时效差值均值=(COLUMN_MAPPING["货代时效差值列名"], "mean"),
        最大延期天数=(COLUMN_MAPPING["货代时效差值列名"], lambda x: min(x.min(), 0)),  # 仅取延期负数
        最大提前天数=(COLUMN_MAPPING["货代时效差值列名"], lambda x: max(x.max(), 0))  # 仅取提前正数
    ).reset_index()

    # 重命名货代列，方便后续使用
    freight_stats.rename(columns={COLUMN_MAPPING["货代列名"]: "货代"}, inplace=True)

    # 计算衍生指标（核心）- 统一保留2位小数
    freight_stats["准时率(%)"] = round(freight_stats["提前准时订单数"] / freight_stats["总订单数"] * 100, 2)
    freight_stats["订单量占比(%)"] = round(freight_stats["总订单数"] / len(df_freight_valid) * 100, 2)
    freight_stats["延期率(%)"] = round(100 - freight_stats["准时率(%)"], 2)

    # ===== 2. 计算上月货代准时率（调整为“准时率差值”）=====
    prev_freight_valid = df_prev[
        df_prev[COLUMN_MAPPING["货代列名"]].notna() &
        (df_prev[COLUMN_MAPPING["货代列名"]] != "")
        ].copy() if not df_prev.empty else pd.DataFrame()

    if len(prev_freight_valid) > 0:
        prev_freight_stats = prev_freight_valid.groupby(COLUMN_MAPPING["货代列名"]).agg(
            上月提前准时订单数=(COLUMN_MAPPING["货代提前延期列名"], lambda x: len(x[x == "提前/准时"])),
            上月总订单数=(COLUMN_MAPPING["货代列名"], "count")
        ).reset_index()
        prev_freight_stats.rename(columns={COLUMN_MAPPING["货代列名"]: "货代"}, inplace=True)
        prev_freight_stats["上月准时率(%)"] = round(
            prev_freight_stats["上月提前准时订单数"] / prev_freight_stats["上月总订单数"] * 100, 2)
        # 合并本月&上月数据
        freight_stats = pd.merge(freight_stats, prev_freight_stats[["货代", "上月准时率(%)"]], on="货代",
                                 how="left")
        freight_stats["准时率差值(%)"] = round(
            freight_stats["准时率(%)"] - freight_stats["上月准时率(%)"].fillna(0), 2)
    else:
        freight_stats["上月准时率(%)"] = None  # 无数据时显示空
        freight_stats["准时率差值(%)"] = None

    # ===== 3. 可视化展示（双轴图 + 所有货代迷你卡片）=====
    col1, col2 = st.columns([2, 1])
    # 3.1 左：货代订单量占比 + 准时率 双轴图（核心趋势）
    with col1:
        import plotly.graph_objects as go

        fig = go.Figure()
        # 订单量占比-柱状图
        fig.add_trace(go.Bar(
            x=freight_stats["货代"],
            y=freight_stats["订单量占比(%)"],
            name="订单量占比(%)",
            yaxis="y1",
            marker_color="#4299e1",
            opacity=0.8,
            text=freight_stats["订单量占比(%)"].apply(lambda x: f"{x:.2f}%"),  # 显示2位小数
            textposition="auto"
        ))
        # 准时率-折线图
        fig.add_trace(go.Scatter(
            x=freight_stats["货代"],
            y=freight_stats["准时率(%)"],
            name="准时率(%)",
            yaxis="y2",
            marker_color="#e53e3e",
            mode="lines+markers+text",
            line=dict(width=3),
            marker=dict(size=8),
            text=freight_stats["准时率(%)"].apply(lambda x: f"{x:.2f}%"),  # 显示2位小数
            textposition="top center"
        ))
        # 图表样式配置
        fig.update_layout(
            title=f"{selected_month} 货代订单量占比 & 准时率对比",
            yaxis=dict(title="订单量占比(%)", side="left", range=[0, 100], color="#4299e1"),
            yaxis2=dict(title="准时率(%)", side="right", overlaying="y", range=[0, 100], color="#e53e3e"),
            xaxis=dict(title="货代名称", tickangle=0),
            legend=dict(x=0.02, y=0.98, bordercolor="#eee", borderwidth=1),
            height=400,
            plot_bgcolor="#ffffff"
        )
        st.plotly_chart(fig, use_container_width=True)

    # 3.2 右：所有货代核心表现迷你卡片（适配3-4个货代，颜色分级）
    with col2:
        st.markdown("#### 货代核心表现")
        for _, row in freight_stats.iterrows():
            # 准时率颜色分级：优质≥90% | 合格80-90% | 异常<80%
            if row["准时率(%)"] >= 90:
                card_bg = "#f0f8f0"
                rate_color = "#2e7d32"
                tag = "优质"
            elif row["准时率(%)"] >= 80:
                card_bg = "#fff8e1"
                rate_color = "#ff9800"
                tag = "合格"
            else:
                card_bg = "#fff0f0"
                rate_color = "#c62828"
                tag = "异常"
            # 准时率差值样式
            diff_val = row["准时率差值(%)"]
            if pd.notna(diff_val):
                if diff_val > 0:
                    diff_text = f"↑{diff_val:.2f}%"
                    diff_color = "#2e7d32"
                elif diff_val < 0:
                    diff_text = f"↓{abs(diff_val):.2f}%"
                    diff_color = "#c62828"
                else:
                    diff_text = "—"
                    diff_color = "#757575"
                # 上月准时率显示（无数据时隐藏）
                prev_rate_text = f"（上月{row['上月准时率(%)']:.2f}%）" if pd.notna(row["上月准时率(%)"]) else ""
            else:
                diff_text = "—"
                diff_color = "#757575"
                prev_rate_text = ""
            # 生成货代迷你卡片
            st.markdown(f"""
            <div style='background-color: {card_bg}; padding: 12px; border-radius: 8px; margin-bottom: 12px; border-left: 4px solid {rate_color};'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <p style='margin: 0; font-weight: bold; font-size: 16px;'>{row['货代']}</p>
                    <span style='font-size: 12px; padding: 2px 6px; border-radius: 12px; background: {rate_color}; color: white;'>{tag}</span>
                </div>
                <p style='margin: 6px 0 0; font-size: 14px;'>
                    准时率：<span style='color: {rate_color}; font-weight: bold; font-size: 18px;'>{row['准时率(%)']:.2f}%</span>
                </p>
                <p style='margin: 4px 0 0; font-size: 12px; color: #666;'>订单：{row['总订单数']}单（{row['订单量占比(%)']:.2f}%）</p>
                <p style='margin: 4px 0 0; font-size: 12px; color: #666;'>差值：<span style='color: {diff_color}; font-weight: bold;'>{diff_text}</span> {prev_rate_text}</p>
                <p style='margin: 4px 0 0; font-size: 12px; color: #666;'>最大延期：{abs(row['最大延期天数'])}天</p>
            </div>
            """, unsafe_allow_html=True)

    # ===== 4. 货代详细时效指标表（带上月差值对比+兼容Streamlit样式）=====
    st.markdown("#### 货代详细时效指标表")

    # ---------------------- 计算上月货代订单类指标 ----------------------
    prev_order_stats = pd.DataFrame()
    if len(prev_freight_valid) > 0:
        prev_order_stats = prev_freight_valid.groupby(COLUMN_MAPPING["货代列名"]).agg(
            上月总订单数=(COLUMN_MAPPING["货代列名"], "count"),
            上月提前准时订单数=(COLUMN_MAPPING["货代提前延期列名"], lambda x: len(x[x == "提前/准时"])),
            上月延期订单数=(COLUMN_MAPPING["货代提前延期列名"], lambda x: len(x[x == "延期"]))
        ).reset_index()
        prev_order_stats.rename(columns={COLUMN_MAPPING["货代列名"]: "货代"}, inplace=True)
        freight_stats = pd.merge(freight_stats, prev_order_stats, on="货代", how="left")
    else:
        freight_stats["上月总订单数"] = None
        freight_stats["上月提前准时订单数"] = None
        freight_stats["上月延期订单数"] = None

    # ---------------------- 格式化订单数列（纯文本兼容版） ----------------------
    display_cols = [
        "货代", "总订单数", "订单量占比(%)", "提前准时订单数", "延期订单数", "延期率(%)",
        "准时率(%)", "上月准时率(%)", "准时率差值(%)",
        "时效差值均值", "最大提前天数", "最大延期天数"
    ]
    freight_display = freight_stats[display_cols].copy()


    # 自定义格式化函数（纯文本，用[]包裹上月信息，视觉区分）
    def format_order_col(current_val, prev_val):
        """
        纯文本格式化：本月数 [差值 上月数]
        - 上月信息用[]包裹，视觉上弱化
        - 差值带正负号，无上月数据时只显示本月数
        """
        if pd.notna(prev_val):
            diff = current_val - prev_val
            diff_sign = "+" if diff > 0 else "" if diff == 0 else "-"
            diff_abs = abs(diff)
            # 用[]包裹上月信息，通过空格/符号实现视觉层次
            return f"{current_val}  [{diff_sign}{diff_abs} 上月{prev_val}]"
        else:
            return f"{current_val}"


    # 应用格式化（直接操作freight_stats的原始数值）
    freight_display["总订单数"] = freight_stats.apply(
        lambda x: format_order_col(x["总订单数"], x["上月总订单数"]), axis=1
    )
    freight_display["提前准时订单数"] = freight_stats.apply(
        lambda x: format_order_col(x["提前准时订单数"], x["上月提前准时订单数"]), axis=1
    )
    freight_display["延期订单数"] = freight_stats.apply(
        lambda x: format_order_col(x["延期订单数"], x["上月延期订单数"]), axis=1
    )

    # 其他数值格式化
    freight_display["时效差值均值"] = freight_display["时效差值均值"].apply(lambda x: f"{x:.2f}")
    freight_display["最大延期天数"] = freight_display["最大延期天数"].apply(
        lambda x: f"{abs(x)}天" if x < 0 else "0天")
    freight_display["最大提前天数"] = freight_display["最大提前天数"].apply(lambda x: f"{x}天" if x > 0 else "0天")

    # 百分比列格式化
    for col in ["订单量占比(%)", "延期率(%)", "准时率(%)", "上月准时率(%)", "准时率差值(%)"]:
        freight_display[col] = freight_display[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "")


    # ---------------------- 表格高亮规则 ----------------------
    def highlight_freight(row):
        styles = [""] * len(row)
        # 准时率差值为负标红
        if row["准时率差值(%)"] and isinstance(row["准时率差值(%)"], str) and float(
                row["准时率差值(%)"].replace("%", "")) < 0:
            styles[display_cols.index(
                "准时率差值(%)")] = "background-color: #fff5f5; color: #c62828; font-weight: bold;"
        # 延期率>20%标红
        if row["延期率(%)"] and isinstance(row["延期率(%)"], str) and float(row["延期率(%)"].replace("%", "")) > 20:
            styles[
                display_cols.index("延期率(%)")] = "background-color: #fff5f5; color: #c62828; font-weight: bold;"
        # 准时率<80%标红
        if row["准时率(%)"] and isinstance(row["准时率(%)"], str) and float(row["准时率(%)"].replace("%", "")) < 80:
            styles[
                display_cols.index("准时率(%)")] = "background-color: #fff5f5; color: #c62828; font-weight: bold;"
        return styles


    # ---------------------- 展示表格（移除unsafe_allow_html，兼容Streamlit） ----------------------
    styled_table = freight_display.style.apply(highlight_freight, axis=1)
    st.dataframe(
        styled_table,
        use_container_width=True,
        hide_index=True  # 移除unsafe_allow_html参数，避免TypeError
    )

    # ===== 5. 数据下载功能 =====
    # 下载数据保留原始数值（非格式化）
    download_data = freight_stats.copy()
    csv_data = download_data.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 下载货代分析完整数据",
        data=csv_data,
        file_name=f"{selected_month}_货代准时率分析数据.csv",
        mime="text/csv",
        key="freight_data_download"
    )
# ===== 6. 货代当月表现总结文字（修复重复问题） =====
st.markdown("### 货代当月表现总结")

# 每次运行都重新创建空列表（避免追加重复内容）
summary_paragraphs = []
for _, row in freight_stats.iterrows():
    # 基础信息提取
    freight_name = row["货代"]
    order_count = row["总订单数"]
    order_ratio = row["订单量占比(%)"]
    on_time_rate = row["准时率(%)"]
    max_delay = abs(row["最大延期天数"])
    prev_rate = row["上月准时率(%)"]
    diff_val = row["准时率差值(%)"]

    # 评级判断+颜色
    if on_time_rate >= 90:
        level_tag = "【优质】"
        level_color = "#2e7d32"
        level_desc = "准时率表现优秀"
    elif on_time_rate >= 80:
        level_tag = "【合格】"
        level_color = "#ff9800"
        level_desc = "准时率表现达标"
    else:
        level_tag = "【异常】"
        level_color = "#c62828"
        level_desc = "准时率表现不达标，需重点关注"

    # 差值描述（修复无上月数据）
    if pd.notna(prev_rate):
        if diff_val > 0:
            diff_desc = f"较上月提升{diff_val:.2f}个百分点"
        elif diff_val < 0:
            diff_desc = f"较上月下降{abs(diff_val):.2f}个百分点"
        else:
            diff_desc = "与上月持平"
    else:
        diff_desc = "无上月数据对比"

    # 延期描述
    delay_desc = "全程无延期订单" if max_delay == 0 else f"最大延期天数为{max_delay}天"

    # 生成单条总结（精简HTML，避免冗余标签）
    summary = f"""
    - <b>{freight_name} <span style='color:{level_color};'>{level_tag}</span></b>：
      本月承接{order_count}单（占总订单量{order_ratio:.2f}%），{level_desc}，准时率为{on_time_rate:.2f}%，{diff_desc}，{delay_desc}。
    """
    summary_paragraphs.append(summary)

# 清空重复内容后，只渲染一次
st.markdown("\n".join(summary_paragraphs), unsafe_allow_html=True)
# ---------------------- ⑤ 当月仓库准时情况 ----------------------
# ---------------------- 仓库准时情况分析（签收-完成上架环节） ----------------------
st.markdown("### 仓库准时情况分析（签收-完成上架环节）")

# ========== 列名映射字典（根据你的实际列名修改！）==========
WAREHOUSE_COLUMN_MAPPING = {
    "仓库列名": "仓库",
    "区域列名": "区域",        # 确保你的数据有这列：美东/美中/美西
    "签收上架时长列名": "签收-完成上架",
}

# ========== 固定区域顺序（强制：美西 → 美中 → 美东）==========
REGION_ORDER = ["美西", "美中", "美东"]

# 筛选有效数据
df_warehouse_valid = df_current_FBA[
    (df_current_FBA[WAREHOUSE_COLUMN_MAPPING["仓库列名"]].notna() &
     (df_current_FBA[WAREHOUSE_COLUMN_MAPPING["仓库列名"]] != "")) &
    (df_current_FBA[WAREHOUSE_COLUMN_MAPPING["签收上架时长列名"]].notna()) &
    (df_current_FBA[WAREHOUSE_COLUMN_MAPPING["区域列名"]].notna())
].copy()

if len(df_warehouse_valid) == 0:
    st.warning(f"{selected_month}月暂无仓库相关数据")
else:
    # ===== 列名校验 =====
    required_cols = [
        WAREHOUSE_COLUMN_MAPPING["仓库列名"],
        WAREHOUSE_COLUMN_MAPPING["签收上架时长列名"],
        WAREHOUSE_COLUMN_MAPPING["区域列名"]
    ]
    missing_cols = [col for col in required_cols if col not in df_warehouse_valid.columns]
    if missing_cols:
        st.error(f"缺少必要列：{missing_cols}")
        st.stop()

    # 统一区域名称（避免脏数据）
    df_warehouse_valid[WAREHOUSE_COLUMN_MAPPING["区域列名"]] = (
        df_warehouse_valid[WAREHOUSE_COLUMN_MAPPING["区域列名"]]
        .astype(str)
        .str.strip()
        .replace({"East": "美东", "Mid": "美中", "West": "美西"})
    )

    # ===== 1. 核心计算 =====
    df_warehouse_valid["提前/延期（仓库）"] = df_warehouse_valid[
        WAREHOUSE_COLUMN_MAPPING["签收上架时长列名"]
    ].apply(lambda x: "提前/准时" if x <= 3 else "延期")

    # ===== 2. 仓库统计 =====
    warehouse_stats = df_warehouse_valid.groupby([
        WAREHOUSE_COLUMN_MAPPING["仓库列名"],
        WAREHOUSE_COLUMN_MAPPING["区域列名"]
    ]).agg(
        总订单数=(WAREHOUSE_COLUMN_MAPPING["仓库列名"], "count"),
        提前准时订单数=("提前/延期（仓库）", lambda x: len(x[x == "提前/准时"])),
        延期订单数=("提前/延期（仓库）", lambda x: len(x[x == "延期"])),
        签收上架时长均值=(WAREHOUSE_COLUMN_MAPPING["签收上架时长列名"], "mean"),
        签收上架时长中位数=(WAREHOUSE_COLUMN_MAPPING["签收上架时长列名"], "median"),
        最长上架时长=(WAREHOUSE_COLUMN_MAPPING["签收上架时长列名"], "max"),
        最短上架时长=(WAREHOUSE_COLUMN_MAPPING["签收上架时长列名"], "min"),
    ).reset_index()

    warehouse_stats.rename(columns={
        WAREHOUSE_COLUMN_MAPPING["仓库列名"]: "仓库",
        WAREHOUSE_COLUMN_MAPPING["区域列名"]: "区域"
    }, inplace=True)

    # 指标计算
    warehouse_stats["准时率(%)"] = round(warehouse_stats["提前准时订单数"] / warehouse_stats["总订单数"] * 100, 2)
    warehouse_stats["订单量占比(%)"] = round(warehouse_stats["总订单数"] / len(df_warehouse_valid) * 100, 2)
    warehouse_stats["延期率(%)"] = round(100 - warehouse_stats["准时率(%)"], 2)

    # ===== 3. 环比（上月）=====
    prev_warehouse_valid = df_prev[
        (df_prev[WAREHOUSE_COLUMN_MAPPING["仓库列名"]].notna()) &
        (df_prev[WAREHOUSE_COLUMN_MAPPING["签收上架时长列名"]].notna()) &
        (df_prev[WAREHOUSE_COLUMN_MAPPING["区域列名"]].notna())
    ].copy() if not df_prev.empty else pd.DataFrame()

    if not prev_warehouse_valid.empty:
        prev_warehouse_valid["提前/延期（仓库）"] = prev_warehouse_valid[
            WAREHOUSE_COLUMN_MAPPING["签收上架时长列名"]].apply(lambda x: "提前/准时" if x <= 3 else "延期")
        prev_warehouse_stats = prev_warehouse_valid.groupby([
            WAREHOUSE_COLUMN_MAPPING["仓库列名"],
            WAREHOUSE_COLUMN_MAPPING["区域列名"]
        ]).agg(
            上月总订单数=(WAREHOUSE_COLUMN_MAPPING["仓库列名"], "count"),
            上月提前准时订单数=("提前/延期（仓库）", lambda x: len(x[x == "提前/准时"])),
            上月延期订单数=("提前/延期（仓库）", lambda x: len(x[x == "延期"])),
        ).reset_index()
        prev_warehouse_stats.rename(columns={
            WAREHOUSE_COLUMN_MAPPING["仓库列名"]: "仓库",
            WAREHOUSE_COLUMN_MAPPING["区域列名"]: "区域"
        }, inplace=True)
        prev_warehouse_stats["上月准时率(%)"] = round(
            prev_warehouse_stats["上月提前准时订单数"] / prev_warehouse_stats["上月总订单数"] * 100, 2)
        warehouse_stats = pd.merge(warehouse_stats, prev_warehouse_stats, on=["仓库", "区域"], how="left")
        warehouse_stats["准时率差值(%)"] = round(warehouse_stats["准时率(%)"] - warehouse_stats["上月准时率(%)"].fillna(0), 2)
    else:
        warehouse_stats["上月准时率(%)"] = None
        warehouse_stats["准时率差值(%)"] = None
        warehouse_stats["上月总订单数"] = None
        warehouse_stats["上月提前准时订单数"] = None
        warehouse_stats["上月延期订单数"] = None

    # ===== 4. 排序规则：区域(美西→美中→美东) → 订单占比(降序) =====
    warehouse_stats["区域排序"] = warehouse_stats["区域"].map({v: i for i, v in enumerate(REGION_ORDER)})
    warehouse_stats = warehouse_stats.sort_values(
        by=["区域排序", "订单量占比(%)"], ascending=[True, False]
    ).reset_index(drop=True)

    # ===== 5. 分区域双轴图：美西 | 美中 | 美东 =====
    st.markdown("#### 各区域仓库订单占比 & 准时率")
    import plotly.graph_objects as go
    col_w, col_m, col_e = st.columns(3)

    for idx, region in enumerate(REGION_ORDER):
        df_region = warehouse_stats[warehouse_stats["区域"] == region]
        if df_region.empty:
            continue
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_region["仓库"], y=df_region["订单量占比(%)"], name="订单占比(%)", marker_color="#9f7aea", opacity=0.8))
        fig.add_trace(go.Scatter(x=df_region["仓库"], y=df_region["准时率(%)"], name="准时率(%)", mode="lines+markers", line=dict(width=3), marker=dict(size=6), marker_color="#38b2ac"))
        fig.update_layout(
            title=f"{region}", height=360,
            yaxis=dict(title="订单占比(%)", range=[0,100], color="#9f7aea"),
            yaxis2=dict(title="准时率(%)", overlaying="y", side="right", range=[0,100], color="#38b2ac"),
            xaxis=dict(tickangle=-45 if len(df_region) > 2 else 0),
            plot_bgcolor="white"
        )
        if idx == 0:
            col_w.plotly_chart(fig, use_container_width=True)
        elif idx == 1:
            col_m.plotly_chart(fig, use_container_width=True)
        else:
            col_e.plotly_chart(fig, use_container_width=True)

    # ===== 6. 分区域仓库卡片：美西 | 美中 | 美东 =====
    st.markdown("#### 各区域仓库表现")
    card_col_w, card_col_m, card_col_e = st.columns(3)
    for idx, region in enumerate(REGION_ORDER):
        df_region = warehouse_stats[warehouse_stats["区域"] == region]
        if df_region.empty:
            continue
        target_col = [card_col_w, card_col_m, card_col_e][idx]
        with target_col:
            st.markdown(f"##### {region}")
            for _, row in df_region.iterrows():
                rate = row["准时率(%)"]
                if rate >= 90:
                    bg, tc, tag = "#f0f8f0", "#2e7d32", "优质"
                elif rate >= 80:
                    bg, tc, tag = "#fff8e1", "#ff9800", "合格"
                else:
                    bg, tc, tag = "#fff0f0", "#c62828", "异常"
                diff = row["准时率差值(%)"]
                pdiff = f"↑{diff:.1f}%" if diff and diff > 0 else f"↓{abs(diff):.1f}%" if diff and diff < 0 else "—"

                # 修复：使用真实列名获取平均/最长时长
                avg_days = row.get("签收上架时长均值", 0)
                max_days = row.get("最长上架时长", 0)

                # 默认显示「当月准时率」（无需自动生成年月）
                rate_title = "当月准时率"

                st.markdown(f"""
                <div style='background:{bg};padding:10px;border-radius:8px;margin-bottom:8px;border-left:4px solid {tc};'>
                <div style='font-weight:bold;font-size:15px;'>{row['仓库']}</div>
                <div style='color:{tc};font-weight:bold;font-size:17px;margin:4px 0;'>{rate_title}：{rate:.1f}%</div>
                <div style='font-size:12px;color:#666;margin-bottom:3px;'>平均时长：{avg_days:.1f} 天</div>
                <div style='font-size:12px;color:#666;margin-bottom:3px;'>最长时长：{max_days:.1f} 天</div>
                <div style='font-size:12px;color:#666;'>订单：{row['总订单数']}单 | 占比 {row['订单量占比(%)']:.1f}%</div>
                <div style='font-size:12px;color:#666;'>环比：{pdiff}</div>
                </div>
                """, unsafe_allow_html=True)

    # ===== 7. 详细表格（带区域列）=====
    st.markdown("#### 仓库详细时效指标表")
    display_cols = [
        "区域", "仓库", "总订单数", "订单量占比(%)", "提前准时订单数", "延期订单数", "延期率(%)",
        "准时率(%)", "上月准时率(%)", "准时率差值(%)", "签收上架时长均值", "最短上架时长", "最长上架时长"
    ]
    warehouse_display = warehouse_stats[display_cols].copy()

    def fmt(x): return f"{x:.2f}" if pd.notna(x) else ""
    warehouse_display["签收上架时长均值"] = warehouse_display["签收上架时长均值"].astype(float).round(2).apply(fmt)
    warehouse_display["最短上架时长"] = warehouse_display["最短上架时长"].astype(float).round(1).apply(lambda x: f"{x:.1f}天")
    warehouse_display["最长上架时长"] = warehouse_display["最长上架时长"].astype(float).round(1).apply(lambda x: f"{x:.1f}天")

    st.dataframe(warehouse_display, use_container_width=True, hide_index=True)

    # ===== 8. 总结（带区域）=====
    # ===== 8. 总结（分三列：美东 | 美中 | 美西）=====
    st.markdown("### 仓库当月表现总结")
    col_east, col_mid, col_west = st.columns(3)

    # 按区域分组整理总结文字
    summary_by_region = {
        "美东": [],
        "美中": [],
        "美西": []
    }

    for _, row in warehouse_stats.iterrows():
        region = row["区域"]
        name = row["仓库"]
        orders = row["总订单数"]
        ratio = row["订单量占比(%)"]
        rate = row["准时率(%)"]
        diff = row["准时率差值(%)"]
        max_duration = row["最长上架时长"]

        # 评级描述
        if rate >= 90:
            level_desc = "表现优秀"
            level_color = "#2e7d32"
        elif rate >= 80:
            level_desc = "表现达标"
            level_color = "#ff9800"
        else:
            level_desc = "需重点关注"
            level_color = "#c62828"

        # 环比描述
        if pd.notna(diff):
            if diff > 0:
                diff_str = f"较上月提升{diff:.1f}个百分点"
            elif diff < 0:
                diff_str = f"较上月下降{abs(diff):.1f}个百分点"
            else:
                diff_str = "与上月持平"
        else:
            diff_str = "无上月数据对比"

        # 组装总结（带颜色）
        summary_item = f"""
        <div style='margin-bottom: 8px;'>
            <b>{name}</b>：<span style='color:{level_color};'>{level_desc}</span>，订单{orders}单（占比{ratio:.1f}%），准时率{rate:.1f}%，{diff_str}，最长上架时长{max_duration:.1f}天。
        </div>
        """
        summary_by_region[region].append(summary_item)

    # 三列渲染
    with col_east:
        st.markdown("#### 美东区域")
        if summary_by_region["美东"]:
            st.markdown("\n".join(summary_by_region["美东"]), unsafe_allow_html=True)
        else:
            st.markdown("暂无美东区域仓库数据")

    with col_mid:
        st.markdown("#### 美中区域")
        if summary_by_region["美中"]:
            st.markdown("\n".join(summary_by_region["美中"]), unsafe_allow_html=True)
        else:
            st.markdown("暂无美中区域仓库数据")

    with col_west:
        st.markdown("#### 美西区域")
        if summary_by_region["美西"]:
            st.markdown("\n".join(summary_by_region["美西"]), unsafe_allow_html=True)
        else:
            st.markdown("暂无美西区域仓库数据")

    # 下载
    csv_data = warehouse_stats.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("📥 下载仓库分析数据", csv_data, f"{selected_month}_仓库分析.csv", "text/csv")

# ======================================================================================
# ======================================================================================
# 📦 物流环节时效分析（耗时分布 + 准时率时效）【完整四合一 · 无报错最终版】
# ======================================================================================
st.divider()
st.subheader("📦 物流环节时效分析（耗时分布 + 准时率时效）")

# ====================== 【独立筛选器】三个环节 + 准时率 共用 ======================
with st.container():
    col1, col2, col3 = st.columns(3)
    with col1:
        months_list = sorted(df_selected["到货年月"].dropna().unique(), reverse=True)
        selected_month_hot = st.multiselect(
            "📅 选择月份（可多选）",
            options=months_list,
            default=months_list[:1] if len(months_list) > 0 else None,
            key="hot_month"
        )
    with col2:
        logistics_list = ["全部"] + sorted([str(x) for x in df_selected["物流方式"].dropna().unique() if x])
        selected_log_hot = st.selectbox(
            "🚛 渠道（物流方式）",
            options=logistics_list,
            index=0,
            key="hot_logistics"
        )
    with col3:
        region_list = ["全部", "美东", "美西", "美中"]
        selected_region_hot = st.selectbox(
            "🌎 区域",
            options=region_list,
            index=0,
            key="hot_region"
        )

# ====================== 统一筛选数据 ======================
def filter_df(df, month_col="到货年月"):
    df = df.copy()
    if selected_month_hot:
        df = df[df[month_col].isin(selected_month_hot)]
    if selected_log_hot != "全部" and "物流方式" in df.columns:
        df = df[df["物流方式"] == selected_log_hot]
    if selected_region_hot != "全部" and "区域" in df.columns:
        df = df[df["区域"] == selected_region_hot]
    df = df.reset_index(drop=True)
    return df

df_current = filter_df(df_selected)
df_current_FBA = filter_df(df_selected_FBA)

import math

# ==============================================
# 【准时率时效表格】
# ==============================================
st.markdown("### 📊 各物流方式 - 准时率 - 时效（含加权）")

target_rates = [75, 80, 85, 90, 95, 100]
time_col = "开船-完成上架"
logistics_col = "物流方式"
region_col = "区域"
stage1_col = "开船-提柜"
stage2_col = "提柜-签收"
stage3_col = "签收-完成上架"

all_results = []
required_cols = [time_col, logistics_col, region_col, stage1_col, stage2_col, stage3_col]
missing_cols = [col for col in required_cols if col not in df_current.columns]

if missing_cols:
    st.warning(f"缺失字段：{missing_cols}")
else:
    df_analysis = df_current.copy()
    for col in [time_col, stage1_col, stage2_col, stage3_col]:
        df_analysis[col] = pd.to_numeric(df_analysis[col], errors="coerce").fillna(0)
    df_analysis = df_analysis[(df_analysis[time_col] > 0)].reset_index(drop=True)

    if not df_analysis.empty:
        unique_logistics = df_analysis[logistics_col].unique()

        def calculate_weighted_by_region(df, col):
            region_counts = df[region_col].value_counts()
            total = len(df)
            weighted = 0.0
            for region, cnt in region_counts.items():
                avg = df[df[region_col] == region][col].mean()
                weighted += avg * (cnt / total)
            return round(weighted, 2)

        for method in unique_logistics:
            df_m = df_analysis[df_analysis[logistics_col] == method].copy()
            total_cnt = len(df_m)
            if total_cnt < 1:
                continue

            df_sorted = df_m.sort_values(time_col, ascending=True).reset_index(drop=True)
            df_sorted["累计占比(%)"] = (df_sorted.reset_index().index + 1) / total_cnt * 100

            for tr in target_rates:
                match = df_sorted[df_sorted["累计占比(%)"] >= tr]
                if not match.empty:
                    t = match[time_col].min()
                    real_r = match[match[time_col]==t]["累计占比(%)"].iloc[0]
                    pass_cnt = len(df_sorted[df_sorted[time_col] <= t])
                    df_pass = df_sorted[df_sorted[time_col] <= t].copy()
                else:
                    t, real_r, pass_cnt = "-", "-", 0
                    df_pass = df_m.copy()

                w1 = round(df_pass[stage1_col].mean(), 2)
                w2 = calculate_weighted_by_region(df_pass, stage2_col)
                w3 = calculate_weighted_by_region(df_pass, stage3_col)
                total_weighted = round(w1 + w2 + w3, 2)

                all_results.append({
                    "物流方式": method,
                    "目标准时率(%)": tr,
                    "实际占比(%)": round(real_r,1) if real_r != "-" else "-",
                    "开船-完成上架(天)": round(t,1) if t != "-" else "-",
                    "达标订单数": pass_cnt,
                    "总单数": total_cnt,
                    "开船-提柜(平均)": w1,
                    "提柜-签收(加权)": w2,
                    "签收-上架(加权)": w3,
                    "总加权时效": total_weighted
                })

if all_results:
    df_results = pd.DataFrame(all_results)
    st.dataframe(df_results, use_container_width=True, height=400)
else:
    st.info("ℹ️ 暂无准时率时效数据")

# ---------------------- 【最终调整版：加总订单数+去差异列】 ----------------------
st.markdown("### 📊 各物流方式 - 时效分布 + 查验差异对比")

if "是否查验" in df_all.columns and "是否为异常数据" in df_all.columns:

    # ===================== 你的逻辑：左右图均直接从df_all取，只受独立筛选器控制 =====================
    # 同步筛选条件
    if selected_month_hot:
        mask_month = df_all["到货年月"].isin(selected_month_hot)
    else:
        mask_month = True
    if selected_log_hot != "全部":
        mask_log = df_all["物流方式"] == selected_log_hot
    else:
        mask_log = True
    if selected_region_hot != "全部":
        mask_region = df_all["区域"] == selected_region_hot
    else:
        mask_region = True

    # 1. 左图：无查验（是否异常=否）
    mask_left = (df_all["是否为异常数据"] == "否") & mask_month & mask_log & mask_region
    df_left = df_all[mask_left].copy()
    df_left = df_left.drop_duplicates(subset=["货件单号"], keep="first")

    # 2. 右图：含查验（是否异常=否 OR 是否查验=是）
    mask_right = ((df_all["是否为异常数据"] == "否") | (df_all["是否查验"] == "是")) & mask_month & mask_log & mask_region
    df_right = df_all[mask_right].copy()
    df_right = df_right.drop_duplicates(subset=["货件单号"], keep="first")

    # 清洗时效
    for col in [time_col, stage1_col, stage2_col, stage3_col]:
        df_left[col] = pd.to_numeric(df_left[col], errors="coerce").fillna(0)
        df_right[col] = pd.to_numeric(df_right[col], errors="coerce").fillna(0)

    df_left = df_left[df_left[time_col] > 0].reset_index(drop=True)
    df_right = df_right[df_right[time_col] > 0].reset_index(drop=True)

    common_logistics = list(
        set(df_left[logistics_col].dropna().unique()) &
        set(df_right[logistics_col].dropna().unique())
    )

    if common_logistics:
        for method in common_logistics:
            st.markdown(f"#### 🚛 物流方式：{method}")

            df_m_left = df_left[df_left[logistics_col] == method].copy()
            df_m_right = df_right[df_right[logistics_col] == method].copy()
            if len(df_m_left) < 1 or len(df_m_right) < 1:
                continue

            # 帕累托数据计算（左图）
            g_left = df_m_left.groupby(time_col).agg(订单数=("FBA号", "count")).reset_index().sort_values(time_col)
            g_left["累计订单数"] = g_left["订单数"].cumsum()
            g_left["无查验累计占比(%)"] = (g_left["累计订单数"] / g_left["订单数"].sum() * 100).round(2)

            # 帕累托数据计算（右图）
            g_right = df_m_right.groupby(time_col).agg(订单数=("FBA号", "count")).reset_index().sort_values(time_col)
            g_right["累计订单数"] = g_right["订单数"].cumsum()
            g_right["含查验累计占比(%)"] = (g_right["累计订单数"] / g_right["订单数"].sum() * 100).round(2)

            # ===================== 新增：总订单数汇总 =====================
            total_no_check = g_left["订单数"].sum()  # 无查验总订单数
            total_with_check = g_right["订单数"].sum()  # 含查验总订单数
            diff_total = total_with_check - total_no_check  # 新增订单数
            # =================================================================

            # 合并成按天数的对比表（去掉占比差异列）
            diff_df = pd.merge(
                g_left[[time_col, "无查验累计占比(%)", "订单数"]],
                g_right[[time_col, "含查验累计占比(%)", "订单数"]],
                on=time_col,
                how="outer",
                suffixes=("_无查验", "_含查验")
            ).sort_values(time_col).fillna(0)

            # 重命名列+调整顺序
            diff_df = diff_df.rename(columns={
                time_col: "开船-完成上架(天)",
                "订单数_无查验": "无查验订单数",
                "订单数_含查验": "含查验订单数"
            })[["开船-完成上架(天)", "无查验订单数", "无查验累计占比(%)", "含查验订单数", "含查验累计占比(%)"]]

            # 一行三列布局
            col1, col2, col3 = st.columns(3)

            # 第1列：无查验帕累托图
            with col1:
                fig1 = go.Figure()
                fig1.add_trace(go.Bar(x=g_left[time_col], y=g_left["订单数"], name="订单数", marker_color="#AED6F1", opacity=0.8))
                fig1.add_trace(go.Scatter(x=g_left[time_col], y=g_left["无查验累计占比(%)"], name="累计占比", line=dict(color="red", width=3), mode="lines+markers", yaxis="y2"))
                fig1.update_layout(
                    title=f"{method}（无查验）",
                    xaxis_title="开船-完成上架（天）",
                    yaxis_title="订单数",
                    yaxis2=dict(overlaying="y", side="right", range=[0,105]),
                    height=450
                )
                st.plotly_chart(fig1, use_container_width=True)

            # 第2列：含查验帕累托图
            with col2:
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(x=g_right[time_col], y=g_right["订单数"], name="订单数", marker_color="#AED6F1", opacity=0.8))
                fig2.add_trace(go.Scatter(x=g_right[time_col], y=g_right["含查验累计占比(%)"], name="累计占比", line=dict(color="red", width=3), mode="lines+markers", yaxis="y2"))
                fig2.update_layout(
                    title=f"{method}（含查验）",
                    xaxis_title="开船-完成上架（天）",
                    yaxis_title="订单数",
                    yaxis2=dict(overlaying="y", side="right", range=[0,105]),
                    height=450
                )
                st.plotly_chart(fig2, use_container_width=True)

            # 第3列：按天数的差异对比表（加总订单数）
            with col3:
                st.subheader("📋 按天数查验影响差异表")
                # 先显示总订单数汇总
                st.info(f"""
                📦 总订单数汇总：
                - 无查验总订单：**{total_no_check}** 单
                - 含查验总订单：**{total_with_check}** 单
                - 新增查验订单：**+{diff_total}** 单
                """)
                # 再显示明细表格
                st.dataframe(
                    diff_df,
                    use_container_width=True,
                    hide_index=True
                )

            st.divider()
    else:
        st.info("无共同物流方式可展示")
else:
    st.info("暂无数据或缺少字段")

# ==============================================
# 1. 开船 - 提柜（按物流方式）✅ 修复完成
# ==============================================
st.markdown("### 🔸 开船-提柜 耗时分布（按物流方式）")
bins1  = [9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,999]
labels1= ['10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29+']
vals1  = [10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29]
col1   = "开船-提柜"

df1 = df_current.copy()
df1[col1] = pd.to_numeric(df1[col1], errors="coerce")
df1 = df1.dropna(subset=[col1])
df1 = df1[df1[col1] >= 0]

if not df1.empty:
    df1['区间'] = pd.cut(df1[col1], bins=bins1, labels=labels1, right=True)
    cross = pd.crosstab(df1['物流方式'], df1['区间'], dropna=False)
    total_all = cross.sum().sum()
    rows = []
    for m in cross.index:
        total = cross.loc[m].sum()
        row = {"分组":m, "加权耗时":0}
        ws = 0
        for i, l in enumerate(labels1):
            cnt = cross.loc[m, l]
            pct = cnt/total*100 if total>0 else 0
            wv = vals1[i] * (cnt/total) if total>0 else 0
            ws += wv
            if pct==0:bg,fc="#fff7e6","black"
            elif pct<10:bg,fc="#ffe2b3","black"
            elif pct<20:bg,fc="#ffc880","black"
            elif pct<30:bg,fc="#ffad4d","black"
            elif pct<40:bg,fc="#ff941a","white"
            else:bg,fc="#e66a00","white"
            row[l] = f"""<div style='background:{bg};color:{fc};padding:2px;text-align:center'><b>{pct:.2f}%</b><br><small>{wv:.2f}</small></div>"""
        row["加权耗时"] = math.ceil(ws) if total>0 else 0
        row["票数"] = total
        row["合计"] = total_all
        rows.append(row)

    order = ["分组","加权耗时"]+labels1+["票数","合计"]
    h = "".join([f"<th>{x}</th>" for x in order])
    b = ""
    for r in rows:
        cs = []
        for c in order:
            if c in ["分组","加权耗时","票数","合计"]:
                cs.append(f"<td style='padding:4px;font-size:13px;text-align:center'>{r[c]}</td>")
            else:
                cs.append(f"<td style='padding:0'>{r[c]}</td>")
        b += "<tr>"+"".join(cs)+"</tr>"

    st.markdown(f"""
    <style>table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #ddd;padding:2px;font-size:12px}}th{{background:#f5f5f5}}</style>
    <table>{h}{b}</table>""", unsafe_allow_html=True)
else:
    st.warning("暂无开船-提柜数据")

# ==============================================
# 2. 提柜 - 签收（按区域）✅ 彻底修复报错
# ==============================================
st.markdown("### 🔸 提柜-签收 耗时分布（按区域）")
bins2  = [-1, 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,999]
labels2= ['0','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16+']
vals2  = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
col2   = "提柜-签收"

df2 = df_current.copy()
df2[col2] = pd.to_numeric(df2[col2], errors="coerce").fillna(0)
df2 = df2[df2[col2] >= 0]

if not df2.empty:
    df2['区间'] = pd.cut(df2[col2], bins=bins2, labels=labels2, right=True)
    cross = pd.crosstab(df2['区域'], df2['区间'], dropna=False)
    total_all = cross.sum().sum()
    rows = []
    for m in cross.index:
        total = cross.loc[m].sum()
        row = {"分组":m, "加权耗时":0}
        ws = 0
        for i, l in enumerate(labels2):
            cnt = cross.loc[m, l]
            pct = cnt/total*100 if total>0 else 0
            wv = vals2[i] * (cnt/total) if total>0 else 0
            ws += wv
            if pct==0:bg,fc="#fff7e6","black"
            elif pct<10:bg,fc="#ffe2b3","black"
            elif pct<20:bg,fc="#ffc880","black"
            elif pct<30:bg,fc="#ffad4d","black"
            elif pct<40:bg,fc="#ff941a","white"
            else:bg,fc="#e66a00","white"
            row[l] = f"""<div style='background:{bg};color:{fc};padding:2px;text-align:center'><b>{pct:.2f}%</b><br><small>{wv:.2f}</small></div>"""
        row["加权耗时"] = math.ceil(ws) if total>0 else 0
        row["票数"] = total
        row["合计"] = total_all
        rows.append(row)

    order = ["分组","加权耗时"]+labels2+["票数","合计"]
    h = "".join([f"<th>{x}</th>" for x in order])
    b = ""
    for r in rows:
        cs = []
        for c in order:
            if c in ["分组","加权耗时","票数","合计"]:
                cs.append(f"<td style='padding:4px;font-size:13px;text-align:center'>{r[c]}</td>")
            else:
                cs.append(f"<td style='padding:0'>{r[c]}</td>")
        b += "<tr>"+"".join(cs)+"</tr>"

    st.markdown(f"""
    <style>table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #ddd;padding:2px;font-size:12px}}th{{background:#f5f5f5}}</style>
    <table>{h}{b}</table>""", unsafe_allow_html=True)
else:
    st.warning("暂无提柜-签收数据")

# ==============================================
# 3. 签收-完成上架（按区域 + FBA）✅ 彻底修复
# ==============================================
st.markdown("### 🔸 签收-完成上架 耗时分布（按区域 - FBA号）")
bins3  = [-1, 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,999]
labels3= ['0','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16+']
vals3  = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
col3   = "签收-完成上架"

df3 = df_current_FBA.copy()
df3[col3] = pd.to_numeric(df3[col3], errors="coerce").fillna(0)
df3 = df3[df3[col3] >= 0]

if not df3.empty:
    df3['区间'] = pd.cut(df3[col3], bins=bins3, labels=labels3, right=True)
    cross = pd.crosstab(df3['区域'], df3['区间'], dropna=False)
    total_all = cross.sum().sum()
    rows = []
    for m in cross.index:
        total = cross.loc[m].sum()
        row = {"分组":m, "加权耗时":0}
        ws = 0
        for i, l in enumerate(labels3):
            cnt = cross.loc[m, l]
            pct = cnt/total*100 if total>0 else 0
            wv = vals3[i] * (cnt/total) if total>0 else 0
            ws += wv
            if pct==0:bg,fc="#fff7e6","black"
            elif pct<10:bg,fc="#ffe2b3","black"
            elif pct<20:bg,fc="#ffc880","black"
            elif pct<30:bg,fc="#ffad4d","black"
            elif pct<40:bg,fc="#ff941a","white"
            else:bg,fc="#e66a00","white"
            row[l] = f"""<div style='background:{bg};color:{fc};padding:2px;text-align:center'><b>{pct:.2f}%</b><br><small>{wv:.2f}</small></div>"""
        row["加权耗时"] = math.ceil(ws) if total>0 else 0
        row["票数"] = total
        row["合计"] = total_all
        rows.append(row)

    order = ["分组","加权耗时"]+labels3+["票数","合计"]
    h = "".join([f"<th>{x}</th>" for x in order])
    b = ""
    for r in rows:
        cs = []
        for c in order:
            if c in ["分组","加权耗时","票数","合计"]:
                cs.append(f"<td style='padding:4px;font-size:13px;text-align:center'>{r[c]}</td>")
            else:
                cs.append(f"<td style='padding:0'>{r[c]}</td>")
        b += "<tr>"+"".join(cs)+"</tr>"

    st.markdown(f"""
    <style>table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #ddd;padding:2px;font-size:12px}}th{{background:#f5f5f5}}</style>
    <table>{h}{b}</table>""", unsafe_allow_html=True)
else:
    st.warning("暂无签收-完成上架数据")
# ---------------------- 不同月份整体趋势分析（总订单+准时率） ----------------------
st.markdown("## 📈 不同月份整体趋势分析")
st.divider()

# ===== 1. 数据预处理（先加物流方式筛选，再聚合年月）=====
# ---------------------- 【修改1】：新增物流方式列校验 ----------------------
required_cols = ["到货年月", "FBA号", "提前/延期(整体)", "物流方式"]  # 新增：物流方式
missing_cols = [col for col in required_cols if col not in df_selected.columns]
if missing_cols:
    st.error(f"缺少月度分析必要列：{missing_cols}，请检查数据列名！")
else:
    # ---------------------- 【新增1】：物流方式筛选器（核心新增） ----------------------
    st.markdown("### 筛选条件")
    col_logistics, col_empty = st.columns([1, 3])
    with col_logistics:
        unique_logistics = sorted(df_selected["物流方式"].dropna().unique())
        logistics_options = ["全部"] + unique_logistics
        selected_logistics = st.selectbox(
            "物流方式",
            options=logistics_options,
            index=0,
            key="selected_logistics"
        )

    if selected_logistics == "全部":
        df_filtered_by_logistics = df_selected.copy()
    else:
        df_filtered_by_logistics = df_selected[df_selected["物流方式"] == selected_logistics].copy()

    if len(df_filtered_by_logistics) == 0:
        st.warning(f"所选物流方式「{selected_logistics}」暂无数据")
    else:
        # ---------------------- 聚合数据 ----------------------
        monthly_stats = df_filtered_by_logistics.groupby("到货年月").agg(
            总订单数=("FBA号", "count"),
            提前准时订单数=("提前/延期(整体)", lambda x: len(x[x == "提前/准时"])),
            延期订单数=("提前/延期(整体)", lambda x: len(x[x == "延期"]))
        ).reset_index()

        # 计算准时率
        monthly_stats["准时率(%)"] = round(monthly_stats["提前准时订单数"] / monthly_stats["总订单数"] * 100, 2)

        # ---------------------- 【新增：关键过滤】单月订单数<4的月份剔除 ----------------------
        monthly_stats = monthly_stats[monthly_stats["总订单数"] >= 4].copy()
        if len(monthly_stats) == 0:
            st.warning("所有月份订单数均小于4，无有效数据可展示")
            st.stop()

        # ---------------------- 日期解析容错 ----------------------
        def safe_parse_ym(ym):
            try:
                return pd.to_datetime(str(ym) + "-01")
            except:
                return pd.NaT

        def calc_prev_n_month(latest_ym, n):
            try:
                latest_dt = pd.to_datetime(latest_ym + "-01")
                prev_dt = latest_dt - pd.DateOffset(months=n - 1)
                return prev_dt.strftime("%Y-%m")
            except:
                return latest_ym

        monthly_stats["年月排序"] = monthly_stats["到货年月"].apply(safe_parse_ym)
        monthly_stats = monthly_stats[monthly_stats["年月排序"].notna()].copy()

        if len(monthly_stats) == 0:
            st.warning("暂无有效月份数据可分析")
        else:
            monthly_stats["中文月份"] = monthly_stats["年月排序"].dt.strftime("%Y年%m月")
            monthly_stats = monthly_stats.sort_values("年月排序", ascending=True).reset_index(drop=True)

            # 计算环比变化
            monthly_stats["总订单数环比变化"] = monthly_stats["总订单数"].diff(1).fillna(0)
            monthly_stats["准时率环比变化(百分点)"] = monthly_stats["准时率(%)"].diff(1).fillna(0)

            # ===== 2. 快捷筛选器 =====
            latest_ym = monthly_stats["到货年月"].max()
            col_quick, col_tip = st.columns([2, 3])
            with col_quick:
                st.markdown("#### 快捷时间筛选")
                quick_options = ["自定义时间范围", "上个月", "近三个月", "近半年", "近一年"]
                selected_quick = st.selectbox(
                    "快速选择",
                    options=quick_options,
                    index=0,
                    key="quick_time_filter",
                    label_visibility="collapsed"
                )
            with col_tip:
                st.markdown(f"#### 筛选基准（自动获取）")
                st.caption(f"📌 数据最新月份：{latest_ym}")
                st.caption(f"💡 快捷筛选均以最新月份为结束时间")

            start_ym = None
            end_ym = latest_ym

            if selected_quick == "上个月":
                start_ym = latest_ym
            elif selected_quick == "近三个月":
                start_ym = calc_prev_n_month(latest_ym, 3)
            elif selected_quick == "近半年":
                start_ym = calc_prev_n_month(latest_ym, 6)
            elif selected_quick == "近一年":
                start_ym = calc_prev_n_month(latest_ym, 12)
            else:
                st.markdown("#### 自定义时间范围")
                col_start, col_end = st.columns(2)
                with col_start:
                    start_month = st.selectbox(
                        "开始月份",
                        options=monthly_stats["中文月份"].tolist(),
                        index=0,
                        key="start_month"
                    )
                with col_end:
                    end_month = st.selectbox(
                        "结束月份",
                        options=monthly_stats["中文月份"].tolist(),
                        index=len(monthly_stats) - 1,
                        key="end_month"
                    )
                start_ym = monthly_stats[monthly_stats["中文月份"] == start_month]["到货年月"].iloc[0]
                end_ym = monthly_stats[monthly_stats["中文月份"] == end_month]["到货年月"].iloc[0]

            # 最终数据筛选
            df_filtered = monthly_stats[
                (monthly_stats["到货年月"] >= start_ym) &
                (monthly_stats["到货年月"] <= end_ym)
            ].copy()
            df_filtered = df_filtered.sort_values("年月排序", ascending=True).reset_index(drop=True)

            start_cn = df_filtered["中文月份"].min() if len(df_filtered) > 0 else ""
            end_cn = df_filtered["中文月份"].max() if len(df_filtered) > 0 else ""
            st.info(f"✅ 筛选结果：{selected_logistics} | {start_cn} 至 {end_cn}（共{len(df_filtered)}个月份）")
            st.dataframe(df_filtered[["中文月份", "总订单数", "准时率(%)"]], use_container_width=True, hide_index=True)

            # ===== 后续原有逻辑 =====
            avg_on_time_rate = df_filtered["准时率(%)"].mean()
            st.markdown("### 月度订单数&准时率趋势")
            import plotly.graph_objects as go

            fig = go.Figure()
            # 左轴：柱状图
            fig.add_trace(go.Bar(
                x=df_filtered["中文月份"],
                y=df_filtered["总订单数"],
                name="总订单数",
                yaxis="y1",
                marker_color="#4299e1",
                opacity=0.8
            ))
            fig.add_trace(go.Bar(
                x=df_filtered["中文月份"],
                y=df_filtered["提前准时订单数"],
                name="提前/准时订单数",
                yaxis="y1",
                marker_color="#48bb78",
                opacity=0.8
            ))
            fig.add_trace(go.Bar(
                x=df_filtered["中文月份"],
                y=df_filtered["延期订单数"],
                name="延期订单数",
                yaxis="y1",
                marker_color="#e53e3e",
                opacity=0.8
            ))
            # 右轴：折线图（准时率）
            fig.add_trace(go.Scatter(
                x=df_filtered["中文月份"],
                y=df_filtered["准时率(%)"],
                name="准时率(%)",
                yaxis="y2",
                marker_color="#9f7aea",
                mode="lines+markers+text",
                line=dict(width=3),
                marker=dict(size=8),
                text=df_filtered["准时率(%)"].apply(lambda x: f"{x:.2f}%"),
                textposition="top center"
            ))
            # 平均准时率红色虚线
            fig.add_trace(go.Scatter(
                x=df_filtered["中文月份"],
                y=[avg_on_time_rate] * len(df_filtered),
                name=f"平均准时率: {avg_on_time_rate:.2f}%",
                yaxis="y2",
                mode="lines",
                line=dict(color="#ff0000", dash="dash", width=2),
                hoverinfo="name+y"
            ))
            # 图表配置
            fig.update_layout(
                title="月度总订单数/提前准时订单数/延期订单数 & 准时率趋势",
                yaxis=dict(title="订单数", side="left", range=[0, max(df_filtered["总订单数"]) * 1.2]),
                yaxis2=dict(title="准时率(%)", side="right", overlaying="y", range=[0, 100]),
                xaxis=dict(title="到货年月", tickangle=45),
                legend=dict(x=0.02, y=0.98, bordercolor="#eee", borderwidth=1),
                height=450,
                plot_bgcolor="#ffffff",
                barmode="group"
            )
            st.plotly_chart(fig, use_container_width=True)

            # ===== 月度明细表格 =====
            st.markdown("### 月度核心指标明细（倒序排列）")
            df_display = df_filtered.sort_values("年月排序", ascending=False).reset_index(drop=True)
            display_cols = [
                "中文月份", "总订单数", "总订单数环比变化", "提前准时订单数", "延期订单数",
                "准时率(%)", "准时率环比变化(百分点)"
            ]
            df_display = df_display[display_cols].copy()

            # 格式化环比变化（带正负号）
            df_display["总订单数环比变化"] = df_display["总订单数环比变化"].apply(
                lambda x: f"+{int(x)}" if x > 0 else f"{int(x)}" if x < 0 else "0"
            )
            df_display["准时率环比变化(百分点)"] = df_display["准时率环比变化(百分点)"].apply(
                lambda x: f"+{x:.2f}" if x > 0 else f"{x:.2f}" if x < 0 else "0.00"
            )
            df_display["准时率(%)"] = df_display["准时率(%)"].apply(lambda x: f"{x:.2f}")

            # 表格高亮规则
            def highlight_monthly(row):
                styles = [""] * len(row)
                if float(row["准时率(%)"]) < 80:
                    styles[display_cols.index("准时率(%)")] = "background-color: #fff5f5; color: #c62828; font-weight: bold;"
                if row["总订单数环比变化"].startswith("-"):
                    styles[display_cols.index("总订单数环比变化")] = "background-color: #fff5f5; color: #c62828; font-weight: bold;"
                if row["准时率环比变化(百分点)"].startswith("-"):
                    styles[display_cols.index("准时率环比变化(百分点)")] = "background-color: #fff5f5; color: #c62828; font-weight: bold;"
                return styles

            styled_table = df_display.style.apply(highlight_monthly, axis=1)
            st.dataframe(styled_table, use_container_width=True, hide_index=True)

            # ===== 数据下载 =====
            csv_data = monthly_stats.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 下载所有月度整体数据",
                data=csv_data,
                file_name="月度整体趋势分析数据.csv",
                mime="text/csv",
                key="monthly_trend_download"
            )

            # ===== 整体趋势总结 =====
            st.markdown("### 整体趋势总结")
            latest_month = df_filtered.iloc[-1]["中文月份"] if len(df_filtered) > 0 else ""
            if latest_month:
                latest_total = df_filtered.iloc[-1]["总订单数"]
                latest_on_time = df_filtered.iloc[-1]["提前准时订单数"]
                latest_delay = df_filtered.iloc[-1]["延期订单数"]
                latest_rate = df_filtered.iloc[-1]["准时率(%)"]
                prev_month = df_filtered.iloc[-2]["中文月份"] if len(df_filtered) > 1 else None
                summary = f"最新{latest_month}整体表现：总订单数{latest_total}单，其中提前/准时订单{latest_on_time}单，延期订单{latest_delay}单，准时率{latest_rate:.2f}%。"
                if prev_month:
                    prev_total = df_filtered.iloc[-2]["总订单数"]
                    prev_rate = df_filtered.iloc[-2]["准时率(%)"]
                    total_change = latest_total - prev_total
                    rate_change = latest_rate - prev_rate
                    summary += f" 与{prev_month}相比，总订单数{'增加' if total_change > 0 else '减少' if total_change < 0 else '持平'} {abs(total_change)}单，准时率{'提升' if rate_change > 0 else '下降' if rate_change < 0 else '持平'} {abs(rate_change):.2f}个百分点。"
                if len(df_filtered) >= 3:
                    rate_trend = df_filtered["准时率(%)"].tail(3).tolist()
                    if rate_trend[2] > rate_trend[1] > rate_trend[0]:
                        summary += f" 近{len(df_filtered)}个月准时率呈上升趋势，整体表现向好！"
                    elif rate_trend[2] < rate_trend[1] < rate_trend[0]:
                        summary += f" 近{len(df_filtered)}个月准时率呈下降趋势，需重点关注延期问题！"
                    else:
                        summary += f" 近{len(df_filtered)}个月准时率波动较小，整体表现稳定。"
                summary += f" 所选时间范围平均准时率为：{avg_on_time_rate:.2f}%。"
                st.markdown(f"> {summary}")



# ---------------------- 货代不同月份趋势分析 ----------------------
st.markdown("## 🚢 货代不同月份趋势分析")
st.divider()

# ===== 1. 数据预处理 & 列名校验 =====
FREIGHT_MONTH_COLUMN_MAPPING = {
    "货代列名": "货代",  # 替换为你实际的货代列名
    "到货年月列名": "到货年月",  # 替换为你实际的到货年月列名
    "提前延期列名": "提前/延期（货代）"  # 替换为你实际的提前/延期列名
}
# ---------------------- 【修改1】：新增物流方式列校验 ----------------------
required_cols = [
    FREIGHT_MONTH_COLUMN_MAPPING["货代列名"],
    FREIGHT_MONTH_COLUMN_MAPPING["到货年月列名"],
    FREIGHT_MONTH_COLUMN_MAPPING["提前延期列名"],
    "FBA号",  # 用于统计订单数
    "物流方式"  # 新增：物流方式列
]
missing_cols = [col for col in required_cols if col not in df_selected.columns]
if missing_cols:
    st.error(f"缺少货代月度分析必要列：{missing_cols}，请检查数据列名！")
else:
    # ---------------------- 【新增1】：物流方式筛选器（第一步筛选） ----------------------
    st.markdown("### 筛选条件")
    # 新增：物流方式筛选行（控制列宽）
    col_logistics, col_empty = st.columns([1, 3])
    with col_logistics:
        # 获取唯一的物流方式（去重+排序+去空）
        unique_logistics = sorted(df_selected["物流方式"].dropna().unique())
        # 新增"全部"选项，默认选中
        logistics_options = ["全部"] + unique_logistics
        selected_logistics = st.selectbox(
            "物流方式",
            options=logistics_options,
            index=0,
            key="freight_selected_logistics"  # 独立key，避免冲突
        )

    # 新增：根据选中的物流方式过滤原始数据
    if selected_logistics == "全部":
        df_filtered_by_logistics = df_selected.copy()
    else:
        df_filtered_by_logistics = df_selected[df_selected["物流方式"] == selected_logistics].copy()

    # 新增：容错处理 - 物流方式筛选后无数据
    if len(df_filtered_by_logistics) == 0:
        st.warning(f"所选物流方式「{selected_logistics}」暂无货代数据")
    else:
        # ---------------------- 【修改2】：数据源从df_selected改为df_filtered_by_logistics ----------------------
        # 筛选有效数据（基于物流方式筛选后的数据）
        df_freight_month_valid = df_filtered_by_logistics[
            (df_filtered_by_logistics[FREIGHT_MONTH_COLUMN_MAPPING["货代列名"]].notna()) &
            (df_filtered_by_logistics[FREIGHT_MONTH_COLUMN_MAPPING["到货年月列名"]].notna())
            ].copy()

        if len(df_freight_month_valid) == 0:
            st.warning("暂无货代跨月份数据可分析")
        else:
            # ===== 2. 按「到货年月+货代」聚合核心指标 =====
            freight_month_stats = df_freight_month_valid.groupby(
                [FREIGHT_MONTH_COLUMN_MAPPING["到货年月列名"], FREIGHT_MONTH_COLUMN_MAPPING["货代列名"]]
            ).agg(
                总订单数=("FBA号", "count"),
                提前准时订单数=(FREIGHT_MONTH_COLUMN_MAPPING["提前延期列名"], lambda x: len(x[x == "提前/准时"])),
                延期订单数=(FREIGHT_MONTH_COLUMN_MAPPING["提前延期列名"], lambda x: len(x[x == "延期"]))
            ).reset_index()

            # 重命名列方便后续使用
            freight_month_stats.rename(columns={
                FREIGHT_MONTH_COLUMN_MAPPING["到货年月列名"]: "到货年月",
                FREIGHT_MONTH_COLUMN_MAPPING["货代列名"]: "货代"
            }, inplace=True)

            # 计算准时率（修复列名：确保列名是「准时率(%)」，无多余空格）
            freight_month_stats["准时率(%)"] = round(
                freight_month_stats["提前准时订单数"] / freight_month_stats["总订单数"] * 100, 2
            )


            # ===== 3. 货代归类（优质/合格/异常 + 颜色标记）=====
            def get_freight_category(rate):
                """根据准时率返回归类标签和颜色"""
                if rate >= 90:
                    return "优质", "#2e7d32"  # 绿色
                elif rate >= 80:
                    return "合格", "#ff9800"  # 黄色/橙色
                else:
                    return "异常", "#c62828"  # 红色


            # 新增归类列
            freight_month_stats["货代归类"] = freight_month_stats["准时率(%)"].apply(
                lambda x: get_freight_category(x)[0])
            freight_month_stats["归类颜色"] = freight_month_stats["准时率(%)"].apply(
                lambda x: get_freight_category(x)[1])


            # ===== 4. 双下拉框时间范围筛选 =====
            # ---------------------- 【修改3】：移除重复的"筛选条件"标题 ----------------------
            # 原st.markdown("### 筛选条件")已上移，此处删除

            # 新增：日期解析容错函数（避免格式错误）
            def safe_parse_ym(ym):
                try:
                    return pd.to_datetime(str(ym) + "-01")
                except:
                    return pd.NaT


            # 生成中文月份列表（用于下拉框）
            freight_month_stats["年月排序"] = freight_month_stats["到货年月"].apply(safe_parse_ym)
            # 过滤无效日期
            freight_month_stats = freight_month_stats[freight_month_stats["年月排序"].notna()].copy()

            if len(freight_month_stats) == 0:
                st.warning("暂无有效货代月份数据可分析")
            else:
                freight_month_stats["中文月份"] = freight_month_stats["年月排序"].dt.strftime("%Y年%m月")

                # 提取唯一的中文月份（正序）
                unique_months = freight_month_stats.sort_values("年月排序")["中文月份"].unique().tolist()
                unique_ym = freight_month_stats.sort_values("年月排序")["到货年月"].unique().tolist()

                # 双下拉框选择开始/结束月份
                # ====================== 快捷筛选器 + 双下拉框 ======================
                st.markdown("#### 快捷筛选")

                # 基准月：数据最新月份 = 2026年2月（自动获取，不用手动改）
                latest_month = freight_month_stats["年月排序"].max()

                # 快捷筛选选项
                quick_options = [
                    "自定义时间",
                    "上个月",
                    "近三个月",
                    "近半年",
                    "近一年"
                ]
                selected_quick = st.selectbox("快捷筛选", options=quick_options, index=0)

                # 根据选项计算 开始月份 & 结束月份
                if selected_quick == "上个月":
                    start_month = latest_month - pd.DateOffset(months=1)
                    end_month = latest_month - pd.DateOffset(months=1)

                elif selected_quick == "近三个月":
                    start_month = latest_month - pd.DateOffset(months=2)
                    end_month = latest_month

                elif selected_quick == "近半年":
                    start_month = latest_month - pd.DateOffset(months=5)
                    end_month = latest_month

                elif selected_quick == "近一年":
                    start_month = latest_month - pd.DateOffset(months=11)
                    end_month = latest_month

                else:  # 自定义时间 range
                    start_month = None
                    end_month = None

                # 生成中文月份映射
                month_cn_list = freight_month_stats.sort_values("年月排序")["中文月份"].tolist()
                month_dt_list = freight_month_stats.sort_values("年月排序")["年月排序"].tolist()
                month_map = dict(zip(month_dt_list, month_cn_list))

                # 如果是快捷筛选 → 自动设置开始/结束月份
                if start_month is not None and end_month is not None:
                    start_month_cn = month_map.get(start_month, month_cn_list[0])
                    end_month_cn = month_map.get(end_month, month_cn_list[-1])
                else:
                    # 原有双下拉框
                    st.markdown("#### 自定义时间范围")
                    col_start, col_end = st.columns(2)
                    with col_start:
                        start_month_cn = st.selectbox("开始月份", options=unique_months, index=0,
                                                      key="freight_start_month")
                    with col_end:
                        end_month_cn = st.selectbox("结束月份", options=unique_months, index=len(unique_months) - 1,
                                                    key="freight_end_month")

                # ====================== 以下你原有代码完全不用动 ======================
                # 安全转换为原始年月格式（避免IndexError）
                start_ym = freight_month_stats[freight_month_stats["中文月份"] == start_month_cn]["到货年月"].iloc[0]
                end_ym = freight_month_stats[freight_month_stats["中文月份"] == end_month_cn]["到货年月"].iloc[0]

                # 安全转换为原始年月格式（避免IndexError）
                start_ym = freight_month_stats[freight_month_stats["中文月份"] == start_month_cn]["到货年月"].iloc[0]
                end_ym = freight_month_stats[freight_month_stats["中文月份"] == end_month_cn]["到货年月"].iloc[0]

                # 筛选时间范围内的数据
                df_freight_filtered = freight_month_stats[
                    (freight_month_stats["到货年月"] >= start_ym) &
                    (freight_month_stats["到货年月"] <= end_ym)
                    ].copy()

                # 按「到货年月降序 + 总订单数降序」排序
                df_freight_filtered["年月排序"] = df_freight_filtered["到货年月"].apply(safe_parse_ym)
                df_freight_filtered = df_freight_filtered.sort_values(
                    by=["年月排序", "总订单数"],
                    ascending=[False, False]
                ).reset_index(drop=True)

                if len(df_freight_filtered) == 0:
                    st.warning("所选时间范围内无货代数据")
                else:
                    # ===== 5. 货代月度明细表格（带颜色归类）=====
                    st.markdown("### 货代月度核心指标明细（到货年月降序+订单数降序）")

                    # 准备展示列
                    display_cols = [
                        "中文月份", "货代", "总订单数", "提前准时订单数", "延期订单数", "准时率(%)", "货代归类"
                    ]
                    df_freight_display = df_freight_filtered[display_cols].copy()


                    # 表格样式：归类列按颜色标记
                    def highlight_freight_category(row):
                        styles = [""] * len(row)
                        # 获取归类颜色
                        color = df_freight_filtered.loc[row.name, "归类颜色"]
                        # 给货代归类列上色
                        styles[
                            display_cols.index(
                                "货代归类")] = f"background-color: {color}; color: white; font-weight: bold;"
                        # 准时率<80%标红
                        if row["准时率(%)"] < 80:
                            styles[display_cols.index(
                                "准时率(%)")] = "background-color: #fff5f5; color: #c62828; font-weight: bold;"
                        return styles


                    # 3. 核心修复：格式化准时率为2位小数（去掉多余0）
                    styled_freight_table = df_freight_display.style.apply(highlight_freight_category, axis=1)
                    # 关键：强制格式化准时率为2位小数，自动去除末尾无意义的0
                    styled_freight_table = styled_freight_table.format({
                        "准时率(%)": lambda x:
                        # 先保留2位小数，再去掉末尾的0和小数点（如果需要）
                        f"{x:.2f}".rstrip('0').rstrip('.') if '.' in f"{x:.2f}" else f"{x:.2f}"
                    })
                    st.dataframe(
                        styled_freight_table,
                        use_container_width=True,
                        hide_index=True
                    )

            # ===== 6. 货代归类结果汇总表（修复KeyError核心点）=====
            st.markdown("### 货代归类结果汇总（所选时间范围）")

            # 按货代+归类汇总（列名无空格，和前面保持一致）
            freight_category_summary = df_freight_filtered.groupby(["货代", "货代归类"]).agg(
                涉及月份数=("到货年月", "nunique"),
                累计订单数=("总订单数", "sum"),
                平均准时率=("准时率(%)", "mean")  # 修复：去掉列名中的多余空格
            ).reset_index()

            # 格式化平均准时率（保留2位小数）
            freight_category_summary["平均准时率"] = round(freight_category_summary["平均准时率"], 2)
            # 重命名列（可选：添加%符号，更直观）
            freight_category_summary.rename(columns={"平均准时率": "平均准时率(%)"}, inplace=True)


            # 汇总表样式
            def highlight_summary_category(row):
                styles = [""] * len(row)
                # 获取归类颜色
                if row["货代归类"] == "优质":
                    color = "#2e7d32"
                elif row["货代归类"] == "合格":
                    color = "#ff9800"
                else:
                    color = "#c62828"
                cate_col_idx = freight_category_summary.columns.get_loc("货代归类")
                styles[cate_col_idx] = f"background-color: {color}; color: white; font-weight: bold;"
                return styles


            styled_summary_table = freight_category_summary.style.apply(highlight_summary_category, axis=1)
            st.dataframe(
                styled_summary_table,
                use_container_width=True,
                hide_index=True
            )

            # ===== 7. 货代月度趋势图（货代筛选器+双轴图）=====
            st.markdown("### 货代月度趋势分析（按货代筛选）")

            # 货代筛选器
            unique_freights = df_freight_filtered["货代"].unique().tolist()
            selected_freight = st.selectbox(
                "选择货代查看趋势",
                options=unique_freights,
                index=0,
                key="selected_freight"
            )

            # 筛选所选货代的数据（按时间正序）
            df_freight_trend = df_freight_filtered[
                df_freight_filtered["货代"] == selected_freight
                ].sort_values("年月排序", ascending=True).reset_index(drop=True)

            if len(df_freight_trend) == 0:
                st.warning(f"所选时间范围内无{selected_freight}的相关数据")
            else:
                # 计算该货代的平均准时率（用于虚线）
                avg_freight_rate = df_freight_trend["准时率(%)"].mean()

                # 绘制双轴趋势图
                import plotly.graph_objects as go

                fig_freight = go.Figure()

                # 左轴：柱状图（总订单数、提前准时订单数、延期订单数）
                fig_freight.add_trace(go.Bar(
                    x=df_freight_trend["中文月份"],
                    y=df_freight_trend["总订单数"],
                    name="总订单数",
                    yaxis="y1",
                    marker_color="#4299e1",
                    opacity=0.8
                ))
                fig_freight.add_trace(go.Bar(
                    x=df_freight_trend["中文月份"],
                    y=df_freight_trend["提前准时订单数"],
                    name="提前/准时订单数",
                    yaxis="y1",
                    marker_color="#48bb78",
                    opacity=0.8
                ))
                fig_freight.add_trace(go.Bar(
                    x=df_freight_trend["中文月份"],
                    y=df_freight_trend["延期订单数"],
                    name="延期订单数",
                    yaxis="y1",
                    marker_color="#e53e3e",
                    opacity=0.8
                ))

                # 右轴：折线图（准时率）
                fig_freight.add_trace(go.Scatter(
                    x=df_freight_trend["中文月份"],
                    y=df_freight_trend["准时率(%)"],
                    name="准时率(%)",
                    yaxis="y2",
                    marker_color="#9f7aea",
                    mode="lines+markers+text",
                    line=dict(width=3),
                    marker=dict(size=8),
                    text=df_freight_trend["准时率(%)"].apply(lambda x: f"{x:.2f}%"),
                    textposition="top center"
                ))

                # 平均准时率红色虚线
                fig_freight.add_trace(go.Scatter(
                    x=df_freight_trend["中文月份"],
                    y=[avg_freight_rate] * len(df_freight_trend),
                    name=f"平均准时率: {avg_freight_rate:.2f}%",
                    yaxis="y2",
                    mode="lines",
                    line=dict(color="#ff0000", dash="dash", width=2),
                    hoverinfo="name+y"
                ))

                # 图表配置
                fig_freight.update_layout(
                    title=f"{selected_freight} - 月度订单数&准时率趋势",
                    yaxis=dict(title="订单数", side="left", range=[0, max(df_freight_trend["总订单数"]) * 1.2]),
                    yaxis2=dict(title="准时率(%)", side="right", overlaying="y", range=[0, 100]),
                    xaxis=dict(title="到货年月", tickangle=45),
                    legend=dict(x=0.02, y=0.98, bordercolor="#eee", borderwidth=1),
                    height=450,
                    plot_bgcolor="#ffffff",
                    barmode="group"
                )
                st.plotly_chart(fig_freight, use_container_width=True)

            # ===== 优化后的货代月度表现总结 =====
            st.markdown("### 货代月度表现总结（综合版）")

            # ---------------------- 第一步：整体汇总 & 核心指标计算 ----------------------
            total_months = df_freight_filtered["中文月份"].nunique()
            total_freights = df_freight_filtered["货代"].nunique()
            total_orders = df_freight_filtered["总订单数"].sum()
            avg_overall_rate = round(df_freight_filtered["准时率(%)"].mean(), 2)

            st.markdown(
                f"> **整体汇总**：所选时间范围共涵盖{total_months}个月份，涉及{total_freights}个货代，累计订单数{total_orders}单，整体平均准时率{avg_overall_rate}%。")

            # --- 核心优化1：先修复最新月份取值逻辑（关键！避免显示2026年2月） ---
            # 对筛选后的数据按年月排序（正序）
            df_filtered_sorted = df_freight_filtered.sort_values("年月排序", ascending=True)
            # 提取筛选范围内的所有有效月份
            valid_months = df_filtered_sorted["中文月份"].unique()
            # 确定筛选范围内的最新月份（避免取到筛选外的月份）
            latest_month = valid_months[-1] if len(valid_months) > 0 else "无数据"


            # --- 核心优化：计算综合评分和评级 ---
            def calculate_comprehensive_score(freight_data):
                """
                根据货代数据计算综合评分和评级。
                综合考虑：订单量、出现频次、加权平均准时率。
                """
                # 1. 基础数据
                total_orders = freight_data["总订单数"].sum()
                total_months = len(freight_data)
                # 加权平均准时率：按订单量加权
                weighted_avg_rate = (freight_data["准时率(%)"] * freight_data[
                    "总订单数"]).sum() / total_orders if total_orders > 0 else 0

                # 2. 设定门槛（可根据业务调整）
                MIN_ORDERS = 5  # 最低订单量门槛
                MIN_MONTHS = 2  # 最低出现月份门槛

                # 3. 评级逻辑
                if total_orders < MIN_ORDERS or total_months < MIN_MONTHS:
                    return "样本不足", weighted_avg_rate, total_orders, total_months
                elif weighted_avg_rate >= 90:
                    return "优质", weighted_avg_rate, total_orders, total_months
                elif weighted_avg_rate >= 80:
                    return "合格", weighted_avg_rate, total_orders, total_months
                else:
                    return "异常", weighted_avg_rate, total_orders, total_months


            # --- 为每个货代计算综合评级 ---
            comprehensive_summary = []
            for freight in df_freight_filtered["货代"].unique():
                freight_data = df_freight_filtered[df_freight_filtered["货代"] == freight].copy()
                # 修复：避免货代只有1条数据时iloc[0]报错
                if len(freight_data) > 0:
                    # 按年月降序排序，取最新月份的表现
                    freight_data_sorted = freight_data.sort_values("年月排序", ascending=False)
                    latest_perf = freight_data_sorted.iloc[0]["货代归类"]
                else:
                    latest_perf = "无数据"

                rating, avg_rate, total_ord, total_mth = calculate_comprehensive_score(freight_data)
                comprehensive_summary.append({
                    "货代": freight,
                    "综合评级": rating,
                    "加权平均准时率": round(avg_rate, 2),
                    "累计订单数": total_ord,
                    "出现月份数": total_mth,
                    "最新月份表现": latest_perf
                })

            df_comprehensive = pd.DataFrame(comprehensive_summary)

            # --- 按综合评级统计 ---
            category_count = df_comprehensive["综合评级"].value_counts()
            cate_summary = []
            if "优质" in category_count:
                cate_summary.append(f"- **优质货代**：共{category_count['优质']}个，主要表现为加权平均准时率≥90%。")
            if "合格" in category_count:
                cate_summary.append(
                    f"- **合格货代**：共{category_count['合格']}个，主要表现为加权平均准时率≥80%且<90%。")
            if "异常" in category_count:
                cate_summary.append(f"- **异常货代**：共{category_count['异常']}个，主要表现为加权平均准时率<80%。")
            if "样本不足" in category_count:
                cate_summary.append(
                    f"- **样本不足货代**：共{category_count['样本不足']}个，因订单量或出现频次过低，暂不评级。")

            st.markdown("\n".join(cate_summary))

            # --- 核心货代点评 ---
            # 排除样本不足的货代
            valid_freights = df_comprehensive[df_comprehensive["综合评级"] != "样本不足"]
            if not valid_freights.empty:
                top_freight = valid_freights.sort_values("累计订单数", ascending=False).iloc[0]
                st.markdown(
                    f">- **核心货代{top_freight['货代']}**：累计订单数最多（{top_freight['累计订单数']}单），加权平均准时率{top_freight['加权平均准时率']}%，综合评级为{top_freight['综合评级']}。")

            # --- 异常提醒 ---
            abnormal_freights = df_comprehensive[df_comprehensive["综合评级"] == "异常"]["货代"].tolist()
            if abnormal_freights:
                st.markdown(
                    f">- **异常提醒**：{','.join(abnormal_freights)}等货代加权平均准时率低于80%，且满足样本量要求，需重点关注并推动时效优化。")

            st.markdown("#### 2. 各货代详细表现（综合评级）")
            for _, row in df_comprehensive.iterrows():
                freight = row["货代"]
                rating = row["综合评级"]
                avg_rate = row["加权平均准时率"]
                total_ord = row["累计订单数"]
                total_mth = row["出现月份数"]
                latest_perf = row["最新月份表现"]

                # 归类样式和描述
                if rating == "优质":
                    color = "#2e7d32"
                    desc = "综合表现优秀，长期稳定可靠。"
                elif rating == "合格":
                    color = "#ff9800"
                    desc = "综合表现达标，仍有优化空间。"
                elif rating == "异常":
                    color = "#c62828"
                    desc = "综合表现不佳，存在较大风险。"
                else:
                    color = "#718096"
                    desc = f"样本不足（订单{total_ord}单/月份{total_mth}个），建议持续观察。"

                # 生成货代卡片（修复HTML渲染问题）
                st.markdown(f"""
                <div style='border:1px solid #e2e8f0; border-radius:6px; padding:15px; margin:10px 0; border-left:4px solid {color};'>
                  <strong style='font-size:16px; color:#1a202c;'>{freight}</strong>
                  <p style='margin:5px 0; color:{color};'>{rating} | {desc}</p>
                  <p style='margin:2px 0; font-size:14px; color:#4a5568;'>📊 加权平均准时率：{avg_rate}% | 📦 累计订单：{total_ord}单 | 📅 出现月份：{total_mth}个月</p>
                  <p style='margin:2px 0; font-size:14px; color:#4a5568;'>🔍 最新月份（{latest_month}）表现：{latest_perf}</p>
                </div>
                """, unsafe_allow_html=True)

            # ===== 9. 数据下载 =====
            # 明细数据下载
            freight_detail_csv = df_freight_display.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 下载货代月度明细数据",
                data=freight_detail_csv,
                file_name="货代月度明细数据.csv",
                mime="text/csv",
                key="freight_detail_download"
            )
            # 汇总数据下载
            freight_summary_csv = freight_category_summary.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📥 下载货代归类汇总数据",
                data=freight_summary_csv,
                file_name="货代归类汇总数据.csv",
                mime="text/csv",
                key="freight_summary_download"
            )
# ---------------------- 仓库不同月份趋势分析（终极修复版 - 无IndexError） ----------------------
st.markdown("## 🏠 仓库不同月份趋势分析")
st.divider()

# ===== 1. 数据预处理 & 列名校验 =====
WAREHOUSE_MONTH_COLUMN_MAPPING = {
    "仓库列名": "仓库",
    "到货年月列名": "到货年月",
    "提前延期列名": "提前/延期（仓库）",
    "区域列名": "区域",
}
required_warehouse_cols = [
    WAREHOUSE_MONTH_COLUMN_MAPPING["仓库列名"],
    WAREHOUSE_MONTH_COLUMN_MAPPING["到货年月列名"],
    WAREHOUSE_MONTH_COLUMN_MAPPING["提前延期列名"],
    WAREHOUSE_MONTH_COLUMN_MAPPING["区域列名"],
    "FBA号", "物流方式", "签收-完成上架"
]
missing_warehouse_cols = [col for col in required_warehouse_cols if col not in df_selected_FBA.columns]
if missing_warehouse_cols:
    st.error(f"缺少仓库月度分析必要列：{missing_warehouse_cols}")
else:
    st.markdown("### 筛选条件")
    col_logistics, col_empty = st.columns([1, 3])
    with col_logistics:
        unique_logistics = sorted(df_selected_FBA["物流方式"].dropna().unique())
        logistics_options = ["全部"] + unique_logistics
        selected_logistics = st.selectbox("物流方式", options=logistics_options, index=0, key="warehouse_selected_logistics")

    if selected_logistics == "全部":
        df_filtered_by_logistics = df_selected_FBA.copy()
    else:
        df_filtered_by_logistics = df_selected_FBA[df_selected_FBA["物流方式"] == selected_logistics].copy()

    if len(df_filtered_by_logistics) == 0:
        st.warning(f"所选物流方式「{selected_logistics}」暂无仓库数据")
    else:
        df_warehouse_month_valid = df_filtered_by_logistics[
            (df_filtered_by_logistics[WAREHOUSE_MONTH_COLUMN_MAPPING["仓库列名"]].notna()) &
            (df_filtered_by_logistics[WAREHOUSE_MONTH_COLUMN_MAPPING["到货年月列名"]].notna()) &
            (df_filtered_by_logistics[WAREHOUSE_MONTH_COLUMN_MAPPING["区域列名"]].notna())
        ].copy()

        if len(df_warehouse_month_valid) == 0:
            st.warning("暂无仓库跨月份数据可分析")
        else:
            warehouse_month_stats = df_warehouse_month_valid.groupby([
                WAREHOUSE_MONTH_COLUMN_MAPPING["到货年月列名"],
                WAREHOUSE_MONTH_COLUMN_MAPPING["仓库列名"],
                WAREHOUSE_MONTH_COLUMN_MAPPING["区域列名"]
            ]).agg(
                总订单数=("FBA号", "count"),
                提前准时订单数=(WAREHOUSE_MONTH_COLUMN_MAPPING["提前延期列名"], lambda x: len(x[x == "提前/准时"])),
                延期订单数=(WAREHOUSE_MONTH_COLUMN_MAPPING["提前延期列名"], lambda x: len(x[x == "延期"]))
            ).reset_index()

            warehouse_month_stats.rename(columns={
                WAREHOUSE_MONTH_COLUMN_MAPPING["到货年月列名"]: "到货年月",
                WAREHOUSE_MONTH_COLUMN_MAPPING["仓库列名"]: "仓库",
                WAREHOUSE_MONTH_COLUMN_MAPPING["区域列名"]: "区域"
            }, inplace=True)

            warehouse_month_stats["准时率(%)"] = round(
                warehouse_month_stats["提前准时订单数"] / warehouse_month_stats["总订单数"] * 100, 2
            )

            def get_warehouse_category(rate):
                if rate >= 90:
                    return "优质", "#2e7d32"
                elif rate >= 80:
                    return "合格", "#ff9800"
                else:
                    return "异常", "#c62828"

            warehouse_month_stats["仓库归类"] = warehouse_month_stats["准时率(%)"].apply(lambda x: get_warehouse_category(x)[0])
            warehouse_month_stats["归类颜色"] = warehouse_month_stats["准时率(%)"].apply(lambda x: get_warehouse_category(x)[1])

            # ===================== 安全日期解析 =====================
            def safe_parse_ym(ym):
                try:
                    s = str(ym).replace("年", "").replace("月", "").replace("-", "")
                    if len(s) == 6:
                        return pd.to_datetime(f"{s[:4]}-{s[4:]}-01")
                    return pd.NaT
                except:
                    return pd.NaT

            warehouse_month_stats["年月排序"] = warehouse_month_stats["到货年月"].apply(safe_parse_ym)
            warehouse_month_stats = warehouse_month_stats[warehouse_month_stats["年月排序"].notna()].copy()
            warehouse_month_stats["中文月份"] = warehouse_month_stats["年月排序"].dt.strftime("%Y年%m月")

            if len(warehouse_month_stats) == 0:
                st.warning("无有效仓库月份数据可分析")
            else:
                unique_months = sorted(warehouse_month_stats["中文月份"].unique())
                latest_month = warehouse_month_stats["年月排序"].max()

                st.markdown("#### 快捷筛选")
                quick_options = ["自定义时间", "上个月", "近三个月", "近半年", "近一年"]
                selected_quick = st.selectbox("快捷筛选", options=quick_options, index=0, key="warehouse_quick_filter")

                start_month_cn = end_month_cn = None
                if selected_quick == "上个月":
                    target = latest_month - pd.DateOffset(months=1)
                elif selected_quick == "近三个月":
                    target = latest_month - pd.DateOffset(months=2)
                elif selected_quick == "近半年":
                    target = latest_month - pd.DateOffset(months=5)
                elif selected_quick == "近一年":
                    target = latest_month - pd.DateOffset(months=11)
                else:
                    target = None

                if target is not None:
                    match = warehouse_month_stats[warehouse_month_stats["年月排序"] == target]
                    if not match.empty:
                        start_month_cn = match["中文月份"].iloc[0]
                    else:
                        start_month_cn = unique_months[0]
                    end_match = warehouse_month_stats[warehouse_month_stats["年月排序"] == latest_month]
                    end_month_cn = end_match["中文月份"].iloc[0] if not end_match.empty else unique_months[-1]

                if start_month_cn is None or end_month_cn is None:
                    st.markdown("#### 自定义时间范围")
                    col_start, col_end = st.columns(2)
                    with col_start:
                        start_month_cn = st.selectbox("开始月份", options=unique_months, index=0, key="warehouse_start")
                    with col_end:
                        end_month_cn = st.selectbox("结束月份", options=unique_months, index=len(unique_months)-1, key="warehouse_end")

                # ===================== 安全日期转换 =====================
                start_dt = warehouse_month_stats[warehouse_month_stats["中文月份"] == start_month_cn]["年月排序"].iloc[0]
                end_dt = warehouse_month_stats[warehouse_month_stats["中文月份"] == end_month_cn]["年月排序"].iloc[0]

                df_warehouse_filtered = warehouse_month_stats[
                    (warehouse_month_stats["年月排序"] >= start_dt) &
                    (warehouse_month_stats["年月排序"] <= end_dt)
                ].copy()

                REGION_ORDER = ["美东", "美中", "美西"]
                df_warehouse_filtered["区域排序"] = df_warehouse_filtered["区域"].map({r:i for i,r in enumerate(REGION_ORDER)})
                df_warehouse_filtered = df_warehouse_filtered.sort_values(["区域排序","总订单数"], ascending=[True,False]).reset_index(drop=True)

                if len(df_warehouse_filtered) == 0:
                    st.warning("所选时间范围内无仓库数据")
                else:
                    # ===================== 1. 三列明细 =====================
                    st.markdown("### 仓库月度核心指标明细（按区域）")
                    col_e, col_m, col_w = st.columns(3)
                    display_cols = ["中文月份", "仓库", "总订单数", "提前准时订单数", "延期订单数", "准时率(%)", "仓库归类"]
                    for i, region in enumerate(REGION_ORDER):
                        df_r = df_warehouse_filtered[df_warehouse_filtered["区域"] == region]
                        with [col_e, col_m, col_w][i]:
                            st.markdown(f"#### {region}")
                            if df_r.empty:
                                st.info("暂无数据")
                            else:
                                st.dataframe(df_r[display_cols], use_container_width=True, hide_index=True)

                    # ===================== 2. 三列汇总 =====================
                    st.markdown("### 仓库归类结果汇总（按区域）")
                    col_es, col_ms, col_ws = st.columns(3)
                    for i, region in enumerate(REGION_ORDER):
                        df_r = df_warehouse_filtered[df_warehouse_filtered["区域"] == region]
                        with [col_es, col_ms, col_ws][i]:
                            st.markdown(f"#### {region}")
                            if df_r.empty:
                                st.info("暂无数据")
                            else:
                                s = df_r.groupby(["仓库","仓库归类"]).agg(
                                    涉及月份数=("到货年月","nunique"),累计订单数=("总订单数","sum"),平均准时率=("准时率(%)","mean")
                                ).reset_index()
                                s["平均准时率"] = round(s["平均准时率"],2)
                                st.dataframe(s, use_container_width=True, hide_index=True)

                    # ===================== 趋势图（已修复空值判断） =====================
                    st.markdown("### 仓库月度趋势分析")
                    search_warehouse = st.text_input("搜索仓库", placeholder="输入仓库名", key="search_warehouse")
                    unique_warehouses = df_warehouse_filtered["仓库"].unique().tolist()

                    # 🔥 修复点：确保永远是列表，永远不为空
                    if search_warehouse.strip():
                        filtered_warehouses = [w for w in unique_warehouses if search_warehouse.strip() in w]
                    else:
                        filtered_warehouses = unique_warehouses.copy()

                    if len(filtered_warehouses) > 0:
                        selected_warehouse = st.selectbox("选择仓库", filtered_warehouses, index=0, key="selected_warehouse")
                        df_trend = df_warehouse_filtered[df_warehouse_filtered["仓库"] == selected_warehouse].sort_values("年月排序")
                        if not df_trend.empty:
                            import plotly.graph_objects as go
                            fig = go.Figure()
                            fig.add_trace(go.Bar(x=df_trend["中文月份"],y=df_trend["总订单数"],name="总订单数",marker_color="#4299e1"))
                            fig.add_trace(go.Bar(x=df_trend["中文月份"],y=df_trend["提前准时订单数"],name="准时",marker_color="#48bb78"))
                            fig.add_trace(go.Bar(x=df_trend["中文月份"],y=df_trend["延期订单数"],name="延期",marker_color="#e53e3e"))
                            fig.add_trace(go.Scatter(x=df_trend["中文月份"],y=df_trend["准时率(%)"],name="准时率",yaxis="y2",marker_color="#9f7aea",mode="lines+markers+text"))
                            fig.update_layout(yaxis2=dict(overlaying="y",side="right",range=[0,100]),height=450,barmode="group")
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("暂无匹配仓库数据")

                    # ===================== 3. 三列仓库卡片 =====================
                    st.markdown("### 各仓库详细表现（按区域：美东→美中→美西）")
                    total_orders = df_warehouse_filtered["总订单数"].sum()
                    wh_summary = []
                    for wh in df_warehouse_filtered["仓库"].unique():
                        d = df_warehouse_filtered[df_warehouse_filtered["仓库"] == wh]
                        region = d["区域"].iloc[0]
                        total = d["总订单数"].sum()
                        avg_rate = (d["准时率(%)"] * d["总订单数"]).sum() / total if total > 0 else 0
                        months = len(d)
                        latest = d.sort_values("年月排序", ascending=False).iloc[0]["仓库归类"]
                        avg_days = df_warehouse_month_valid[df_warehouse_month_valid["仓库"] == wh]["签收-完成上架"].mean()
                        wh_summary.append({
                            "仓库": wh, "区域": region,
                            "综合评级": "优质" if avg_rate>=90 else "合格" if avg_rate>=80 else "异常",
                            "加权平均准时率": round(avg_rate,2),
                            "累计订单数": total,
                            "订单占比(%)": round(total/total_orders*100,2),
                            "出现月份数": months,
                            "最新表现": latest,
                            "平均上架时效": round(avg_days,1) if pd.notna(avg_days) else 0
                        })

                    df_summary = pd.DataFrame(wh_summary)
                    df_summary["区域排序"] = df_summary["区域"].map({r:i for i,r in enumerate(REGION_ORDER)})
                    df_summary = df_summary.sort_values(["区域排序","订单占比(%)"], ascending=[True,False]).reset_index(drop=True)

                    col_ecard, col_mcard, col_wcard = st.columns(3)
                    for i, region in enumerate(REGION_ORDER):
                        df_r = df_summary[df_summary["区域"] == region]
                        with [col_ecard, col_mcard, col_wcard][i]:
                            st.markdown(f"#### {region}")
                            if df_r.empty:
                                st.info("暂无数据")
                            else:
                                for _, row in df_r.iterrows():
                                    color = "#2e7d32" if row["综合评级"] == "优质" else "#ff9800" if row["综合评级"] == "合格" else "#c62828"
                                    st.markdown(f"""
                                    <div style='border:1px solid #e2e8f0; border-radius:6px; padding:12px; margin:8px 0; border-left:4px solid {color};'>
                                    <strong>{row['仓库']}</strong><br>
                                    {row['综合评级']} | 准时率 {row['加权平均准时率']}%<br>
                                    订单：{row['累计订单数']}单 ({row['订单占比(%)']}%)<br>
                                    平均时效：{row['平均上架时效']}天
                                    </div>
                                    """, unsafe_allow_html=True)

                    # 数据下载
                    st.markdown("### 数据下载")
                    c1,c2 = st.columns(2)
                    with c1:
                        st.download_button("下载明细", df_warehouse_filtered.to_csv(index=False,encoding="utf-8-sig"), "仓库月度明细.csv")
                    with c2:
                        st.download_button("下载汇总", df_summary.to_csv(index=False,encoding="utf-8-sig"), "仓库表现汇总.csv")

#物流成本分析区域
st.title("📊 物流成本分析")

# 1. 加载成本数据
@st.cache_data(show_spinner="加载成本数据中...")
def load_cost_data():
    url = "https://raw.githubusercontent.com/Jane-zzz-123/Logistics/main/CAE.xlsx"
    df_cost = pd.read_excel(url, sheet_name="数据")

    need_cols = ["周期", "月份", "目的仓", "仓库", "区域", "实际物流方式", "货代", "货代渠道", "重量", "报关费","运输方式",
                 "总费用", "总运费", "入库配置费折算RMB"]
    df_cost = df_cost[[col for col in need_cols if col in df_cost.columns]]

    # 必须字段
    df_cost = df_cost.dropna(subset=["周期", "实际物流方式", "重量"])
    df_cost = df_cost[(df_cost["重量"] > 0)]

    # 填充缺失费用为0
    for c in ["总费用", "总运费", "入库配置费折算RMB"]:
        if c in df_cost.columns:
            df_cost[c] = pd.to_numeric(df_cost[c], errors="coerce").fillna(0)
        else:
            df_cost[c] = 0

    # 重新计算总费用（确保 = 运费+入库费）
    df_cost["总费用"] = df_cost["总运费"] + df_cost["入库配置费折算RMB"]

    df_cost["周期"] = pd.to_numeric(df_cost["周期"], errors="coerce").astype(int)
    df_cost["月份"] = pd.to_numeric(df_cost["月份"], errors="coerce").astype(int)
    df_cost = df_cost.sort_values("周期").reset_index(drop=True)
    return df_cost

df_cost = load_cost_data()

# ====================== 自定义颜色映射 ======================
color_map = {
    "空派": "#1f77b4",        # 蓝色
    "以星特快": "#2ca02c",    # 绿色
    "以星": "#ff7f0e",        # 橙色
    "正班": "#7f7f7f",        # 灰色
    "普船": "#ffdd00"         # 黄色
}
default_color = "#9467bd"

# ====================== 切换：按月份 / 按周期 ======================
view_mode = st.radio("筛选维度", ["按周期", "按月份"], horizontal=True)

# ====================== 筛选面板 ======================
with st.expander("🔎 筛选条件", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        if view_mode == "按周期":
            period_list = sorted(df_cost["周期"].unique())
            max_p = max(period_list) if len(period_list) else 0
            default_val = [p for p in period_list if p >= max_p - 3] if len(period_list) >=4 else period_list
            selected = st.multiselect("周期", period_list, default=default_val)
        else:
            month_list = sorted(df_cost["月份"].dropna().unique())
            default_val = month_list[-3:] if len(month_list) >= 3 else month_list
            selected = st.multiselect("月份", month_list, default=default_val)

    with col2:
        area_list = ["全部"] + sorted(df_cost["区域"].dropna().unique())
        selected_area = st.selectbox("区域", area_list)

# ====================== 费用说明 ======================
st.markdown("""
<div style="background-color:#f7fafc; padding:12px 16px; border-radius:8px; font-size:14px; line-height:1.6;">
<b>📌 费用计算公式说明：</b><br>
• 运费 = 账单运费 + 附加费 + 运费税点<br>
• 总运费 = 报关费 + 报关费税点 + 运费<br>
• 入库配置费折算RMB = 入库配置费单价（美元） × 汇率<br>
• 总费用 = 总运费 + 入库配置费折算RMB
</div>
""", unsafe_allow_html=True)
# ====================== 数据筛选 ======================
df = df_cost.copy()
if view_mode == "按周期":
    df = df[df["周期"].isin(selected)] if selected else df
else:
    df = df[df["月份"].isin(selected)] if selected else df

if selected_area != "全部":
    df = df[df["区域"] == selected_area]

if df.empty:
    st.warning("无数据")
    st.stop()

group_col = "周期" if view_mode == "按周期" else "月份"

# ====================== 统一计算函数（总费用/总运费/入库费 逻辑完全一样） ======================
def calc_summary(df, value_col):
    df_sum = df.groupby([group_col, "实际物流方式"], as_index=False).agg(
        总重量=("重量", "sum"),
        总金额=(value_col, "sum")
    )
    df_sum["折算单价"] = (df_sum["总金额"] / df_sum["总重量"]).round(4)
    df_sum = df_sum.sort_values(["实际物流方式", group_col]).reset_index(drop=True)

    # 环比
    df_sum["上周单价"] = df_sum.groupby("实际物流方式")["折算单价"].shift(1)
    df_sum["环比差值"] = (df_sum["折算单价"] - df_sum["上周单价"]).round(2)
    df_sum["环比幅度"] = np.where(
        df_sum["上周单价"] > 0,
        (df_sum["环比差值"] / df_sum["上周单价"] * 100).round(2),
        0
    )
    return df_sum

# 计算三个指标
df_total = calc_summary(df, "总费用")
df_freight = calc_summary(df, "总运费")
df_storage = calc_summary(df, "入库配置费折算RMB")

all_logistics = sorted(df_cost["实际物流方式"].unique())
sorted_values = sorted(df_total[group_col].unique()) if len(df_total) else []
latest = max(selected) if selected else (sorted_values[-1] if len(sorted_values) else 0)

# ====================== 一行三列布局 ======================
col_left, col_mid, col_right = st.columns(3)

# ====================== 渲染函数（三个指标共用一套UI） ======================
def render_analysis(col, title, df_sum, latest):
    with col:
        st.markdown(f"### {title}")
        latest_data = df_sum[df_sum[group_col] == latest].copy()
        all_logi = sorted(df_cost["实际物流方式"].unique())

        # 总结
        st.markdown("##### 📝 成本变化")
        html = ""
        for logi in all_logi:
            row = latest_data[latest_data["实际物流方式"] == logi]
            if row.empty:
                html += f"<div>• {logi}：无数据</div>"
                continue
            price = row["折算单价"].iloc[0]
            diff = row["环比差值"].iloc[0]
            pct = row["环比幅度"].iloc[0]
            if pd.isna(diff):
                html += f"<div>• <b>{logi}</b>：¥{price:.2f}（首期）</div>"
            elif diff > 0:
                html += f"<div style='color:red'>• <b>{logi}</b>：↑ ¥{diff:.2f}（+{pct:.2f}%）单价 ¥{price:.2f}</div>"
            else:
                html += f"<div style='color:green'>• <b>{logi}</b>：↓ ¥{abs(diff):.2f}（{pct:.2f}%）单价 ¥{price:.2f}</div>"
        st.markdown(html, unsafe_allow_html=True)

        # 趋势图
        st.markdown("##### 📈 单价趋势")
        df_sum["x_str"] = df_sum[group_col].astype(str)
        cmap = {k: color_map.get(k, default_color) for k in all_logi}
        fig = px.line(df_sum, x="x_str", y="折算单价", color="实际物流方式",
                      color_discrete_map=cmap, markers=True)
        fig.update_traces(text=df_sum["折算单价"].round(2), textposition="top center")
        fig.update_xaxes(type="category")
        st.plotly_chart(fig, use_container_width=True)

        # 统计表
        st.markdown("##### 📋 单价统计表")
        data_map = {(str(r[group_col]), r["实际物流方式"]): r for _, r in df_sum.iterrows()}
        table = "<table style='width:100%;border-collapse:collapse;font-size:12px;text-align:center'>"
        table += f"<tr style='background:#f0f2f6'><td>{group_col}</td>"
        for l in all_logi:
            table += f"<td style='border:1px solid #ddd;padding:4px'>{l}</td>"
        table += "</tr>"
        for v in sorted_values:
            table += f"<tr><td style='border:1px solid #ddd'>{v}</td>"
            for logi in all_logi:
                key = (str(v), logi)
                if key not in data_map:
                    table += "<td style='border:1px solid #ddd'>-</td>"
                    continue
                r = data_map[key]
                price = r["折算单价"]
                diff = r["环比差值"]
                pct = r["环比幅度"]
                if pd.isna(diff):
                    txt, color = "首期", "#888"
                else:
                    sign = "+" if diff > 0 else ""
                    txt = f"{sign}{diff:.2f} ({sign}{pct:.2f}%)"
                    color = "red" if diff > 0 else "green"
                cell = f"{price:.2f}<br><small style='color:{color}'>{txt}</small>"
                table += f"<td style='border:1px solid #ddd;padding:4px'>{cell}</td>"
            table += "</tr>"
        table += "</table>"
        st.markdown(table, unsafe_allow_html=True)

# ====================== 分别渲染三列 ======================
render_analysis(col_left, "💰 总费用", df_total, latest)
render_analysis(col_mid, "🚚 总运费", df_freight, latest)
render_analysis(col_right, "📦 入库配置费", df_storage, latest)

st.caption("🔴 单价上升｜🟢 单价下降｜单价 = 总金额 ÷ 总重量")

# ====================== 🧾 报关费分析（受上方筛选控制 · 按运输方式 · 总金额） ======================
st.markdown("---")
st.title("🧾 报关费分析")

# 核心：直接继承上方的筛选维度，不再额外显示按钮
group_col = "周期" if view_mode == "按周期" else "月份"

# 核心：使用筛选后的 df，受上方筛选控制 | 按【运输方式】分组
def calculate_customs(df_filtered, group_col):
    # 按 周期/月份 + 运输方式 汇总报关费总金额
    df_cus = df_filtered.groupby([group_col, "运输方式"], as_index=False).agg(
        报关费=("报关费", "sum")
    )
    df_cus = df_cus.sort_values([group_col, "运输方式"]).reset_index(drop=True)

    # 环比
    df_cus["上期金额"] = df_cus.groupby("运输方式")["报关费"].shift(1)
    df_cus["环比差值"] = (df_cus["报关费"] - df_cus["上期金额"]).round(2)
    df_cus["环比幅度"] = np.where(
        df_cus["上期金额"] > 0,
        (df_cus["环比差值"] / df_cus["上期金额"] * 100).round(2),
        0
    )
    return df_cus

# 关键：使用筛选后的 df，完全跟随上方筛选器变化
df_customs = calculate_customs(df, group_col)

# ====================== 折线图 ======================
st.subheader("📈 报关费总金额趋势")
df_customs["x_str"] = df_customs[group_col].astype(str)

fig_cus = px.line(
    df_customs,
    x="x_str",
    y="报关费",
    color="运输方式",
    color_discrete_map=color_map,
    markers=True
)
fig_cus.update_traces(
    text=df_customs["报关费"].round(2),
    textposition="top center"
)
fig_cus.update_xaxes(type="category")
st.plotly_chart(fig_cus, use_container_width=True)

# ====================== 统计表 ======================
st.subheader("📋 报关费总金额统计表（带环比）")
data_map = {(str(r[group_col]), r["运输方式"]): r for _, r in df_customs.iterrows()}
trans_list = sorted(df["运输方式"].dropna().unique())
val_list = sorted(df_customs[group_col].unique())

table_html = f"<table style='width:100%;border-collapse:collapse;text-align:center;font-size:14px;'>"
table_html += f"<tr style='background:#f0f2f6;font-weight:bold'><td>{group_col}</td>"
for t in trans_list:
    table_html += f"<td style='border:1px solid #ddd;padding:8px'>{t}</td>"
table_html += "</tr>"

for val in val_list:
    table_html += f"<tr><td style='border:1px solid #ddd;padding:8px'>{val}</td>"
    for t in trans_list:
        key = (str(val), t)
        if key not in data_map:
            table_html += "<td style='border:1px solid #ddd'>-</td>"
            continue
        r = data_map[key]
        amount = r["报关费"]
        diff = r["环比差值"]
        pct = r["环比幅度"]

        if pd.isna(diff):
            txt = "首期"
            color = "#888"
        else:
            sign = "+" if diff > 0 else ""
            txt = f"{sign}{diff:.2f} ({sign}{pct:.2f}%)"
            color = "#ff4b4b" if diff > 0 else "#00b578"

        cell = f"<div>{amount:.2f}</div><div style='font-size:12px;color:{color}'>{txt}</div>"
        table_html += f"<td style='border:1px solid #ddd;padding:8px'>{cell}</td>"
    table_html += "</tr>"
table_html += "</table>"

st.markdown(table_html, unsafe_allow_html=True)
st.caption("📌 红色=上升 | 绿色=下降 | 数值为报关费总金额")

# ===================== 数据源链接展示（直接打开/下载） =====================
st.subheader("📋 原始数据源（点击链接直接访问）")

# 你的Excel文件直链
data_source_url = "https://github.com/Jane-zzz-123/Logistics/raw/main/Logisticsdata.xlsx"

# 美化的链接展示（大字体、醒目颜色）
st.markdown(f"""
<div style='background-color: #f0f8fb; padding: 20px; border-radius: 10px; margin: 10px 0;'>
    <p style='font-size: 16px; color: #2d3748; margin: 0 0 10px;'>📌 数据源文件地址：</p>
    <a href='{data_source_url}' target='_blank' style='font-size: 18px; color: #4299e1; font-weight: bold; text-decoration: none;'>
        {data_source_url}
    </a>
    <p style='font-size: 14px; color: #718096; margin: 10px 0 0;'>
        💡 点击链接可直接打开/下载Excel文件 | 建议复制链接到浏览器打开
    </p>
</div>
""", unsafe_allow_html=True)

# 补充提示（方便看板人员操作）
st.caption("✅ 操作说明：")
st.caption("1. 点击链接 → 浏览器会直接打开Excel文件（部分浏览器）或自动下载")
st.caption("2. 若链接无法打开，复制链接到Chrome/Firefox浏览器地址栏访问")
st.caption("3. 文件格式：XLSX | 可直接用Excel/WPS打开校验数据")