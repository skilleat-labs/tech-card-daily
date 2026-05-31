"""
daily_runner.py
전체 파이프라인 오케스트레이터:
  1. 오늘 포스팅할 키워드 선택 (topics/*.json 로테이션)
  2. Claude API로 카드 콘텐츠 생성
  3. Playwright로 PNG 렌더링
  4. Buffer API로 포스팅
  5. 포스팅 기록 업데이트

환경변수:
  ANTHROPIC_API_KEY
  BUFFER_ACCESS_TOKEN
  BUFFER_PROFILE_IDS
  SERIES_ID            (선택, 기본값: 순환)
"""

import asyncio
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import anthropic
import requests

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from render_cards import render_cards, load_series_config
from post_to_buffer import post_cards


PROJECT_ROOT = Path(__file__).parent.parent
TOPICS_DIR   = PROJECT_ROOT / "topics"
OUTPUT_DIR   = PROJECT_ROOT / "output"

# 시리즈 로테이션 순서
SERIES_ROTATION = ["k8s", "docker", "azure", "aiml"]
CLAUDE_MODEL    = "claude-sonnet-4-20250514"


def pick_keyword(series_id: str) -> tuple[str, dict]:
    """
    topics/{series_id}.json에서 아직 포스팅하지 않은 키워드를 선택합니다.
    Returns: (keyword, topics_data)
    """
    topics_path = TOPICS_DIR / f"{series_id}.json"
    with open(topics_path, encoding="utf-8") as f:
        data = json.load(f)

    posted = set(data.get("posted", []))
    remaining = [kw for kw in data["keywords"] if kw not in posted]

    if not remaining:
        # 모두 소진 → 초기화
        print(f"  [{series_id}] 모든 키워드 소진, 처음부터 시작")
        data["posted"] = []
        remaining = data["keywords"]

    keyword = remaining[0]
    return keyword, data


def save_keyword_posted(series_id: str, keyword: str):
    """포스팅 완료된 키워드를 기록합니다."""
    topics_path = TOPICS_DIR / f"{series_id}.json"
    with open(topics_path, encoding="utf-8") as f:
        data = json.load(f)

    if keyword not in data.get("posted", []):
        data.setdefault("posted", []).append(keyword)

    with open(topics_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_series() -> str:
    """오늘 날짜 기반으로 시리즈를 순환 선택합니다."""
    override = os.environ.get("SERIES_ID")
    if override and override in SERIES_ROTATION:
        return override

    day_index = (date.today() - date(2025, 1, 1)).days
    return SERIES_ROTATION[day_index % len(SERIES_ROTATION)]


def generate_card_content(api_key: str, series_cfg: dict, user_prompt: str) -> dict:
    """Claude API로 카드 콘텐츠를 생성합니다."""
    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = f"""너는 {series_cfg['icon']} {series_cfg['name']} 기술 개념을 SNS 카드 이미지로 설명하는 콘텐츠 크리에이터야.
브랜드: 스킬잇 (@feeltechedu)

반드시 아래 JSON 형식으로만 응답해:

```json
{{
  "cards": [
    {{
      "layout": "hook|answer|points|custom",
      "content": {{}}
    }}
  ],
  "caption": "Instagram 캡션 (이모지+해시태그 포함)",
  "caption_linkedin": "LinkedIn 캡션 (전문적 톤)"
}}
```

layout별 content:
- hook:   {{ question, sub }}
- answer: {{ title, desc, diagram_nodes: [{{label, sub, main?}}] }}
- points: {{ title, items: [{{label, desc}}] }}
- custom: {{ title, body }}

카드 수는 콘텐츠 복잡도에 맞게 자유롭게 (1~5장). 모든 텍스트 한국어."""

    user_message = f"시리즈: {series_cfg['icon']} {series_cfg['name']}\n\n{user_prompt}"

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    text = message.content[0].text

    # JSON 추출
    import re
    match = re.search(r"```json\s*([\s\S]*?)```", text) or re.search(r"(\{[\s\S]*\})", text)
    if not match:
        raise ValueError(f"JSON 파싱 실패:\n{text}")

    return json.loads(match.group(1))


def save_card_data(series_id: str, keyword: str, data: dict) -> Path:
    """카드 데이터를 JSON으로 저장합니다."""
    today = date.today().strftime("%Y%m%d")
    path = OUTPUT_DIR / f"{today}_{series_id}_{keyword}_data.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return path


async def run_pipeline():
    # ── 환경변수 확인 ──
    api_key      = os.environ.get("ANTHROPIC_API_KEY")
    buffer_token = os.environ.get("BUFFER_ACCESS_TOKEN")
    profile_ids  = [p.strip() for p in os.environ.get("BUFFER_PROFILE_IDS", "").split(",") if p.strip()]

    if not api_key:
        print("ANTHROPIC_API_KEY 없음", file=sys.stderr); sys.exit(1)
    if not buffer_token:
        print("BUFFER_ACCESS_TOKEN 없음", file=sys.stderr); sys.exit(1)
    if not profile_ids:
        print("BUFFER_PROFILE_IDS 없음", file=sys.stderr); sys.exit(1)

    # ── 1. 시리즈 & 키워드 선택 ──
    series_id = pick_series()
    keyword, _ = pick_keyword(series_id)
    series_cfg = load_series_config(series_id)

    print(f"오늘의 포스팅: [{series_cfg['name']}] {keyword}")
    print(f"시작 시각: {datetime.now(timezone.utc).isoformat()}")

    # ── 2. 카드 콘텐츠 생성 ──
    print("\n[Step 1] Claude API로 콘텐츠 생성 중...")
    user_prompt = f"{keyword}에 대해 실무자가 헷갈리기 쉬운 개념을 카드로 설명해줘. 기본 3장 구성으로."
    card_data = generate_card_content(api_key, series_cfg, user_prompt)
    print(f"  카드 수: {len(card_data.get('cards', []))}장")
    print(f"  캡션 미리보기: {card_data.get('caption', '')[:50]}...")

    data_path = save_card_data(series_id, keyword, card_data)
    print(f"  데이터 저장: {data_path}")

    # ── 3. PNG 렌더링 ──
    print("\n[Step 2] Playwright로 PNG 렌더링 중...")
    today_str = date.today().strftime("%Y%m%d")
    render_output = OUTPUT_DIR / today_str / f"{series_id}_{keyword}"

    image_paths = await render_cards(series_id, keyword, card_data, render_output)
    expected = len(card_data.get("cards", []))

    if len(image_paths) < expected:
        print(f"경고: {len(image_paths)}/{expected}장 렌더링됨", file=sys.stderr)

    # 캡션 txt 저장
    if card_data.get("caption"):
        (render_output / "caption_instagram.txt").write_text(card_data["caption"], encoding="utf-8")
    if card_data.get("caption_linkedin"):
        (render_output / "caption_linkedin.txt").write_text(card_data["caption_linkedin"], encoding="utf-8")

    # ── 4. Buffer 포스팅 ──
    print("\n[Step 3] Buffer API 포스팅 중...")
    result = post_cards(
        series_name=series_cfg["name"],
        keyword=keyword,
        card_data=card_data,
        image_paths=image_paths,
        access_token=buffer_token,
        profile_ids=profile_ids,
    )

    print(f"  포스팅 결과: {result.get('success', False)}")

    # ── 5. 포스팅 기록 ──
    save_keyword_posted(series_id, keyword)
    print(f"\n완료! [{series_cfg['name']}] {keyword} 포스팅 성공")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
