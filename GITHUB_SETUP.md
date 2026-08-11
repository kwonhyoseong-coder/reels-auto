# 🚀 GitHub에 올려서 자동 RSS 갱신하기

한 번만 세팅하면, 그 뒤로는 GitHub이 매일 3회(06/12/18시 KST) 알아서 정부 사이트를
크롤링해 `output/policy-feed.xml`을 최신 상태로 유지해줍니다.
이 XML의 공개 URL을 Make의 RSS Watch 모듈에 넣으면 끝.

---

## 1. GitHub에 리포지토리 만들기

1. https://github.com/new 접속
2. **Repository name**: `reels-auto` (원하는 이름)
3. **Public** 선택 (Private도 되지만, Make가 raw URL을 읽으려면 Public이 가장 간단)
4. **Add a README**는 체크하지 말 것 (이미 우리 파일이 있으니)
5. **Create repository** 클릭

## 2. 이 폴더를 GitHub에 올리기

GitHub에서 만든 직후 뜨는 화면의 주소를 복사해둡니다. 보통 이런 형식:
```
https://github.com/당신의ID/reels-auto.git
```

터미널에서 이 폴더로 이동한 뒤:

```bash
cd /home/user/reels-auto           # 혹은 다운로드 받은 위치
git init
git branch -M main
git add .
git commit -m "Initial commit: 정부 보도자료 크롤러"
git remote add origin https://github.com/당신의ID/reels-auto.git
git push -u origin main
```

ID/비밀번호 요청이 뜨면 GitHub **Personal Access Token**을 비밀번호 대신 입력.
(토큰 발급: GitHub → Settings → Developer settings → Personal access tokens →
Generate new token → `repo` 권한 체크)

## 3. Actions 권한 켜기

리포지토리의 **Settings → Actions → General** 로 가서:
- **Workflow permissions** 섹션에서 **Read and write permissions** 선택
- Save

이게 꺼져있으면 자동 커밋이 안 돼요!

## 4. 첫 실행 트리거

GitHub의 **Actions** 탭으로 가면 "Build policy RSS feed" 워크플로가 보입니다.

- 왼쪽에서 해당 워크플로 선택
- 오른쪽 **Run workflow** 버튼 클릭 → 한 번 수동 실행
- 1~2분 뒤에 초록색 ✅가 뜨면 성공

성공하면 리포지토리의 `output/policy-feed.xml`이 새로 생기고 커밋 로그에도
"chore: refresh policy feed ..." 가 보일 거예요.

## 5. Make에 넣을 공개 RSS URL

리포지토리 페이지에서 `output/policy-feed.xml` 파일을 열고,
오른쪽 위 **Raw** 버튼을 누르면 주소창의 URL이 Make에 넣을 최종 RSS입니다.
보통 이런 형식:

```
https://raw.githubusercontent.com/당신의ID/reels-auto/main/output/policy-feed.xml
```

이 주소를 Make의 **RSS → Watch RSS feed items** 모듈 URL 칸에 붙여넣으세요.

---

## 검증 팁

- `https://raw.githubusercontent.com/.../policy-feed.xml` 을 브라우저에서 열었을 때
  XML이 보이면 정상.
- 새 글이 없으면 XML이 안 바뀔 수 있어요. 다음 크롤링(6시간 뒤)을 기다리거나,
  Actions에서 수동 실행해보세요.
- 빌드 로그가 실패하면 Actions 탭의 빨간 ✕를 클릭해서 에러 메시지 확인.

---

## 그 다음 단계

이 RSS URL이 준비되면 Make로 돌아가서:
1. 새 시나리오의 첫 모듈로 **RSS → Watch RSS feed items**
2. URL에 위 raw 주소 붙여넣기
3. "Choose where to start" → **From now on** (실제 운영 시) 또는
   **Select the first RSS feed item** (테스트 시)

이후 OpenAI 모듈 연결은 채팅에서 이어서 도와드려요.
