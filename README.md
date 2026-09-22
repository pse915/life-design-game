# LIFE DESIGN v2

Streamlit 기반 생애 설계 교육 게임입니다.

## Kenney Blocky Characters

이 프로젝트는 원본 Kenney 에셋을 저장소에 포함시키는 대신, 사용자가 다운로드한 GLB/Texture 파일을 다음 위치에 넣는 구조를 지원합니다.

```
assets/characters/blocky/
├── character-f.glb
└── Textures/
    └── texture-f.png
```

실제 제공된 Kenney ZIP의 GLB는 `Textures/texture-f.png`를 외부 URI로 참조하므로, `app.py`가 GLB와 PNG를 읽어 브라우저 3D 뷰어에서 해당 텍스처 URL을 매핑합니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Google Sheets

`.streamlit/secrets.toml.example`을 복사하여 `.streamlit/secrets.toml`을 만들고 서비스 계정 정보를 입력합니다. Google Sheet의 `학생정보` 탭을 서비스 계정 이메일과 편집자 권한으로 공유합니다.

실제 `secrets.toml`은 GitHub에 올리지 마세요.
