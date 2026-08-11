# 📣 Make.com 세팅 가이드 (무료 플랜)

GitHub Actions가 영상을 만들어서 Release에 올리고,
우리 Make 시나리오의 **Webhook 주소**로 `video_url`과 `caption`을 쏴줍니다.
Make는 그걸 받아서 인스타에 올리기만 하면 끝이에요.

> Make 무료 플랜: 월 1,000 operations. 하루 2~3개 발송이면 100건도 안 씁니다.

---

## 1️⃣ 새 시나리오 만들기

1. Make 로그인 → **Scenarios → Create scenario**
2. 가운데 `+` 클릭 → **"Webhooks"** 검색 → **Custom webhook** 선택
3. 액션은 **"Custom webhook"** (Watch가 아니라 그냥 trigger)
4. **Add** 버튼으로 새 webhook 만들기
   - Webhook name: `Reels incoming` (아무거나)
   - **IP restriction**: 비워두기
   - **Save**
5. 잠시 후 "**Address**"가 발급됨. 그 주소를 통째로 복사

   예:
   ```
   https://hook.eu1.make.com/abcd1234xyz...
   ```

6. GitHub 리포지토리로 가서:
   - **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `MAKE_WEBHOOK_URL`
   - Secret: 방금 복사한 webhook 주소 붙여넣기
   - Add secret

---

## 2️⃣ Instagram for Business 모듈 연결

1. Make 시나리오의 Webhook 박스 오른쪽 `+` 클릭
2. **"Instagram for Business"** 검색 → 선택
3. 액션은 **"Publish a Reel"** (없으면 "Create a Reel" / "Upload a Reel")
4. **Add** 버튼으로 커넥션 추가
   - Facebook으로 로그인 (인스타가 붙어있는 FB 계정)
   - 권한 허용
   - Instagram 계정 선택
5. 모듈 설정:
   - **Instagram Account**: 방금 연결한 계정
   - **Video URL**: 클릭 → Webhook이 보낸 `video_url` 매핑
   - **Caption**: `caption` 매핑
   - **Share to Feed**: Yes
   - **Disable Comments**: 취향껏
   - Cover photo / Thumbnail: 비워둬도 됨 (Instagram이 자동 선택)

---

## 3️⃣ 테스트

1. GitHub Actions 탭 → **Build and publish reel** → **Run workflow**
2. 5~10분 뒤:
   - Action이 초록 ✅
   - Releases 탭에 mp4 파일 올라감
   - Make 시나리오가 자동 실행되어 인스타에 릴스 발행
3. Make 시나리오가 자동 실행되지 않으면:
   - Make 시나리오 편집 화면에서 Webhook의 **"Redetermine data structure"** 클릭
   - GitHub Actions를 한 번 더 수동 실행해서 payload가 들어오게 하기

---

## 4️⃣ 운영

- 매일 06:00 / 12:00 / 18:00 KST에 자동 실행
- 새 정부 보도자료가 있을 때만 영상이 만들어지고 발송
- 없으면 Release도 안 만들고 조용히 종료
- Make 시나리오 왼쪽 아래 토글을 **켜두면**(Scheduling ON) 24시간 대기

Make의 스케줄링은 Webhook 트리거라 켜두기만 하면 되고,
"얼마나 자확 확인" 같은 설정은 없습니다. Webhook은 실시간으로 바로 실행돼요.

---

## 5️⃣ 점검/중지 방법

- **발행 중지**: GitHub Actions 탭에서 workflow를 **Disable**
- **하나만 건너뛰기**: GitHub Secrets에서 `MAKE_WEBHOOK_URL`을 잠시 지우면, 영상만 만들어지고 발행은 안 됨
- **삭제**: 인스타에서 직접 게시물 삭제 (Make는 나중에 다시 안 올림 — `state.json`에 ID가 기록됨)
