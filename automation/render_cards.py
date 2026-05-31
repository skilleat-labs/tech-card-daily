"""
render_cards.py
Playwright 헤드리스 브라우저로 카드 3장을 PNG로 렌더링합니다.

사용법:
  python automation/render_cards.py \
    --series k8s \
    --keyword Pod \
    --output-dir output/
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Playwright는 GitHub Actions에서 pip install로 설치
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("playwright가 설치되지 않았습니다. pip install playwright 후 playwright install chromium 실행")
    sys.exit(1)


CARD_SIZE = 1080  # px


async def render_cards(series_id: str, keyword: str, card_data: dict, output_dir: Path) -> list[Path]:
    """
    카드 3장을 PNG로 렌더링하여 output_dir에 저장합니다.
    Returns: 생성된 파일 경로 리스트
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # index.html 경로 (프로젝트 루트 기준)
    project_root = Path(__file__).parent.parent
    html_path = project_root / "index.html"

    if not html_path.exists():
        raise FileNotFoundError(f"index.html을 찾을 수 없습니다: {html_path}")

    output_files = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": CARD_SIZE, "height": CARD_SIZE})

        # index.html 로드
        await page.goto(f"file://{html_path.absolute()}")
        await page.wait_for_load_state("networkidle")

        # JavaScript로 카드 렌더링 트리거
        series_config = load_series_config(series_id)

        for card_index in range(3):
            png_path = output_dir / f"{series_id}_{keyword}_card{card_index + 1}.png"

            # 브라우저에서 카드 HTML 생성 후 스크린샷
            await page.evaluate(f"""
                (() => {{
                    const data = {json.dumps(card_data)};
                    const series = {json.dumps(series_config)};
                    const htmls = buildCardHTMLs(data, series);

                    // 오프스크린 컨테이너에 주입
                    const container = document.getElementById('offscreen-container');
                    container.style.cssText = 'position:fixed;top:0;left:0;width:1080px;height:1080px;';
                    container.innerHTML = htmls[{card_index}];
                }})()
            """)

            # 잠깐 대기 (폰트 렌더링)
            await asyncio.sleep(0.3)

            # 스크린샷
            element = await page.query_selector("#offscreen-container .gamtech-card")
            if element:
                await element.screenshot(path=str(png_path))
                output_files.append(png_path)
                print(f"  ✓ 카드 {card_index + 1} 저장: {png_path}")
            else:
                print(f"  ✗ 카드 {card_index + 1} 렌더링 실패", file=sys.stderr)

        await browser.close()

    return output_files


def load_series_config(series_id: str) -> dict:
    project_root = Path(__file__).parent.parent
    config_path = project_root / "topics" / f"{series_id}.json"

    if not config_path.exists():
        raise FileNotFoundError(f"시리즈 설정 없음: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    return {
        "id":    cfg["series"],
        "color": cfg["color"],
        "icon":  cfg["icon"],
        "name":  cfg["name"],
    }


async def main():
    parser = argparse.ArgumentParser(description="감테크 카드 PNG 렌더링")
    parser.add_argument("--series",     required=True, help="시리즈 ID (k8s, docker, azure, aiml)")
    parser.add_argument("--keyword",    required=True, help="키워드")
    parser.add_argument("--card-data",  required=True, help="카드 데이터 JSON 문자열 또는 파일 경로")
    parser.add_argument("--output-dir", default="output", help="PNG 출력 디렉토리")
    args = parser.parse_args()

    # card-data 파싱
    if os.path.isfile(args.card_data):
        with open(args.card_data, encoding="utf-8") as f:
            card_data = json.load(f)
    else:
        card_data = json.loads(args.card_data)

    output_dir = Path(args.output_dir)
    files = await render_cards(args.series, args.keyword, card_data, output_dir)

    print(f"\n렌더링 완료: {len(files)}장 저장됨")
    for f in files:
        print(f"  {f}")


if __name__ == "__main__":
    asyncio.run(main())
