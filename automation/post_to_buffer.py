"""
post_to_buffer.py
Buffer API를 사용해 Instagram / LinkedIn에 카드 이미지를 예약 포스팅합니다.

Buffer API 문서: https://buffer.com/developers/api
사용하는 엔드포인트:
  POST /1/media/upload.json  — 이미지 업로드
  POST /1/updates/create.json — 포스트 예약

환경변수:
  BUFFER_ACCESS_TOKEN   — Buffer OAuth 액세스 토큰
  BUFFER_PROFILE_IDS    — 쉼표 구분 프로필 ID (Instagram,LinkedIn)
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

import requests


BUFFER_API_BASE = "https://api.bufferapp.com/1"


def upload_image(access_token: str, image_path: Path) -> str:
    """이미지를 Buffer에 업로드하고 media_id를 반환합니다."""
    url = f"{BUFFER_API_BASE}/media/upload.json"

    with open(image_path, "rb") as f:
        resp = requests.post(
            url,
            data={"access_token": access_token},
            files={"file": (image_path.name, f, "image/png")},
            timeout=60,
        )

    resp.raise_for_status()
    data = resp.json()

    if not data.get("success"):
        raise RuntimeError(f"이미지 업로드 실패: {data}")

    return data["media"]["picture"]


def create_update(
    access_token: str,
    profile_ids: list[str],
    text: str,
    media_urls: list[str],
    scheduled_at: str | None = None,
) -> dict:
    """Buffer 업데이트(포스트)를 생성합니다."""
    url = f"{BUFFER_API_BASE}/updates/create.json"

    payload = {
        "access_token": access_token,
        "text": text,
        "media[photo]": media_urls[0] if media_urls else "",
        "now": "true" if not scheduled_at else "false",
    }

    # 다중 프로필
    for i, pid in enumerate(profile_ids):
        payload[f"profile_ids[{i}]"] = pid

    # 추가 이미지 (카드 2, 3장)
    for i, url_str in enumerate(media_urls[1:], start=1):
        payload[f"media[photos][{i}]"] = url_str

    if scheduled_at:
        payload["scheduled_at"] = scheduled_at

    resp = requests.post(url, data=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_caption(series_name: str, keyword: str, card_data: dict) -> str:
    """Claude가 생성한 캡션 사용, 없으면 자동 생성"""
    # Claude가 생성한 캡션 우선 사용
    if card_data.get("caption"):
        return card_data["caption"]

    # fallback: 자동 생성
    cards = card_data.get("cards", [])
    hook_card  = next((c for c in cards if c.get("layout") == "hook"), None)
    pts_card   = next((c for c in cards if c.get("layout") == "points"), None)

    hook   = hook_card["content"].get("question", "") if hook_card else ""
    items  = pts_card["content"].get("items", []) if pts_card else []
    hashtags = build_hashtags(series_name, keyword)

    lines = [hook, ""] if hook else []
    for p in items[:3]:
        lines.append(f"• {p.get('label', '')}: {p.get('desc', '')}")
    lines += ["", hashtags, "", "─────────────────", "스킬잇 @feeltechedu"]

    return "\n".join(lines)


def build_hashtags(series_name: str, keyword: str) -> str:
    base_tags = ["#감테크", "#IT기술", "#개발공부", "#테크설명", "#feeltechedu"]

    series_tags = {
        "Kubernetes": ["#쿠버네티스", "#kubernetes", "#k8s", "#클라우드네이티브", "#devops"],
        "Docker":     ["#도커", "#docker", "#컨테이너", "#container", "#devops"],
        "Azure":      ["#애저", "#azure", "#클라우드", "#microsoft", "#cloud"],
        "AI·ML":      ["#AI", "#머신러닝", "#인공지능", "#LLM", "#생성AI"],
    }

    kw_tag = f"#{keyword.replace(' ', '').replace('-', '')}"

    tags = base_tags + series_tags.get(series_name, []) + [kw_tag]
    return " ".join(tags[:15])  # 인스타그램 최대 30개, 가독성 위해 15개


def post_cards(
    series_name: str,
    keyword: str,
    card_data: dict,
    image_paths: list[Path],
    access_token: str,
    profile_ids: list[str],
    scheduled_at: str | None = None,
) -> dict:
    """
    카드 이미지를 업로드하고 Buffer에 예약합니다.
    """
    print(f"이미지 업로드 중 ({len(image_paths)}장)...")
    media_urls = []

    for i, path in enumerate(image_paths):
        print(f"  업로드 {i+1}/{len(image_paths)}: {path.name}")
        url = upload_image(access_token, path)
        media_urls.append(url)
        time.sleep(0.5)  # API 레이트 리밋 방지

    caption = build_caption(series_name, keyword, card_data)
    print(f"\n캡션:\n{caption}\n")

    print("Buffer 업데이트 생성 중...")
    result = create_update(
        access_token=access_token,
        profile_ids=profile_ids,
        text=caption,
        media_urls=media_urls,
        scheduled_at=scheduled_at,
    )

    return result


def main():
    parser = argparse.ArgumentParser(description="Buffer API 포스팅")
    parser.add_argument("--series-name", required=True)
    parser.add_argument("--keyword",     required=True)
    parser.add_argument("--card-data",   required=True, help="JSON 파일 또는 문자열")
    parser.add_argument("--images",      required=True, nargs="+", help="PNG 파일 경로들")
    parser.add_argument("--scheduled-at", default=None, help="ISO 8601 예약 시간 (없으면 즉시)")
    args = parser.parse_args()

    access_token = os.environ.get("BUFFER_ACCESS_TOKEN")
    profile_ids_str = os.environ.get("BUFFER_PROFILE_IDS", "")

    if not access_token:
        print("BUFFER_ACCESS_TOKEN 환경변수가 필요합니다.", file=sys.stderr)
        sys.exit(1)

    if not profile_ids_str:
        print("BUFFER_PROFILE_IDS 환경변수가 필요합니다.", file=sys.stderr)
        sys.exit(1)

    profile_ids = [pid.strip() for pid in profile_ids_str.split(",") if pid.strip()]

    # card_data 로드
    if os.path.isfile(args.card_data):
        with open(args.card_data, encoding="utf-8") as f:
            card_data = json.load(f)
    else:
        card_data = json.loads(args.card_data)

    image_paths = [Path(p) for p in args.images]
    for p in image_paths:
        if not p.exists():
            print(f"이미지 파일 없음: {p}", file=sys.stderr)
            sys.exit(1)

    result = post_cards(
        series_name=args.series_name,
        keyword=args.keyword,
        card_data=card_data,
        image_paths=image_paths,
        access_token=access_token,
        profile_ids=profile_ids,
        scheduled_at=args.scheduled_at,
    )

    print("포스팅 완료!")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
