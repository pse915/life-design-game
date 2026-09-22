from __future__ import annotations

import base64
import html
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ============================================================
# LIFE DESIGN v5
# Robustness-first Streamlit life simulation for Home Economics
# ============================================================
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
CHAR_DIR = APP_DIR / "assets" / "characters" / "blocky"
CHAR_TEX_DIR = CHAR_DIR / "Textures"

# ---------- Safe data loading ----------
def load_json(name: str, fallback: Any) -> Any:
    path = DATA_DIR / name
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        st.warning(f"데이터 파일 '{name}'을 읽지 못해 기본값을 사용합니다: {exc}")
        return fallback

VALUES = load_json("values.json", [])
CAREERS = load_json("careers.json", [])
LIFE_STAGES = load_json("life_stages.json", [])
EVENTS = load_json("events.json", [])

DEFAULT_CHARACTERS = ["a", "d", "g", "j", "m", "q"]
VALUE_TO_TAG = {
    "도덕성": "도덕",
    "자기 발전": "성장",
    "자기 만족": "만족",
    "가정의 행복": "가족",
    "건강": "건강",
    "인간관계": "관계",
    "사회적 지위": "성취",
    "경제적 안정": "경제",
}

STAT_KEYS = ["건강", "경제", "가족", "인간관계", "자기발전", "만족도"]
ECON_KEYS = ["현금", "자산", "월소득", "월지출", "부채"]
HEADERS = [
    "학번", "회차", "저장시간", "캐릭터", "가치관", "생애목표", "직업목표",
    "건강목표", "경제목표", "가족목표", "자기발전목표", "최종직업",
    "건강", "경제", "가족", "인간관계", "자기발전", "만족도",
    "현금", "자산", "월소득", "월지출", "부채", "재무상태",
    "발생사건", "주요선택", "실행방안", "성찰",
]

st.set_page_config(
    page_title="LIFE DESIGN · 나의 생애 설계도",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Secrets / Google Sheets ----------
def secret(path: str, fallback: str = "") -> Any:
    cur: Any = st.secrets
    for key in path.split("."):
        try:
            cur = cur[key]
        except Exception:
            return fallback
    return cur

SHEET_URL = str(secret("app.spreadsheet_url", ""))
WORKSHEET = str(secret("app.worksheet_name", "학생정보"))
TEACHER_PIN = str(secret("app.teacher_pin", "1234"))


def get_ws():
    """Create a gspread worksheet only when the user actually saves/loads data."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except Exception as exc:
        raise RuntimeError(
            "Google Sheets 기능에 필요한 패키지가 없습니다. requirements.txt의 "
            "gspread/google-auth 설치 상태를 확인하세요."
        ) from exc

    if "google" not in st.secrets:
        raise RuntimeError("Streamlit Secrets에 [google] 서비스 계정 정보가 없습니다.")
    if not SHEET_URL:
        raise RuntimeError("Streamlit Secrets의 app.spreadsheet_url을 설정하세요.")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        dict(st.secrets["google"]), scopes=scopes
    )
    return gspread.authorize(creds).open_by_url(SHEET_URL).worksheet(WORKSHEET)


def col_letter(n: int) -> str:
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def ensure_headers(ws) -> None:
    first = ws.row_values(1)
    if not first:
        ws.append_row(HEADERS, value_input_option="RAW")
        return
    merged = list(first)
    for h in HEADERS:
        if h not in merged:
            merged.append(h)
    if merged != first:
        ws.update(f"A1:{col_letter(len(merged))}1", [merged])


def save_result(row: dict[str, Any]) -> None:
    ws = get_ws()
    ensure_headers(ws)
    headers = ws.row_values(1)
    ws.append_row([row.get(h, "") for h in headers], value_input_option="USER_ENTERED")


def student_rows(sid: str) -> list[dict[str, Any]]:
    ws = get_ws()
    ensure_headers(ws)
    wanted = str(sid).strip().lstrip("'")
    rows = ws.get_all_records()
    return [r for r in rows if str(r.get("학번", "")).strip().lstrip("'") == wanted]

# ---------- State ----------
def fresh_game() -> dict[str, Any]:
    return {
        "건강": 60,
        "경제": 50,
        "가족": 60,
        "인간관계": 60,
        "자기발전": 50,
        "만족도": 60,
        "stage": 0,
        "events": [],
        "choices": [],
        "choice_tags": [],
        "plans": [],
        "plan_effects": {},
        "cash": 300,
        "assets": 0,
        "income": 280,
        "expenses": 220,
        "debt": 0,
        "stage_finance": [],
    }


def init_state() -> None:
    st.session_state.setdefault("page", "start")
    st.session_state.setdefault("attempt", 1)
    st.session_state.setdefault("student_id", "")
    st.session_state.setdefault("character", "a")
    st.session_state.setdefault("values", [])
    st.session_state.setdefault("game", fresh_game())
    st.session_state.setdefault("completed_attempts", [])
    st.session_state.setdefault("saved_attempts", set())
    st.session_state.setdefault("reflection", "")
    st.session_state.setdefault("start_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def reset_game(new_attempt: bool = False) -> None:
    sid = st.session_state.get("student_id", "")
    character = st.session_state.get("character", "a")
    old_attempt = int(st.session_state.get("attempt", 1))
    completed = list(st.session_state.get("completed_attempts", []))
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.student_id = sid
    st.session_state.character = character
    st.session_state.attempt = old_attempt + 1 if new_attempt else 1
    st.session_state.page = "character" if new_attempt else "start"
    st.session_state.game = fresh_game()
    st.session_state.values = []
    st.session_state.completed_attempts = completed
    st.session_state.saved_attempts = set()
    st.session_state.reflection = ""
    st.session_state.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---------- Game mechanics ----------
def clamp(v: float, low: float = 0, high: float = 100) -> int:
    return int(max(low, min(high, round(v))))


def apply_effects(effects: dict[str, Any]) -> None:
    g = st.session_state.game
    for key, raw in (effects or {}).items():
        try:
            delta = float(raw)
        except (TypeError, ValueError):
            continue
        if key in STAT_KEYS:
            g[key] = clamp(g.get(key, 50) + delta)
        elif key == "현금":
            g["cash"] = max(0, int(g.get("cash", 0) + delta))
        elif key == "자산":
            g["assets"] = max(0, int(g.get("assets", 0) + delta))
        elif key == "부채":
            g["debt"] = max(0, int(g.get("debt", 0) + delta))
        elif key == "월소득":
            g["income"] = max(0, int(g.get("income", 0) + delta))
        elif key == "월지출":
            g["expenses"] = max(0, int(g.get("expenses", 0) + delta))


def finance_step() -> None:
    """Advance one life stage financially; prevents economy from being a cosmetic score."""
    g = st.session_state.game
    monthly_balance = int(g["income"] - g["expenses"])
    g["cash"] = max(0, int(g["cash"] + monthly_balance * 6))
    if monthly_balance > 0:
        g["assets"] += max(0, monthly_balance * 2)
        g["경제"] = clamp(g["경제"] + 4)
    elif monthly_balance < 0:
        shortage = abs(monthly_balance) * 3
        g["debt"] += shortage
        g["경제"] = clamp(g["경제"] - 7)
    if g["debt"] > g["assets"] + g["cash"]:
        g["경제"] = clamp(g["경제"] - 3)
    g["stage_finance"].append({
        "stage": int(g["stage"]),
        "현금": g["cash"],
        "자산": g["assets"],
        "부채": g["debt"],
        "월소득": g["income"],
        "월지출": g["expenses"],
    })


def value_alignment(tag: str) -> int:
    selected = set(st.session_state.get("values", []))
    tags = {VALUE_TO_TAG.get(v) for v in selected}
    return 4 if tag in tags else 0


def goal_alignment(choice_text: str) -> int:
    text = choice_text + " " + " ".join(
        str(st.session_state.get(k, ""))
        for k in ["career_goal", "health_goal", "economy_goal", "family_goal", "growth_goal"]
    )
    keyword_map = {
        "건강": ["건강", "운동", "식습관"],
        "경제": ["돈", "경제", "저축", "투자", "소득", "안정"],
        "가족": ["가족", "부모", "자녀", "관계"],
        "성장": ["공부", "배움", "성장", "자기계발", "진로"],
    }
    for tag, words in keyword_map.items():
        if any(w in text for w in words):
            return 2
    return 0


def effective_choice(choice: dict[str, Any]) -> dict[str, Any]:
    picked = dict(choice)
    effects = dict(picked.get("effects", {}))
    tag = str(picked.get("tag", ""))
    bonus = value_alignment(tag) + goal_alignment(str(picked.get("choice", "")))
    if bonus:
        effects["만족도"] = effects.get("만족도", 0) + bonus
    picked["effects"] = effects
    picked["alignment"] = bonus
    return picked


def career_effect(career: dict[str, Any]) -> None:
    g = st.session_state.game
    # Career choice creates both opportunity and cost rather than simply adding a score.
    g["income"] = max(100, 240 + int(career.get("economy", 0)) * 12)
    g["expenses"] = max(160, 210 + int(career.get("risk", 0)) * 5)
    g["경제"] = clamp(50 + int(career.get("economy", 0)))
    g["자기발전"] = clamp(50 + int(career.get("growth", 0)))
    risk = int(career.get("risk", 0))
    g["만족도"] = clamp(g["만족도"] + value_alignment(str(career.get("tag", ""))) - risk // 3)


def event_for_stage(stage_name: str) -> dict[str, Any] | None:
    matches = [e for e in EVENTS if str(e.get("stage", "")) == stage_name]
    if not matches:
        return None
    # Deterministic per stage: replay is comparable and not frustrating.
    return matches[0]

# ---------- 3D character viewer ----------
def show_character(letter: str, height: int = 430) -> None:
    """Safe public character renderer. Kept as show_character because older versions called this name."""
    letter = str(letter or "a").lower()
    if letter not in DEFAULT_CHARACTERS:
        letter = "a"
    glb = CHAR_DIR / f"character-{letter}.glb"
    tex = CHAR_TEX_DIR / f"texture-{letter}.png"
    if not glb.exists():
        st.error(f"캐릭터 모델 파일이 없습니다: {glb}")
        return
    try:
        g64 = base64.b64encode(glb.read_bytes()).decode("ascii")
        t64 = base64.b64encode(tex.read_bytes()).decode("ascii") if tex.exists() else ""
    except OSError as exc:
        st.error(f"캐릭터 파일을 읽지 못했습니다: {exc}")
        return

    texture_url = f"data:image/png;base64,{t64}" if t64 else ""
    # Three.js is used only as a browser renderer; Streamlit remains the app shell.
    src = f"""<!doctype html>
<html><body style="margin:0;overflow:hidden;background:transparent">
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
<script>
const scene=new THREE.Scene();
const camera=new THREE.PerspectiveCamera(28,innerWidth/innerHeight,.01,100);
const renderer=new THREE.WebGLRenderer({{alpha:true,antialias:true}});
renderer.setSize(innerWidth,innerHeight);renderer.setPixelRatio(Math.min(devicePixelRatio,2));
document.body.appendChild(renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff,0x888888,2.3));
const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(2,4,4);scene.add(light);
const loader=new THREE.GLTFLoader();
const textureURL={json.dumps(texture_url)};
loader.manager.setURLModifier(url=>{{
  const lower=url.toLowerCase();
  return lower.includes('texture-{letter}.png') ? textureURL : url;
}});
loader.load('data:model/gltf-binary;base64,{g64}',g=>{{
  const root=g.scene;scene.add(root);
  const box=new THREE.Box3().setFromObject(root);
  const size=box.getSize(new THREE.Vector3());
  const center=box.getCenter(new THREE.Vector3());
  root.position.sub(center);
  root.position.y-=size.y*.02;
  root.scale.setScalar(1.55/Math.max(size.x,size.y,size.z));
  let lastX=0,rot=0;
  addEventListener('pointerdown',e=>lastX=e.clientX);
  addEventListener('pointermove',e=>{{if(e.buttons){{rot+=(e.clientX-lastX)*.012;lastX=e.clientX;root.rotation.y=rot;}}}});
  function animate(){{requestAnimationFrame(animate);renderer.render(scene,camera);}} animate();
}},undefined,()=>document.body.innerHTML='<div style="font:14px sans-serif;color:#777;padding:20px">캐릭터를 불러오지 못했습니다.</div>');
addEventListener('resize',()=>{{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);}});
</script></body></html>"""
    components.html(src, height=height, scrolling=False)

# Backward-compatible alias for any old code path.
viewer = show_character

# ---------- UI ----------
def css() -> None:
    st.markdown(
        """<style>
        :root{color-scheme:light}
        .stApp{background:#f5f5f7;color:#1d1d1f}
        .block-container{max-width:1260px;padding-top:2rem;padding-bottom:5rem}
        [data-testid=stHeader]{background:rgba(245,245,247,.88)}
        h1,h2,h3{letter-spacing:-.045em}
        .hero,.card,.stage,.blueprint{background:#fff;border:1px solid #e5e5ea;border-radius:24px;box-shadow:0 10px 35px rgba(0,0,0,.045)}
        .hero{padding:36px 40px;margin-bottom:20px}
        .card{padding:22px;margin:10px 0}
        .stage{padding:20px}
        .blueprint{padding:24px}
        .eyebrow{color:#86868b;font-weight:750;letter-spacing:.09em;font-size:.75rem}
        .muted{color:#6e6e73}
        .pill{display:inline-block;background:#f2f2f7;border-radius:999px;padding:5px 10px;margin:3px;font-size:.86rem}
        div.stButton>button{border-radius:14px;min-height:44px;font-weight:650}
        [data-testid=stMetric]{background:#fff;border:1px solid #e5e5ea;border-radius:18px;padding:12px}
        </style>""",
        unsafe_allow_html=True,
    )


def metrics() -> None:
    g = st.session_state.game
    cols = st.columns(6)
    for c, key in zip(cols, STAT_KEYS):
        c.metric(key, int(g.get(key, 0)))


def finance_metrics() -> None:
    g = st.session_state.game
    a, b, c, d = st.columns(4)
    a.metric("현금", f"{g['cash']:,}")
    b.metric("자산", f"{g['assets']:,}")
    c.metric("월 잉여", f"{g['income'] - g['expenses']:,}")
    d.metric("부채", f"{g['debt']:,}")


def make_row() -> dict[str, Any]:
    g = st.session_state.game
    return {
        "학번": st.session_state.student_id,
        "회차": st.session_state.attempt,
        "저장시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "캐릭터": st.session_state.character,
        "가치관": ", ".join(st.session_state.values),
        "생애목표": st.session_state.get("life_goal", ""),
        "직업목표": st.session_state.get("career_goal", ""),
        "건강목표": st.session_state.get("health_goal", ""),
        "경제목표": st.session_state.get("economy_goal", ""),
        "가족목표": st.session_state.get("family_goal", ""),
        "자기발전목표": st.session_state.get("growth_goal", ""),
        "최종직업": st.session_state.get("career_name", ""),
        "건강": g["건강"], "경제": g["경제"], "가족": g["가족"],
        "인간관계": g["인간관계"], "자기발전": g["자기발전"], "만족도": g["만족도"],
        "현금": g["cash"], "자산": g["assets"], "월소득": g["income"],
        "월지출": g["expenses"], "부채": g["debt"],
        "재무상태": "건전" if g["debt"] <= g["assets"] + g["cash"] else "주의",
        "발생사건": " | ".join(g["events"]),
        "주요선택": " | ".join(g["choices"]),
        "실행방안": " | ".join(g["plans"]),
        "성찰": st.session_state.get("reflection", ""),
    }


def finalize_attempt() -> None:
    row = make_row()
    existing = [x for x in st.session_state.completed_attempts if x.get("회차") != row["회차"]]
    st.session_state.completed_attempts = existing + [row]


def save_current() -> None:
    key = f"{st.session_state.student_id}-{st.session_state.attempt}"
    if key in st.session_state.saved_attempts:
        st.info("이번 회차는 이미 저장되었습니다.")
        return
    save_result(make_row())
    st.session_state.saved_attempts.add(key)
    st.success("Google Sheets의 '학생정보' 시트에 저장했습니다.")


# ---------- Boot ----------
css()
init_state()

st.markdown(
    '<div class="hero"><div class="eyebrow">HOME ECONOMICS · LIFE DESIGN SIMULATION</div>'
    '<h1>나의 생애 설계도</h1>'
    '<p class="muted">가치관 → 목표 → 실행 → 생애주기 → 사건과 선택 → 결과 → 재설계</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### LIFE DESIGN")
    st.caption(f"현재 회차 · {st.session_state.get('attempt', 1)}회차")
    if st.session_state.get("student_id"):
        st.code(str(st.session_state.student_id), language=None)
    if st.button("처음부터 다시", use_container_width=True):
        reset_game(False); st.rerun()
    if st.button("내 기록", use_container_width=True):
        st.session_state.page = "history"; st.rerun()
    if st.button("교사용 모드", use_container_width=True):
        st.session_state.page = "teacher"; st.rerun()

# ---------- Start ----------
if not st.session_state.get("student_id"):
    left, center, right = st.columns([1, 2, 1])
    with center:
        st.markdown(
            '<div class="card"><h2>게임을 시작해 볼까요?</h2>'
            '<p class="muted">학번을 입력하고, 나만의 캐릭터와 가치관을 선택해 보세요.</p></div>',
            unsafe_allow_html=True,
        )
        sid = st.text_input("학번", placeholder="학번을 입력하세요", max_chars=20, key="start_student_id")
        if st.button("게임 시작하기  →", type="primary", use_container_width=True):
            sid = sid.strip()
            if sid:
                st.session_state.student_id = sid
                st.session_state.page = "character"
                st.session_state.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.rerun()
            else:
                st.warning("학번을 입력해 주세요.")
    st.stop()

steps = ["character", "values", "goals", "career", "plan", "life", "result", "history"]
labels = ["캐릭터", "가치관", "목표", "직업", "실행방안", "생애주기", "결과", "기록"]
page = st.session_state.get("page", "character")
idx = steps.index(page) if page in steps else 0
if page in steps:
    st.progress((idx + 1) / len(steps), text=f"{labels[idx]} · {idx + 1}/{len(steps)}")

# ---------- Character ----------
if page == "character":
    st.subheader("0. 나를 나타내는 캐릭터")
    st.write("6개의 캐릭터 중 하나를 선택하세요. 이후 생애주기에서는 연령 단계에 맞는 캐릭터로 변화합니다.")
    chars = [("a", "캐릭터 A"), ("d", "캐릭터 B"), ("g", "캐릭터 C"), ("j", "캐릭터 D"), ("m", "캐릭터 E"), ("q", "캐릭터 F")]
    for row in range(0, 6, 3):
        cols = st.columns(3)
        for col, (letter, name) in zip(cols, chars[row:row + 3]):
            with col:
                st.markdown(f'<div class="card"><h3>{name}</h3></div>', unsafe_allow_html=True)
                show_character(letter, 270)
                selected = st.session_state.character == letter
                if st.button("선택됨 ✓" if selected else "이 캐릭터 선택", key=f"character_select_{letter}", use_container_width=True):
                    st.session_state.character = letter
                    st.rerun()
    st.info(f"현재 선택한 캐릭터: {st.session_state.character.upper()}")
    if st.button("다음 · 가치관 →", type="primary", use_container_width=True):
        st.session_state.page = "values"; st.rerun()

# ---------- Values ----------
elif page == "values":
    st.subheader("1. 나의 가치관")
    st.write("교과서의 가치관 중 지금의 나에게 중요한 것을 최대 3개 선택하세요. 이후 사건의 선택 결과와 만족도에 실제로 반영됩니다.")
    value_names = [x.get("name", "") for x in VALUES if x.get("name")]
    selected = st.multiselect("가치관", value_names, max_selections=3, default=st.session_state.values)
    st.session_state.values = selected
    for i in range(0, len(VALUES), 2):
        a, b = st.columns(2)
        for c, v in zip((a, b), VALUES[i:i + 2]):
            c.markdown(f'<div class="card"><b>{html.escape(str(v.get("name", "")))}</b><p class="muted">{html.escape(str(v.get("description", "")))}</p></div>', unsafe_allow_html=True)
    if st.button("다음 · 생애 목표 →", type="primary", disabled=not selected):
        st.session_state.page = "goals"; st.rerun()

# ---------- Goals ----------
elif page == "goals":
    st.subheader("2. 생애 목표와 하위 목표")
    st.session_state.life_goal = st.text_area("어떤 인생을 살고 싶은가?", value=st.session_state.get("life_goal", ""), height=100)
    a, b = st.columns(2)
    with a:
        st.session_state.career_goal = st.text_input("직업 목표", value=st.session_state.get("career_goal", ""))
        st.session_state.health_goal = st.text_input("건강 목표", value=st.session_state.get("health_goal", ""))
        st.session_state.economy_goal = st.text_input("경제 목표", value=st.session_state.get("economy_goal", ""))
    with b:
        st.session_state.family_goal = st.text_input("가족 목표", value=st.session_state.get("family_goal", ""))
        st.session_state.growth_goal = st.text_input("자기발전 목표", value=st.session_state.get("growth_goal", ""))
    st.caption("목표는 이후 선택의 '나에게 맞는가?'를 판단하는 기준으로 사용됩니다.")
    if st.button("다음 · 직업 선택 →", type="primary", disabled=not st.session_state.life_goal.strip()):
        st.session_state.page = "career"; st.rerun()

# ---------- Career ----------
elif page == "career":
    st.subheader("3. 직업 선택")
    names = [x.get("name", "직업") for x in CAREERS]
    if not names:
        st.error("careers.json에 직업 데이터가 없습니다.")
        st.stop()
    current = st.session_state.get("career_name", names[0])
    career = st.selectbox("직업", names, index=names.index(current) if current in names else 0)
    chosen = next((x for x in CAREERS if x.get("name") == career), CAREERS[0])
    a, b = st.columns([1, 2])
    with a:
        show_character(st.session_state.character, 360)
    with b:
        st.markdown(f"### {html.escape(str(chosen.get('name', '직업')))}")
        st.write(chosen.get("description", ""))
        st.info(chosen.get("tradeoff", ""))
        st.write(f"경제 기회 +{chosen.get('economy', 0)} · 자기발전 +{chosen.get('growth', 0)} · 위험도 {chosen.get('risk', 0)}")
    if st.button("이 직업으로 설계하기", type="primary"):
        st.session_state.career_name = career
        career_effect(chosen)
        st.session_state.page = "plan"
        st.rerun()

# ---------- Action plan ----------
elif page == "plan":
    st.subheader("4. 목표를 이루기 위한 실행 방안")
    st.caption("실행 방안은 '좋은 말'이 아니라 이후 생애의 자원과 선택 가능성에 영향을 주는 행동입니다.")
    plans = [
        ("건강", "규칙적인 운동과 식습관을 유지한다", {"건강": 8, "만족도": 3}),
        ("경제", "수입의 일부를 저축하고 지출을 관리한다", {"경제": 9, "만족도": -2, "현금": 30}),
        ("가족", "가족과 정기적으로 대화하고 시간을 확보한다", {"가족": 8, "인간관계": 5}),
        ("자기발전", "매년 새로운 지식이나 기술을 배우는 시간을 확보한다", {"자기발전": 9, "경제": -2}),
        ("균형", "일·가족·건강에 시간을 균형 있게 배분한다", {"건강": 4, "가족": 4, "만족도": 5}),
    ]
    selected_plan_labels = []
    for key, label, _ in plans:
        if st.checkbox(label, key=f"plan_pick_{key}"):
            selected_plan_labels.append(label)
    st.info(f"선택한 실행 방안 {len(selected_plan_labels)}개")
    finance_metrics()
    if st.button("실행 계획 확정 → 생애주기 시작", type="primary"):
        g = st.session_state.game
        # Apply only at confirmation, so reruns/unchecking cannot double-apply effects.
        for key, label, eff in plans:
            if label in selected_plan_labels:
                apply_effects(eff)
                g["plans"].append(label)
                g["plan_effects"][label] = eff
        st.session_state.page = "life"
        st.rerun()

# ---------- Life simulation ----------
elif page == "life":
    g = st.session_state.game
    i = max(0, min(int(g.get("stage", 0)), max(0, len(LIFE_STAGES) - 1)))
    if not LIFE_STAGES:
        st.error("life_stages.json에 생애주기 데이터가 없습니다.")
        st.stop()
    stage = LIFE_STAGES[i]
    stage_name = str(stage.get("name", f"{i + 1}단계"))
    emoji = str(stage.get("emoji", "🌱"))
    character = str(stage.get("character", DEFAULT_CHARACTERS[i % len(DEFAULT_CHARACTERS)]))
    st.subheader(f"{emoji} {stage_name}")
    left, right = st.columns([1, 1.5])
    with left:
        show_character(character, 400)
    with right:
        st.markdown(
            f'<div class="stage"><h2>{emoji} {html.escape(stage_name)}</h2>'
            f'<p>{html.escape(str(stage.get("period", "")))}</p>'
            f'<p>{html.escape(str(stage.get("description", "이 시기의 삶과 발달 과업을 경험합니다.")))}</p>'
            f'<b>핵심 영역 · {html.escape(str(stage.get("focus", "")))}</b></div>',
            unsafe_allow_html=True,
        )
        st.markdown("**발달 과업**")
        for task in stage.get("tasks", []):
            st.markdown("- " + str(task))
    metrics(); finance_metrics()

    event = event_for_stage(stage_name)
    if event is None:
        st.error(f"'{stage_name}'에 연결된 사건 데이터가 없습니다. events.json의 stage 값을 확인하세요.")
        st.stop()
    st.markdown(
        f'<div class="card"><div class="eyebrow">LIFE EVENT {i + 1} / {len(LIFE_STAGES)}</div>'
        f'<h3>{html.escape(str(event.get("title", "생애 사건")))}</h3>'
        f'<p>{html.escape(str(event.get("description", "")))}</p></div>',
        unsafe_allow_html=True,
    )
    choices = event.get("choices", [])
    if not isinstance(choices, list) or not choices:
        st.error("이 사건에 선택지가 없습니다.")
        st.stop()

    labels_for_radio = []
    choice_map = {}
    for idx_choice, raw_choice in enumerate(choices):
        effective = effective_choice(raw_choice)
        text = str(effective.get("choice", f"선택 {idx_choice + 1}"))
        tag = str(effective.get("tag", ""))
        alignment = int(effective.get("alignment", 0))
        suffix = " · 나의 가치관과 연결" if alignment > 0 else ""
        display = text + suffix
        labels_for_radio.append(display)
        choice_map[display] = effective

    radio_key = f"choice_{i}_attempt_{st.session_state.attempt}"
    choice_display = st.radio("어떻게 대응할까요?", labels_for_radio, key=radio_key)
    picked = choice_map[choice_display]
    if int(picked.get("alignment", 0)) > 0:
        st.caption("선택한 가치관/목표와 연결된 선택입니다. 게임에는 추가 만족도 효과가 적용됩니다.")
    if st.button("선택 적용 →", type="primary"):
        apply_effects(picked.get("effects", {}))
        g["events"].append(str(event.get("title", "생애 사건")))
        g["choices"].append(str(picked.get("choice", "")))
        g["choice_tags"].append(str(picked.get("tag", "")))
        finance_step()
        if i < len(LIFE_STAGES) - 1:
            g["stage"] = i + 1
            st.rerun()
        finalize_attempt()
        st.session_state.page = "result"
        st.rerun()

# ---------- Result ----------
elif page == "result":
    finalize_attempt()
    st.subheader("🏁 나의 생애 설계 결과")
    st.markdown(
        f'<div class="blueprint"><div class="eyebrow">MY LIFE BLUEPRINT · {st.session_state.attempt}회차</div>'
        f'<h2>{html.escape(str(st.session_state.get("life_goal", "")))}</h2>'
        f'<p><b>가치관</b> · {html.escape(", ".join(st.session_state.values))}</p>'
        f'<p><b>직업</b> · {html.escape(str(st.session_state.get("career_name", "")))}</p></div>',
        unsafe_allow_html=True,
    )
    metrics(); finance_metrics()
    df = pd.DataFrame({"영역": STAT_KEYS, "점수": [st.session_state.game[k] for k in STAT_KEYS]}).set_index("영역")
    st.bar_chart(df, height=300)

    st.markdown("### 생애주기별 선택")
    for s, e, c, tag in zip(
        LIFE_STAGES,
        st.session_state.game["events"],
        st.session_state.game["choices"],
        st.session_state.game["choice_tags"],
    ):
        st.write(f"{s.get('emoji', '🌱')} **{s.get('name', '')}** · {e} → {c} · `{tag}`")

    st.markdown("### 실행 방안과 결과의 연결")
    if st.session_state.game["plans"]:
        for p in st.session_state.game["plans"]:
            st.write("•", p)
    else:
        st.caption("선택한 실행 방안이 없습니다.")

    st.session_state.reflection = st.text_area("이번 설계를 돌아보며", value=st.session_state.get("reflection", ""), height=130)
    a, b, c = st.columns(3)
    with a:
        if st.button("결과 저장", type="primary", use_container_width=True):
            try:
                save_current()
            except Exception as exc:
                st.error(f"저장에 실패했습니다. Google Sheets 설정/공유 권한을 확인하세요.\n\n{exc}")
    with b:
        if st.button("2회차 재설계", use_container_width=True):
            reset_game(new_attempt=True)
            st.session_state.page = "values"
            st.rerun()
    with c:
        if st.button("1·2회차 비교", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()

# ---------- History ----------
elif page == "history":
    st.subheader("내 생애 설계 기록")
    session_rows = list(st.session_state.get("completed_attempts", []))
    try:
        rows = student_rows(st.session_state.student_id)
    except Exception as exc:
        rows = []
        st.warning(f"Google Sheets 기록을 불러오지 못했습니다. 현재 세션 기록만 표시합니다.\n\n{exc}")
    combined = session_rows + rows
    if not combined:
        st.info("저장된 결과가 없습니다. 게임을 완료하면 이곳에서 비교할 수 있습니다.")
    else:
        df = pd.DataFrame(combined)
        if "회차" in df:
            df = df.drop_duplicates(subset=["회차"], keep="last").sort_values("회차")
        st.dataframe(df, use_container_width=True, hide_index=True)
        if len(df) >= 2:
            st.markdown("### 1회차 ↔ 2회차 변화")
            metrics_to_compare = ["건강", "경제", "가족", "인간관계", "자기발전", "만족도", "현금", "자산", "부채"]
            first, second = df.iloc[-2], df.iloc[-1]
            compare = []
            for metric in metrics_to_compare:
                if metric in df.columns:
                    a = pd.to_numeric(first[metric], errors="coerce")
                    b = pd.to_numeric(second[metric], errors="coerce")
                    if pd.notna(a) and pd.notna(b):
                        compare.append({"영역": metric, "1회차": a, "2회차": b, "변화": b - a})
            if compare:
                st.dataframe(pd.DataFrame(compare), use_container_width=True, hide_index=True)
            st.info("2회차의 목표·가치관·실행 방안을 바꿨다면 결과가 어떻게 달라졌는지 성찰해 보세요.")

# ---------- Teacher ----------
elif page == "teacher":
    st.subheader("교사용 수업 모드")
    pin = st.text_input("교사용 PIN", type="password")
    if pin == TEACHER_PIN:
        try:
            df = pd.DataFrame(get_ws().get_all_records())
            if df.empty:
                st.info("저장된 결과가 없습니다.")
            else:
                st.metric("저장된 설계 수", len(df))
                numeric_cols = [c for c in STAT_KEYS + ECON_KEYS if c in df.columns]
                for c in numeric_cols:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
                st.markdown("### 학급 전체 경향")
                score_cols = [c for c in STAT_KEYS if c in df.columns]
                if score_cols:
                    st.bar_chart(df[score_cols].mean())
                if "가치관" in df.columns:
                    st.markdown("### 가치관 선택 경향")
                    value_counts = {}
                    for text in df["가치관"].dropna().astype(str):
                        for value in [x.strip() for x in text.split(",") if x.strip()]:
                            value_counts[value] = value_counts.get(value, 0) + 1
                    if value_counts:
                        st.bar_chart(pd.Series(value_counts).sort_values(ascending=False))
                st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"교사용 데이터 조회 실패: {exc}")
    else:
        st.caption("교사용 PIN을 입력하세요.")
