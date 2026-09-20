import calendar
from datetime import date, datetime, timedelta, timezone

import extra_streamlit_components as stx
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="每日待辦清單", page_icon="📅", layout="centered")

# 手機直立時 Streamlit 會把 st.columns 拆成一欄一列,月曆會變成一週七列。
# 這段只在窄螢幕生效,讓月曆格子和任務列維持橫排。
st.markdown(
    """
    <style>
    @media (max-width: 640px) {
        .block-container { padding: 1rem 0.6rem 4rem !important; }
        h1 { font-size: 1.5rem !important; }

        [class*="st-key-cal"] [data-testid="stHorizontalBlock"],
        [class*="st-key-row"] [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
            gap: 0.25rem !important;
        }
        [class*="st-key-cal"] [data-testid="stColumn"],
        [class*="st-key-row"] [data-testid="stColumn"] {
            min-width: 0 !important;
        }

        [class*="st-key-cal"] .stButton button,
        [class*="st-key-cal"] .stButton button p {
            padding: 0.15rem 0 !important;
            font-size: 0.72rem !important;
            line-height: 1.25 !important;
        }
        [class*="st-key-row"] .stButton button { padding: 0.15rem 0 !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Supabase 連線 ----------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]


def get_supabase() -> Client:
    """每個瀏覽器 session 各自持有一個 Client。

    不能用 @st.cache_resource:那會讓整個 App 共用同一個 Client,
    後登入者的 access token 會蓋掉前一位,RLS 的 auth.uid() 就會指向錯誤的人。
    """
    if "supabase" not in st.session_state:
        st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return st.session_state.supabase


supabase = get_supabase()

CATEGORIES = {
    "工作": "#4A90D9",
    "生活": "#67C23A",
    "學習": "#E6A23C",
    "其他": "#909399",
}

# ---------- 記住登入(把 refresh token 存在瀏覽器 cookie) ----------
COOKIE_NAME = "sb_refresh_token"
COOKIE_DAYS = 30


def get_cookie_manager() -> stx.CookieManager:
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager(key="auth_cookies")
    return st.session_state.cookie_manager


cookies = get_cookie_manager()


def remember_session(session) -> None:
    """把 access token 和 refresh token 一起存進 cookie。

    兩個都存,下次載入才能先用 access token 認身分。只存 refresh token 的話,
    每次開啟都得拿它去換新的,而它是一次性的 —— 新的還沒寫回 cookie 就關掉頁面,
    登入狀態就沒了。
    """
    if session is None or not session.refresh_token:
        return
    cookies.set(
        COOKIE_NAME,
        f"{session.access_token}|{session.refresh_token}",
        expires_at=datetime.now(timezone.utc) + timedelta(days=COOKIE_DAYS),
        key="cookie_set",
    )


def forget_session() -> None:
    try:
        cookies.delete(COOKIE_NAME, key="cookie_del")
    except Exception:
        pass


# token 真的被伺服器拒絕才算數;連線失敗之類的不該把人踢出去
FATAL_AUTH_ERRORS = ("AuthApiError", "AuthSessionMissingError", "AuthInvalidJwtError")


def restore_session() -> bool:
    """重新整理後,用 cookie 裡的 token 換回登入狀態。"""
    raw = cookies.get(COOKIE_NAME)
    if not raw or not isinstance(raw, str):
        return False

    try:
        if "|" in raw:
            access_token, refresh_token = raw.split("|", 1)
            # access token 還沒過期的話,set_session 不會動到 refresh token
            res = supabase.auth.set_session(access_token, refresh_token)
        else:
            # 舊版 cookie 只存了 refresh token,換一次就會升級成新格式
            refresh_token = raw
            res = supabase.auth.refresh_session(refresh_token)
    except Exception as e:
        if type(e).__name__ in FATAL_AUTH_ERRORS:
            forget_session()
        return False

    if res.session is None:
        return False

    st.session_state.user = res.user
    if res.session.refresh_token != refresh_token:
        remember_session(res.session)  # 真的換過 token 才寫回去
    return True


# ---------- 登入 / 註冊 ----------


def login_page():
    st.title("📅 每日待辦清單")
    tab1, tab2 = st.tabs(["登入", "註冊"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("密碼", type="password", key="login_pw")
        st.checkbox("記住我(30 天內免再登入)", value=True, key="remember_me")
        if st.button("登入", use_container_width=True):
            try:
                res = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                st.session_state.user = res.user
                if st.session_state.get("remember_me", True):
                    remember_session(res.session)
                st.rerun()
            except Exception as e:
                st.error(f"登入失敗:{e}")

    with tab2:
        email2 = st.text_input("Email", key="signup_email")
        password2 = st.text_input("密碼(至少 6 碼)", type="password", key="signup_pw")
        if st.button("註冊", use_container_width=True):
            try:
                res = supabase.auth.sign_up({"email": email2, "password": password2})
                if res.session is not None:
                    # Supabase 關掉 Email 驗證時會直接發 session,等同已登入
                    st.session_state.user = res.user
                    remember_session(res.session)
                    st.rerun()
                else:
                    st.success("註冊成功!請至信箱完成驗證後,回到「登入」分頁登入。")
            except Exception as e:
                st.error(f"註冊失敗:{e}")


if "user" not in st.session_state:
    cookies.get_all()  # 讓 cookie 元件先掛載,回來時會自動觸發一次 rerun
    restore_session()

if "user" not in st.session_state:
    login_page()
    st.stop()

user = st.session_state.user
user_id = user.id

with st.sidebar:
    st.write(f"👤 {user.email}")
    if st.button("登出"):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        forget_session()
        st.session_state.pop("user", None)
        st.session_state.pop("selected_date", None)
        st.session_state.pop("supabase", None)  # 連同持有 token 的 Client 一起丟掉
        st.rerun()

# ---------- 資料存取 ----------


def fetch_month_tasks(year: int, month: int):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    res = (
        supabase.table("tasks")
        .select("task_date, is_completed")
        .eq("user_id", user_id)
        .gte("task_date", start.isoformat())
        .lt("task_date", end.isoformat())
        .execute()
    )
    return res.data


def fetch_day_tasks(day: date):
    res = (
        supabase.table("tasks")
        .select("*")
        .eq("user_id", user_id)
        .eq("task_date", day.isoformat())
        .order("created_at")
        .execute()
    )
    return res.data


def add_task(day: date, content: str, category: str):
    supabase.table("tasks").insert(
        {
            "user_id": user_id,
            "task_date": day.isoformat(),
            "content": content,
            "category": category,
            "is_completed": False,
        }
    ).execute()


def toggle_task(task_id: str, is_completed: bool):
    supabase.table("tasks").update({"is_completed": is_completed}).eq(
        "id", task_id
    ).execute()


def update_task(task_id: str, content: str, category: str):
    supabase.table("tasks").update({"content": content, "category": category}).eq(
        "id", task_id
    ).execute()


def delete_task(task_id: str):
    supabase.table("tasks").delete().eq("id", task_id).execute()


# ---------- Session state ----------
if "view_year" not in st.session_state:
    today = date.today()
    st.session_state.view_year = today.year
    st.session_state.view_month = today.month
if "selected_date" not in st.session_state:
    st.session_state.selected_date = None
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None

# ---------- 月曆畫面 ----------


def render_calendar():
    year = st.session_state.view_year
    month = st.session_state.view_month

    tasks = fetch_month_tasks(year, month)
    status_by_day = {}
    for t in tasks:
        status_by_day.setdefault(t["task_date"], []).append(t["is_completed"])

    cal = calendar.Calendar(firstweekday=6)  # 星期日開頭
    weeks = cal.monthdayscalendar(year, month)
    weekday_labels = ["日", "一", "二", "三", "四", "五", "六"]
    today = date.today()

    # key="cal" 會在外層加上 st-key-cal 這個 class,手機版 CSS 靠它認出月曆
    with st.container(key="cal"):
        col1, col2, col3 = st.columns([1, 2, 1], vertical_alignment="center")
        with col1:
            if st.button("◀", use_container_width=True, help="上個月"):
                if month == 1:
                    st.session_state.view_year -= 1
                    st.session_state.view_month = 12
                else:
                    st.session_state.view_month -= 1
                st.rerun()
        with col2:
            st.markdown(
                f"<div style='text-align:center;font-weight:bold;font-size:1.1rem'>"
                f"{year} 年 {month} 月</div>",
                unsafe_allow_html=True,
            )
        with col3:
            if st.button("▶", use_container_width=True, help="下個月"):
                if month == 12:
                    st.session_state.view_year += 1
                    st.session_state.view_month = 1
                else:
                    st.session_state.view_month += 1
                st.rerun()

        header_cols = st.columns(7)
        for i, label in enumerate(weekday_labels):
            header_cols[i].markdown(
                f"<div style='text-align:center;font-weight:bold'>{label}</div>",
                unsafe_allow_html=True,
            )

        for week in weeks:
            cols = st.columns(7)
            for i, day_num in enumerate(week):
                with cols[i]:
                    if day_num == 0:
                        st.write("")
                        continue
                    d = date(year, month, day_num)
                    d_str = d.isoformat()
                    mark = ""
                    if d_str in status_by_day:
                        mark = "🟢" if all(status_by_day[d_str]) else "🟠"
                    prefix = "🔷" if d == today else ""
                    label = f"{prefix}{day_num}{mark}"
                    if st.button(label, key=f"day_{d_str}", use_container_width=True):
                        st.session_state.selected_date = d
                        st.session_state.editing_id = None
                        st.rerun()

    st.caption("🟢 全部完成　🟠 還有沒做完的　🔷 今天")


# ---------- 單日任務畫面 ----------


def render_task_editor(t: dict):
    """把某一列換成編輯框。"""
    with st.form(f"edit_form_{t['id']}"):
        c1, c2 = st.columns([3, 1])
        with c1:
            content = st.text_input(
                "任務內容", value=t["content"], label_visibility="collapsed"
            )
        with c2:
            names = list(CATEGORIES.keys())
            current = names.index(t["category"]) if t["category"] in names else len(names) - 1
            category = st.selectbox(
                "分類", names, index=current, label_visibility="collapsed"
            )

        b1, b2 = st.columns(2)
        saved = b1.form_submit_button("儲存", use_container_width=True)
        cancelled = b2.form_submit_button("取消", use_container_width=True)

        if saved and content.strip():
            update_task(t["id"], content.strip(), category)
            st.session_state.editing_id = None
            st.rerun()
        if cancelled:
            st.session_state.editing_id = None
            st.rerun()


def render_day_view(day: date):
    if st.button("⬅ 返回月曆"):
        st.session_state.selected_date = None
        st.session_state.editing_id = None
        st.rerun()

    st.subheader(day.strftime("%Y 年 %m 月 %d 日"))

    tasks = fetch_day_tasks(day)
    total = len(tasks)
    done = sum(1 for t in tasks if t["is_completed"])
    if total > 0:
        st.progress(done / total)
        st.caption(f"已完成 {done} / {total} 項")
    else:
        st.caption("尚未新增任務")

    for t in tasks:
        if st.session_state.get("editing_id") == t["id"]:
            render_task_editor(t)
            continue

        with st.container(key=f"row_{t['id']}"):
            c1, c2, c3, c4 = st.columns(
                [0.7, 5.3, 0.9, 0.9], vertical_alignment="center"
            )
            with c1:
                checked = st.checkbox(
                    "完成",
                    value=t["is_completed"],
                    key=f"chk_{t['id']}",
                    label_visibility="collapsed",
                )
                if checked != t["is_completed"]:
                    toggle_task(t["id"], checked)
                    st.rerun()
            with c2:
                color = CATEGORIES.get(t["category"], "#909399")
                text = t["content"]
                if t["is_completed"]:
                    text = (
                        f"<span style='text-decoration:line-through;color:gray'>"
                        f"{text}</span>"
                    )
                st.markdown(
                    f"<div style='word-break:break-word;line-height:1.4'>"
                    f"<span style='color:{color}'>●</span> {text}</div>",
                    unsafe_allow_html=True,
                )
            with c3:
                if st.button("✏️", key=f"edit_{t['id']}", help="編輯"):
                    st.session_state.editing_id = t["id"]
                    st.rerun()
            with c4:
                if st.button("🗑", key=f"del_{t['id']}", help="刪除"):
                    delete_task(t["id"])
                    st.rerun()

    st.divider()
    st.write("**新增任務**")
    with st.form("add_task_form", clear_on_submit=True):
        new_content = st.text_input("任務內容")
        new_category = st.selectbox("分類", list(CATEGORIES.keys()))
        submitted = st.form_submit_button("新增任務", use_container_width=True)
        if submitted and new_content.strip():
            add_task(day, new_content.strip(), new_category)
            st.rerun()


# ---------- 主流程 ----------
st.title("📅 每日待辦清單")

if st.session_state.selected_date:
    render_day_view(st.session_state.selected_date)
else:
    render_calendar()
