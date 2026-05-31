/**
 * api-client.js
 * Claude API 호출 — 프롬프트 기반, 가변 카드 수
 */

'use strict';

const CLAUDE_MODEL   = 'claude-sonnet-4-20250514';
const CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages';

// ── 카드 생성 ─────────────────────────────────────────────────
/**
 * @param {string} apiKey
 * @param {object} series  - { id, color, icon, name }
 * @param {string} userPrompt - 사용자 자유 지시문
 * @returns {Promise<{cards: object[], caption: string, caption_linkedin: string}>}
 */
async function callClaudeAPI(apiKey, series, userPrompt) {
  const systemPrompt = buildSystemPrompt(series);
  const userMessage  = buildUserMessage(series, userPrompt);

  const response = await fetch(CLAUDE_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type':       'application/json',
      'x-api-key':          apiKey,
      'anthropic-version':  '2023-06-01',
      'anthropic-dangerous-direct-browser-access': 'true',
    },
    body: JSON.stringify({
      model:      CLAUDE_MODEL,
      max_tokens: 2048,
      system:     systemPrompt,
      messages:   [{ role: 'user', content: userMessage }],
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(`API ${response.status}: ${err?.error?.message || response.statusText}`);
  }

  const result = await response.json();
  const text   = result.content?.[0]?.text || '';
  return parseJSON(text);
}

// ── 추천 생성 ─────────────────────────────────────────────────
/**
 * @param {string} apiKey
 * @param {object} series
 * @param {string[]} postedKeywords - 이미 포스팅한 키워드 목록
 * @returns {Promise<Array<{title,reason,prompt,cards_hint}>>}
 */
async function getRecommendations(apiKey, series, postedKeywords = []) {
  const posted = postedKeywords.length
    ? `이미 다룬 주제: ${postedKeywords.join(', ')}`
    : '아직 포스팅 없음';

  const prompt = `${series.icon} ${series.name} 시리즈 SNS 카드 콘텐츠 아이디어를 3개 추천해줘.

${posted}

아래 JSON 형식으로만 응답해:
\`\`\`json
[
  {
    "title": "콘텐츠 제목 (20자 이내)",
    "reason": "추천 이유 한 줄 (30자 이내)",
    "prompt": "카드 생성기에 입력할 프롬프트 (구체적으로, 50-80자)",
    "cards_hint": 3
  }
]
\`\`\`

조건:
- 이미 다룬 주제와 겹치지 않게
- 실무자가 실제로 헷갈리거나 유용한 주제
- prompt 필드는 바로 카드 생성에 쓸 수 있도록 구체적으로 작성
- cards_hint: 콘텐츠 복잡도에 따라 1~4 중 적절히`;

  const response = await fetch(CLAUDE_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type':       'application/json',
      'x-api-key':          apiKey,
      'anthropic-version':  '2023-06-01',
      'anthropic-dangerous-direct-browser-access': 'true',
    },
    body: JSON.stringify({
      model:      CLAUDE_MODEL,
      max_tokens: 1024,
      messages:   [{ role: 'user', content: prompt }],
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(`API ${response.status}: ${err?.error?.message || response.statusText}`);
  }

  const result = await response.json();
  const text   = result.content?.[0]?.text || '';
  const parsed = parseJSON(text);
  return Array.isArray(parsed) ? parsed : [];
}

// ── 프롬프트 빌더 ─────────────────────────────────────────────
function buildSystemPrompt(series) {
  return `너는 ${series.icon} ${series.name} 분야의 현직 시니어 엔지니어이자 기술 교육 전문가야.
해당 기술을 실무에서 수년간 직접 써봤고, 초보자와 중급자가 어느 지점에서 막히는지 정확히 알고 있어.
브랜드: 스킬잇 (@feeltechedu)
타겟 독자: 실무 1~3년차 개발자, 기술직 취준생, 비개발 직군 중 기술 관심자

---

## 콘텐츠 품질 기준 (반드시 지킬 것)

1. **단순 정의 나열 금지**
   - 나쁜 예: "Pod는 쿠버네티스의 가장 작은 배포 단위입니다"
   - 좋은 예: "Pod가 컨테이너를 감싸는 이유 — IP 하나를 여러 컨테이너가 나눠 쓰려면"

2. **"왜 이렇게 설계됐는가" 반드시 포함**
   - 개념의 존재 이유, 이 구조가 해결하는 문제를 한 문장이라도 포함

3. **실무 오해/실수 포인트 1개 이상 포함**
   - 실제로 많이 하는 착각이나 함정 (points 카드의 항목 중 하나로)

4. **비유는 한국 독자에게 친숙한 것으로**
   - 아파트/호실, 택배/물류, 식당/주방, 회사 조직도 등

5. **hook 질문은 "실제로 구글에 검색할 법한 문장" 수준으로**
   - 나쁜 예: "Pod가 무엇인지 아시나요?"
   - 좋은 예: "컨테이너 1개 실행했는데 왜 Pod IP랑 컨테이너 IP가 같지?"

---

## 카드 레이아웃 종류
- hook: 훅 질문으로 시작 (첫 카드 전용)
- answer: 핵심 답변 + SVG 흐름도
- points: 핵심 포인트 목록 (최대 3개, 실무 오해 포인트 포함)
- custom: 자유 형식 (비교표, Before/After, 주의사항 등)

---

반드시 아래 JSON 형식으로만 응답해 (마크다운 코드블록 포함):

\`\`\`json
{
  "cards": [
    {
      "layout": "hook",
      "content": {
        "question": "실무에서 실제로 헷갈리는 질문 (물음표로 끝, 30자 이내)",
        "sub": "공감 유도 보조 문장 (30자 이내)"
      }
    },
    {
      "layout": "answer",
      "content": {
        "title": "핵심 답변 제목 — 왜/무엇인지 담기 (20자 이내)",
        "desc": "설계 이유 또는 비유 포함 설명 2줄 (각 40자 이내, 줄바꿈=\\n)",
        "diagram_nodes": [
          {"label": "노드명 (8자 이내)", "sub": "설명 (6자 이내)"},
          {"label": "핵심노드 (8자 이내)", "sub": "설명 (6자 이내)", "main": true},
          {"label": "노드명 (8자 이내)", "sub": "설명 (6자 이내)"}
        ]
      }
    },
    {
      "layout": "points",
      "content": {
        "title": "섹션 제목 (20자 이내)",
        "items": [
          {"label": "포인트1 (10자 이내)", "desc": "실무 맥락 포함 설명 (35자 이내)"},
          {"label": "포인트2 (10자 이내)", "desc": "실무 맥락 포함 설명 (35자 이내)"},
          {"label": "⚠ 흔한 실수", "desc": "실제로 많이 하는 착각이나 함정 (35자 이내)"}
        ]
      }
    }
  ],
  "caption": "Instagram 캡션 (이모지 포함, 핵심 인사이트 1줄 + 해시태그 줄바꿈 후 추가, 총 300자 이내)",
  "caption_linkedin": "LinkedIn 캡션 (해시태그 없이, 왜 이 개념이 실무에서 중요한지 전문적 톤으로, 200자 이내)"
}
\`\`\`

추가 규칙:
- 카드 수는 사용자 요청에 따라 1~5장 자유롭게 (기본 3장)
- diagram_nodes는 3~4개, 흐름 순서대로
- 모든 텍스트 한국어
- caption에는 관련 해시태그 10~15개 포함`;
}

function buildUserMessage(series, userPrompt) {
  return `시리즈: ${series.icon} ${series.name}

사용자 지시:
${userPrompt}`;
}

// ── JSON 파싱 헬퍼 ────────────────────────────────────────────
function parseJSON(text) {
  const jsonMatch = text.match(/```json\s*([\s\S]*?)```/) || text.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
  if (!jsonMatch) throw new Error('응답에서 JSON을 찾을 수 없습니다.\n\n' + text.slice(0, 200));
  try {
    return JSON.parse(jsonMatch[1]);
  } catch(e) {
    throw new Error('JSON 파싱 실패: ' + e.message);
  }
}
