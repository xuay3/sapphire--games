"""从森空岛《明日方舟：终末地》WIKI 抓取当前「干员寻访」与倒计时。

WIKI 是纯前端渲染，所以用无头浏览器加载后读渲染文本。
页面上的「还剩 X 天 Y 小时」会在抓取时换算成绝对时间写回。

用法：
    python tools/fetch_endfield.py [games.json] [--dry-run]
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

BJ = timezone(timedelta(hours=8))
URL = "https://wiki.skland.com/endfield"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "datasource" / "games.json"

REMAIN_RE = re.compile(r"干员寻访\s*\n\s*([^\n]+?)\s*\n\s*还剩\s*(?:(\d+)\s*天)?\s*(?:(\d+)\s*小时)?")


def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
            viewport={"width": 1440, "height": 1200},
            locale="zh-CN",
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(4000)
        text = page.inner_text("body")
        browser.close()
    return text


def parse(text, now):
    m = REMAIN_RE.search(text)
    if not m:
        return None
    name = m.group(1).strip()
    days = int(m.group(2) or 0)
    hours = int(m.group(3) or 0)
    end = (now + timedelta(days=days, hours=hours)).replace(minute=0, second=0, microsecond=0)
    return {"name": name, "days": days, "hours": hours, "end": end}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv[1:]
    data_path = Path(args[0]) if args else DATA

    now = datetime.now(BJ).replace(minute=0, second=0, microsecond=0)
    print("打开森空岛 WIKI（无头浏览器）…")
    text = scrape()
    info = parse(text, now)
    if not info:
        print("没解析到「干员寻访」区块，页面结构可能变了")
        return 1

    print(f"当前寻访：{info['name']}  还剩 {info['days']} 天 {info['hours']} 小时")
    print(f"换算结束时间：{info['end'].isoformat()}")

    data = json.loads(data_path.read_text(encoding="utf-8"))
    game = next((g for g in data["games"] if g["id"] == "endfield"), None)
    if game is None:
        print("games.json 里没有 endfield 条目")
        return 1

    pools = [p for p in (game.get("pools") or []) if p.get("name") != info["name"]]
    pools.insert(0, {
        "name": info["name"],
        "type": "character",
        "start": "",
        "end": info["end"].isoformat(),
        "featured": [],
    })
    game["pools"] = pools[:4]

    # WIKI 上寻访与各活动倒计时一致，可视为版本边界
    version = game.get("version") or {}
    version["end"] = info["end"].isoformat()
    version["endNote"] = "森空岛 WIKI 倒计时换算（当前版本活动结束）"
    game["version"] = version

    game["source"] = URL
    game["confidence"] = "auto"
    game["note"] = "寻访与剩余时间由 tools/fetch_endfield.py 从森空岛 WIKI 自动同步"
    game["updatedAt"] = now.strftime("%Y-%m-%d")
    data["updatedAt"] = datetime.now(BJ).isoformat(timespec="seconds")

    if dry:
        print("\n[dry-run] 未写入文件")
        return 0

    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n已写入 {data_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
