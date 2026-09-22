from __future__ import annotations

import base64
import html
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
CHAR_DIR = APP_DIR / "assets" / "characters" / "blocky"

DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/여기에_구글시트_ID/edit"
DEFAULT_WORKSHEET = "학생정보"
TEACHER_PIN = "1234"

st.set_page_config(
    page_title="LIFE DESIGN · 나의 생애 설계도",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def load_json(name: str) -> Any:
    with open(DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


VALUES = load_json("values.json")
CAREERS = load_json("careers.json")
LIFE_STAGES = load_json("life_stages.json")
EVENTS = load_json("events.json")


def setting(path: str, fallback: Any) -> Any:
    cur: Any = st.secrets
    for key in path.split("."):
        try:
            cur = cur[key]
        except Exception:
            return fallback
    return cur


SHEET_URL = setting("app.spreadsheet_url", DEFAULT_SHEET_URL)
WORKSHEET_NAME = setting("app.worksheet_name", DEFAULT_WORKSHEET)
TEACHER_PIN = str(setting("app.teacher_pin", TEACHER_PIN))


# ----------------------------- Google Sheets -----------------------------
@st.cache_resource(show_spinner=False)
def get_worksheet():
    import gspread
    from google.oauth2.service_account import Credentials

    if "google" not in st.secrets:
        raise RuntimeError("Streamlit Secrets의 [google] 서비스 계정 정보가 없습니다.")
    if not SHEET_URL or "여기에_구글시트" in SHEET_URL:
        raise RuntimeError("app.spreadsheet_url에 실제 Google Sheet URL을 입력하세요.")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(dict(st.secrets["google"]), scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_url(SHEET_URL)
    return spreadsheet.worksheet(WORKSHEET_NAME)


HEADERS = [
    "학번", "회차", "저장시간", "가치관", "생애목표", "직업목표",
    "건강목표", "경제목표", "가족목표", "자기발전목표", "최종직업",
    "건강", "경제", "가족", "인간관계", "자기발전", "만족도",
    "발생사건", "주요선택", "성찰",
]


def ensure_headers(ws) -> None:
    first = ws.row_values(1)
    if not first:
        ws.append_row(HEADERS, value_input_option="RAW")
        return
    missing = [h for h in HEADERS if h not in first]
    if missing:
        ws.update_cell(1, len(first) + 1, missing[0])
        for h in missing[1:]:
            ws.update_cell(1, len(ws.row_values(1)) + 1, h)


def save_result(result: dict[str, Any]) -> tuple[bool, str]:
    try:
        ws = get_worksheet()
        ensure_headers(ws)
        headers = ws.row_values(1)
        row = [result.get(h, "") for h in headers]
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True, "Google Sheets에 저장했습니다."
    except Exception as e:
        return False, f"Google Sheets 저장 실패: {e}"


def get_student_results(student_id: str) -> list[dict[str, Any]]:
    ws = get_worksheet()
    ensure_headers(ws)
    records = ws.get_all_records()
    sid = str(student_id).strip()
    return [r for r in records if str(r.get("학번", "")).strip().lstrip("'") == sid]


# ----------------------------- UI helpers -----------------------------
def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root { color-scheme: light; }
        .stApp { background:#f5f5f7; color:#1d1d1f; }
        [data-testid="stHeader"] { background:rgba(245,245,247,.88); }
        [data-testid="stToolbar"] { visibility:hidden; }
        .block-container { max-width:1240px; padding-top:2.2rem; padding-bottom:4rem; }
        h1,h2,h3 { letter-spacing:-.035em; }
        .hero { background:#fff; border:1px solid #e5e5ea; border-radius:28px; padding:34px 38px; box-shadow:0 12px 40px rgba(0,0,0,.06); }
        .eyebrow { color:#86868b; font-size:.78rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
        .hero-title { font-size:clamp(2rem,5vw,4.2rem); line-height:1.03; font-weight:750; margin:.3rem 0 1rem; }
        .hero-sub { color:#6e6e73; font-size:1.05rem; max-width:780px; line-height:1.7; }
        .card { background:#fff; border:1px solid #e5e5ea; border-radius:22px; padding:22px; margin:.6rem 0; box-shadow:0 8px 28px rgba(0,0,0,.035); }
        .stage { display:flex; align-items:center; gap:12px; padding:13px 15px; border-radius:16px; background:#fff; border:1px solid #e5e5ea; }
        .stage-dot { width:11px; height:11px; border-radius:50%; background:#1d1d1f; }
        .muted { color:#6e6e73; }
        .metric { background:#fff; border:1px solid #e5e5ea; border-radius:18px; padding:16px; }
        .metric-num { font-size:1.8rem; font-weight:750; }
        .metric-label { color:#6e6e73; font-size:.8rem; }
        .value-card { min-height:130px; }
        .small { font-size:.85rem; color:#6e6e73; }
        div.stButton > button { border-radius:14px; border:1px solid #d2d2d7; min-height:42px; font-weight:650; }
        div.stButton > button[kind="primary"] { border:none; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def model_viewer_html(glb: bytes, texture: bytes | None = None, height: int = 420) -> str:
    glb64 = base64.b64encode(glb).decode("ascii")
    tex64 = base64.b64encode(texture).decode("ascii") if texture else ""
    tex_url = f"data:image/png;base64,{tex64}" if tex64 else ""
    # Kenney GLBs in this pack reference Textures/texture-x.png externally.
    # LoadingManager maps that relative URL to the supplied texture data URL.
    return f"""
<!doctype html><html><head><meta charset='utf-8'>
<style>html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}}canvas{{display:block}}</style>
<script src='https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js'></script>
<script src='https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js'></script>
</head><body><script>
const scene=new THREE.Scene();
scene.background=null;
const camera=new THREE.PerspectiveCamera(28,innerWidth/innerHeight,.01,100);
camera.position.set(0.0,0.15,3.2);
const renderer=new THREE.WebGLRenderer({{antialias:true,alpha:true}});
renderer.setPixelRatio(Math.min(devicePixelRatio,2)); renderer.setSize(innerWidth,innerHeight); renderer.outputColorSpace=THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff,0xb0b0b0,2.2));
const key=new THREE.DirectionalLight(0xffffff,2.0); key.position.set(2,3,4); scene.add(key);
const loader=new THREE.GLTFLoader();
const original=loader.manager.resolveURL;
loader.manager.resolveURL=function(url){{ if(url.toLowerCase().includes('texture-f.png') || url.toLowerCase().includes('texture-f')) return {json.dumps(tex_url)}; return original.call(this,url); }};
const data='data:model/gltf-binary;base64,{glb64}';
loader.load(data,g=>{{
  const root=g.scene; scene.add(root);
  const box=new THREE.Box3().setFromObject(root); const size=box.getSize(new THREE.Vector3()); const center=box.getCenter(new THREE.Vector3());
  root.position.sub(center); root.position.y-=size.y*.02;
  const max=Math.max(size.x,size.y,size.z); root.scale.setScalar(1.65/max);
  root.traverse(o=>{{if(o.isMesh){{o.castShadow=true;o.frustumCulled=false;}}}});
}},undefined,e=>{{document.body.innerHTML='<div style="font:14px sans-serif;color:#666;padding:20px">3D 캐릭터를 불러오지 못했습니다.</div>'; console.error(e)}});
let downX=0,rot=0;
addEventListener('pointerdown',e=>downX=e.clientX); addEventListener('pointermove',e=>{{if(e.buttons)rot+=(e.clientX-downX)*.01,downX=e.clientX}});
function animate(){{requestAnimationFrame(animate); scene.traverse(o=>{{if(o.userData&&o.userData.isCharacter) o.rotation.y=rot}}); renderer.render(scene,camera)}} animate();
addEventListener('resize',()=>{{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight)}});
</script></body></html>"""


def show_character(character_letter: str = "f", height: int = 420) -> None:
    glb_path = CHAR_DIR / f"character-{character_letter}.glb"
    tex_path = CHAR_DIR / "Textures" / f"texture-{character_letter}.png"
    if not glb_path.exists():
        st.info("Kenney GLB를 `assets/characters/blocky/`에 넣으면 3D 캐릭터가 표시됩니다.")
        return
    glb = glb_path.read_bytes()
    texture = tex_path.read_bytes() if tex_path.exists() else None
    components.html(model_viewer_html(glb, texture, height), height=height, scrolling=False)


def metric_grid(state: dict[str, Any]) -> None:
    cols = st.columns(5)
    for c, key, label in zip(cols, ["건강", "경제", "가족", "인간관계", "자기발전"], ["건강", "경제", "가족", "관계", "자기발전"]):
        with c:
            st.markdown(f'<div class="metric"><div class="metric-num">{state[key]}</div><div class="metric-label">{label}</div></div>', unsafe_allow_html=True)


def reset_game() -> None:
    keep = {"page", "student_id"}
    for k in list(st.session_state.keys()):
        if k not in keep:
            del st.session_state[k]
    st.session_state.page = "values"
    st.session_state.attempt = st.session_state.get("attempt", 1)


def init_game() -> None:
    if "game" not in st.session_state:
        st.session_state.game = {
            "건강": 60, "경제": 50, "가족": 60, "인간관계": 60, "자기발전": 50,
            "만족도": 60, "events": [], "choices": [], "stage_index": 0,
        }
    if "attempt" not in st.session_state: st.session_state.attempt = 1
    if "page" not in st.session_state: st.session_state.page = "values"


def apply_effects(effects: dict[str, int]) -> None:
    g = st.session_state.game
    for k, v in effects.items():
        if k in g and isinstance(g[k], (int, float)):
            g[k] = max(0, min(100, int(g[k] + v)))


def make_result() -> dict[str, Any]:
    g = st.session_state.game
    return {
        "학번": st.session_state.student_id,
        "회차": st.session_state.attempt,
        "저장시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "가치관": ", ".join(st.session_state.get("values", [])),
        "생애목표": st.session_state.get("life_goal", ""),
        "직업목표": st.session_state.get("career_goal", ""),
        "건강목표": st.session_state.get("health_goal", ""),
        "경제목표": st.session_state.get("economy_goal", ""),
        "가족목표": st.session_state.get("family_goal", ""),
        "자기발전목표": st.session_state.get("growth_goal", ""),
        "최종직업": st.session_state.get("career_name", ""),
        "건강": g["건강"], "경제": g["경제"], "가족": g["가족"], "인간관계": g["인간관계"], "자기발전": g["자기발전"], "만족도": g["만족도"],
        "발생사건": " | ".join(g["events"]),
        "주요선택": " | ".join(g["choices"]),
        "성찰": st.session_state.get("reflection", ""),
    }


# ----------------------------- Pages -----------------------------
inject_css()
init_game()

st.markdown('<div class="hero"><div class="eyebrow">HOME ECONOMICS · LIFE DESIGN</div><div class="hero-title">나의 생애 설계도</div><div class="hero-sub">가치관을 선택하고, 목표를 세우고, 예상하지 못한 삶의 사건에 대응하면서 나만의 생애 설계도를 만들어 봅니다.</div></div>', unsafe_allow_html=True)

if not st.session_state.get("student_id"):

    st.markdown("""
    <div class="hero" style="text-align:center;padding:55px 40px 45px;">
        <div class="eyebrow">HOME ECONOMICS · LIFE DESIGN</div>
        <h1 style="font-size:3rem;margin:12px 0;">나의 생애 설계도</h1>
        <p class="muted" style="font-size:1.05rem;">
            나의 가치관을 선택하고<br>
            미래의 삶을 직접 설계해 보세요.
        </p>
    </div>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 2, 1])

    with center:
        sid = st.text_input(
            "학번",
            placeholder="학번을 입력하세요",
            max_chars=20,
            key="start_student_id"
        )

        if st.button(
            "게임 시작하기  →",
            type="primary",
            use_container_width=True
        ):
            if sid.strip():
                st.session_state.student_id = sid.strip()
                st.session_state.page = "values"
                st.rerun()
            else:
                st.warning("학번을 입력해 주세요.")

    st.stop()

page = st.session_state.page

# Progress
steps = ["values", "goals", "career", "life", "events", "result"]
labels = ["가치관", "목표", "직업", "생애주기", "생애 사건", "결과"]
idx = steps.index(page) if page in steps else 0
st.progress((idx + 1) / len(steps), text=f"{labels[idx]} · {idx+1}/{len(steps)}")

if page == "values":
    st.subheader("1. 내가 중요하게 생각하는 것")
    st.write("교과서의 가치관 가운데 지금의 나에게 중요한 것을 최대 3개 선택하세요.")
    selected = st.multiselect("가치관", [v["name"] for v in VALUES], max_selections=3, default=st.session_state.get("values", []))
    if selected:
        st.session_state.values = selected
    cols = st.columns(2)
    for i, v in enumerate(VALUES):
        with cols[i % 2]:
            st.markdown(f'<div class="card value-card"><b>{html.escape(v["name"])}</b><p class="muted">{html.escape(v["description"])}</p></div>', unsafe_allow_html=True)
    if st.button("다음 · 생애 목표", type="primary", disabled=not selected):
        st.session_state.page = "goals"; st.rerun()

elif page == "goals":
    st.subheader("2. 나의 생애 목표")
    st.caption("목표는 정답이 없습니다. 내가 선택한 가치관을 바탕으로 구체적으로 표현해 보세요.")
    st.session_state.life_goal = st.text_area("어떤 인생을 살고 싶은가?", value=st.session_state.get("life_goal", ""), height=100)
    c1,c2 = st.columns(2)
    with c1:
        st.session_state.career_goal = st.text_input("직업 목표", value=st.session_state.get("career_goal", ""))
        st.session_state.health_goal = st.text_input("건강 목표", value=st.session_state.get("health_goal", ""))
        st.session_state.economy_goal = st.text_input("경제 목표", value=st.session_state.get("economy_goal", ""))
    with c2:
        st.session_state.family_goal = st.text_input("가족 목표", value=st.session_state.get("family_goal", ""))
        st.session_state.growth_goal = st.text_input("자기발전 목표", value=st.session_state.get("growth_goal", ""))
    if st.button("다음 · 직업 선택", type="primary", disabled=not st.session_state.life_goal.strip()):
        st.session_state.page = "career"; st.rerun()

elif page == "career":
    st.subheader("3. 나의 직업 선택")
    st.caption("직업마다 장점과 부담이 다릅니다. 나의 가치관과 목표를 생각하며 선택하세요.")
    names = [c["name"] for c in CAREERS]
    default = st.session_state.get("career_name", names[0])
    career = st.selectbox("직업", names, index=names.index(default))
    chosen = next(c for c in CAREERS if c["name"] == career)
    a,b = st.columns([1,2])
    with a: show_character("f", 360)
    with b:
        st.markdown(f"### {html.escape(chosen['name'])}")
        st.write(chosen["description"])
        st.markdown(f"**예상 특성:** {chosen['tradeoff']}")
        st.markdown(f"**시작 자원:** 경제 {chosen['economy']} · 자기발전 {chosen['growth']}")
    if st.button("이 직업으로 설계하기", type="primary"):
        st.session_state.career_name = career
        st.session_state.game["경제"] = max(0, min(100, 50 + int(chosen["economy"])))
        st.session_state.game["자기발전"] = max(0, min(100, 50 + int(chosen["growth"])))
        st.session_state.page = "life"; st.rerun()

elif page == "life":
    g = st.session_state.game
    st.subheader("4. 생애주기를 따라가 보기")
    stage = LIFE_STAGES[g["stage_index"]]
    st.markdown(f'<div class="stage"><div class="stage-dot"></div><div><b>{stage["name"]}</b><div class="small">{stage["period"]}</div></div></div>', unsafe_allow_html=True)
    st.write(stage["description"])
    st.markdown("**주요 발달 과업**")
    for task in stage["tasks"]: st.markdown(f"- {task}")
    metric_grid(g)
    if st.button("다음 생애 단계로", type="primary"):
        if g["stage_index"] < len(LIFE_STAGES) - 1:
            g["stage_index"] += 1
            st.rerun()
        st.session_state.page = "events"; st.rerun()

elif page == "events":
    g = st.session_state.game
    st.subheader("5. 예상하지 못한 생애 사건")
    if not g["events"]:
        event = random.choice(EVENTS)
        st.session_state.current_event = event
    event = st.session_state.get("current_event")
    if event:
        st.markdown(f'<div class="card"><div class="eyebrow">LIFE EVENT</div><h2>{html.escape(event["title"])}</h2><p>{html.escape(event["description"])}</p></div>', unsafe_allow_html=True)
        choice_names = [x["choice"] for x in event["choices"]]
        choice = st.radio("어떻게 대응할까요?", choice_names)
        if st.button("선택 적용", type="primary"):
            picked = next(x for x in event["choices"] if x["choice"] == choice)
            apply_effects(picked["effects"])
            g["events"].append(event["title"])
            g["choices"].append(choice)
            g["만족도"] = max(0, min(100, int(g["만족도"] + picked.get("satisfaction", 0))))
            st.session_state.current_event = None
            st.session_state.page = "result"
            st.rerun()
    metric_grid(g)

elif page == "result":
    g = st.session_state.game
    st.subheader("6. 나의 생애 설계 결과")
    metric_grid(g)
    st.markdown(f'<div class="card"><h3>{html.escape(st.session_state.get("career_name", ""))}</h3><p>{html.escape(st.session_state.get("life_goal", ""))}</p><p class="muted">가치관: {html.escape(", ".join(st.session_state.get("values", [])))}</p></div>', unsafe_allow_html=True)
    chart = pd.DataFrame({"영역":["건강","경제","가족","인간관계","자기발전","만족도"],"점수":[g["건강"],g["경제"],g["가족"],g["인간관계"],g["자기발전"],g["만족도"]]}).set_index("영역")
    st.bar_chart(chart, height=300)
    st.session_state.reflection = st.text_area("이번 설계를 돌아보며", value=st.session_state.get("reflection", ""), height=130)
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("결과 저장", type="primary", use_container_width=True):
            ok,msg = save_result(make_result())
            (st.success if ok else st.error)(msg)
    with c2:
        if st.button("2회차 재설계", use_container_width=True):
            old = st.session_state.attempt
            reset_game(); st.session_state.attempt = old + 1; st.session_state.page = "values"; st.rerun()
    with c3:
        if st.button("내 기록 보기", use_container_width=True): st.session_state.page = "history"; st.rerun()

elif page == "history":
    st.subheader("내 생애 설계 기록")
    if st.button("기록 불러오기", type="primary"):
        try:
            rows = get_student_results(st.session_state.student_id)
            if not rows: st.info("저장된 결과가 없습니다.")
            else:
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"조회 실패: {e}")

elif page == "teacher":
    st.subheader("교사용 수업 모드")
    pin = st.text_input("교사용 PIN", type="password")
    if pin == TEACHER_PIN:
        try:
            ws = get_worksheet(); rows = ws.get_all_records(); df = pd.DataFrame(rows)
            if df.empty: st.info("아직 저장된 결과가 없습니다.")
            else:
                st.metric("저장된 설계 수", len(df))
                for col in ["건강","경제","가족","인간관계","자기발전","만족도"]:
                    if col in df: df[col] = pd.to_numeric(df[col], errors="coerce")
                st.bar_chart(df[[c for c in ["건강","경제","가족","인간관계","자기발전","만족도"] if c in df]].mean().sort_values())
                st.dataframe(df[[c for c in ["학번","회차","가치관","최종직업","건강","경제","가족","인간관계","자기발전","만족도"] if c in df]], use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"교사용 데이터 조회 실패: {e}")
    else:
        st.caption("교사용 PIN을 입력하세요.")
