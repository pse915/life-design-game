from __future__ import annotations
import base64, html, json, random
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

APP_DIR=Path(__file__).resolve().parent
DATA_DIR=APP_DIR/"data"
CHAR_DIR=APP_DIR/"assets"/"characters"/"blocky"

def load_json(name): return json.loads((DATA_DIR/name).read_text(encoding="utf-8"))
VALUES=load_json("values.json"); CAREERS=load_json("careers.json")
LIFE_STAGES=load_json("life_stages.json"); EVENTS=load_json("events.json")

st.set_page_config(page_title="LIFE DESIGN · 나의 생애 설계도",page_icon="🌱",layout="wide",initial_sidebar_state="collapsed")

def secret(path, fallback=""):
    cur=st.secrets
    for k in path.split("."):
        try: cur=cur[k]
        except Exception: return fallback
    return cur

SHEET_URL=secret("app.spreadsheet_url","")
WORKSHEET=secret("app.worksheet_name","학생정보")
TEACHER_PIN=str(secret("app.teacher_pin","1234"))

HEADERS=["학번","회차","저장시간","캐릭터","가치관","생애목표","직업목표","건강목표","경제목표","가족목표","자기발전목표","최종직업",
         "건강","경제","가족","인간관계","자기발전","만족도","발생사건","주요선택","실행방안","성찰"]

@st.cache_resource(show_spinner=False)
def get_ws():
    import gspread
    from google.oauth2.service_account import Credentials
    if "google" not in st.secrets: raise RuntimeError("Streamlit Secrets에 [google] 서비스 계정 정보가 없습니다.")
    if not SHEET_URL: raise RuntimeError("app.spreadsheet_url을 설정하세요.")
    scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
    creds=Credentials.from_service_account_info(dict(st.secrets["google"]),scopes=scopes)
    return gspread.authorize(creds).open_by_url(SHEET_URL).worksheet(WORKSHEET)

def ensure_headers(ws):
    first=ws.row_values(1)
    if not first: ws.append_row(HEADERS,value_input_option="RAW"); return
    missing=[h for h in HEADERS if h not in first]
    if missing: ws.update(f"A1:{chr(64+len(first)+len(missing))}1",[first+missing])

def save_result(row):
    ws=get_ws(); ensure_headers(ws); headers=ws.row_values(1)
    ws.append_row([row.get(h,"") for h in headers],value_input_option="USER_ENTERED")

def student_rows(sid):
    ws=get_ws(); ensure_headers(ws)
    return [r for r in ws.get_all_records() if str(r.get("학번","")).strip().lstrip("'")==str(sid).strip()]

def init():
    if "game" not in st.session_state:
        st.session_state.game={"건강":60,"경제":50,"가족":60,"인간관계":60,"자기발전":50,"만족도":60,
                               "stage":0,"events":[],"choices":[],"plans":[],"history":[]}
    st.session_state.setdefault("attempt",1); st.session_state.setdefault("page","start")
    st.session_state.setdefault("values",[]); st.session_state.setdefault("character","a")

def reset(keep_attempt=True):
    attempt=st.session_state.get("attempt",1) if keep_attempt else 1
    sid=st.session_state.get("student_id","")
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.session_state.student_id=sid; st.session_state.attempt=attempt; init()

def effects(e):
    g=st.session_state.game
    for k,v in e.items():
        if k in g: g[k]=max(0,min(100,int(g[k]+v)))

def viewer(letter,height=430):
    glb=CHAR_DIR/f"character-{letter}.glb"; tex=CHAR_DIR/"Textures"/f"texture-{letter}.png"
    if not glb.exists(): st.warning(f"character-{letter}.glb가 없습니다."); return
    g64=base64.b64encode(glb.read_bytes()).decode()
    t64=base64.b64encode(tex.read_bytes()).decode() if tex.exists() else ""
    url=f"data:image/png;base64,{t64}"
    src=f"""<!doctype html><html><body style="margin:0;overflow:hidden;background:transparent">
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
<script>
const s=new THREE.Scene(), c=new THREE.PerspectiveCamera(28,innerWidth/innerHeight,.01,100);
const r=new THREE.WebGLRenderer({{alpha:true,antialias:true}});r.setSize(innerWidth,innerHeight);r.setPixelRatio(Math.min(devicePixelRatio,2));document.body.appendChild(r.domElement);
s.add(new THREE.HemisphereLight(0xffffff,0x888888,2.3));let l=new THREE.DirectionalLight(0xffffff,2);l.position.set(2,4,4);s.add(l);
const loader=new THREE.GLTFLoader(), manager=loader.manager; const texURL={json.dumps(url)};
manager.setURLModifier(u=>u.toLowerCase().includes("texture-{letter}.png")?texURL:u);
loader.load("data:model/gltf-binary;base64,{g64}",g=>{{const root=g.scene;s.add(root);
let box=new THREE.Box3().setFromObject(root),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3());
root.position.sub(center);root.position.y-=size.y*.02;root.scale.setScalar(1.55/Math.max(size.x,size.y,size.z));
let down=0,rot=0;addEventListener("pointerdown",e=>down=e.clientX);addEventListener("pointermove",e=>{{if(e.buttons){{rot+=(e.clientX-down)*.012;down=e.clientX;root.rotation.y=rot}}}});
function a(){{requestAnimationFrame(a);r.render(s,c)}}a()}},undefined,()=>document.body.innerHTML="<div style='font:14px sans-serif;color:#777;padding:20px'>캐릭터를 불러오지 못했습니다.</div>");
addEventListener("resize",()=>{{c.aspect=innerWidth/innerHeight;c.updateProjectionMatrix();r.setSize(innerWidth,innerHeight)}});
</script></body></html>"""
    components.html(src,height=height,scrolling=False)

def metrics():
    g=st.session_state.game
    cols=st.columns(6)
    for c,k in zip(cols,["건강","경제","가족","인간관계","자기발전","만족도"]):
        c.metric(k,g[k])

def make_row():
    g=st.session_state.game
    return {"학번":st.session_state.student_id,"회차":st.session_state.attempt,
            "저장시간":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"캐릭터":st.session_state.character,
            "가치관":", ".join(st.session_state.values),"생애목표":st.session_state.get("life_goal",""),
            "직업목표":st.session_state.get("career_goal",""),"건강목표":st.session_state.get("health_goal",""),
            "경제목표":st.session_state.get("economy_goal",""),"가족목표":st.session_state.get("family_goal",""),
            "자기발전목표":st.session_state.get("growth_goal",""),"최종직업":st.session_state.get("career_name",""),
            "건강":g["건강"],"경제":g["경제"],"가족":g["가족"],"인간관계":g["인간관계"],"자기발전":g["자기발전"],
            "만족도":g["만족도"],"발생사건":" | ".join(g["events"]),"주요선택":" | ".join(g["choices"]),
            "실행방안":" | ".join(g["plans"]),"성찰":st.session_state.get("reflection","")}

def css():
    st.markdown("""<style>
    :root{color-scheme:light}.stApp{background:#f5f5f7;color:#1d1d1f}.block-container{max-width:1260px;padding-top:2rem;padding-bottom:4rem}
    [data-testid=stHeader]{background:rgba(245,245,247,.9)} h1,h2,h3{letter-spacing:-.04em}
    .hero,.card,.stage{background:#fff;border:1px solid #e5e5ea;border-radius:24px;box-shadow:0 8px 30px rgba(0,0,0,.04)}
    .hero{padding:34px 38px;margin-bottom:18px}.card{padding:22px;margin:10px 0}.stage{padding:18px}
    .eyebrow{color:#86868b;font-weight:700;letter-spacing:.08em;font-size:.78rem}.muted{color:#6e6e73}
    div.stButton>button{border-radius:14px;min-height:42px;font-weight:650}
    </style>""",unsafe_allow_html=True)

css(); init()
st.markdown('<div class="hero"><div class="eyebrow">HOME ECONOMICS · LIFE DESIGN</div><h1>나의 생애 설계도</h1><p class="muted">가치관 → 목표 → 실행 → 생애주기 → 사건과 선택 → 결과 → 재설계</p></div>',unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### LIFE DESIGN")
    sid=st.text_input("학번",value=st.session_state.get("student_id",""),max_chars=20)
    if sid.strip(): st.session_state.student_id=sid.strip()
    if st.button("처음부터 다시",use_container_width=True): reset(False); st.rerun()
    if st.button("내 기록",use_container_width=True): st.session_state.page="history"; st.rerun()
    if st.button("교사용 모드",use_container_width=True): st.session_state.page="teacher"; st.rerun()

if not st.session_state.get("student_id"):
    left, center, right = st.columns([1, 2, 1])
    with center:
        st.markdown('<div class="card"><h2>게임을 시작해 볼까요?</h2><p class="muted">학번을 입력하면 나만의 생애 설계를 시작합니다.</p></div>', unsafe_allow_html=True)
        sid = st.text_input("학번", placeholder="학번을 입력하세요", max_chars=20, key="start_student_id")
        if st.button("게임 시작하기  →", type="primary", use_container_width=True):
            if sid.strip():
                st.session_state.student_id = sid.strip()
                st.session_state.page = "character"
                st.rerun()
            else:
                st.warning("학번을 입력해 주세요.")
    st.stop()

steps=["character","values","goals","career","plan","life","result","history"]
labels=["캐릭터","가치관","목표","직업","실행방안","생애주기","결과","기록"]
page=st.session_state.page
idx=steps.index(page) if page in steps else 0
st.progress((idx+1)/len(steps),text=f"{labels[idx]} · {idx+1}/{len(steps)}")

if page=="character":
    st.subheader("0. 나를 나타내는 캐릭터")
    st.write("6개의 캐릭터 중 하나를 선택하세요. 선택한 캐릭터는 설계 기록에 저장되고, 생애주기에서는 연령 단계에 맞는 캐릭터로 변화합니다.")
    chars=[("a","캐릭터 A"),("d","캐릭터 B"),("g","캐릭터 C"),("j","캐릭터 D"),("m","캐릭터 E"),("q","캐릭터 F")]
    for row in range(0,6,3):
        cols=st.columns(3)
        for col,(letter,name) in zip(cols,chars[row:row+3]):
            with col:
                st.markdown(f'<div class="card"><h3>{name}</h3></div>',unsafe_allow_html=True)
                show_character(letter,270)
                if st.button("선택",key=f"character_select_{letter}",use_container_width=True):
                    st.session_state.character=letter
                    st.session_state.page="values"
                    st.rerun()
    st.info(f"현재 선택한 캐릭터: {st.session_state.character.upper()}")

elif page=="values":
    st.subheader("1. 나의 가치관")
    st.write("교과서의 가치관 중 지금의 나에게 중요한 것을 최대 3개 선택하세요.")
    selected=st.multiselect("가치관",[x["name"] for x in VALUES],max_selections=3,default=st.session_state.values)
    st.session_state.values=selected
    for i in range(0,len(VALUES),2):
        a,b=st.columns(2)
        for c,v in zip((a,b),VALUES[i:i+2]):
            c.markdown(f'<div class="card"><b>{html.escape(v["name"])}</b><p class="muted">{html.escape(v["description"])}</p></div>',unsafe_allow_html=True)
    if st.button("다음 · 생애 목표",type="primary",disabled=not selected): st.session_state.page="goals"; st.rerun()

elif page=="goals":
    st.subheader("2. 생애 목표와 하위 목표")
    st.session_state.life_goal=st.text_area("어떤 인생을 살고 싶은가?",value=st.session_state.get("life_goal",""),height=100)
    a,b=st.columns(2)
    with a:
        st.session_state.career_goal=st.text_input("직업 목표",value=st.session_state.get("career_goal",""))
        st.session_state.health_goal=st.text_input("건강 목표",value=st.session_state.get("health_goal",""))
        st.session_state.economy_goal=st.text_input("경제 목표",value=st.session_state.get("economy_goal",""))
    with b:
        st.session_state.family_goal=st.text_input("가족 목표",value=st.session_state.get("family_goal",""))
        st.session_state.growth_goal=st.text_input("자기발전 목표",value=st.session_state.get("growth_goal",""))
    if st.button("다음 · 직업 선택",type="primary",disabled=not st.session_state.life_goal.strip()): st.session_state.page="career"; st.rerun()

elif page=="career":
    st.subheader("3. 직업 선택")
    names=[x["name"] for x in CAREERS]; career=st.selectbox("직업",names,index=names.index(st.session_state.get("career_name",names[0])))
    chosen=next(x for x in CAREERS if x["name"]==career)
    a,b=st.columns([1,2])
    with a: viewer(st.session_state.character,360)
    with b:
        st.markdown(f"### {chosen['name']}"); st.write(chosen["description"]); st.info(chosen["tradeoff"])
        st.write(f"시작 자원 · 경제 +{chosen['economy']} · 자기발전 +{chosen['growth']}")
    if st.button("이 직업으로 설계하기",type="primary"):
        st.session_state.career_name=career
        g=st.session_state.game;g["경제"]=max(0,min(100,50+chosen["economy"]));g["자기발전"]=max(0,min(100,50+chosen["growth"]))
        st.session_state.page="plan";st.rerun()

elif page=="plan":
    st.subheader("4. 목표를 이루기 위한 실행 방안")
    st.caption("같은 목표라도 어떤 실행 방안을 선택하느냐에 따라 이후 삶의 자원이 달라집니다.")
    plans=[
        ("건강","규칙적인 운동과 식습관을 유지한다",{"건강":8,"만족도":3}),
        ("경제","수입의 일부를 저축하고 지출을 관리한다",{"경제":9,"만족도":-2}),
        ("가족","가족과 정기적으로 대화하고 시간을 확보한다",{"가족":8,"인간관계":5}),
        ("자기발전","매년 새로운 지식이나 기술을 배우는 시간을 확보한다",{"자기발전":9,"경제":-2}),
        ("균형","일·가족·건강에 시간을 균형 있게 배분한다",{"건강":4,"가족":4,"만족도":5}),
    ]
    for key,label,e in plans:
        if st.checkbox(label,key="plan_"+key):
            if label not in st.session_state.game["plans"]: st.session_state.game["plans"].append(label)
            # effects are intentionally applied only once when the plan is first selected
            if "applied_"+key not in st.session_state: effects(e); st.session_state["applied_"+key]=True
    if st.button("실행 계획을 확정하고 생애주기로",type="primary"): st.session_state.page="life";st.rerun()
    metrics()

elif page=="life":
    g=st.session_state.game
    i=max(0,min(int(g.get("stage",0)),len(LIFE_STAGES)-1))
    stage=LIFE_STAGES[i]
    stage_name=stage.get("name",f"{i+1}단계")
    emoji=stage.get("emoji","🌱")
    character=stage.get("character",["a","d","g","j","m","q"][i])
    st.subheader(f"{emoji} {stage_name}")
    left,right=st.columns([1,1.5])
    with left:
        show_character(character,400)
    with right:
        st.markdown(f'<div class="stage"><h2>{emoji} {html.escape(stage_name)}</h2><p>{html.escape(stage.get("period",""))}</p><p>{html.escape(stage.get("description","이 시기의 삶과 발달 과업을 경험합니다."))}</p><b>핵심 영역 · {html.escape(stage.get("focus",""))}</b></div>',unsafe_allow_html=True)
        st.markdown("**발달 과업**")
        for task in stage.get("tasks",[]):
            st.markdown("- "+str(task))
    metrics()
    event=next((e for e in EVENTS if e.get("stage")==stage_name),None)
    if event is None:
        st.error(f"'{stage_name}'에 연결된 사건 데이터가 없습니다.")
        st.stop()
    st.markdown(f'<div class="card"><div class="eyebrow">LIFE EVENT {i+1} / {len(LIFE_STAGES)}</div><h3>{html.escape(event.get("title","생애 사건"))}</h3><p>{html.escape(event.get("description",""))}</p></div>',unsafe_allow_html=True)
    choices=event.get("choices",[])
    if not choices:
        st.error("이 사건에 선택지가 없습니다.")
        st.stop()
    choice=st.radio("어떻게 대응할까요?",[x.get("choice","선택") for x in choices],key=f"choice_{i}")
    if st.button("선택 적용",type="primary"):
        picked=next((x for x in choices if x.get("choice")==choice),choices[0])
        effects(picked.get("effects",{}))
        g["events"].append(event.get("title","생애 사건"))
        g["choices"].append(choice)
        if i < len(LIFE_STAGES)-1:
            g["stage"]=i+1
            st.rerun()
        st.session_state.page="result"
        st.rerun()

elif page=="result":
    st.subheader("🏁 나의 생애 설계 결과")
    metrics()
    st.markdown(f'<div class="card"><h3>{html.escape(st.session_state.get("career_name",""))}</h3><p>{html.escape(st.session_state.get("life_goal",""))}</p><p class="muted">가치관 · {html.escape(", ".join(st.session_state.values))}</p></div>',unsafe_allow_html=True)
    df=pd.DataFrame({"영역":["건강","경제","가족","인간관계","자기발전","만족도"],"점수":[st.session_state.game[k] for k in ["건강","경제","가족","인간관계","자기발전","만족도"]]}).set_index("영역")
    st.bar_chart(df,height=300)
    st.markdown("### 생애주기별 선택")
    for s,e,c in zip(LIFE_STAGES,st.session_state.game["events"],st.session_state.game["choices"]):
        st.write(f"{s['emoji']} **{s['name']}** · {e} → {c}")
    st.session_state.reflection=st.text_area("이번 설계를 돌아보며",value=st.session_state.get("reflection",""),height=130)
    a,b,c=st.columns(3)
    with a:
        if st.button("결과 저장",type="primary",use_container_width=True):
            try: save_result(make_row());st.success("Google Sheets에 저장했습니다.")
            except Exception as e: st.error(str(e))
    with b:
        if st.button("2회차 재설계",use_container_width=True):
            old=st.session_state.attempt; reset();st.session_state.attempt=old+1;st.session_state.page="values";st.rerun()
    with c:
        if st.button("1·2회차 비교",use_container_width=True): st.session_state.page="history";st.rerun()

elif page=="history":
    st.subheader("내 생애 설계 기록")
    try:
        rows=student_rows(st.session_state.student_id)
        if not rows: st.info("저장된 결과가 없습니다.")
        else:
            df=pd.DataFrame(rows)
            st.dataframe(df,use_container_width=True,hide_index=True)
            if len(df)>=2:
                st.markdown("### 회차 비교")
                for metric in ["건강","경제","가족","인간관계","자기발전","만족도"]:
                    if metric in df.columns:
                        nums=pd.to_numeric(df[metric],errors="coerce")
                        st.write(f"**{metric}** · 1회차 {nums.iloc[0]} → 2회차 {nums.iloc[1]} · 변화 {nums.iloc[1]-nums.iloc[0]:+.0f}")
    except Exception as e: st.error(str(e))

elif page=="teacher":
    st.subheader("교사용 수업 모드")
    pin=st.text_input("교사용 PIN",type="password")
    if pin==TEACHER_PIN:
        try:
            df=pd.DataFrame(get_ws().get_all_records())
            if df.empty: st.info("저장된 결과가 없습니다.")
            else:
                st.metric("저장된 설계 수",len(df))
                cols=[c for c in ["건강","경제","가족","인간관계","자기발전","만족도"] if c in df]
                for c in cols: df[c]=pd.to_numeric(df[c],errors="coerce")
                st.bar_chart(df[cols].mean())
                st.dataframe(df,use_container_width=True,hide_index=True)
        except Exception as e: st.error(str(e))
    else: st.caption("교사용 PIN을 입력하세요.")
