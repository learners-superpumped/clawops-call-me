# ClawOps CallMe

**Claude Code가 전화로 당신에게 연락하는 플러그인.**

작업을 시작하고 자리를 비우세요. Claude가 완료했거나, 막혔거나, 결정이 필요할 때 전화/워치가 울립니다.

<img src="./call-me-comic-min.png" width="800" alt="ClawOps CallMe 만화">

- **미니멀 플러그인** - 딱 하나의 기능: 전화 걸기. 복잡한 설정 없음.
- **다중 턴 대화** - 자연스럽게 대화하며 의사결정.
- **어디서나 동작** - 스마트폰, 스마트워치, 유선 전화까지!
- **Tool-use 조합 가능** - 통화 중에도 Claude가 웹 검색 등 다른 도구를 사용할 수 있음.

---

## 빠른 시작

### 1. 필요한 계정 준비

다음이 필요합니다:

- **전화 제공자**: [ClawOps](https://platform.claw-ops.com) (자체 호스팅 CPaaS)
- **OpenAI API 키**: 음성-텍스트 변환(STT) 및 텍스트-음성 변환(TTS)용
- **ngrok 계정**: [ngrok.com](https://ngrok.com)에서 무료 가입 (웹훅 터널링용)

### 2. 전화 제공자 설정

[ClawOps](https://platform.claw-ops.com)는 Asterisk 기반 자체 호스팅 CPaaS로, Twilio 호환 Voice API를 제공합니다. SIP 트렁크(예: KT 비즈니스)를 보유한 경우 사용하세요.

**전제 조건**: ClawOps 인스턴스가 실행 중이어야 합니다.

**설정 단계:**

1. ClawOps 웹 대시보드에 로그인
2. **설정 → API Keys**에서 API 키 생성 (`sk_...` 키가 발급됨 — 한 번만 표시되므로 저장 필수)
3. 같은 설정 페이지에서 **Account ID**와 **Webhook Signing Key** 복사
4. 대시보드에서 전화번호 프로비저닝 (`Numbers` → `Provision Number`)
   - 프로비저닝된 번호가 `CALLME_PHONE_NUMBER`로 사용됨
5. 프로비저닝 후 표시되는 SIP 인증 정보로 SIP 소프트폰(예: Linphone) 등록
   - 소프트폰 내선번호가 `CALLME_USER_PHONE_NUMBER`로 사용됨

### 3. 환경변수 설정

`~/.claude/settings.json`(권장) 또는 셸에서 export로 설정하세요.

```json
{
  "env": {
    "CALLME_PHONE_ACCOUNT_SID": "ACxxxxxxxxxxxxxxxx",
    "CALLME_PHONE_API_KEY": "sk_your-api-key",
    "CALLME_PHONE_SIGNING_KEY": "your-signing-key",
    "CALLME_PHONE_NUMBER": "+821012345678",
    "CALLME_USER_PHONE_NUMBER": "softphone",
    "CALLME_CLAWOPS_BASE_URL": "https://api.claw-ops.com",
    "CALLME_OPENAI_API_KEY": "sk-...",
    "CALLME_NGROK_AUTHTOKEN": "your-ngrok-token"
  }
}
```

#### 필수 변수

| 변수                       | 설명                                    |
| -------------------------- | --------------------------------------- |
| `CALLME_PHONE_ACCOUNT_SID` | ClawOps Account ID (`AC...`)            |
| `CALLME_PHONE_API_KEY`     | ClawOps API 키 (`sk_...`)               |
| `CALLME_PHONE_SIGNING_KEY` | ClawOps 웹훅 서명 키 (서명 검증용)      |
| `CALLME_PHONE_NUMBER`      | Claude가 발신하는 전화번호 (E.164 형식) |
| `CALLME_USER_PHONE_NUMBER` | 수신할 전화번호 또는 SIP 내선번호       |
| `CALLME_OPENAI_API_KEY`    | OpenAI API 키 (TTS 및 실시간 STT용)     |
| `CALLME_NGROK_AUTHTOKEN`   | ngrok 인증 토큰 (웹훅 터널링용)         |

#### 선택 변수

| 변수                             | 기본값                     | 설명                                                 |
| -------------------------------- | -------------------------- | ---------------------------------------------------- |
| `CALLME_CLAWOPS_BASE_URL`        | `https://api.claw-ops.com` | ClawOps API 기본 URL                                 |
| `CALLME_TTS_VOICE`               | `onyx`                     | OpenAI 음성: alloy, echo, fable, onyx, nova, shimmer |
| `CALLME_PORT`                    | `3333`                     | 웹훅 HTTP 서버 포트                                  |
| `CALLME_CONTROL_PORT`            | `3334`                     | 데몬 제어 API 포트                                   |
| `CALLME_NGROK_DOMAIN`            | -                          | 커스텀 ngrok 도메인 (유료 기능)                      |
| `CALLME_TRANSCRIPT_TIMEOUT_MS`   | `180000`                   | 사용자 음성 대기 타임아웃 (3분)                      |
| `CALLME_STT_SILENCE_DURATION_MS` | `800`                      | 발화 종료 감지 무음 시간                             |

### 4. 플러그인 설치

```bash
/plugin marketplace add learners-superpumped/call-me
/plugin install callme@callme
```

Claude Code를 재시작하면 완료!

---

## 동작 원리

```
Claude Code A ──stdio──► MCP Server A ──┐
Claude Code B ──stdio──► MCP Server B ──┤ HTTP (localhost:3334)
Claude Code C ──stdio──► MCP Server C ──┘
                                        │
                                        ▼
                            ClawOps CallMe Daemon (공유)
                              ├── ngrok 터널 (단일)
                              ├── 웹훅 HTTP 서버
                              ├── WebSocket 미디어 스트림
                              └── Call Manager
                                        │
                                        ▼
                                    ClawOps
                                        │
                                        ▼
                                  전화가 울림
                                  사용자가 말함
                                  텍스트가 Claude에게 전달
```

여러 Claude Code 세션이 하나의 데몬 프로세스를 공유합니다. 첫 번째 MCP 서버가 데몬을 자동 시작하고, 이후 서버들은 기존 데몬에 연결됩니다. 데몬은 하나의 ngrok 터널, 하나의 웹훅 서버, 모든 통화 상태를 관리합니다. 모든 MCP 서버가 연결을 끊으면 30초 후 데몬이 자동 종료됩니다.

---

## 도구(Tools)

### `initiate_call`

전화를 겁니다.

```typescript
const { callId, response } = await initiate_call({
  message: "안녕하세요! 인증 시스템을 완료했어요. 다음에 뭘 작업할까요?",
});
```

### `continue_call`

후속 질문으로 대화를 이어갑니다.

```typescript
const response = await continue_call({
  call_id: callId,
  message: "알겠습니다. 레이트 리미팅도 추가할까요?",
});
```

### `speak_to_user`

응답을 기다리지 않고 사용자에게 말합니다. 시간이 오래 걸리는 작업 전에 요청을 확인할 때 유용합니다.

```typescript
await speak_to_user({
  call_id: callId,
  message: "해당 정보를 검색해볼게요. 잠시만 기다려주세요...",
});
// 시간이 걸리는 작업 수행
const results = await performSearch();
// 대화 계속
const response = await continue_call({
  call_id: callId,
  message: `${results.length}개의 결과를 찾았습니다...`,
});
```

### `end_call`

통화를 종료합니다.

```typescript
await end_call({
  call_id: callId,
  message: "좋습니다, 바로 시작할게요. 나중에 또 통화해요!",
});
```

---

## 인바운드 콜 (수신 전화)

외부 발신자(또는 본인)가 전화번호로 직접 전화하면 Claude가 워크스페이스 코드에 접근하여 응답합니다. 전화번호가 Claude Code의 음성 인터페이스가 됩니다.

### 설정

기존 환경변수와 함께 다음 변수를 추가하여 인바운드 콜을 활성화하세요:

| 변수                             | 필수             | 기본값        | 설명                                           |
| -------------------------------- | ---------------- | ------------- | ---------------------------------------------- |
| `CALLME_INBOUND_ENABLED`         | 아니오           | `false`       | 인바운드 콜 처리 활성화                        |
| `CALLME_WORKSPACE_DIR`           | 인바운드 활성 시 | —             | 인바운드 콜에서 Claude CLI가 실행되는 디렉토리 |
| `CALLME_INBOUND_WHITELIST`       | 아니오           | —             | 추가 허용 전화번호 (쉼표 구분, E.164 형식)     |
| `CALLME_INBOUND_PERMISSION_MODE` | 아니오           | `plan`        | 인바운드 세션의 Claude Code 권한 모드          |
| `CALLME_INBOUND_MAX_CALLS`       | 아니오           | `1`           | 최대 동시 인바운드 콜 수                       |
| `CALLME_INBOUND_GREETING`        | 아니오           | 한국어 기본값 | 전화 응답 시 인사 메시지                       |

### 동작 흐름

```
발신자가 전화번호로 전화
        │
        ▼
ClawOps → 웹훅 → ClawOps CallMe Daemon
        │
        ▼
화이트리스트 확인 (사용자 번호 자동 허용)
        │
        ▼
TTS 인사말 재생 (콜드 스타트 지연 커버)
        │
        ▼
CALLME_WORKSPACE_DIR에서 Claude CLI 실행
        │
        ▼
음성 대화 루프 (STT ↔ Claude ↔ TTS)
```

1. 수신 전화가 웹훅을 통해 데몬에 도달
2. 발신자 번호를 화이트리스트에서 확인
3. TTS 인사말이 즉시 재생되어 Claude CLI 실행 지연(5~15초)을 커버
4. `CALLME_WORKSPACE_DIR`에서 MCP 설정, 스킬, `CLAUDE.md`와 함께 Claude CLI 실행
5. 발신자가 음성 대화 루프를 통해 Claude와 자연스럽게 대화

### 참고 사항

- `CALLME_USER_PHONE_NUMBER`는 자동으로 화이트리스트에 추가됨 — 별도 등록 불필요
- TTS 인사말이 Claude CLI 콜드 스타트 지연(첫 턴에서 5~15초)을 커버
- 아웃바운드와 인바운드 콜이 동시성 제한을 공유 — 기본적으로 한 번에 한 통화만 가능
- 인바운드 세션은 워크스페이스의 기존 MCP 설정, 스킬, `CLAUDE.md`를 사용

---

## 비용

| 서비스    | 비용                   |
| --------- | ---------------------- |
| 발신 통화 | SIP 트렁크 비용만      |
| 전화번호  | ClawOps에서 프로비저닝 |

OpenAI 비용 추가:

- **음성-텍스트 변환(STT)**: ~$0.006/분 (Realtime STT)
- **텍스트-음성 변환(TTS)**: ~$0.02/분

**합계**: ~$0.02/분 + SIP 트렁크

---

## 문제 해결

### Claude가 도구를 사용하지 않는 경우

1. 모든 필수 환경변수가 설정되었는지 확인 (`~/.claude/settings.json` 권장)
2. 플러그인 설치 후 Claude Code 재시작
3. 명시적으로 요청: "작업이 끝나면 전화해서 다음 단계를 논의해줘."

### 전화가 연결되지 않는 경우

1. `claude --debug`로 MCP 서버 로그(stderr) 확인
2. ClawOps 인증 정보가 올바른지 확인
3. ngrok이 터널을 생성할 수 있는지 확인

### 오디오 문제

1. ClawOps에서 전화번호가 프로비저닝되었는지 확인
2. 웹훅 URL이 ngrok URL과 일치하는지 확인

### ngrok 오류

1. `CALLME_NGROK_AUTHTOKEN`이 올바른지 확인
2. ngrok 무료 티어 한도에 도달했는지 확인
3. `CALLME_PORT=3335`로 다른 포트 시도

### 데몬 문제

1. `~/.callme/daemon.log`에서 데몬 로그 확인
2. 데몬 상태 확인: `curl http://127.0.0.1:3334/status`
3. 비정상 데몬 종료: `kill $(cat ~/.callme/daemon.pid)`
4. 잠금 해제: `rmdir ~/.callme/daemon.lock.d 2>/dev/null`

---

## 개발

```bash
cd server
bun install
bun run dev          # MCP 서버 (데몬 자동 시작)
bun run daemon       # 데몬 수동 시작
```

---

## 라이선스

MIT
