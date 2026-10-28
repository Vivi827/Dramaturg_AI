> **폐기됨.** 이 명세는 연구계획서·기획안과 맞지 않아 [`phase1/SPEC.md`](../phase1/SPEC.md)(v2)로 대체되었습니다. 기록용으로만 남겨 둡니다.

# Phase 1 프로토타입 설계 명세 (Next.js + Supabase)

> 이 파일이 구현의 기준이다. 모호하면 추측하지 말고 질문하라.

## 0. 결정 사항 요약
- 형태: 웹 앱. AI는 **연구자 실시간 Wizard-of-Oz**다(자동 응답 아님, LLM 호출 없음).
  참여자의 AI 요청이 DB에 쓰이면, 연구자 전용 위저드 콘솔이 참여자의 실시간 상태와 미리 준비한
  응답 풀을 보여주고, 연구자가 카드 1~4장을 골라 보낸다.
- 스택: Next.js(App Router, TypeScript) + Supabase(Postgres, Auth, Realtime), Vercel 배포.
  Supabase 프로젝트 리전은 가능하면 서울(ap-northeast-2).
- 참여자: 로그인 없음. 진입 시 Supabase **익명 로그인**(signInAnonymously)으로 auth.uid()를 받고,
  참여자 코드(P01 등)를 입력한다. 이름·이메일은 받지도 저장하지도 않는다.
- 연구자: `/wizard` 경로, Supabase 이메일 로그인 + `admins` 테이블에 등록된 계정만.
- UI 언어: 한국어. 데스크톱 1280px 이상 전용.

## 1. 연구 맥락
- 연구: 드라마투르기 기반 AI 인터랙티브 시스템을 활용한 배우의 캐릭터 해석 지원 연구, Phase 1 형성 연구.
  참여자는 성인 배우 4~5명.
- 연구자가 Zoom으로 진행하며 참여자 화면 전체를 녹화한다(사전 고지됨). 페이지에 녹화 표지는 넣지 않는다.
- 과제는 구두로 안내한다: 표적 장면에서 캐릭터 A의 등장 부분을 비트로 나누고, 비트마다 목적과
  행동동사를 적고, 이유를 메모한다. Think-Aloud로 진행한다.
  페이지에 과제 설명·조작 안내 문구를 넣지 않는다(조작은 연습 단계에서 구두로 가르친다).
- 관찰 목표: 참여자가 AI를 언제 찾는지, AI 응답을 결과물에 반영하는지, 탐색 흐름이 바뀌는지와
  그 시점. 그래서 모든 행동을 타임스탬프 로그로 남긴다.

## 2. 라우트
- `/` 참여자 화면
- `/wizard` 위저드 콘솔(관리자 로그인 필요)
- `/wizard/import` 대본 세트·응답 풀 JSON 붙여넣기 업로드(관리자만)

## 3. 참여자 화면
### 3.0 입장과 단계
- 첫 방문: 익명 로그인 → 참여자 코드 입력(형식 `^P\d{2}$`) → `sessions` 행 생성(phase='practice')
  → 연습 대본(script_sets.kind='practice')을 연다.
- 새로고침·재방문 시 같은 브라우저면 세션을 이어간다(작업, 단계, 메인 영역 모드, 열린 비트 복원).
- 연구자가 phase를 'task'로 바꾸면 Realtime으로 감지해 [과제 시작] 버튼을 띄운다.
  누른 시각을 `task_start_at`과 이벤트 `task_start`로 기록하고 표적 대본(kind='task')으로 바꾼다.
  연습 중 만든 비트·메모는 mode='practice'로 남기고 과제 화면에는 보이지 않는다.
- phase='done'이면 모든 입력을 잠그고 "수고하셨습니다"를 표시한다.
- 저장이 RLS로 거부되면 "저장 권한이 없습니다. 연구자에게 알려 주세요"를 상단에 고정 표시.

### 3.1 레이아웃
```
+--------------------------------------------+-----------+
| 메인 영역 (높이 약 75%)                       |           |
|   대본 모드 또는 비트 상세 모드               |   AI      |
+--------------------------------------------+  사이드바 |
| 비트 메뉴 (높이 약 25%, 가로 스크롤)          |  (세로)   |
+--------------------------------------------+-----------+
```
- AI 사이드바: 오른쪽, 화면 높이 전체. 기본 접힘(44px 세로 탭), 펼치면 너비 약 20%(최소 320px).
  펼친 만큼 왼쪽 작업 영역이 좁아지며 덮어쓰지 않는다.
- 왼쪽 작업 영역 = 위 메인 영역 + 아래 비트 메뉴. 둘 다 가로로 꽉 찬다.
- 메인 영역 두 모드: (a) 대본 모드(기본) (b) 비트 상세 모드. 전환마다 `mode_switch` 기록.
- 본문은 차분한 종이 대본 느낌. 한글 본문 16px 이상.

### 3.2 대본 뷰어 (대본 모드)
- 장면 탭(이전 장면들 + 표적 장면), 기본은 표적 장면. 줄 번호, 화자(굵게), 지문(기울임·회색). 수정 불가.
- 표적 캐릭터 대사 강조 토글(기본 꺼짐).
- 대본 모드에서는 브라우저 일반 텍스트 드래그 선택을 끈다(user-select: none).
- 비트 만들기(표적 장면에서만, 연습 단계에서는 연습 장면에서):
  1. 글자 위에서 마우스를 1초 이상 누르고 있으면(5px 이상 움직이지 않을 때) 그 글자가 시작점.
     누르는 동안 커서 옆 원형 진행 표시. 1초 전에 떼면 아무 일도 없다. → `beat_start_set`
  2. 시작점에 깃발 표시가 남고, 다음 클릭한 글자가 끝점 → 비트 저장(`beat_end_set`, `beat_create`).
     끝점이 시작점보다 앞이면 두 점을 바꾼다. Esc 또는 시작점 재클릭은 취소(`beat_select_cancel`).
  3. 비트 범위는 겹칠 수 없다. 겹치면 저장하지 않고 끝점 근처에 이유를 한 줄 3초간 표시(`beat_overlap_rejected`).
  4. 범위: `{start:{line, offset}, end:{line, offset}}`, offset은 줄 안 글자 위치.
- 저장된 비트는 옅은 색 하이라이트로 묶이고 범위 시작 줄 왼쪽 여백에 비트 번호 라벨.
  하이라이트에 마우스를 올리면 그 비트 전체가 진해지고 비트 메뉴의 해당 카드 테두리가 굵어진다.
  반대로 메뉴 카드에 올리면 대본의 범위가 진해진다.
- 보이는 줄 범위가 바뀔 때 2초 디바운스로 `viewport` 기록.

### 3.3 비트 메뉴 (아래 25%)
- 등록한 비트를 대본 순서로 가로 나열한 카드. 번호는 대본 위치로 매번 계산(저장하지 않음).
- 카드: 번호, 줄 범위, 목적 한 줄 미리보기(없으면 "목적 없음"), 동사 수, 메모 수, 첨부 수, 완성 체크.
- 카드를 누르면 메인 영역이 그 비트의 상세 모드로 바뀐다(`beat_open`). 열린 카드는 강조.
- 비트가 없으면 "비트가 없습니다"만.
- 완성 비트 = 목적이 있고 동사가 1개 이상.

### 3.4 비트 상세 모드 (메인 영역)
- 머리: [← 대본으로], 비트 번호, 장면·줄 범위, [범위 다시 선택], [삭제(확인)].
  - [← 대본으로]: 대본 모드로 돌아가 그 비트 범위로 스크롤·강조.
  - [범위 다시 선택]: 대본 모드에서 "범위 다시 선택 중" 띠를 띄우고 3.2 방식으로 새 범위를 받는다
    (`beat_range_change`). 범위 밖으로 밀려난 동사·메모는 지우지 않고 "범위 밖"으로 표시.
- 목적: 한 줄 입력, placeholder "~하기 위해".
- 비트 본문: 큰 글씨, 화자·지문 구분 유지. 문장 분리 기준: . ? ! … 뒤, 줄바꿈, 화자 교체. 지문은 한 문장.
- 본문에서 드래그로 텍스트를 고르면 선택 옆 작은 메뉴 [행동동사] [메모]. Shift+클릭은 현재 선택을
  클릭한 문장까지 늘린다. Esc로 닫는다.
  - 행동동사: 선택을 문장 경계로 넓혀 하나의 동사 그룹으로 묶는다. 그룹 색 배경 + 그룹 번호 라벨,
    오른쪽 여백에 동사 입력칸(placeholder "상대를 ~하다"). 한 문장은 한 그룹에만 속한다.
    다른 그룹 문장을 고르면 새 그룹으로 옮기고 `verb_remove` + `verb_assign` 기록. 그룹 삭제 버튼.
  - 메모: 고른 글자 범위 그대로(문장으로 넓히지 않음) 밑줄. 구글독스 댓글처럼 오른쪽 여백에 메모 카드,
    밑줄과 카드를 호버하면 서로 강조. 메모 범위끼리 겹쳐도 된다. 카드에서 수정·삭제.
- 첨부: AI 레퍼런스를 채택하면 머리 아래 카드 제목 칩(본문 자동 입력 없음).
- 모든 입력은 800ms 디바운스 저장, 저장마다 수정 전·후 값을 이벤트로
  (목적=`beat_edit`, 동사=`verb_edit`, 메모=`beat_memo_create|edit|delete`).

### 3.5 대본 메모 (대본 모드)
- 줄 사이 빈 공간에 마우스를 올리면 "+ 메모". 누르면 그 자리에 접히는 텍스트박스.
  장면 맨 앞·맨 뒤(비등장 시간)에도 가능. 줄 사이 감지 영역은 글자 영역과 겹치지 않게(hold클릭 충돌 방지).
- 종류: "생각"(노랑 계열), "전사·비등장 시간"(보라 계열). 색 + 라벨. 만들 때 고르고 나중에 변경 가능.
- 접힌 상태는 첫 줄 미리보기. `note_create|edit|toggle|delete` 기록.

### 3.6 AI 사이드바
- 기본 접힘. 열기·닫기 기록(직전 이벤트 유형 포함).
- 상단 고정 문구: "일부 응답은 연구진이 미리 준비했습니다."
- 도구: [시대배경] [인물 관계] (언제든), 자유 질문 입력 + [보내기],
  [내 해석으로 레퍼런스 찾기] — 완성 비트가 1개 이상일 때만 활성. 누르면 완성 비트 드롭다운
  (상세 모드에서는 열린 비트가 기본 선택). 비활성 툴팁: "비트 하나에 목적과 행동동사를 먼저 적어 주세요."
- 요청은 `requests`에 insert. 레퍼런스 요청은 그 순간 비트의 목적·동사 그룹·메모 스냅샷을 함께 저장.
- 대기 중 "자료를 찾는 중…". `responses`를 Realtime으로 받는다. 사이드바가 접혀 있으면 탭에 점만 표시하고
  자동으로 펼치지 않는다.
- 응답 카드: 유형 라벨, 제목, 출처 유형(희곡/공연/배우 인터뷰/역사 자료), 요약 2~3문장, 짧은 인용(있으면),
  출처 링크(새 탭, `ref_link_open`), 레퍼런스면 "비트 n과 연결". 유사/대조 라벨은 settings.show_polarity가 true일 때만.
- 레퍼런스 카드에 [채택] [보류] [배제] + 이유 한 줄(선택) → `decisions` insert. 채택하면 비트에 칩.
  바꾸면 새 결정으로 기록.
- 지난 응답은 시간순으로 남는다. AI 응답이 비트·메모에 자동 입력되는 기능은 만들지 않는다.

## 4. 위저드 콘솔 (`/wizard`, admins만)
- 세션 목록(Realtime): 코드, phase, 마지막 활동, 대기 요청 수 배지.
- phase 제어: practice / task / done.
- 실시간 미러(읽기 전용): 현재 모드, 보고 있는 장면·줄 범위, 비트(목적·동사·메모), 대본 메모, 요청.
  방금 바뀐 것 강조. 최근 이벤트 10개.
- 요청 큐: 대기 요청, 대기 시간(초) 카운트업, 알림음 켜기/끄기.
- 응답 풀: 유형·분기·태그 필터와 검색. 레퍼런스 요청이면 요청 스냅샷의 목적·동사·메모에서 각 분기
  keywords 등장 횟수를 세어 분기 후보를 순서대로 강조(결정은 사람).
- 보내기: 카드 1~4장 선택(단축키 1~4, Enter) → `responses` insert(카드 스냅샷 복사, 본문 수정 불가),
  해당 요청 status='answered'. type='fallback' 카드는 범위 밖 질문용 고정 문구.
- 선택 사유 메모와 관찰 마커([멈칫] [탐색 전환] [AI 반영] [기타] + 메모)는 `wizard_log`에. 참여자는 못 읽는다.
- 사후 타임라인: 한 세션의 이벤트·요청·응답·결정·마커를 시간순 세로 타임라인. task_start 기준 경과(분:초),
  유형 필터, AI 관련 항목과 mode_switch 강조. 사후 인터뷰 화면 공유용.
- 내보내기: 선택 세션 전체 JSON + 이벤트 CSV를 브라우저 다운로드.
- 삭제: [세션 데이터 삭제] — 내보내기 후에만 활성, 두 번 확인, cascade 삭제.

## 5. 데이터 모델 (Postgres)
```sql
admins(user_id uuid pk references auth.users)
script_sets(id text pk, kind text check (kind in ('task','practice')), title text,
            target_character text, scenes jsonb)          -- scenes: [{id,title,isTarget,lines:[{n,speaker,text,kind}]}]
settings(key text pk, value jsonb)                        -- show_polarity 등
pool_cards(id text pk, type text check (type in ('background','relation','reference','fallback')),
           branch text, polarity text, title text, source_type text, summary text, quote text,
           source_url text, tags text[], keywords text[])
sessions(id uuid pk default gen_random_uuid(), user_id uuid unique references auth.users,
         code text unique check (code ~ '^P\d{2}$'), phase text default 'practice',
         ui_mode text, open_beat_id uuid, created_at timestamptz default now(),
         task_start_at timestamptz, last_active_at timestamptz)
beats(id uuid pk, session_id uuid references sessions on delete cascade, mode text, scene_id text,
      range jsonb, text text, purpose text, verbs jsonb default '[]',   -- [{id, sentenceIdx:[], verb}]
      memos jsonb default '[]',                                      -- [{id, start, end, text, createdAt}]
      attached_card_ids text[] default '{}', created_at timestamptz, updated_at timestamptz)
notes(id uuid pk, session_id uuid ... cascade, mode text, scene_id text, after_line int,
      kind text, text text, collapsed bool, created_at, updated_at)
requests(id uuid pk, session_id ... cascade, type text, text text, beat_id uuid,
         beat_snapshot jsonb, status text default 'pending', created_at timestamptz)
responses(id uuid pk, session_id ... cascade, request_id uuid, cards jsonb, sent_at timestamptz)
decisions(id uuid pk, session_id ... cascade, card_id text, beat_id uuid, decision text, reason text, t timestamptz)
event_batches(session_id ... cascade, seq int, events jsonb, primary key(session_id, seq))
wizard_log(id uuid pk, session_id uuid ... cascade, t timestamptz, kind text, label text, note text)
```

## 6. 접근 규칙 (RLS)
- 모든 테이블 RLS 켬. `is_admin()` = `exists(select 1 from admins where user_id = auth.uid())` (security definer).
- 헬퍼 `my_session_id()` = `select id from sessions where user_id = auth.uid()`.
- script_sets, settings: 인증 사용자(익명 포함) select, 쓰기는 admin.
- pool_cards, wizard_log, admins: admin만 select/쓰기.
- sessions: 본인 insert(user_id = auth.uid()), 본인 select/update. **phase는 참여자가 바꿀 수 없다**
  → 트리거로 non-admin의 phase 변경을 거부한다. task_start_at은 본인이 비어 있을 때 1회만 기록할 수 있다.
  admin은 전체 select/update/delete.
- beats, notes, requests, decisions, event_batches: 본인 세션 행만 select/insert/update/delete. admin 전체 select/delete.
- responses: 참여자는 본인 세션 select만. insert는 admin만.
- Realtime: sessions, beats, notes, requests, responses, decisions를 publication에 추가. RLS가 적용되게 postgres_changes 사용.
- service role 키는 클라이언트에 절대 노출하지 않는다. 환경변수: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY.
- Supabase 대시보드에서 Anonymous sign-in 활성화 필요(README에 명시).

## 7. 이벤트 로그
- 유형:
  - 입장·단계: session_join, task_start
  - 화면: mode_switch(from,to), scene_open, viewport
  - 비트 만들기: beat_start_set, beat_end_set, beat_select_cancel, beat_overlap_rejected,
    beat_create, beat_range_change, beat_delete, beat_open
  - 비트 편집: beat_edit, verb_assign, verb_edit, verb_remove, beat_memo_create, beat_memo_edit, beat_memo_delete
  - 대본 메모: note_create, note_edit, note_toggle, note_delete
  - AI: ai_panel_open, ai_panel_close, ai_request, ai_response_shown, ref_link_open, ref_decision
- 각 이벤트 `{t: Date.now(), type, target, data}`. 키 입력·마우스 호버는 기록하지 않는다.
- 메모리에 모았다가 10초마다 또는 25개마다 event_batches 한 행으로 insert. pagehide·visibilitychange에서도 flush.
  실패 시 다음 회차에 합친다.

## 8. 시드와 데이터 넣기
- 대본·응답 풀을 코드에 하드코딩하지 않는다.
- `supabase/seed.sql`에 동작 확인용 샘플만: 만든 장면 2개(task), 짧은 연습 장면 1개(practice), 카드 4장(각 type 1장).
- `/wizard/import`: script_sets와 pool_cards를 JSON 붙여넣기로 upsert(검증 오류는 줄 단위로 표시).
- script_sets(kind='task')가 없으면 참여자 화면은 "연구 준비 중입니다"만 표시.

## 9. 산출물
- Next.js 앱 소스, `supabase/migrations/*.sql`(테이블·RLS·트리거·publication), `supabase/seed.sql`.
- README: Supabase 프로젝트 생성(서울 리전), Anonymous sign-in 켜기, 관리자 계정 만들고 admins에 넣는 SQL,
  Vercel 환경변수, 로컬 실행 방법.

## 10. 완료 기준 (직접 확인하고 결과를 보고할 것)
1. 샘플 데이터로 참여자 화면이 열리고, hold클릭→클릭으로 비트가 만들어지며 겹치는 범위는 거부된다.
2. 비트 메뉴를 누르면 상세 모드로 바뀌고, [← 대본으로]는 그 범위로 돌아간다.
3. 상세 모드에서 드래그 → [행동동사]는 문장 단위 그룹을, [메모]는 밑줄과 여백 메모를 만든다.
4. 대본 하이라이트와 비트 메뉴 호버가 서로 강조된다.
5. 비트·동사·메모·대본 메모가 새로고침 뒤에도 남는다.
6. 완성 비트가 없으면 레퍼런스 버튼이 비활성이다.
7. 두 브라우저(참여자/관리자)로 요청 → 콘솔 큐 → 보내기 → 참여자 사이드바 카드까지 2초 안에 동작한다.
8. event_batches에 위 행동들이 시간순으로 남는다.
9. 참여자 세션으로 pool_cards, wizard_log, 다른 세션 행을 select하면 0행이고, phase 변경과 responses insert는 거부된다
   (RLS 테스트 SQL 또는 스크립트 포함).
10. 확인하지 못한 항목은 못 했다고 알려라.
