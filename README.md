# 🎬 릴스 자동화 (정책·혜택 꿀팁 채널용)

뉴스/RSS → LLM 대본 → TTS+자막 영상 → Instagram Graph API 발행까지 한 번에.

> 원칙: **공식 출처 기반, 투자 정보 일절 X**. 대본 프롬프트에서 강제합니다.

---

## 📁 구조

```
reels-auto/
├── .env.example       # 설정 템플릿 (.env로 복사해서 채우기)
├── src/
│   ├── collect.py     # RSS 수집 + 키워드 필터
│   ├── script.py      # LLM으로 릴스 대본 JSON 생성
│   ├── render.py      # TTS + 자막 → 1080x1920 MP4
│   ├── publish.py     # S3/R2 업로드 → IG Graph API 발행
│   └── main.py        # 전체 파이프라인
└── output/            # 렌더된 MP4
```

---

## ✅ 1회성 셋업 (한 번만 하면 됨)

### 1. 패키지 설치
```bash
pip install moviepy edge-tts feedparser boto3 openai python-dotenv pillow
sudo apt install ffmpeg fonts-nanum
```

### 2. Instagram 비즈니스 계정 + Facebook 페이지 연결
1. 인스타 앱 → 설정 및 개인정보 → 계정 유형 및 도구 → **프로페셔널 계정으로 전환** (크리에이터 또는 비즈니스)
2. [Facebook 페이지](https://www.facebook.com/pages/create) 하나 생성
3. 페이지 설정 → 연결된 계정 → Instagram 계정 연결

### 3. Meta for Developers 앱 만들기
1. https://developers.facebook.com/apps/ → **앱 만들기** → 유형: **Business**
2. 앱 대시보드 → **Instagram Graph API** 제품 추가
3. "Instagram 계정" 토글에서 비즈니스 계정 연결 → **IG User ID** 복사 (`.env`의 `IG_USER_ID`)
4. 같은 화면의 **Facebook Page** 섹션에서 페이지 선택 → `FB_PAGE_ID`, 60일 임시 토큰 생성
5. (권장) [Graph API Explorer](https://developers.facebook.com/tools/explorer/)에서
   - 권한 추가: `pages_show_list`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`, `business_management`
   - 장기 토큰으로 교체 (60일 → 영구):
     ```
     GET /oauth/access_token?grant_type=fb_exchange_token&client_id={앱ID}
        &client_secret={앱시크릿}&fb_exchange_token={단기토큰}
     ```
6. `.env`에 `IG_USER_ID`, `FB_PAGE_ID`, `FB_ACCESS_TOKEN` 붙여넣기

### 4. 영상 호스팅 (Cloudflare R2 추천 — 무료 플랜 존재)
- Instagram API는 `video_url`이 **공개 HTTPS URL**이어야 함 (로컬 파일 불가)
- R2: https://developers.cloudflare.com/r2/ 참고해 퍼블릭 버킷 + 커스텀 도메인 연결
- AWS S3도 동일하게 작동
- `.env`에 엔드포인트/버킷/공개도메인/키 입력

### 5. LLM
- 기본 OpenAI. 다른 OpenAI 호환 엔드포인트(Upstage, HyperCLOVA X 등)도 `OPENAI_BASE_URL`만 바꾸면 됨

### 6. RSS 피드
- `RSS_FEEDS`에 콤마로 구분해 입력. 추천:
  - 정부24 보도자료: `https://www.korea.kr/rss/incurityView.do`
  - 고용노동부 보도자료
  - 기획재정부, 국세청, 복지로, 각 지자시 보도자료 RSS

---

## 🚀 실행

```bash
cp .env.example .env       # 값 채우기

# (1) 샘플 영상만 렌더 (아무 키 없이 테스트)
python src/main.py --test

# (2) 실제 뉴스 수집 → 대본 생성 → 영상 저장까지 (발행X)
python src/main.py --dry-run

# (3) 수집 → 생성 → 렌더 → S3 업로드 → 인스타 발행
python src/main.py
```

---

## ⏰ 매일 자동 실행 (크론)

오전 7시, 오후 6시 하루 2회:
```cron
0 7,18 * * * cd /home/user/reels-auto && /usr/bin/python3 src/main.py >> output/run.log 2>&1
```
GitHub Actions나 서버 크론 어디서든 돌아갑니다.

---

## 🎨 커스터마이징 포인트

| 바꾸고 싶은 것 | 파일 |
|---|---|
| 자막 폰트/색/크기 | `render.py` 상단 상수 |
| 음성 (남/녀, 속도) | `render.py` `_synth()`의 `voice=`, `rate=` |
| 대본 톤/분량 | `script.py` `SYSTEM_PROMPT` |
| 수집 키워드 | `collect.py` `keywords` 리스트 |
| 게시 문구 형식 | `publish.py` `build_caption()` |

### edge-tts 한국어 보이스 목록
- `ko-KR-SunHiNeural` (여성, 차분)
- `ko-KR-InJoonNeural` (남성, 신뢰감)
- `ko-KR-JiMinNeural` (여성, 친근)
- `ko-KR-BongJinNeural` (남성, 활기)

---

## ⚠️ 주의사항

- Instagram API는 **24시간에 50개** 업로드 제한이 있음
- 같은 비디오를 짧은 시간에 반복 게시하면 스팸으로 간주될 수 있음
- 앱 심사 전에는 자신의 계정에만 올릴 수 있음 (다른 계정 게시는 앱 심사 필요)
- 영상 길이는 3초~90분, **90초 이내**가 릴스로 가장 안전
- 썸네일/커버 이미지가 필요하면 `publish.create_reel_container`에 `cover_url` 추가

---

## 🧪 발행 전 최종 체크리스트

- [ ] `.env`의 모든 키 입력
- [ ] `python src/main.py --test`로 샘플 영상 확인
- [ ] `--dry-run`으로 실제 대본/영상 품질 확인
- [ ] 계정이 비즈니스/크리에이터이고 FB 페이지와 연결됨
- [ ] R2/S3 공개 URL이 브라우저에서 바로 열림
- [ ] LLM이 만들어준 대본이 **원문과 1:1로 일치**하는지 육안 검수 (특히 숫자·일자)
