# 🗂️ 업무 비서 봇 — 사용 설명서

서은님 업무를 도와주는 텔레그램 봇입니다. 두 가지를 해요.

1. **업무 다이제스트** — 지정한 업무방들을 지켜보다가, 사담은 거르고 **나에게 떨어진 일·요청·마감**을 방별로 정리해 보냅니다. (한국시간 8~22시, 30분마다)
2. **회의록 설명** — 봇에게 회의록이나 업무 메시지(글 또는 파일)를 보내면, **핵심·결정사항·할 일·용어**를 풀어서 설명해줍니다. (몇 분~십몇 분 안에 답장)

> 주식봇과 **같은 텔레그램 계정·세션**을 재활용합니다. 텔레그램 로그인 다시 안 해요. 새로 받는 건 **봇 토큰 하나**뿐.

---

## 1. 처음 세팅 (한 번만)

대부분 주식봇에서 그대로 가져옵니다.

### A. 새 봇 만들기
1. 텔레그램 `@BotFather` → `/newbot` → 업무 비서용 봇 생성 → **토큰** 복사
2. 그 봇 대화창을 열어 **START**(또는 `안녕`)를 한 번 눌러요 (봇이 나에게 DM 보낼 수 있게)

### B. GitHub 저장소
1. github.com → **New repository** → 이름 `work-assistant-bot` → **Public** → Create
2. **Add file → Upload files** → 이 폴더 파일 전부 드래그 → Commit
   - ⚠️ `.env` 는 올리지 않음(숨김파일이라 자동 제외). 비밀값은 C에서.
   - 워크플로 2개(`.github/workflows/digest.yml`, `reply.yml`)는 폴더째 올라가요. 안 올라가면 Actions 탭 → "set up a workflow yourself" 로 두 파일 내용 각각 붙여넣기.

### C. 비밀값 1개 (`ENV_FILE`)
**Settings → Secrets and variables → Actions → New repository secret**
- Name: `ENV_FILE`
- Secret: 아래를 채워서 통째로 붙여넣기 (주식봇 값 대부분 재활용)

```
TG_API_ID=30875478
TG_API_HASH=9aa90846205b6f072bbb2ba42e092f17
TG_PHONE=+821039374698
TG_SESSION_STRING=(주식봇에서 쓰던 그 세션 문자열 그대로)
BOT_TOKEN=(BotFather 새 봇 토큰)
CHAT_ID=6051269607
LLM_ENABLED=true
GEMINI_API_KEY=(주식봇과 같은 Gemini 키 재활용 가능)
GEMINI_MODEL=gemini-2.5-flash
MY_NAME=서은
LOOKBACK_MINUTES=90
MAX_MSGS_PER_ROOM=120
DIGEST_MODE=new
```

### D. 켜기
**Actions** 탭 → `work-digest` → **Run workflow** 로 테스트. 업무 다이제스트가 오면 성공.
그 다음 봇에게 회의록을 한 번 보내보면, `work-reply` 가 (몇 분 뒤) 설명을 답장해요.

---

## 2. 회의록 설명, 이렇게 써요

봇 대화창에:
- **글 붙여넣기**: 회의록/메시지 그대로 붙이고 "이거 설명해줘" 라고 적으면 돼요(안 적어도 설명함).
- **파일 보내기**: `.docx`, `.pdf`, `.txt` 파일을 보내면 내용을 읽어 설명해요. 캡션에 질문을 적으면 그 질문 위주로 답해요.
- **그냥 질문**: "이 약어 무슨 뜻이야?" 같은 것도 답해줘요.

> ⏱️ 답장은 즉답이 아니라 **약 10분 간격**으로 확인 후 와요(무료 GitHub 방식 특성). 즉답이 필요하면 작은 서버(VPS)로 옮기면 됩니다.

---

## 3. 바꾸고 싶을 때

GitHub에서 파일 열고 **연필(Edit) → 수정 → Commit** 하면 다음 실행부터 반영돼요.

### 감시 업무방 바꾸기 → `rooms.txt`
한 줄에 방 하나. **방 ID(`-100...`) 또는 방 이름**(정확히).
- 추가: 새 줄에 ID나 이름
- 빼기: 줄 맨 앞에 `#`
- 봇이 못 찾은 방은 다이제스트 맨 아래 **"⚠️ 못 찾은 방"** 에 떠요 → 이름을 정확히 고치거나 ID로 바꾸세요.

> 방 ID를 정확히 알고 싶으면: 옵시디언 `📋 텔레그램 방 목록` 노트에 ID가 있어요. 거기서 복사하면 가장 확실해요.

### 보고 주기 바꾸기 → `.github/workflows/digest.yml` 의 `cron`
GitHub은 UTC(한국 −9). 현재 8~22시 30분마다: `0,30 23,0-13 * * *`
- 1시간마다: `0 23,0-13 * * *`
- 새 업무 없을 때도 매번 받기: Secrets `ENV_FILE` 의 `DIGEST_MODE` 를 `always` 로

### 회의록 응답 주기 → `.github/workflows/reply.yml` 의 `cron`
현재 약 10분마다(`*/10 * * * *`). 더 자주(5분) 가능하지만 GitHub이 자주 건너뛰어요.

### '나' 이름 / 수집 범위 → Secrets `ENV_FILE`
- `MY_NAME` : 나를 지목한 업무 판별용 이름
- `LOOKBACK_MINUTES` : 한 번에 몇 분치 메시지를 볼지(30분 주기면 90 권장)
- `DIGEST_MODE` : `new`(새 업무만) / `always`(매번)

---

## 4. 파일 구조

```
work-assistant-bot/
├─ rooms.txt             ← 감시 업무방 목록
├─ .github/workflows/
│   ├─ digest.yml        ← 업무 다이제스트 주기(8~22시 30분마다)
│   └─ reply.yml         ← 회의록 응답 주기(~10분)
│
├─ collector.py          업무방 메시지 수집(발신자 포함)
├─ extractor.py          사담 거르고 업무 추출(+ 나에게 떨어진 일 표시)
├─ explainer.py          회의록/질문 받아 설명 답장
├─ formatter.py          다이제스트 메시지 구성
├─ sender.py             봇 전송
├─ llm.py                Gemini 호출
├─ config.py             설정 로더
├─ main_digest.py        업무 다이제스트 1회 실행
└─ main_reply.py         회의록 응답 1회 실행
```

---

## 5. 주의

- 봇은 **읽기·요약 보조**예요. 중요한 지시는 원문도 직접 확인하세요.
- 업무 추출은 AI 판단이라 가끔 사담을 업무로 보거나 그 반대일 수 있어요. 어색하면 `extractor.py` 프롬프트를 조이면 됩니다.
- `.env`, `TG_SESSION_STRING`, 봇 토큰은 비밀입니다. Public 저장소엔 코드만, 비밀값은 Secrets에만.
- 회의록 파일은 봇이 잠깐 내려받아 텍스트만 읽고 버립니다(저장 안 함).
