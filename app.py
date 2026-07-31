from __future__ import annotations

from datetime import datetime, timedelta
import time

import extra_streamlit_components as stx
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components
from streamlit_plotly_events import plotly_events

from twstock_lab.analysis import analyze_stock
from twstock_lab.backtest import BacktestConfig, monte_carlo, run_backtest
from twstock_lab.cloud_storage import (
    AUTH_SESSION_SECONDS,
    SupabaseClient,
    SupabasePortfolioStore,
    sign_session_token,
    verify_session_token,
)
from twstock_lab.changelog import CHANGELOG, CURRENT_VERSION
from twstock_lab.indicators import add_indicators
from twstock_lab.models import StockAnalysisRequest
from twstock_lab.market_clock import market_clock
from twstock_lab.portfolio import PortfolioItem, PortfolioStore, SessionPortfolioStore, holding_action
from twstock_lab.providers import HybridTaiwanProvider
from twstock_lab.statistics import win_rate_test

UP_COLOR = "#ff4d4f"
DOWN_COLOR = "#22c55e"

st.set_page_config(page_title="台股智慧分析室", page_icon="📈", layout="wide")
st.markdown("""
<style>
.stApp {
  background:
    radial-gradient(circle at 10% 10%, rgba(46, 196, 182, .16), transparent 30%),
    radial-gradient(circle at 90% 5%, rgba(59, 130, 246, .18), transparent 32%),
    linear-gradient(135deg, #09111f 0%, #111b2e 52%, #0a1222 100%);
}
[data-testid="stSidebar"] {
  background: rgba(10, 20, 36, .72);
  backdrop-filter: blur(20px);
  border-right: 1px solid rgba(255,255,255,.10);
}
[data-testid="stSidebar"] h2 {
  margin-bottom:.1rem !important;
  font-size:1.35rem !important;
}
.st-key-sidebar_nav [data-testid="stVerticalBlock"] {
  gap:.55rem !important;
}
.st-key-sidebar_nav .stButton > button {
  width:100%;
  min-height:52px;
  max-height:52px;
  padding:.55rem .9rem;
  border-radius:14px;
  justify-content:flex-start;
  background:rgba(255,255,255,.045);
  border-color:rgba(148,163,184,.28);
  box-shadow:none;
  transition:transform .16s ease, background .16s ease, border-color .16s ease;
}
.st-key-sidebar_nav .stButton > button:hover {
  transform:translateX(3px);
  background:rgba(56,189,248,.12);
  border-color:rgba(125,211,252,.55);
}
.st-key-sidebar_nav .stButton > button[kind="primary"] {
  background:linear-gradient(100deg,rgba(14,165,233,.28),rgba(99,102,241,.22));
  border-color:rgba(125,211,252,.65);
  box-shadow:inset 3px 0 0 #38bdf8,0 8px 22px rgba(2,132,199,.12);
}
.st-key-sidebar_nav .stButton p {
  width:100%;
  text-align:left;
  font-size:1rem;
  font-weight:700;
  white-space:nowrap;
}
[data-testid="stAppViewContainer"] > .main .block-container {
  width:100%;
  max-width:none;
  padding-top: 1.35rem;
  padding-left:clamp(1rem,2.2vw,2rem);
  padding-right:clamp(1rem,2.2vw,2rem);
  padding-bottom: 4rem;
}
[data-testid="stAppViewContainer"] > .main [data-testid="stVerticalBlock"] {gap:.85rem;}
[data-testid="stHorizontalBlock"] {align-items:stretch;}
h1 {font-size:clamp(2.1rem, 4vw, 3.5rem) !important; line-height:1.08 !important;}
h2 {font-size:clamp(1.5rem, 2.4vw, 2rem) !important;}
h3 {font-size:clamp(1.15rem, 1.8vw, 1.5rem) !important;}
[data-testid="stMetric"], [data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(255,255,255,.065);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 18px;
  box-shadow: 0 12px 35px rgba(0,0,0,.16);
  backdrop-filter: blur(18px);
}
[data-testid="stMetric"] {
  height:118px;
  min-height:118px;
  padding:12px 14px;
  display:flex;
  flex-direction:column;
  justify-content:center;
}
[data-testid="stMetricLabel"] {min-height:1.55rem;}
[data-testid="column"] {min-width:0;}
[data-baseweb="tab-list"] {gap:.35rem; overflow-x:auto; scrollbar-width:thin;}
[data-baseweb="tab"] {min-height:44px; white-space:nowrap; padding-left:1rem; padding-right:1rem;}
[data-testid="stSegmentedControl"] {
  padding:.3rem; border-radius:14px;
  background:rgba(255,255,255,.045);
  border:1px solid rgba(148,163,184,.18);
}
[data-testid="stSegmentedControl"] button {min-height:42px;}
[data-testid="stCaptionContainer"] {line-height:1.45;}
[data-testid="stForm"] {border-radius:16px; border:1px solid rgba(255,255,255,.10); padding:1rem;}
[data-testid="stExpander"] {border-radius:14px !important; overflow:hidden;}
[data-testid="stToggle"] {
  padding:.7rem 1rem;
  border:1px solid rgba(125,211,252,.28);
  border-radius:16px;
  background:linear-gradient(90deg,rgba(14,165,233,.12),rgba(99,102,241,.10));
  backdrop-filter:blur(14px);
}
[data-testid="stToggle"] label {font-weight:700;}
.st-key-beginner_assist [data-testid="stCheckbox"] {
  width:100%;
  min-height:50px;
  padding:.45rem .55rem;
  border-radius:14px;
  background:linear-gradient(90deg,rgba(14,165,233,.12),rgba(99,102,241,.10));
  border:1px solid rgba(125,211,252,.28);
}
.st-key-beginner_assist [data-testid="stCheckbox"] > label {
  min-height:34px;
  align-items:center;
}
.st-key-beginner_assist [data-testid="stCheckbox"] > label > div:nth-of-type(1) {
  transform:scale(1.12);
  transform-origin:left center;
  margin-right:8px;
  flex-shrink:0;
}
.st-key-beginner_assist [data-testid="stWidgetLabel"] {
  align-items:center;
  gap:.45rem;
}
.st-key-beginner_assist [data-testid="stWidgetLabel"] p {
  font-size:16px !important;
  line-height:1.3 !important;
  font-weight:800 !important;
  white-space:normal !important;
}
.st-key-beginner_assist [data-testid="stTooltipIcon"],
.st-key-beginner_assist [data-testid="stTooltipHoverTarget"] {
  width:18px !important;
  height:18px !important;
}
.st-key-beginner_assist [data-testid="stTooltipIcon"] svg {
  width:18px !important;
  height:18px !important;
}
.beginner-strip {
  padding:12px 16px; margin:6px 0 14px; border-radius:14px;
  color:#dbeafe; background:rgba(30,64,175,.16);
  border:1px solid rgba(96,165,250,.32);
}
.stButton > button {
  width: 100%;
  min-height: 44px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,.15);
  background: rgba(255,255,255,.07);
}
.advice-card {padding: 16px 18px; border-radius: 16px; margin: 8px 0; backdrop-filter: blur(14px);}
.advice-green {background: rgba(16,185,129,.16); border: 1px solid rgba(52,211,153,.6);}
.advice-yellow {background: rgba(245,158,11,.16); border: 1px solid rgba(251,191,36,.65);}
.advice-red {background: rgba(239,68,68,.16); border: 1px solid rgba(248,113,113,.65);}
.small-muted {opacity:.72; font-size:.88rem;}
.portfolio-head {font-size:.78rem; opacity:.62; padding:2px 4px 6px; white-space:nowrap;}
.portfolio-cell {padding:7px 4px 2px; line-height:1.25; white-space:nowrap;}
.portfolio-cell.right {text-align:right; font-variant-numeric:tabular-nums;}
.portfolio-name {font-weight:700; overflow:hidden; text-overflow:ellipsis;}
.portfolio-action {font-size:.86rem; overflow:hidden; text-overflow:ellipsis;}
.portfolio-section-title {
  display:flex; align-items:center; justify-content:space-between;
  margin:.2rem 0 .65rem; color:#e2e8f0;
}
.portfolio-section-title span {font-size:.82rem; opacity:.65; font-weight:400;}
.portfolio-card-meta {
  margin-top:.55rem; padding:.65rem .8rem; border-radius:12px;
  font-size:.9rem; line-height:1.45;
}
.portfolio-card-meta.advice-green {background:rgba(16,185,129,.12);}
.portfolio-card-meta.advice-yellow {background:rgba(245,158,11,.12);}
.portfolio-card-meta.advice-red {background:rgba(239,68,68,.12);}
.portfolio-card-meta .reason {display:block; margin-top:.18rem; opacity:.76; font-size:.82rem;}
.portfolio-card-meta .level {font-weight:750;}
.result-count {
  padding:.45rem .7rem; border-radius:10px;
  background:rgba(56,189,248,.08); border:1px solid rgba(125,211,252,.18);
  color:#bae6fd; font-size:.84rem;
}
.trend-card {
  padding:14px 16px; border-radius:15px; margin:.2rem 0 .7rem;
  line-height:1.55; backdrop-filter:blur(14px);
}
.trend-card .title {font-size:1.08rem; font-weight:800;}
.trend-card .detail {margin-top:.22rem; font-size:.88rem; opacity:.82;}
.trend-bull {background:rgba(239,68,68,.13); border:1px solid rgba(248,113,113,.5);}
.trend-bear {background:rgba(34,197,94,.13); border:1px solid rgba(74,222,128,.5);}
.trend-neutral {background:rgba(245,158,11,.13); border:1px solid rgba(251,191,36,.5);}
.hot-rank-card {
  width:100%;
  height:82px;
  min-height:82px;
  max-height:82px;
  box-sizing:border-box;
  display:flex;
  flex-direction:column;
  justify-content:center;
  overflow:hidden;
  padding:.65rem .8rem;
  margin:.35rem 0;
  border:1px solid rgba(148,163,184,.22);
  border-radius:14px;
  background:rgba(255,255,255,.045);
}
.hot-rank-card .rank-line {
  display:flex;
  justify-content:space-between;
  align-items:baseline;
  gap:.65rem;
}
.hot-rank-card .stock-name {
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-weight:750;
}
.hot-rank-card .change-up {color:#ff7b7d;font-weight:800;white-space:nowrap;}
.hot-rank-card .change-down {color:#4ade80;font-weight:800;white-space:nowrap;}
.hot-rank-card .change-flat {color:#facc15;font-weight:800;white-space:nowrap;}
.hot-rank-card .rank-meta {
  margin-top:.2rem;
  color:rgba(226,232,240,.68);
  font-size:.78rem;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
}
[class*="st-key-hot-"] .stButton > button {
  height:44px;
  min-height:44px;
  max-height:44px;
}
.rooteat-easter-egg {
  position:fixed;
  right:22px;
  bottom:76px;
  z-index:999;
  text-align:right;
  color:rgba(226,232,240,.42);
  user-select:none;
}
.rooteat-easter-egg summary {
  list-style:none;
  cursor:pointer;
  font-family:"Brush Script MT","Segoe Script","Lucida Handwriting",cursive;
  font-size:2rem;
  font-style:italic;
  line-height:1;
  letter-spacing:.04em;
  transform:rotate(-5deg);
  transition:color .25s ease, text-shadow .25s ease, transform .25s ease;
}
.rooteat-easter-egg summary::-webkit-details-marker {display:none;}
.rooteat-easter-egg summary:hover,
.rooteat-easter-egg[open] summary {
  color:#7dd3fc;
  text-shadow:0 0 8px rgba(56,189,248,.65),0 0 22px rgba(99,102,241,.55);
  transform:rotate(-3deg) scale(1.08);
}
.rooteat-easter-egg span {
  display:inline-block;
  margin-top:.45rem;
  padding:.45rem .7rem;
  border:1px solid rgba(125,211,252,.28);
  border-radius:10px;
  color:#dbeafe;
  background:rgba(9,17,31,.88);
  box-shadow:0 8px 24px rgba(0,0,0,.28);
  font-size:.76rem;
}
@media (min-width: 900px) {
  [data-testid="stSidebar"] {width:320px !important; min-width:320px !important; max-width:320px !important;}
  [data-testid="stSidebar"] > div:first-child {width:320px !important;}
}
@media (max-width: 899px) {
  [data-testid="stAppViewContainer"] > .main .block-container {padding-left:1rem; padding-right:1rem;}
  .portfolio-head {display:none;}
  .portfolio-cell {white-space:normal; font-size:.88rem;}
  [data-testid="stMetric"] {height:108px; min-height:108px; padding:10px 12px;}
  [data-testid="stSegmentedControl"] {overflow-x:auto;}
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_provider(cache_version: str) -> HybridTaiwanProvider:
    # The version participates in Streamlit's resource-cache key so deployments
    # never retain a provider instance created from older parsing logic.
    _ = cache_version
    return HybridTaiwanProvider()


def public_demo_mode() -> bool:
    try:
        host = str(st.context.headers.get("Host", "")).lower()
    except Exception:
        host = ""
    try:
        configured = bool(st.secrets.get("PUBLIC_DEMO_MODE", False))
    except Exception:
        configured = False
    return configured or host.endswith(".streamlit.app")


@st.cache_resource
def get_local_portfolio_store() -> PortfolioStore:
    return PortfolioStore()


def get_portfolio_store():
    if public_demo_mode():
        cloud = get_cloud_client()
        user = st.session_state.get("cloud_user")
        if cloud is not None and user:
            return SupabasePortfolioStore(cloud, user["id"])
        return SessionPortfolioStore(st.session_state)
    return get_local_portfolio_store()


@st.cache_resource
def get_cloud_client() -> SupabaseClient | None:
    try:
        url = str(st.secrets.get("SUPABASE_URL", "")).strip()
        key = str(st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")).strip()
    except Exception:
        return None
    return SupabaseClient(url, key) if url and key else None


AUTH_COOKIE_NAME = "twstock_auth"
AUTH_COOKIE_REFRESH_SECONDS = 5 * 60
_AUTH_COOKIE_MANAGER = stx.CookieManager(key="twstock-auth-cookie-manager")


def get_auth_cookie_secret() -> str:
    try:
        return str(st.secrets.get("AUTH_COOKIE_SECRET", "")).strip()
    except Exception:
        return ""


def auth_cookie_manager() -> stx.CookieManager:
    return _AUTH_COOKIE_MANAGER


def render_page_header(caption: str) -> None:
    title_col, changelog_col = st.columns([5, 1.35], vertical_alignment="top")
    with title_col:
        st.title("台股智慧分析室")
        st.caption(caption)
    with changelog_col:
        with st.popover("📝 更新日誌", use_container_width=True):
            st.markdown("### 更新日誌")
            st.caption(f"目前版本：{CURRENT_VERSION}")
            for index, release in enumerate(CHANGELOG):
                with st.expander(
                    f"{release.version}｜{release.title}",
                    expanded=index == 0,
                ):
                    for change in release.changes:
                        st.markdown(f"- {change}")
        st.caption(CURRENT_VERSION)
    st.markdown(
        '<details class="rooteat-easter-egg">'
        '<summary title="作者留下的小彩蛋">Rooteat</summary>'
        '<span>Found it ✦ Designed &amp; crafted by Rooteat</span>'
        '</details>',
        unsafe_allow_html=True,
    )


def save_auth_cookie(user: dict[str, str], *, force: bool = False) -> None:
    secret = get_auth_cookie_secret()
    if not secret:
        return
    now = int(time.time())
    last_refresh = int(st.session_state.get("_auth_cookie_refreshed_at", 0))
    if not force and now - last_refresh < AUTH_COOKIE_REFRESH_SECONDS:
        return
    token = sign_session_token(user["id"], user["username"], secret, now=now)
    auth_cookie_manager().set(
        AUTH_COOKIE_NAME,
        token,
        key="twstock-auth-cookie-set",
        max_age=AUTH_SESSION_SECONDS,
        secure=public_demo_mode(),
        same_site="lax",
    )
    st.session_state["_auth_cookie_refreshed_at"] = now


def clear_auth_cookie() -> None:
    manager = auth_cookie_manager()
    if manager.get(AUTH_COOKIE_NAME) is not None:
        manager.delete(AUTH_COOKIE_NAME, key="twstock-auth-cookie-delete")
    st.session_state.pop("_auth_cookie_refreshed_at", None)


def restore_auth_cookie() -> None:
    client = get_cloud_client()
    secret = get_auth_cookie_secret()
    if client is None or not secret:
        return
    current = st.session_state.get("cloud_user")
    if current:
        save_auth_cookie(current)
        return
    token = auth_cookie_manager().get(AUTH_COOKIE_NAME)
    if not token:
        return
    restored = verify_session_token(token, secret)
    if restored is None:
        clear_auth_cookie()
        return
    user = client.get_user(str(restored["id"]), str(restored["username"]))
    if user is None:
        clear_auth_cookie()
        return
    st.session_state.cloud_user = {"id": user.id, "username": user.username}
    save_auth_cookie(st.session_state.cloud_user, force=True)


def render_cloud_login() -> None:
    client = get_cloud_client()
    if client is None or st.session_state.get("cloud_user"):
        return
    render_page_header("登入後即可永久保存自己的持股與關注清單")
    st.warning(
        "🔐 密碼安全提醒：請不要輸入你平常用於 Email、銀行、社群或其他網站的重要密碼。"
        "為本站另外設定一組至少 8 個字元、自己好記的獨立密碼即可。"
    )
    login_tab, register_tab = st.tabs(["登入", "建立帳號"])
    with login_tab:
        with st.form("cloud-login"):
            username = st.text_input("帳號", key="login_username")
            password = st.text_input("密碼", type="password", key="login_password")
            submitted = st.form_submit_button("登入並載入我的組合", type="primary")
        if submitted:
            try:
                user = client.authenticate(username, password)
                if user is None:
                    st.error("帳號或密碼不正確")
                else:
                    st.session_state.cloud_user = {"id": user.id, "username": user.username}
                    save_auth_cookie(st.session_state.cloud_user, force=True)
                    st.success("登入成功，正在載入你的專屬組合")
            except Exception as exc:
                st.error(f"登入暫時失敗：{exc}")
    with register_tab:
        with st.form("cloud-register"):
            new_username = st.text_input(
                "建立帳號", help="3–32 個英文字母、數字、底線、句點或連字號"
            )
            new_password = st.text_input("建立密碼", type="password")
            confirm_password = st.text_input("再次輸入密碼", type="password")
            registered = st.form_submit_button("建立帳號", type="primary")
        if registered:
            if new_password != confirm_password:
                st.error("兩次輸入的密碼不同")
            else:
                try:
                    user = client.register(new_username, new_password)
                    st.session_state.cloud_user = {"id": user.id, "username": user.username}
                    save_auth_cookie(st.session_state.cloud_user, force=True)
                    st.success("帳號建立完成，正在載入你的專屬組合")
                except Exception as exc:
                    st.error(str(exc))
    st.info("帳號資料經雜湊後保存；系統管理者也無法讀取你的原始密碼。")
    st.stop()


def money(value: float) -> str:
    return f"{value:,.2f}"


BEGINNER_HELP = {
    "最新價": "目前最近一筆成交價格。盤中會變動；收盤後則是最近收盤價。",
    "漲跌幅": "相較前一交易日收盤價的變動百分比。例如 +2% 代表每 100 元上漲約 2 元；-2% 則下跌約 2 元。",
    "成交量": "今天成交的股票數量；台股介面常用「張」，1 張通常等於 1,000 股。ETF 亦通常以張呈現。",
    "綜合分數": "系統把技術、基本、籌碼與風險資料換算成 0–100 分；分數越高只代表條件相對較有利，不保證上漲。",
    "資料信心度": "衡量資料完整度與新鮮度，不是上漲機率。缺資料或行情過期時會降低。",
    "技術面": "從價格、趨勢、成交量及 RSI、MACD 等指標觀察市場行為。",
    "基本面": "從營收、獲利、估值等資料觀察公司體質與價格是否合理。",
    "籌碼面": "觀察外資、投信、自營商等市場參與者近期買賣方向。",
    "風險面": "綜合波動、回撤、流動性與估值風險；本系統已轉換為越高越穩健的分數。",
    "RSI(14)": "相對強弱指標，觀察近 14 日漲跌動能。常見解讀是高於 70 偏熱、低於 30 偏弱，但不能單獨當作買賣依據。",
    "MACD": "用不同速度的移動平均線觀察趨勢與動能；數值轉正或黃金交叉常被視為轉強訊號，但也可能落後價格。",
    "KD-K": "KD 指標中反應較快的 K 值，常用來觀察短期價格位置與轉折。",
    "KD-D": "KD 指標中較平滑的 D 值；K 向上穿越 D 常稱黃金交叉，向下穿越則稱死亡交叉。",
    "ATR(14)": "近 14 日的平均真實波幅，用來衡量價格波動大小；數值越大通常代表波動與停損空間也較大。",
    "本益比": "股價相對每股盈餘的倍數，常用來看市場願意為獲利支付多高價格；不同產業不宜直接硬比。",
    "股價…16041 tokens truncated…ost:,.2f}</span>" if item.average_cost else f"{item.shares:,.0f} 股<br><span class='small-muted'>未設定成本</span>",
                        f"${market_value:,.0f}" if item.shares else "關注中",
                    )
                    classes = (
                        "portfolio-cell portfolio-name", "portfolio-cell right",
                        "portfolio-cell right", "portfolio-cell right",
                    )
                    for col, value, class_name in zip(cells, values, classes):
                        col.markdown(f'<div class="{class_name}">{value}</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="portfolio-card-meta {css_class}">'
                        f'<span class="level">{icon} {level}｜{action}</span>'
                        f'<span class="reason">{reason}</span></div>',
                        unsafe_allow_html=True,
                    )
                    with st.expander("查看價位、分析理由與修改"):
                        if st.button(
                            "📊 查看智慧分析",
                            key=f"analyze-portfolio-{item.code}",
                            type="primary",
                            use_container_width=True,
                        ):
                            st.session_state.pending_stock = item.code
                            st.session_state.active_page = "智慧分析"
                            st.session_state.return_to_portfolio = True
                            st.rerun()
                        c1, c2 = st.columns(2)
                        c1.metric("綜合分數", f"{result.overall_score:.0f}")
                        c2.metric("資料信心度", f"{result.confidence:.0f}%")
                        st.caption(
                            f"布局 {result.watch_low:.2f}–{result.watch_high:.2f}　｜　"
                            f"失效 {result.invalidation_price:.2f}　｜　"
                            f"目標一 {result.first_target_price:.2f}　｜　目標二 {result.second_target_price:.2f}"
                        )
                        with st.form(f"edit-{item.code}"):
                            e1, e2, e3 = st.columns([1, 1, 2])
                            new_shares = e1.number_input("股數", min_value=0.0, value=float(item.shares), step=100.0, key=f"shares-{item.code}")
                            new_cost = e2.number_input("平均成本", min_value=0.0, value=float(item.average_cost), step=1.0, key=f"cost-{item.code}")
                            new_note = e3.text_input("備註", value=item.note, key=f"note-{item.code}")
                            if st.form_submit_button("儲存修改", type="primary"):
                                store.upsert(PortfolioItem(item.code, new_shares, new_cost, new_note))
                                st.rerun()
                        if st.button("從清單移除", key=f"remove-{item.code}"):
                            store.delete(item.code)
                            st.rerun()

    render_items(held_tab, True)
    render_items(watch_tab, False)
    with dividend_tab:
        render_dividend_calendar(provider, analyzed)


if public_demo_mode():
    restore_auth_cookie()
    render_cloud_login()

provider = get_provider(CURRENT_VERSION)
render_page_header("上市＋上櫃股票與 ETF｜最新行情輔助 × 多構面風險評分｜不構成投資建議")
if beginner_mode():
    render_beginner_guide()
render_market_clocks()
st.caption("倒數依台股 09:00–13:30、美股 09:30–16:00 正常交易時段估算；週末已排除，特殊休市與提早收盤請以交易所公告為準。")

if "pending_stock" in st.session_state:
    st.session_state.stock_query = st.session_state.pop("pending_stock")

with st.sidebar:
    st.header("功能頁籤")
    st.caption("快速切換分析工具")
    cloud_user = st.session_state.get("cloud_user")
    if cloud_user:
        st.success(f"☁️ 已登入：{cloud_user['username']}")
        if st.button("登出", key="cloud-logout"):
            clear_auth_cookie()
            st.session_state.pop("cloud_user", None)
            st.toast("已安全登出")
    elif public_demo_mode():
        st.warning("目前尚未連接雲端帳號，資料只暫存在本次工作階段。")
    st.toggle(
        "🎓 新手輔助術語提示",
        key="beginner_assist",
        help="開啟後會顯示白話術語表，並在指標卡與 K 線圖加入滑鼠懸停說明。",
    )
    st.divider()
    pages = [
        ("🌐", "大盤趨勢"), ("📊", "智慧分析"), ("✨", "近期關注"), ("🔮", "趨勢排行"),
        ("💼", "我的組合"),
        ("🔥", "市場排行"), ("ℹ️", "使用說明"),
    ]
    if "active_page" not in st.session_state:
        st.session_state.active_page = "大盤趨勢"
    with st.container(key="sidebar_nav"):
        for icon, label in pages:
            if st.button(
                f"{icon}　{label}", key=f"nav-{label}",
                type="primary" if st.session_state.active_page == label else "secondary",
            ):
                st.session_state.active_page = label
                if label != "智慧分析":
                    st.session_state.pop("return_to_portfolio", None)
                st.rerun()
    page = st.session_state.active_page
    st.divider()
    with st.expander("智慧分析設定", expanded=page == "智慧分析"):
        if "stock_query" not in st.session_state:
            st.session_state.stock_query = "2330"
        stock_query = st.text_input("股票代碼或名稱", key="stock_query")
        horizon_label = st.radio(
            "分析週期", ["短線", "中線", "長線"], index=1, horizontal=True,
            help="短線 1–10 日；中線 1–3 個月；長線 6–24 個月",
        )
        horizon = {"短線": "短線", "中線": "波段", "長線": "中長期"}[horizon_label]
        risk_profile = st.selectbox("風險屬性", ["保守", "穩健", "積極"], index=1)
        include_news = st.checkbox("納入國際新聞情緒（5%）", value=False)
        refresh = st.button("重新抓取最新資料", use_container_width=True)
    with st.expander("進階：上傳 CSV 備援"):
        uploaded = st.file_uploader("日線 CSV", type="csv", help="date, open, high, low, close, volume")
    st.caption("Yahoo 僅補最新行情；分析資料會顯示實際來源與時間。")

if page == "大盤趨勢":
    render_market_overview(provider)
    st.stop()

if page == "近期關注":
    render_opportunity_scan(provider, horizon, risk_profile)
    st.stop()

if page == "趨勢排行":
    render_trend_rankings(provider, horizon, risk_profile)
    st.stop()

if page == "我的組合":
    render_portfolio(provider, horizon, risk_profile)
    st.stop()

if page == "市場排行":
    render_hot_list(provider)
    st.info("點選任一標的後，左側切回「智慧分析」即可查看短線、中線或長線建議。")
    st.stop()

if page == "使用說明":
    st.markdown("""
    ## 使用方式

    1. 左側選擇「智慧分析」。
    2. 輸入股票或 ETF 代碼／名稱。
    3. 選擇短線、中線或長線，以及風險屬性。
    4. 查看綜合分數、信心度、支持因素、風險、觀察區與失效條件。

    **週期定義**

    - 短線：1–10 個交易日，技術與成交動能權重較高。
    - 中線：1–3 個月，平衡技術、基本、籌碼與風險。
    - 長線：6–24 個月，基本面與風險權重較高。

    **近期關注與我的組合**

    - 「近期關注」會從市場熱門候選中重新評分，可一鍵加入清單。
    - 「我的組合」可保存股數、成本與備註，並顯示補入、續抱、減碼或退出參考。
    - 第一、第二目標價、布局區和失效價均由近期支撐壓力、均線與 ATR 計算，不代表精確最高或最低價。

    分析結果是客觀資料整理與規則評分，不保證未來績效，也不構成投資建議。
    """)
    st.stop()

if uploaded:
    try:
        manual = add_indicators(pd.read_csv(uploaded))
        st.info("目前顯示上傳資料的技術圖表；完整適合度分析需選擇官方股票代碼。")
        render_price_chart(manual)
    except Exception as exc:
        st.error(f"CSV 格式錯誤：{exc}")
    st.stop()

try:
    matches = provider.search_stocks(stock_query)
except Exception as exc:
    matches = []
    st.warning(f"股票清單暫時無法更新：{exc}")

selected_code = None
if stock_query.strip().isdigit() and 4 <= len(stock_query.strip()) <= 6:
    exact = [x for x in matches if x.code == stock_query.strip()]
    if exact:
        selected_code = exact[0].code
elif matches:
    options = {f"{x.code} {x.name}｜{x.industry or '其他業'}（{x.market}）": x.code for x in matches[:30]}
    chosen = st.selectbox("搜尋結果", list(options))
    selected_code = options[chosen]

if not selected_code:
    st.info("請輸入四位數股票代碼，或以公司名稱搜尋後選擇股票。")
    render_hot_list(provider)
    st.stop()

try:
    with st.spinner("正在取得市場資料並計算適合度…"):
        result = analyze_stock(
            provider,
            StockAnalysisRequest(
                stock_code=selected_code, horizon=horizon, risk_profile=risk_profile,
                include_news=include_news,
            ),
            refresh=refresh,
        )
except Exception as exc:
    st.error(f"無法完成分析：{exc}")
    render_hot_list(provider)
    st.stop()

quote = result.quote
market_time = quote.meta.market_time.astimezone().strftime("%Y-%m-%d %H:%M") if quote.meta.market_time else "未提供"
asset_type = getattr(result.stock, "asset_type", "ETF" if result.stock.code.startswith("00") else "STOCK")
asset_label = "ETF" if asset_type == "ETF" else "股票"
if st.session_state.get("return_to_portfolio"):
    if st.button("← 返回我的組合", key="back-to-portfolio", use_container_width=False):
        st.session_state.active_page = "我的組合"
        st.session_state.pop("return_to_portfolio", None)
        st.rerun()
industry_label = result.stock.industry or ("ETF" if asset_type == "ETF" else "其他業")
st.subheader(f"{result.stock.code} {result.stock.name}｜{industry_label}｜{result.stock.market} {asset_label}")
render_live_quote(provider, result)
top_scores = st.columns(4)
metric_card(top_scores[0], "技術面", f"{result.technical_score:.0f}")
metric_card(top_scores[1], "基本面", f"{result.fundamental_score:.0f}")
metric_card(top_scores[2], "籌碼面", f"{result.chip_score:.0f}")
metric_card(top_scores[3], "風險面", f"{result.risk_score:.0f}")
if result.signal.startswith("偏多"):
    st.success(f"分析結論：{result.signal}")
elif "觀望" in result.signal:
    st.warning(f"分析結論：{result.signal}")
else:
    st.error(f"分析結論：{result.signal}")
st.caption(f"完整分析基準時間：{market_time}｜來源：{quote.meta.source}｜分析週期：{horizon_label}｜風險屬性：{risk_profile}")
if quote.meta.warning:
    st.warning(quote.meta.warning)

tabs = st.tabs(["綜合判斷", "技術分析", "基本籌碼", "歷史驗證", "新聞趨勢", "資料狀態"])

with tabs[0]:
    st.markdown("### 理性數據綜合建議")
    if result.signal.startswith("偏多"):
        recommendation = "可列入分批布局觀察，但不建議追價；以觀察區與失效價管理風險。"
    elif "觀望" in result.signal:
        recommendation = "目前先觀望，等待趨勢、動能或基本數據改善後再重新評估。"
    else:
        recommendation = "目前不建議新建部位；若已持有，應檢查失效價與可承受風險。"
    st.write(f"**{horizon_label}建議：{recommendation}**")
    st.caption(
        f"依技術 {result.technical_score:.0f}、基本 {result.fundamental_score:.0f}、"
        f"籌碼 {result.chip_score:.0f}、風險 {result.risk_score:.0f} 分綜合判定；"
        f"資料信心度 {result.confidence:.0f}%。"
    )
    st.divider()
    a, b = st.columns(2)
    with a:
        st.markdown("### 支持因素")
        if result.positive_reasons:
            for reason in result.positive_reasons:
                st.write(f"✅ {reason}")
        else:
            st.write("目前沒有明確加分因素。")
    with b:
        st.markdown("### 風險與扣分因素")
        if result.negative_reasons:
            for reason in result.negative_reasons:
                st.write(f"⚠️ {reason}")
        else:
            st.write("目前沒有明確扣分因素。")
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("觀察區下緣", money(result.watch_low))
    c2.metric("觀察區上緣", money(result.watch_high))
    c3.metric("失效參考價", money(result.invalidation_price))
    c4.metric("單股部位上限", f"{result.max_position_pct:.0%}")
    t1, t2 = st.columns(2)
    t1.metric("第一停利／減碼參考", money(result.first_target_price))
    t2.metric("第二停利／減碼參考", money(result.second_target_price))
    if result.missing_data:
        st.markdown("### 資料限制")
        for item in result.missing_data:
            st.write(f"• {item}")
    st.info("評分是依目前可取得資料產生的研究結果；觀察區與失效價不是委託價格，也不保證未來報酬。")

with tabs[1]:
    latest = result.prices.iloc[-1]
    trend_label, trend_icon, trend_class, trend_reasons = technical_trend_view(latest)
    st.markdown(
        f'<div class="trend-card {trend_class}">'
        f'<div class="title">{trend_icon} 技術趨勢：{trend_label}</div>'
        f'<div class="detail">{"　｜　".join(trend_reasons)}</div>'
        f'<div class="detail">綜合均線、RSI、MACD 與 KD；這是目前技術狀態，不等同未來一定上漲或下跌。</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown("### 價格趨勢與成交量")
    chart_range = st.segmented_control(
        "顯示區間",
        options=["一週內", "一個月內", "三個月內", "半年內"],
        default="一個月內",
        key=f"chart-range-{result.stock.code}",
        help="只改變圖表顯示範圍，不會重新下載或改變分析評分。",
    )
    chart_type = st.segmented_control(
        "圖表／指標",
        options=["K 線與均線", "布林通道", "RSI", "MACD", "KD", "ATR 與量能"],
        default="K 線與均線",
        key=f"chart-type-{result.stock.code}",
        help="切換不同技術指標圖，不會改變綜合分析分數。",
    )
    if chart_type == "K 線與均線" or not chart_type:
        render_price_chart(result.prices, chart_range or "一個月內")
    else:
        render_indicator_chart(result.prices, chart_range or "一個月內", chart_type)
    st.markdown("### 技術指標摘要")
    momentum_cols = st.columns(3)
    for col, label, value in zip(
        momentum_cols,
        ("RSI(14)", "MACD", "ATR(14)"),
        (latest.rsi14, latest.macd, latest.atr14),
    ):
        metric_card(col, label, f"{value:.2f}")
    signal_cols = st.columns(3)
    for col, label, value in zip(
        signal_cols,
        ("KD-K", "KD-D", "風險分數"),
        (latest.kd_k, latest.kd_d, result.risk_score),
    ):
        metric_card(col, label, f"{value:.2f}", term="風險面" if label == "風險分數" else label)
    if beginner_mode():
        st.caption("RSI、MACD、KD 用於觀察動能與趨勢，ATR 用於衡量波動；請將滑鼠移到指標名稱旁的「?」查看個別解釋。")

with tabs[2]:
    st.markdown("### 基本面與估值" if asset_type == "STOCK" else "### ETF 估值參考")
    v1, v2, v3, v4 = st.columns(4)
    metric_card(v1, "本益比", f"{result.valuation.get('pe', float('nan')):.2f}")
    metric_card(v2, "股價淨值比", f"{result.valuation.get('pb', float('nan')):.2f}")
    metric_card(v3, "殖利率", f"{result.valuation.get('yield', float('nan')):.2f}%")
    if asset_type == "STOCK":
        metric_card(v4, "月營收年增", f"{result.revenue.get('yoy', float('nan')):.2f}%")
        st.markdown("### 籌碼")
        st.json(result.institutional)
        if "法人籌碼資料不完整" in result.missing_data:
            st.warning("目前官方端點未提供完整三大法人個股資料，籌碼分數以可取得資料計算並降低信心度。")
    else:
        v4.metric("商品類型", "ETF")
        st.info("ETF 不套用個別公司的月營收與法人籌碼評分；主要依趨勢、動能、波動、回撤、流動性與可取得的殖利率資料分析。")

with tabs[3]:
    st.markdown("### 以目前週期設定進行歷史驗證")
    horizon_config = {
        "短線": BacktestConfig(entry_ma=20, exit_ma=5, max_holding_days=10, rsi_max=68),
        "波段": BacktestConfig(entry_ma=60, exit_ma=20, max_holding_days=60, rsi_max=72),
        "中長期": BacktestConfig(entry_ma=120, exit_ma=60, max_holding_days=120, rsi_max=78),
    }[horizon]
    backtest = run_backtest(result.prices[["date", "open", "high", "low", "close", "volume"]], horizon_config)
    metrics, trades, equity = backtest["metrics"], backtest["trades"], backtest["equity"]
    cols = st.columns(6)
    for col, (label, value) in zip(cols, [
        ("總報酬", f"{metrics['total_return']:.1%}"), ("年化報酬", f"{metrics['annual_return']:.1%}"),
        ("最大回撤", f"{metrics['max_drawdown']:.1%}"), ("Sharpe", f"{metrics['sharpe']:.2f}"),
        ("交易數", str(metrics["trade_count"])), ("勝率", f"{metrics['win_rate']:.1%}"),
    ]):
        col.metric(label, value)
    curve = go.Figure(go.Scatter(x=equity.date, y=equity.equity, name="策略資產"))
    curve.update_layout(height=360, margin={"l": 10, "r": 10, "t": 20, "b": 10})
    st.plotly_chart(curve, use_container_width=True)
    stats = win_rate_test(metrics["wins"], metrics["trade_count"], 0.6)
    st.write(f"勝率 95% 信賴區間：{stats['lower']:.1%}～{stats['upper']:.1%}；高於 60% 的單尾 p-value：{stats['p_value']:.4f}")
    if not trades.empty:
        simulations = monte_carlo(trades.net_return, horizon_config.initial_capital)
        st.write(f"Bootstrap 最終資產高於初始資金機率：{(simulations > horizon_config.initial_capital).mean():.1%}")
        st.dataframe(trades, use_container_width=True, hide_index=True)
    st.caption("歷史績效僅用於檢查策略穩定性，不會直接改寫目前的購買適合度分數。")

with tabs[4]:
    st.markdown("### 國際新聞討論趨勢")
    if not include_news:
        st.info("在左側勾選「納入國際新聞情緒（5%）」後重新分析。新聞分數只作低權重輔助。")
    elif result.news_warning:
        st.warning(result.news_warning)
    else:
        st.metric("新聞情緒分數", f"{result.news_score:.0f} / 100" if result.news_score is not None else "無資料")
        for headline in result.news_headlines:
            st.write(f"• {headline}")
        st.caption("新聞標題以規則式正負關鍵詞彙彙整，可能受到媒體偏誤、語境與同名公司影響；最高只占總分 5%。")

with tabs[5]:
    rows = []
    for meta in result.data_status:
        rows.append({
            "資料來源": meta.source,
            "市場時間": meta.market_time.isoformat() if meta.market_time else "未提供",
            "擷取時間": meta.fetched_at.isoformat(),
            "是否降級／過期": "是" if meta.is_stale else "否",
            "說明": meta.warning or "",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"頁面產生時間：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")

st.divider()
render_hot_list(provider)
st.caption("本系統僅供研究與模擬，不構成投資建議；請自行評估財務狀況、投資目標與風險承受能力。")

