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
    "股價淨值比": "股價相對每股淨值的倍數，常用於金融、資產型公司等；低不一定便宜，高也不一定昂貴。",
    "殖利率": "每股現金股利 ÷ 股價的比例；是歷史或預估參考，不代表未來一定發放相同股利。",
    "月營收年增": "本月營收與去年同月相比的成長率，可降低季節性干擾，但營收成長不一定等於獲利成長。",
    "MA20": "20 日移動平均線，約代表近一個月交易日的平均收盤價，台股常稱「月線」。",
    "MA60": "60 日移動平均線，約代表近一季交易日的平均收盤價，台股常稱「季線」。",
    "布林通道": "由移動平均線與價格標準差形成上、中、下三條軌道，用來觀察價格相對位置與波動擴張或收縮。",
    "成交量均線": "一段期間的平均成交量；目前成交量高於均量，代表交易比近期平均活躍。",
}


def beginner_mode() -> bool:
    return bool(st.session_state.get("beginner_assist", False))


def metric_card(container, label: str, value, delta=None, term: str | None = None) -> None:
    help_text = BEGINNER_HELP.get(term or label) if beginner_mode() else None
    container.metric(
        label,
        value,
        delta,
        help=help_text,
        delta_color="inverse" if delta is not None else "normal",
    )


def render_beginner_guide() -> None:
    st.markdown(
        '<div class="beginner-strip">💡 新手輔助已開啟：將滑鼠移到指標名稱旁的「?」即可看白話解釋；'
        'K 線圖移到任一根 K 棒，可查看當日點位與漲跌幅。</div>',
        unsafe_allow_html=True,
    )
    with st.expander("📖 常用盤中術語與交易時間", expanded=False):
        st.markdown("""
| 術語 | 白話說明 |
|---|---|
| **點／點位** | 股票通常稱「股價」或「元」；「大盤上漲 100 點」才常稱為點。個股從 100 元漲到 102 元，通常說「漲 2 元、漲 2%」。 |
| **漲跌幅** | `(目前價格－昨收價) ÷ 昨收價 × 100%`。台股一般股票單日漲跌幅多為 ±10%，但新上市、恢復交易等情況可能例外。 |
| **開盤價** | 當天第一筆撮合成交價；不一定等於前一天收盤價。 |
| **盤中** | 一般指正常交易進行中的時間，台股集中市場通常為交易日 **09:00–13:30**。 |
| **早盤** | 開盤後的前一段時間，市場慣用說法，沒有唯一法定分界；通常約指 **09:00–10:30**。 |
| **盤中段** | 市場慣用說法，通常約指 **10:30–12:30**。 |
| **尾盤／盤尾** | 接近收盤的最後一段，通常約指 **12:30–13:30**；最後幾分鐘的價格可能較活躍。 |
| **收盤價** | 正常交易結束時形成的當日最後成交價。 |
| **紅／綠** | 台股慣例是紅色代表上漲、綠色代表下跌；本系統的建議燈號另採綠＝較高、黃＝觀察、紅＝優先處理。 |
| **一張** | 台股股票通常 1 張＝1,000 股；不足一張稱為零股。 |
| **多頭／偏多** | 買方力量較強或看法偏向上漲；不等於接下來一定會漲。 |
| **空頭／偏空** | 賣方力量較強或看法偏向下跌；「放空」則是先賣後買的交易方式，風險較高。 |
| **利多／利空** | 可能有利／不利價格的消息或因素；消息公布後，價格不一定照直覺反應。 |
| **盤整** | 價格在一段區間內來回，還沒有明顯上漲或下跌趨勢。 |
| **支撐／壓力** | 過去較容易止跌／遇到賣壓的位置，是觀察區而非保證不會跌破或突破。 |
| **停損／停利** | 事先設定判斷失效時退出，或達到目標時分批落袋；重點是控制風險與執行紀律。 |
| **除息** | 股票扣除現金股利價值的參考日；在除息日前一交易日持有，通常才有資格參與該次配息。 |
        """)
        st.caption("時段名稱中的早盤、盤中段、尾盤屬市場慣用語；實際交易與特殊商品時段仍以交易所公告為準。")
    with st.expander("📈 技術分析導讀與常見型態", expanded=False):
        st.markdown("""
**技術分析在看什麼？**

技術分析主要整理歷史價格、成交量和市場交易行為；基本面則著重公司的營收、獲利、財務與估值。兩者回答的問題不同，可以互相補充。

**新手可以照這個順序看**

1. **先看基本面與商品性質**：確認自己買的是個股或 ETF，公司／商品做什麼、資料是否完整，先回答「值不值得持續研究」。
2. **再看大方向**：用 MA20、MA60 判斷目前偏上升、下降或盤整，避免只因一天紅 K 就認定趨勢翻多。
3. **標示支撐、壓力與失效位置**：先決定判斷錯誤時如何退出，再考慮可能的進場區與目標。
4. **觀察 K 線與成交量**：確認突破、跌破或轉折是否伴隨較活躍的成交量；量能只代表活躍，不保證方向。
5. **最後用 RSI、MACD、KD 輔助確認**：指標互相矛盾時應降低信心，不需要為了買進而挑選最樂觀的單一指標。

| 類別 | 白話解釋 | 本系統 |
|---|---|---|
| **趨勢** | 價格大致可分為上升、下降或橫向盤整；不要因單日漲跌就認定趨勢改變。 | MA20、MA60 與 K 線 |
| **成交量** | 反映交易活躍程度。價漲量增、價跌量增代表的市場力道不同，需與價格一起看。 | 成交量、20 日均量 |
| **支撐／壓力** | 過去較容易止跌或遇到賣壓的價格區域，不是一條保證有效的精準價位。 | 觀察區、目標與失效參考 |
| **K 線分析** | 一根 K 棒濃縮一段時間的開、高、低、收，呈現當期多空交戰結果。 | 可直接點選日 K 查看解說 |
| **型態分析** | 觀察多根 K 棒組成的形狀；型態通常要等突破或跌破關鍵位置才算確認。 | 提供名詞導讀，不自動宣稱型態成立 |
| **技術指標** | 把價格或成交量轉成數學指標，協助比較趨勢、動能和波動。 | RSI、MACD、KD、ATR、布林通道 |

**常見圖形型態**

| 名稱 | 辨識概念 | 新手注意 |
|---|---|---|
| **頭肩頂** | 三個高峰，中間較高；連接兩側低點的線常稱頸線。 | 未跌破頸線前，不宜只看外形就判定反轉。 |
| **雙重頂／M 頭** | 價格兩次挑戰相近高點未能站穩。 | 通常要再觀察是否跌破兩峰之間的低點。 |
| **圓弧頂** | 價格由上升逐漸轉平，再緩慢走弱。 | 形成時間較長，主觀辨識差異也較大。 |
| **三角收斂** | 高低波動範圍逐漸縮小。 | 只代表力量收斂，向上或向下突破前方向未知。 |
| **箱型整理** | 價格在相對固定的上、下邊界間來回。 | 假突破常見，需搭配收盤位置與成交量確認。 |

**其他常見工具**

- **趨勢線**：連接一系列高點或低點，用來輔助觀察方向與可能的支撐壓力。
- **斐波那契回撤**：用 23.6%、38.2%、50%、61.8% 等比例標示潛在回撤位置；這些只是觀察區，不是自然法則。
- **黃金交叉／死亡交叉**：較快的線向上／向下穿越較慢的線。交叉通常落後價格，不能保證後續方向。

> 技術分析源自歷史資料，無法事先知道財報意外、政策、戰爭或其他突發事件；不同人畫出的趨勢線與型態也可能不同。應搭配基本面、籌碼、風險控管與部位規劃。

[延伸閱讀：量化通技術分析教學懶人包](https://quantpass.org/technical-analysis-lists/)

[延伸閱讀：永豐金證券技術分析與基本面搭配](https://www.sinotrade.com.tw/richclub/hotstock/%E6%8A%80%E8%A1%93%E5%88%86%E6%9E%90%E6%95%99%E5%AD%B8%E6%87%B6%E4%BA%BA%E5%8C%85-%E6%8A%80%E8%A1%93%E5%88%86%E6%9E%90%E7%9C%9F%E7%9A%84%E6%9C%89%E7%94%A8%E5%97%8E-%E8%88%87%E5%9F%BA%E6%9C%AC%E9%9D%A2%E6%80%8E%E9%BA%BC%E6%90%AD%E9%85%8D-%E7%94%A8-%E6%93%8D%E7%9B%A4%E5%BF%85%E4%BF%AE%E8%AA%B2-%E5%AF%A6%E6%88%B0%E6%A1%88%E4%BE%8B%E8%AE%93%E4%BD%A0%E6%87%82--686f51d7532fa101531fe407)
        """)


def advice_level(action: str) -> tuple[str, str]:
    if any(word in action for word in ("退出", "緊急", "減碼，暫不", "偏空")):
        return "advice-red", "需優先處理"
    if any(word in action for word in ("可評估分批補入", "偏多", "續抱／")):
        return "advice-green", "建議度較高"
    return "advice-yellow", "警戒／持續觀察"


def render_market_clocks() -> None:
    clocks = [market_clock("台股"), market_clock("美股")]
    blocks = []
    for clock in clocks:
        blocks.append(f"""
        <div class="clock">
          <div class="name">{clock.name} <span>{clock.status}</span></div>
          <div class="event">{clock.event_label}</div>
          <div class="countdown" data-target="{clock.target.isoformat()}">--:--:--</div>
          <div class="zone">{clock.timezone_name}</div>
        </div>""")
    components.html(f"""
    <style>
      body {{margin:0;color:#eef5ff;font-family:system-ui;background:transparent}}
      .wrap {{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
      .clock {{padding:14px 18px;border-radius:18px;background:rgba(255,255,255,.08);
        border:1px solid rgba(255,255,255,.15);backdrop-filter:blur(15px)}}
      .name {{font-size:17px;font-weight:700}} .name span {{font-size:12px;color:#7dd3fc;margin-left:6px}}
      .event,.zone {{font-size:12px;opacity:.72}} .countdown {{font-size:24px;font-weight:750;margin:3px 0}}
    </style>
    <div class="wrap">{''.join(blocks)}</div>
    <script>
    function tick(){{
      document.querySelectorAll('.countdown').forEach(el=>{{
        let seconds=Math.max(0,Math.floor((new Date(el.dataset.target)-new Date())/1000));
        let d=Math.floor(seconds/86400); seconds%=86400;
        let h=Math.floor(seconds/3600); seconds%=3600;
        let m=Math.floor(seconds/60), s=seconds%60;
        el.textContent=(d?d+'天 ':'')+[h,m,s].map(x=>String(x).padStart(2,'0')).join(':');
      }});
    }} tick(); setInterval(tick,1000);
    </script>
    """, height=120)


@st.fragment(run_every="10s")
def render_live_quote(provider: HybridTaiwanProvider, result) -> None:
    clock = market_clock("台股")
    quote = result.quote
    warning = None
    if clock.status == "交易中":
        try:
            quote = provider.get_latest_quote(result.stock, refresh=True)
        except Exception as exc:
            warning = f"即時行情更新失敗，保留最後成功資料：{exc}"
    columns = st.columns(4)
    metric_card(columns[0], "最新價", money(quote.price), f"{quote.change_pct:+.2f}%", "最新價")
    metric_card(columns[1], "成交量", f"{quote.volume / 1000:,.0f} 張")
    metric_card(columns[2], "綜合分數", f"{result.overall_score:.0f} / 100")
    metric_card(columns[3], "資料信心度", f"{result.confidence:.0f}%")
    market_time = quote.meta.market_time.astimezone().strftime("%Y-%m-%d %H:%M:%S") if quote.meta.market_time else "未提供"
    if clock.status == "交易中":
        st.caption(f"🟢 盤中自動更新：每 10 秒｜行情時間 {market_time}｜{quote.meta.source}")
    else:
        st.caption(f"⚪ 目前{clock.status}，暫停自動抓取｜最後行情時間 {market_time}｜{quote.meta.source}")
    if warning:
        st.warning(warning)


def explain_kbar(row: pd.Series) -> tuple[str, str]:
    open_price, high, low, close = (float(row[key]) for key in ("open", "high", "low", "close"))
    full_range = max(high - low, 1e-9)
    body = abs(close - open_price)
    upper_shadow = high - max(open_price, close)
    lower_shadow = min(open_price, close) - low
    direction = "紅 K（收盤高於開盤，多方當日略勝）" if close > open_price else (
        "黑 K（收盤低於開盤，空方當日略勝）" if close < open_price else "平盤 K"
    )

    if body / full_range <= 0.08:
        pattern = "十字線"
        meaning = "開盤與收盤很接近，代表當日多空拉鋸、方向尚未明朗。"
    elif upper_shadow >= body * 2 and lower_shadow <= full_range * 0.12:
        pattern = "長上影／倒鎚型"
        meaning = "盤中曾明顯上攻，但收盤前被賣壓壓回；需搭配前後趨勢與成交量確認。"
    elif lower_shadow >= body * 2 and upper_shadow <= full_range * 0.12:
        pattern = "長下影／鎚子型"
        meaning = "盤中曾明顯下探，之後出現承接拉回；是否止跌仍需後續 K 棒確認。"
    elif body / full_range <= 0.35 and upper_shadow > 0 and lower_shadow > 0:
        pattern = "紡錘線"
        meaning = "實體較短且上下都有影線，表示買賣雙方交戰激烈、暫無明確勝方。"
    elif body / full_range >= 0.65:
        pattern = "長實體紅 K" if close > open_price else "長實體黑 K"
        meaning = "實體占當日波幅較高，代表當日方向力道較明顯；仍要確認是否有量能與趨勢配合。"
    else:
        pattern = "一般紅 K" if close > open_price else "一般黑 K"
        meaning = "當日有方向但強度並非極端，建議連同前後 K 棒、均線與成交量一起判讀。"
    return f"{pattern}｜{direction}", meaning


def filter_chart_range(prices: pd.DataFrame, display_range: str) -> pd.DataFrame:
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    range_days = {"一週內": 7, "一個月內": 31, "三個月內": 93, "半年內": 183}
    cutoff = frame["date"].max() - timedelta(days=range_days.get(display_range, 183))
    return frame[frame["date"] >= cutoff].copy()


def technical_trend_view(row: pd.Series) -> tuple[str, str, str, list[str]]:
    votes: list[tuple[int, str]] = []
    if pd.notna(row.ma20):
        votes.append((1 if row.close >= row.ma20 else -1, "股價在月線之上" if row.close >= row.ma20 else "股價在月線之下"))
    if pd.notna(row.ma60):
        votes.append((1 if row.close >= row.ma60 else -1, "股價在季線之上" if row.close >= row.ma60 else "股價在季線之下"))
    votes.append((1 if row.macd >= row.macd_signal else -1, "MACD 動能偏強" if row.macd >= row.macd_signal else "MACD 動能偏弱"))
    if row.rsi14 >= 55:
        votes.append((1, f"RSI {row.rsi14:.0f} 偏強"))
    elif row.rsi14 <= 45:
        votes.append((-1, f"RSI {row.rsi14:.0f} 偏弱"))
    else:
        votes.append((0, f"RSI {row.rsi14:.0f} 中性"))
    votes.append((1 if row.kd_k >= row.kd_d else -1, "KD 短期動能向上" if row.kd_k >= row.kd_d else "KD 短期動能向下"))
    total = sum(score for score, _ in votes)
    if total >= 2:
        return "偏多（看漲趨勢）", "🔴", "trend-bull", [reason for _, reason in votes]
    if total <= -2:
        return "偏空（看跌趨勢）", "🟢", "trend-bear", [reason for _, reason in votes]
    return "多空交錯（盤整觀望）", "🟡", "trend-neutral", [reason for _, reason in votes]


def style_technical_chart(fig: go.Figure, height: int = 460) -> None:
    fig.update_layout(
        height=height,
        margin={"l": 58, "r": 22, "t": 42, "b": 36},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,.62)",
        font={"color": "#dbeafe"},
        hovermode="x unified",
        hoverlabel={"bgcolor": "#0f172a", "font_color": "#f8fafc"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "left", "x": 0},
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(148,163,184,.12)", tickfont={"color": "#cbd5e1"})
    fig.update_yaxes(
        showgrid=True, gridcolor="rgba(148,163,184,.12)",
        tickfont={"color": "#cbd5e1"}, separatethousands=True,
    )


def render_indicator_explanation(chart_type: str, row: pd.Series) -> None:
    selected_date = pd.to_datetime(row.date).date()
    with st.container(border=True):
        st.markdown(f"#### 👆 點選日期：{selected_date:%Y-%m-%d}｜{chart_type}")
        if chart_type == "布林通道":
            position = (
                "收盤位於上軌之上，價格相對近期波動區間偏高"
                if row.close > row.bollinger_upper else
                "收盤位於下軌之下，價格相對近期波動區間偏低"
                if row.close < row.bollinger_lower else
                "收盤位於通道內，尚未超出近期主要波動範圍"
            )
            cols = st.columns(4)
            for col, label, value in zip(
                cols, ("收盤價", "布林上軌", "中軌 MA20", "布林下軌"),
                (row.close, row.bollinger_upper, row.ma20, row.bollinger_lower),
            ):
                col.metric(label, f"{value:,.2f}")
            st.info(f"這個位置代表：{position}。觸及軌道不等於一定反轉，強勢趨勢可能沿著上軌或下軌移動。")
        elif chart_type == "RSI":
            state = "偏熱區" if row.rsi14 >= 70 else "偏弱區" if row.rsi14 <= 30 else "中性區"
            c1, c2 = st.columns(2)
            c1.metric("RSI(14)", f"{row.rsi14:.2f}")
            c2.metric("所在區域", state)
            st.info(f"這個位置代表：RSI 處於{state}。偏熱不等於立刻下跌，偏弱也不等於立刻反彈，仍要確認趨勢。")
        elif chart_type == "MACD":
            histogram = row.macd - row.macd_signal
            relation = "MACD 位於訊號線上方，短期動能相對較強" if histogram >= 0 else "MACD 位於訊號線下方，短期動能相對較弱"
            cols = st.columns(3)
            cols[0].metric("MACD", f"{row.macd:.3f}")
            cols[1].metric("訊號線", f"{row.macd_signal:.3f}")
            cols[2].metric("柱狀差", f"{histogram:+.3f}", delta_color="inverse")
            st.info(f"這個位置代表：{relation}。MACD 是落後指標，交叉出現時價格可能已先移動。")
        elif chart_type == "KD":
            zone = "高檔區" if max(row.kd_k, row.kd_d) >= 80 else "低檔區" if min(row.kd_k, row.kd_d) <= 20 else "中間區"
            relation = "K 值高於 D 值，短期動能相對轉強" if row.kd_k >= row.kd_d else "K 值低於 D 值，短期動能相對轉弱"
            cols = st.columns(3)
            cols[0].metric("K 值", f"{row.kd_k:.2f}")
            cols[1].metric("D 值", f"{row.kd_d:.2f}")
            cols[2].metric("所在區域", zone)
            st.info(f"這個位置代表：{relation}，目前位於{zone}。鈍化時指標可能長時間停留高檔或低檔。")
        else:
            volume_ratio = row.volume / row.volume_ma20 if pd.notna(row.volume_ma20) and row.volume_ma20 else float("nan")
            atr_pct = row.atr14 / row.close * 100 if row.close else float("nan")
            activity = "高於近期均量，交易較活躍" if pd.notna(volume_ratio) and volume_ratio >= 1 else "低於近期均量，交易相對清淡"
            cols = st.columns(4)
            cols[0].metric("ATR(14)", f"{row.atr14:,.2f}")
            cols[1].metric("ATR／股價", f"{atr_pct:.2f}%")
            cols[2].metric("成交量", f"{row.volume / 1000:,.0f} 張")
            cols[3].metric("相對20日均量", f"{volume_ratio:.2f} 倍" if pd.notna(volume_ratio) else "資料不足")
            st.info(f"這個位置代表：成交量{activity}。ATR 越高表示波動越大，但 ATR 本身不判斷上漲或下跌。")
        st.caption("這是單日指標狀態說明，不是買進或賣出指令；請搭配趨勢、基本面、籌碼與風險承受能力。")


def render_indicator_chart(prices: pd.DataFrame, display_range: str, chart_type: str) -> None:
    recent = filter_chart_range(prices, display_range)
    fig = go.Figure()
    beginner_note = ""

    if chart_type == "布林通道":
        fig.add_trace(go.Scatter(
            x=recent.date, y=recent.bollinger_upper, name="上軌",
            line={"color": "#94a3b8", "width": 1},
        ))
        fig.add_trace(go.Scatter(
            x=recent.date, y=recent.bollinger_lower, name="下軌",
            line={"color": "#94a3b8", "width": 1}, fill="tonexty",
            fillcolor="rgba(148,163,184,.10)",
        ))
        fig.add_trace(go.Scatter(x=recent.date, y=recent.ma20, name="中軌 MA20", line={"color": "#facc15"}))
        fig.add_trace(go.Scatter(x=recent.date, y=recent.close, name="收盤價", line={"color": "#60a5fa", "width": 2}))
        beginner_note = "布林通道以 20 日均線為中軌；價格靠近上、下軌代表相對位置偏高或偏低，不等於立即反轉。"
    elif chart_type == "RSI":
        fig.add_trace(go.Scatter(x=recent.date, y=recent.rsi14, name="RSI(14)", line={"color": "#a78bfa", "width": 2}))
        fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", annotation_text="70 偏熱")
        fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", annotation_text="30 偏弱")
        fig.update_yaxes(range=[0, 100])
        beginner_note = "RSI 高於 70 常稱偏熱、低於 30 常稱偏弱；強勢趨勢中可能長時間停留在高檔或低檔。"
    elif chart_type == "MACD":
        histogram = recent.macd - recent.macd_signal
        colors = ["#ef4444" if value >= 0 else "#22c55e" for value in histogram]
        fig.add_trace(go.Bar(x=recent.date, y=histogram, name="柱狀差", marker_color=colors))
        fig.add_trace(go.Scatter(x=recent.date, y=recent.macd, name="MACD", line={"color": "#60a5fa", "width": 2}))
        fig.add_trace(go.Scatter(x=recent.date, y=recent.macd_signal, name="訊號線", line={"color": "#facc15", "width": 2}))
        fig.add_hline(y=0, line_color="rgba(255,255,255,.35)")
        beginner_note = "MACD 向上穿越訊號線常稱黃金交叉，向下穿越稱死亡交叉；交叉可能落後價格，需配合趨勢判讀。"
    elif chart_type == "KD":
        fig.add_trace(go.Scatter(x=recent.date, y=recent.kd_k, name="K 值", line={"color": "#60a5fa", "width": 2}))
        fig.add_trace(go.Scatter(x=recent.date, y=recent.kd_d, name="D 值", line={"color": "#facc15", "width": 2}))
        fig.add_hline(y=80, line_dash="dash", line_color="#ef4444", annotation_text="80 高檔")
        fig.add_hline(y=20, line_dash="dash", line_color="#22c55e", annotation_text="20 低檔")
        fig.update_yaxes(range=[0, 100])
        beginner_note = "KD 常用 80／20 觀察相對高低檔；K、D 交叉只是動能變化，不宜單獨視為買賣訊號。"
    else:  # ATR 與量能
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.45, 0.55], vertical_spacing=0.08)
        fig.add_trace(go.Scatter(x=recent.date, y=recent.atr14, name="ATR(14)", line={"color": "#fb923c", "width": 2}), row=1, col=1)
        volume_colors = ["#ef4444" if close >= open_ else "#22c55e" for open_, close in zip(recent.open, recent.close)]
        fig.add_trace(go.Bar(x=recent.date, y=recent.volume, name="成交量", marker_color=volume_colors), row=2, col=1)
        fig.add_trace(go.Scatter(x=recent.date, y=recent.volume_ma20, name="20 日均量", line={"color": "#60a5fa", "width": 2}), row=2, col=1)
        beginner_note = "ATR 衡量平均波動幅度，不判斷漲跌方向；成交量高於均量代表交易較活躍，仍需搭配價格方向。"

    if beginner_mode():
        click_y = {
            "布林通道": recent.close,
            "RSI": recent.rsi14,
            "MACD": recent.macd,
            "KD": recent.kd_k,
            "ATR 與量能": recent.atr14,
        }[chart_type]
        click_trace = go.Scatter(
            x=recent.date, y=click_y, mode="markers", name="點選日期",
            marker={"size": 20, "opacity": 0.015, "color": "#38bdf8"},
            showlegend=False, hoverinfo="skip",
        )
        if chart_type == "ATR 與量能":
            fig.add_trace(click_trace, row=1, col=1)
        else:
            fig.add_trace(click_trace)

    style_technical_chart(fig, 500 if chart_type == "ATR 與量能" else 450)
    if beginner_mode():
        selected_points = plotly_events(
            fig,
            click_event=True,
            select_event=False,
            hover_event=False,
            override_height=500 if chart_type == "ATR 與量能" else 450,
            override_width="100%",
            key=f"beginner-indicator-{chart_type}-{display_range}",
        )
        st.info(f"💡 {beginner_note}")
        if selected_points:
            selected_x = selected_points[-1].get("x")
            if selected_x is not None:
                selected_date = pd.to_datetime(selected_x).date()
                matched = recent[pd.to_datetime(recent.date).dt.date == selected_date]
                if not matched.empty:
                    render_indicator_explanation(chart_type, matched.iloc[-1])
        else:
            st.caption("🖱️ 請直接點一下圖中的線、柱狀或日期位置，下方會顯示該日指標的補充解釋。")
    else:
        st.plotly_chart(fig, use_container_width=True, key=f"indicator-{chart_type}-{display_range}")


def render_price_chart(prices: pd.DataFrame, display_range: str = "半年內") -> None:
    recent = filter_chart_range(prices, display_range)
    recent["change_pct"] = recent["close"].pct_change().mul(100)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.04)
    fig.add_trace(go.Candlestick(
        x=recent.date, open=recent.open, high=recent.high, low=recent.low, close=recent.close, name="K 線",
        increasing={"line": {"color": UP_COLOR, "width": 1.5}, "fillcolor": UP_COLOR},
        decreasing={"line": {"color": DOWN_COLOR, "width": 1.5}, "fillcolor": DOWN_COLOR},
        opacity=1,
        customdata=recent[["change_pct"]].to_numpy(),
        text=[
            f"當日漲跌 {value:+.2f}%" if pd.notna(value) else "區間首日"
            for value in recent["change_pct"]
        ] if beginner_mode() else None,
        hoverinfo="all",
    ), row=1, col=1)
    for period, color in ((20, "#f2c14e"), (60, "#4cc9f0")):
        fig.add_trace(go.Scatter(
            x=recent.date, y=recent[f"ma{period}"], name=f"MA{period}",
            line={"width": 1.5, "color": color}
        ), row=1, col=1)
    volume_colors = [
        UP_COLOR if close >= open_price else DOWN_COLOR
        for open_price, close in zip(recent.open, recent.close)
    ]
    fig.add_trace(go.Bar(
        x=recent.date, y=recent.volume, name="成交量",
        marker={"color": volume_colors, "opacity": .62},
    ), row=2, col=1)
    if beginner_mode():
        # Transparent close-price points make each candlestick easy to click/select
        # while preserving the original candlestick appearance.
        fig.add_trace(go.Scatter(
            x=recent.date, y=recent.close, mode="markers", name="點選 K 棒",
            marker={"size": 22, "opacity": 0.015, "color": "#38bdf8"},
            selected={"marker": {"opacity": 0.95, "size": 16, "color": "#facc15"}},
            unselected={"marker": {"opacity": 0.015}},
            showlegend=False,
            customdata=recent.index.to_numpy(), hoverinfo="skip",
        ), row=1, col=1)
    fig.update_layout(
        height=560, xaxis_rangeslider_visible=False,
        margin={"l": 62, "r": 22, "t": 44, "b": 36},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "left", "x": 0},
        hovermode="x unified",
        clickmode="event+select",
        selectionrevision="beginner-kbar-selection",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,.62)",
        font={"color": "#dbeafe"},
        hoverlabel={"bgcolor": "#0f172a", "font_color": "#f8fafc"},
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="rgba(148,163,184,.12)",
        tickfont={"color": "#cbd5e1"},
    )
    fig.update_yaxes(
        showgrid=True, gridcolor="rgba(148,163,184,.12)",
        tickfont={"color": "#cbd5e1"}, separatethousands=True,
    )
    if beginner_mode():
        selected_points = plotly_events(
            fig,
            click_event=True,
            select_event=False,
            hover_event=False,
            override_height=560,
            override_width="100%",
            key="beginner-kbar-click-chart",
        )
    else:
        st.plotly_chart(
            fig, use_container_width=True, key="price-kbar-chart",
            config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
        )
        selected_points = []
    if beginner_mode():
        st.caption("🔴 紅 K＝收盤高於開盤；🟢 綠 K＝收盤低於開盤。點一下 K 棒可看白話解讀；點擊不會改變分析結果。")
        if selected_points:
            point = selected_points[-1]
            selected_x = point.get("x") if isinstance(point, dict) else getattr(point, "x", None)
            if selected_x is not None:
                selected_date = pd.to_datetime(selected_x).date()
                matched = recent[pd.to_datetime(recent.date).dt.date == selected_date]
                if not matched.empty:
                    row = matched.iloc[-1]
                    pattern, meaning = explain_kbar(row)
                    day_change = float(row["change_pct"]) if pd.notna(row["change_pct"]) else 0.0
                    with st.container(border=True):
                        st.markdown(f"#### 🕯️ 點選的 K 棒：{selected_date:%Y-%m-%d}")
                        st.markdown(f"**型態判讀：{pattern}**")
                        values = st.columns(4)
                        values[0].metric("開盤", f"{row.open:,.2f}")
                        values[1].metric("最高", f"{row.high:,.2f}")
                        values[2].metric("最低", f"{row.low:,.2f}")
                        values[3].metric(
                            "收盤", f"{row.close:,.2f}", f"{day_change:+.2f}%",
                            delta_color="inverse",
                        )
                        st.info(f"這根 K 棒代表：{meaning}")
                        st.caption("型態名稱是依單根 K 棒比例做的輔助辨識，不代表下一交易日必然上漲或下跌。")
        else:
            st.info("🖱️ 尚未選取 K 棒：請直接點一下圖中的任一根 K 棒，下方就會顯示該日型態解說。")


def _render_hot_list_content(provider: HybridTaiwanProvider, clock) -> None:
    st.subheader("市場熱門清單")
    is_trading = clock.status == "交易中"
    use_current_day_snapshot = clock.status in ("交易中", "已收盤")
    if clock.status == "已收盤" and st.button(
        "重新抓取今日收盤排行",
        key="refresh-closed-market-ranking",
        use_container_width=True,
    ):
        provider.cache.delete("hot:mis:full-market:v3")
    try:
        hot = provider.get_hot_lists(refresh=use_current_day_snapshot)
    except Exception as exc:
        st.warning(f"暫時無法取得市場排行：{exc}")
        return
    refreshed_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    if is_trading:
        st.caption(f"🟢 盤中排行每 10 秒自動更新｜最右側＝相較昨收漲跌幅｜本次更新：{refreshed_at}")
    elif clock.status == "已收盤":
        st.caption(f"🔵 今日收盤排行（盤後快取 5 分鐘）｜最右側＝今日收盤相較昨收漲跌幅｜檢查時間：{refreshed_at}")
    else:
        st.caption(f"⚪ 目前{clock.status}，顯示最近官方盤後排行｜最右側＝相較前一交易日收盤價｜檢查時間：{refreshed_at}")
    industries = sorted({stock.industry or "其他業" for stock in provider.search_stocks()})
    selected_industry = st.selectbox(
        "產業分類",
        ["全部產業", *industries],
        key="market_rank_industry",
        help="排行先依成交量或漲跌幅產生，再顯示所選產業中的標的。",
    )
    columns = st.columns(3)
    for column, key, title in zip(columns, ("volume", "gainers", "losers"), ("成交量排行", "漲幅排行", "跌幅排行")):
        with column:
            st.markdown(f"**{title}**")
            ranking = hot[key]
            if selected_industry != "全部產業":
                ranking = [item for item in ranking if item.get("industry") == selected_industry]
            if not ranking:
                st.caption("此產業目前沒有進入前 50 名的標的。")
            for rank, item in enumerate(ranking[:10], start=1):
                change_class = (
                    "change-up" if item["change_pct"] > 0
                    else "change-down" if item["change_pct"] < 0
                    else "change-flat"
                )
                direction = "▲" if item["change_pct"] > 0 else "▼" if item["change_pct"] < 0 else "—"
                market_time = item.get("market_time")
                source = item.get("source", "來源未提供")
                expects_today = clock.status in ("交易中", "已收盤")
                is_current = bool(
                    market_time
                    and (
                        not expects_today
                        or market_time.date() == datetime.now(market_time.tzinfo).date()
                    )
                )
                if expects_today and not is_current:
                    change_class = "change-flat"
                    direction = "⚠"
                    change_text = "今日行情待更新"
                else:
                    change_text = f"{direction} {item['change_pct']:+.2f}%"
                if market_time:
                    local_market_time = market_time.astimezone()
                    if "盤後" in source or (
                        local_market_time.hour == 0 and local_market_time.minute == 0
                    ):
                        time_text = local_market_time.strftime("%m/%d 收盤")
                    else:
                        time_text = local_market_time.strftime("%m/%d %H:%M")
                else:
                    time_text = "行情日期未提供"
                source_text = (
                    "MIS 即時" if "MIS" in source
                    else "Yahoo 最新" if "Yahoo" in source
                    else "官方盤後"
                )
                st.markdown(
                    f'<div class="hot-rank-card">'
                    f'<div class="rank-line"><span class="stock-name">{rank}. {item["code"]} {item["name"]}</span>'
                    f'<span class="{change_class}">{change_text}</span></div>'
                    f'<div class="rank-meta">{item.get("industry", "其他業")}　｜　'
                    f'現價 {item["price"]:,.2f}　｜　{time_text} · {source_text}</div></div>',
                    unsafe_allow_html=True,
                )
                if st.button("查看分析", key=f"hot-{key}-{item['code']}", use_container_width=True):
                    st.session_state.pending_stock = item["code"]
                    st.session_state.active_page = "智慧分析"
                    st.rerun()


@st.fragment(run_every="10s")
def _render_live_hot_list(provider: HybridTaiwanProvider) -> None:
    _render_hot_list_content(provider, market_clock("台股"))


def render_hot_list(provider: HybridTaiwanProvider) -> None:
    clock = market_clock("台股")
    if clock.status == "交易中":
        _render_live_hot_list(provider)
    else:
        _render_hot_list_content(provider, clock)


def render_market_overview(provider: HybridTaiwanProvider) -> None:
    st.subheader("台灣加權指數｜大盤趨勢")
    st.caption("先看整體市場方向，再進入個股分析；大盤趨勢不代表每一檔股票都會同方向移動。")
    refresh_market = st.button("重新整理大盤", key="refresh-market-index")
    try:
        prices, quote = provider.get_market_index(refresh=refresh_market)
    except Exception as exc:
        st.warning(f"暫時無法取得大盤資料：{exc}")
        return
    prices = add_indicators(prices)
    latest = prices.iloc[-1]
    above_ma20 = pd.notna(latest.ma20) and latest.close >= latest.ma20
    above_ma60 = pd.notna(latest.ma60) and latest.close >= latest.ma60
    if above_ma20 and above_ma60:
        trend, trend_note = "偏多趨勢", "指數位於月線與季線之上，整體價格趨勢相對較強。"
    elif not above_ma20 and not above_ma60:
        trend, trend_note = "偏弱趨勢", "指數位於月線與季線之下，市場風險相對較高。"
    else:
        trend, trend_note = "震盪整理", "月線與季線訊號不同，市場方向尚未一致。"

    metrics = st.columns(4)
    metric_card(metrics[0], "加權指數", f"{quote.price:,.2f}", f"{quote.change_pct:+.2f}%", "漲跌幅")
    metrics[1].metric("目前趨勢", trend)
    metrics[2].metric("月線 MA20", f"{latest.ma20:,.2f}" if pd.notna(latest.ma20) else "資料不足")
    metrics[3].metric("季線 MA60", f"{latest.ma60:,.2f}" if pd.notna(latest.ma60) else "資料不足")

    recent = filter_chart_range(prices, "半年內")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=recent.date, y=recent.close, name="加權指數", line={"color": "#60a5fa", "width": 2.4}))
    fig.add_trace(go.Scatter(x=recent.date, y=recent.ma20, name="MA20 月線", line={"color": "#facc15", "width": 1.7}))
    fig.add_trace(go.Scatter(x=recent.date, y=recent.ma60, name="MA60 季線", line={"color": "#22d3ee", "width": 1.7}))
    style_technical_chart(fig, 440)
    st.plotly_chart(fig, use_container_width=True, key="market-index-trend")
    if trend == "偏多趨勢":
        st.success(f"大盤判讀：{trend_note}")
    elif trend == "偏弱趨勢":
        st.warning(f"大盤判讀：{trend_note}")
    else:
        st.info(f"大盤判讀：{trend_note}")
    market_time = quote.meta.market_time.astimezone().strftime("%Y-%m-%d %H:%M") if quote.meta.market_time else "時間未知"
    st.caption(f"行情時間：{market_time}｜資料來源：{quote.meta.source}｜僅供市場環境參考")
    render_industry_heat(provider)


def render_industry_heat(provider: HybridTaiwanProvider) -> None:
    st.markdown("### 產業熱度與警示")
    st.caption("依產業平均漲跌、上漲家數比例與成交活躍度整理；紅色偏強、黃色觀察、綠色偏弱。")
    clock = market_clock("台股")
    try:
        snapshot = provider.get_hot_lists(
            refresh=clock.status in ("交易中", "已收盤")
        ).get("all", [])
    except Exception as exc:
        st.warning(f"產業熱度暫時無法取得：{exc}")
        return
    frame = pd.DataFrame(snapshot)
    if frame.empty or "industry" not in frame:
        st.info("目前沒有足夠的產業行情資料。")
        return
    frame = frame[(frame["industry"].notna()) & (frame["industry"] != "ETF")].copy()
    if frame.empty:
        st.info("目前沒有足夠的個股產業資料。")
        return
    industry = (
        frame.groupby("industry", as_index=False)
        .agg(
            平均漲跌幅=("change_pct", "mean"),
            上漲比例=("change_pct", lambda values: float((values > 0).mean())),
            成交量=("volume", "sum"),
            股票數=("code", "nunique"),
        )
    )
    industry["熱度分數"] = (
        50
        + industry["平均漲跌幅"].clip(-10, 10) * 4
        + (industry["上漲比例"] - 0.5) * 30
    ).clip(0, 100)
    industry["狀態"] = industry["熱度分數"].apply(
        lambda score: "強勢關注" if score >= 60 else "弱勢警示" if score < 40 else "中性觀察"
    )
    color_map = {"強勢關注": "#ff5b61", "中性觀察": "#facc15", "弱勢警示": "#22c55e"}

    chart_left, chart_right = st.columns([1, 1.35])
    pie_data = industry.nlargest(12, "成交量").copy()
    with chart_left:
        pie = go.Figure(go.Pie(
            labels=pie_data["industry"],
            values=pie_data["成交量"],
            hole=.58,
            marker={"colors": [color_map[state] for state in pie_data["狀態"]]},
            customdata=pie_data[["平均漲跌幅", "上漲比例", "熱度分數"]],
            hovertemplate=(
                "%{label}<br>成交量占比 %{percent}<br>平均漲跌 %{customdata[0]:+.2f}%"
                "<br>上漲家數 %{customdata[1]:.0%}<br>熱度 %{customdata[2]:.0f}<extra></extra>"
            ),
        ))
        pie.update_layout(
            title="主要產業成交熱度",
            height=430,
            margin={"l": 10, "r": 10, "t": 52, "b": 10},
            paper_bgcolor="rgba(0,0,0,0)",
            font={"color": "#dbeafe"},
            legend={"orientation": "h", "y": -0.05},
        )
        st.plotly_chart(pie, use_container_width=True, key="industry-heat-pie")
    with chart_right:
        ranked = industry.sort_values("熱度分數").tail(16)
        bars = go.Figure(go.Bar(
            x=ranked["熱度分數"],
            y=ranked["industry"],
            orientation="h",
            marker_color=[color_map[state] for state in ranked["狀態"]],
            customdata=ranked[["平均漲跌幅", "上漲比例", "股票數"]],
            hovertemplate=(
                "%{y}<br>熱度 %{x:.0f}<br>平均漲跌 %{customdata[0]:+.2f}%"
                "<br>上漲家數 %{customdata[1]:.0%}<br>樣本 %{customdata[2]:.0f} 檔<extra></extra>"
            ),
        ))
        bars.update_layout(
            title="產業熱度排行",
            height=430,
            margin={"l": 18, "r": 18, "t": 52, "b": 35},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,23,42,.38)",
            font={"color": "#dbeafe"},
            xaxis={"range": [0, 100], "title": "熱度分數"},
            yaxis={"title": ""},
        )
        st.plotly_chart(bars, use_container_width=True, key="industry-heat-bars")

    strong = industry.sort_values("熱度分數", ascending=False).head(5)
    weak = industry.sort_values("熱度分數").head(5)
    status_counts = industry["狀態"].value_counts()
    summary_cols = st.columns(3)
    summary_cols[0].success(
        "強勢關注\n\n" + "、".join(
            f"{row.industry} {row.熱度分數:.0f}" for row in strong.itertuples()
        )
    )
    summary_cols[1].warning(
        f"中性觀察：{status_counts.get('中性觀察', 0)} 個產業\n\n"
        "強勢不代表適合追價，仍需查看個股估值與風險。"
    )
    summary_cols[2].error(
        "弱勢警示\n\n" + "、".join(
            f"{row.industry} {row.熱度分數:.0f}" for row in weak.itertuples()
        )
    )
    if len(frame) < 100:
        st.caption(f"目前以 {len(frame)} 檔可取得行情的股票作為產業樣本，資料覆蓋不足時請降低解讀信心。")


def render_trend_rankings(
    provider: HybridTaiwanProvider,
    default_horizon: str,
    risk_profile: str,
) -> None:
    st.subheader("技術趨勢排行")
    st.caption(
        "依均線、MACD、RSI、KD、成交量與風險資料分類；排行代表目前技術狀態，不是未來漲跌保證。"
    )
    industry_options = ["全部產業", *sorted({
        stock.industry or "其他業" for stock in provider.search_stocks()
    })]
    with st.container(border=True):
        control_horizon, control_industry, control_count, control_action = st.columns([1.4, 1.4, 1.2, 1])
        trend_horizon = control_horizon.selectbox(
            "分析週期",
            ["短線", "波段", "中長期"],
            index=["短線", "波段", "中長期"].index(default_horizon),
            format_func={"短線": "短期 1–10 日", "波段": "中期 1–3 月", "中長期": "長期 6–24 月"}.get,
            key="trend-rank-horizon",
        )
        trend_industry = control_industry.selectbox(
            "產業分類", industry_options, key="trend-rank-industry"
        )
        candidate_count = control_count.select_slider(
            "掃描候選數", options=[10, 20, 30], value=20, key="trend-rank-count"
        )
        force_scan = control_action.button(
            "重新掃描", type="primary", use_container_width=True, key="trend-rank-scan"
        )

    scan_signature = (trend_horizon, trend_industry, candidate_count, risk_profile)
    cached_signature = st.session_state.get("trend_rank_signature")
    should_scan = force_scan or not st.session_state.get("trend_rank_results") or cached_signature != scan_signature
    if should_scan:
        try:
            hot = provider.get_hot_lists(
                refresh=market_clock("台股").status in ("交易中", "已收盤")
            )
        except Exception as exc:
            st.warning(f"趨勢候選暫時無法取得：{exc}")
            return
        candidates: list[str] = []
        for item in hot["volume"] + hot["gainers"] + hot["losers"]:
            if trend_industry != "全部產業" and item.get("industry") != trend_industry:
                continue
            if item["code"] not in candidates:
                candidates.append(item["code"])
            if len(candidates) >= candidate_count:
                break
        if not candidates:
            st.info("目前沒有符合此產業條件的候選股票。")
            return
        progress = st.progress(0, text="正在建立技術趨勢排行…")
        scanned = []
        for index, code in enumerate(candidates):
            try:
                result = analyze_stock(
                    provider,
                    StockAnalysisRequest(code, trend_horizon, risk_profile),
                )
                trend_label, trend_icon, trend_class, reasons = technical_trend_view(
                    result.prices.iloc[-1]
                )
                if trend_label.startswith("偏多"):
                    category = "看漲"
                    direction_score = result.technical_score
                elif trend_label.startswith("偏空"):
                    category = "看跌"
                    direction_score = 100 - result.technical_score
                else:
                    category = "盤整"
                    direction_score = 100 - abs(result.technical_score - 50) * 2
                rank_score = max(0, direction_score) * result.confidence / 100
                scanned.append({
                    "result": result,
                    "category": category,
                    "trend_label": trend_label,
                    "trend_icon": trend_icon,
                    "trend_class": trend_class,
                    "reasons": reasons,
                    "rank_score": rank_score,
                })
            except Exception:
                pass
            progress.progress(
                (index + 1) / len(candidates),
                text=f"已分析 {index + 1}/{len(candidates)}",
            )
        progress.empty()
        st.session_state.trend_rank_results = scanned
        st.session_state.trend_rank_signature = scan_signature
        st.session_state.trend_rank_time = datetime.now().astimezone()

    scanned = st.session_state.get("trend_rank_results", [])
    if not scanned:
        st.info("目前沒有足夠資料建立趨勢排行。")
        return
    scan_time = st.session_state.get("trend_rank_time")
    if scan_time:
        st.caption(
            f"本次排行時間：{scan_time:%Y-%m-%d %H:%M:%S}｜"
            "排序值＝方向強度 × 資料信心度；建議約每 5 分鐘重新掃描。"
        )
    bullish_tab, neutral_tab, bearish_tab = st.tabs(["🔴 看漲趨勢", "🟡 盤整觀望", "🟢 看跌趨勢"])
    for tab, category in zip(
        (bullish_tab, neutral_tab, bearish_tab),
        ("看漲", "盤整", "看跌"),
    ):
        with tab:
            items = sorted(
                (item for item in scanned if item["category"] == category),
                key=lambda item: item["rank_score"],
                reverse=True,
            )
            if not items:
                st.info(f"本次候選中沒有明確的{category}標的。")
                continue
            for rank, item in enumerate(items, start=1):
                result = item["result"]
                with st.container(border=True):
                    info, scores, action = st.columns([2.5, 1.4, 1])
                    info.markdown(
                        f"**{rank}. {item['trend_icon']} {result.stock.code} {result.stock.name}**  \n"
                        f"{result.stock.industry or '其他業'}｜{item['trend_label']}"
                    )
                    info.caption("｜".join(item["reasons"][:3]))
                    scores.metric(
                        "技術分數",
                        f"{result.technical_score:.0f}",
                        help="0–100 的技術條件分數；看跌排行會以反向強度排序。",
                    )
                    scores.caption(
                        f"信心 {result.confidence:.0f}%｜排序 {item['rank_score']:.1f}"
                    )
                    if action.button(
                        "查看完整分析",
                        key=f"trend-open-{category}-{result.stock.code}",
                        use_container_width=True,
                    ):
                        st.session_state.pending_stock = result.stock.code
                        st.session_state.active_page = "智慧分析"
                        st.rerun()
    st.info(
        "「看漲」表示目前技術條件相對偏多；「看跌」表示風險或弱勢訊號較多。"
        "兩者都可能因價格、成交量或市場環境改變而快速翻轉。"
    )


def render_opportunity_scan(provider: HybridTaiwanProvider, horizon: str, risk_profile: str) -> None:
    st.subheader("近期值得關注的候選")
    st.caption("候選來自官方成交量與漲幅排行，再以技術、基本、籌碼與風險資料重新評分；不是保證上漲清單。")
    if "scan_horizon" not in st.session_state:
        st.session_state.scan_horizon = "波段"
    if "_previous_scan_horizon" not in st.session_state:
        st.session_state._previous_scan_horizon = st.session_state.scan_horizon
    industry_options = ["全部產業", *sorted({
        stock.industry or "其他業" for stock in provider.search_stocks()
    })]
    if "scan_industry" not in st.session_state:
        st.session_state.scan_industry = "全部產業"
    if "_previous_scan_industry" not in st.session_state:
        st.session_state._previous_scan_industry = st.session_state.scan_industry
    with st.container(border=True):
        selected_horizon = st.segmented_control(
            "投資週期",
            options=["短線", "波段", "中長期"],
            format_func={"短線": "短期投資", "波段": "中期投資", "中長期": "長期投資"}.get,
            key="scan_horizon",
            help="短期約 1–10 日；中期約 1–3 個月；長期約 6–24 個月。",
        )
        if selected_horizon != st.session_state._previous_scan_horizon:
            st.session_state.pop("opportunity_results", None)
            st.session_state._previous_scan_horizon = selected_horizon
        horizon = selected_horizon or "波段"
        range_text = {
            "短線": "1–10 個交易日｜技術與籌碼權重較高",
            "波段": "1–3 個月｜技術、基本與籌碼均衡",
            "中長期": "6–24 個月｜基本面與風險權重較高",
        }[horizon]
        st.markdown(f'<div class="result-count">目前選擇：{range_text}</div>', unsafe_allow_html=True)
        control_industry, control_count, control_action = st.columns([1.45, 1.7, 1])
        selected_industry = control_industry.selectbox(
            "產業分類",
            industry_options,
            key="scan_industry",
        )
        if selected_industry != st.session_state._previous_scan_industry:
            st.session_state.pop("opportunity_results", None)
            st.session_state._previous_scan_industry = selected_industry
        max_candidates = control_count.select_slider(
            "最多顯示筆數", options=[10, 20, 30, 40, 50], value=20,
            key="scan_max_candidates",
        )
        start_scan = control_action.button(
            "開始掃描",
            type="primary",
            use_container_width=True,
            key="start-opportunity-scan",
        )
    if start_scan:
        hot = provider.get_hot_lists(refresh=True)
        candidates = []
        for item in hot["volume"] + hot["gainers"]:
            if selected_industry != "全部產業" and item.get("industry") != selected_industry:
                continue
            if item["code"] not in candidates:
                candidates.append(item["code"])
            if len(candidates) >= max_candidates:
                break
        progress = st.progress(0, text="正在分析候選標的…")
        results = []
        for index, code in enumerate(candidates):
            try:
                results.append(analyze_stock(
                    provider, StockAnalysisRequest(code, horizon, risk_profile)
                ))
            except Exception:
                pass
            progress.progress((index + 1) / len(candidates), text=f"已分析 {index + 1}/{len(candidates)}")
        progress.empty()
        st.session_state.opportunity_results = sorted(
            results, key=lambda x: (x.confidence >= 60, x.overall_score), reverse=True
        )
        st.session_state.opportunity_results_horizon = horizon
        st.session_state.opportunity_results_industry = selected_industry
    results = st.session_state.get("opportunity_results", [])
    if not results:
        st.info(f"已切換至{range_text}。按下「開始掃描」後，系統會依這個週期重新評分候選。")
        return
    st.markdown(
        f'<div class="result-count">本次找到 {len(results)} 檔候選｜產業：{selected_industry}｜分析週期：{range_text}</div>',
        unsafe_allow_html=True,
    )
    scan_headers = st.columns([2.4, 1.4, 1.7, 1])
    for col, label, align in zip(
        scan_headers, ("標的與建議", "分數／信心", "參考布局區", "操作"), ("", "right", "right", "")
    ):
        col.markdown(f'<div class="portfolio-head {align}">{label}</div>', unsafe_allow_html=True)
    for result in results:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.4, 1.4, 1.7, 1])
            css_class, level = advice_level(result.signal)
            icon = {"advice-green": "🟢", "advice-yellow": "🟡", "advice-red": "🔴"}[css_class]
            c1.markdown(
                f'<div class="portfolio-cell portfolio-name">{icon} {result.stock.code} {result.stock.name}'
                f'<br><span class="small-muted">{result.stock.industry or "其他業"}</span>'
                f'<br><span class="small-muted">{result.signal}</span></div>', unsafe_allow_html=True,
            )
            c2.markdown(
                f'<div class="portfolio-cell right">{result.overall_score:.0f} 分'
                f'<br><span class="small-muted">信心 {result.confidence:.0f}%</span></div>', unsafe_allow_html=True,
            )
            c3.markdown(
                f'<div class="portfolio-cell right">{result.watch_low:.2f}–{result.watch_high:.2f}</div>',
                unsafe_allow_html=True,
            )
            if c4.button("加入清單", key=f"scan-add-{result.stock.code}"):
                get_portfolio_store().upsert(PortfolioItem(result.stock.code, 0, 0, "近期關注"))
                st.toast(f"已加入 {result.stock.code}")


def previous_weekday(value):
    day = value - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def render_dividend_calendar(provider: HybridTaiwanProvider, analyzed) -> None:
    now = datetime.now().astimezone()
    rows = []
    warnings = []
    for item, result, *_ in analyzed:
        if item.shares <= 0 or result is None:
            continue
        try:
            events = provider.get_dividend_events(result.stock)
        except Exception as exc:
            warnings.append(f"{item.code}：{exc}")
            continue
        relevant = [
            event for event in events
            if event.ex_dividend_date is None
            or event.ex_dividend_date.year >= now.year - 1
        ][:6]
        for event in relevant:
            ex_date = event.ex_dividend_date
            last_holding = previous_weekday(ex_date) if ex_date else None
            if ex_date and ex_date > now:
                eligibility = f"需於 {last_holding:%Y-%m-%d} 收盤前持有"
            elif ex_date:
                eligibility = "若除息日前已持有，通常具領息資格"
            else:
                eligibility = "等待除息日公告"
            rows.append({
                "代碼": item.code,
                "名稱": result.stock.name,
                "持有股數": item.shares,
                "每股現金股利": event.cash_per_share,
                "預估稅前股息": item.shares * event.cash_per_share,
                "除息日": ex_date.strftime("%Y-%m-%d") if ex_date else "待公告",
                "最後持有參考日": last_holding.strftime("%Y-%m-%d") if last_holding else "待公告",
                "預計發放／入帳日": event.payment_date.strftime("%Y-%m-%d") if event.payment_date else "待公司／投信公告",
                "資格說明": eligibility,
                "狀態": event.status,
                "來源": event.source,
            })
    st.markdown("### 股息摘要")
    current_rows = [
        row for row in rows
        if row["除息日"] == "待公告" or row["除息日"].startswith(str(now.year))
    ]
    estimated = sum(row["預估稅前股息"] for row in current_rows)
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{now.year} 年目前可查股息", f"${estimated:,.0f}")
    c2.metric("有股息資料標的", len({row["代碼"] for row in rows}))
    c3.metric("待公告入帳日", sum(row["預計發放／入帳日"] == "待公司／投信公告" for row in rows))
    st.caption("金額為每股現金股利 × 目前記錄股數的稅前估算；實際資格以除息基準、持股紀錄、稅務及公司／投信公告為準。")
    if not rows:
        st.info("目前持股尚未找到近期股息公告或除息紀錄。")
    else:
        table = pd.DataFrame(rows)
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "每股現金股利": st.column_config.NumberColumn(format="$%.4f"),
                "預估稅前股息": st.column_config.NumberColumn(format="$%.0f"),
                "持有股數": st.column_config.NumberColumn(format="%.0f"),
            },
        )
    if warnings:
        with st.expander("部分資料取得失敗"):
            for warning in warnings:
                st.write(f"• {warning}")
    st.info("官方 OpenAPI 並非每一筆都提供現金發放日；未公告時會顯示待公告，不以固定天數推測入帳。")


def render_portfolio(provider: HybridTaiwanProvider, horizon: str, risk_profile: str) -> None:
    store = get_portfolio_store()
    st.subheader("我的組合清單")
    st.caption("先看總覽與顏色，再展開需要處理的標的；詳細價位與編輯欄位預設收合。")
    with st.expander("＋ 新增股票或 ETF"):
        with st.form("portfolio-add-form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
            code = c1.text_input("股票／ETF 代碼")
            shares = c2.number_input("股數", min_value=0.0, step=100.0)
            cost = c3.number_input("平均成本", min_value=0.0, step=1.0)
            note = c4.text_input("備註")
            submitted = st.form_submit_button("加入組合")
            if submitted:
                try:
                    provider.get_stock(code.strip())
                    store.upsert(PortfolioItem(code.strip(), shares, cost, note))
                    st.success(f"已保存 {code.strip()}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"無法加入：{exc}")
    items = store.list()
    analyzed = []
    for item in items:
        try:
            result = analyze_stock(provider, StockAnalysisRequest(item.code, horizon, risk_profile))
            action, reason = holding_action(result, item.average_cost)
            css_class, level = advice_level(action)
            analyzed.append((item, result, action, reason, css_class, level))
        except Exception as exc:
            analyzed.append((item, None, "暫時無法分析", str(exc), "advice-yellow", "資料異常"))

    held = [row for row in analyzed if row[0].shares > 0]
    market_value = sum(row[0].shares * row[1].quote.price for row in held if row[1])
    total_cost = sum(row[0].shares * row[0].average_cost for row in held)
    pnl = market_value - total_cost
    status_counts = {
        "green": sum(row[4] == "advice-green" for row in held),
        "yellow": sum(row[4] == "advice-yellow" for row in held),
        "red": sum(row[4] == "advice-red" for row in held),
    }
    summary_finance = st.columns(3)
    summary_finance[0].metric("持有市值", f"${market_value:,.0f}")
    summary_finance[1].metric("投入成本", f"${total_cost:,.0f}")
    summary_finance[2].metric(
        "未實現損益",
        f"${pnl:,.0f}",
        f"{pnl / total_cost:+.1%}" if total_cost else None,
        delta_color="inverse",
    )
    summary_status = st.columns(3)
    summary_status[0].metric("🟢 建議較高", status_counts["green"])
    summary_status[1].metric("🟡 觀察", status_counts["yellow"])
    summary_status[2].metric("🔴 優先處理", status_counts["red"])

    held_tab, watch_tab, dividend_tab = st.tabs([
        f"持有（{len(held)}）",
        f"關注（{sum(row[0].shares == 0 for row in analyzed)}）",
        "股息行事曆",
    ])

    def render_items(target, holding: bool):
        subset = [row for row in analyzed if (row[0].shares > 0) == holding]
        with target:
            section_label = "持有部位" if holding else "關注清單"
            section_hint = "市值與損益依最新可用價格估算" if holding else "尚未計入持有部位與總成本"
            st.markdown(
                f'<div class="portfolio-section-title"><b>{section_label}</b><span>{section_hint}</span></div>',
                unsafe_allow_html=True,
            )
            if not subset:
                st.info("目前沒有資料。")
            else:
                headers = st.columns([2.2, 1.25, 1.75, 1.4])
                for col, label, align in zip(
                    headers,
                    ("股票", "現價／報酬", "持有股數／平均成本", "部位市值"),
                    ("", "right", "right", "right"),
                ):
                    col.markdown(
                        f'<div class="portfolio-head {align}">{label}</div>',
                        unsafe_allow_html=True,
                    )
            for item, result, action, reason, css_class, level in subset:
                if result is None:
                    with st.expander(f"🟡 {item.code}｜暫時無法分析"):
                        st.warning(reason)
                    continue
                gain = result.quote.price / item.average_cost - 1 if item.average_cost else None
                icon = {"advice-green": "🟢", "advice-yellow": "🟡", "advice-red": "🔴"}[css_class]
                gain_text = f"{gain:+.1%}" if gain is not None else "未設定成本"
                market_value = item.shares * result.quote.price
                with st.container(border=True):
                    cells = st.columns([2.2, 1.25, 1.75, 1.4])
                    values = (
                        f"{icon} {item.code} {result.stock.name}<br><span class='small-muted'>{result.stock.industry or '其他業'}</span>",
                        f"${result.quote.price:,.2f}<br><span class='small-muted'>{gain_text}</span>",
                        f"{item.shares:,.0f} 股<br><span class='small-muted'>成本 ${item.average_cost:,.2f}</span>" if item.average_cost else f"{item.shares:,.0f} 股<br><span class='small-muted'>未設定成本</span>",
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
