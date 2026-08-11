# 🔑 Gemini API 키 발급 (무료, 신용카드 불필요)

1. https://aistudio.google.com/apikey 접속
2. Google 계정으로 로그인
3. **Create API key** 클릭
4. Google Cloud 프로젝트 선택 ("Create API key in new project" 추천)
5. 발급된 키(`AIza...`) 복사

## GitHub Secret에 등록

리포지토리의 **Settings → Secrets and variables → Actions → New repository secret**:

- Name: `GEMINI_API_KEY`
- Secret: `AIza...`

이것만 하면 끝. 무료 티어는 1분 15건, 하루 1,500건이라
하루 3개 릴스 만드는 우리한텐 차고 넘쳐요.

> 만약 나중에 403/quota 에러가 나면 키를 새로 만들어 바꿔 넣으면 됩니다.
