"""从 PRTS 自动抓取《明日方舟》的版本活动时间与限时寻访，写回 games.json。

用法：
    python tools/fetch_arknights.py            # 直接更新 datasource/games.json
    python tools/fetch_arknights.py --dry-run  # 只打印，不写文件

数据来源：
- 活动/版本时间：PRTS Semantic MediaWiki 查询（分类:有活动信息的页面）
- 限时寻访：PRTS 页面「卡池一览/限时寻访」的 wikitext 表格
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BJ = timezone(timedelta(hours=8))
API = "https://prts.wiki/api.php"
UA = "sapphire-widget/1.0 (+https://github.com/hyuannn)"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "datasource" / "games.json"

BANNER_PAGE = "卡池一览/限时寻访"


def get_json(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def wikitext(page):
    data = get_json({"action": "parse", "page": page, "prop": "wikitext",
                     "format": "json", "formatversion": "2"})
    return data.get("parse", {}).get("wikitext", "")


def iso(ts):
    return datetime.fromtimestamp(int(ts), BJ).isoformat()


def query_activities():
    """返回近期活动：[{name, start, end, start_ts, end_ts}]"""
    q = ("[[分类:有活动信息的页面]][[活动开始时间cn::>>2026-01-01]]"
         "|?名称|?活动开始时间#ISO|?活动结束时间#ISO|limit=60|order=desc")
    data = get_json({"action": "ask", "query": q, "format": "json"})
    out = []
    for item in data.get("query", {}).get("results", {}).values():
        p = item.get("printouts", {})
        names = p.get("名称") or []
        starts = p.get("活动开始时间") or []
        ends = p.get("活动结束时间") or []
        if not names or not starts or not ends:
            continue
        try:
            s_ts = int(starts[0]["timestamp"])
            e_ts = int(ends[0]["timestamp"])
        except (KeyError, IndexError, ValueError):
            continue
        out.append({"name": str(names[0]).strip(),
                    "start": iso(s_ts), "end": iso(e_ts),
                    "start_ts": s_ts, "end_ts": e_ts})
    return out


BANNER_RE = re.compile(
    r"\|\s*(\[\[文件:[^\n]*?)"
    r"\n\|\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})~<br/>\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*"
    r"\n\|\s*(\{\{干员头像[^\n]*)"
)

LINK_RE = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
OPER_RE = re.compile(r"\{\{干员头像\|([^}|]+)")


def parse_banners(text):
    out = []
    for m in BANNER_RE.finditer(text):
        head, start, end, ops = m.groups()
        links = LINK_RE.findall(head)
        name = links[-1][1].strip() if links else "限时寻访"
        featured = [o.strip() for o in OPER_RE.findall(ops)]
        out.append({
            "name": name,
            "type": "other",
            "start": start.replace(" ", "T") + ":00+08:00",
            "end": end.replace(" ", "T") + ":00+08:00",
            "featured": featured,
        })
    return out


PREFER = ("SideStory", "主线", "庆典", "限定", "故事集", "危机合约")
# 常驻系统 / 签到类，不算「版本」
EXCLUDE = ("签到", "补给", "礼包", "商店", "协议", "演算", "集成战略", "剿灭", "基建")
MAX_DAYS = 120


def pick_version(acts, now_ts):
    active = [a for a in acts if a["start_ts"] <= now_ts < a["end_ts"]]
    # 排除常驻玩法、超长活动、签到类
    active = [a for a in active
              if (a["end_ts"] - a["start_ts"]) <= MAX_DAYS * 86400
              and not any(k in a["name"] for k in EXCLUDE)]
    if not active:
        return None
    preferred = [a for a in active if any(k in a["name"] for k in PREFER)]
    pool = preferred or active
    pool.sort(key=lambda a: a["start_ts"], reverse=True)
    return pool[0]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv[1:]
    data_path = Path(args[0]) if args else DATA
    now = datetime.now(BJ)
    now_ts = int(now.timestamp())

    print("拉取 PRTS 活动数据…")
    acts = query_activities()
    print(f"  活动条目：{len(acts)}")
    version = pick_version(acts, now_ts)

    print(f"拉取 PRTS「{BANNER_PAGE}」…")
    banners = parse_banners(wikitext(BANNER_PAGE))
    print(f"  寻访条目：{len(banners)}")

    # 只保留未结束的寻访
    keep = []
    for b in banners:
        end = datetime.fromisoformat(b["end"])
        start = datetime.fromisoformat(b["start"])
        if end < now - timedelta(hours=1):
            continue
        keep.append(b)
    keep.sort(key=lambda b: b["start"], reverse=True)
    keep = keep[:6]

    if version:
        print(f"  版本候选：{version['name']}  {version['start']} → {version['end']}")
    else:
        print("  没有找到正在进行的活动，版本信息保持不变")

    data = json.loads(data_path.read_text(encoding="utf-8"))
    game = next((g for g in data["games"] if g["id"] == "arknights"), None)
    if game is None:
        print("games.json 里没有 arknights 条目")
        return 1

    if version:
        game["version"] = {
            "name": version["name"],
            "start": version["start"],
            "end": version["end"],
            "endNote": "PRTS 自动同步（当前活动结束时间）",
        }
    game["pools"] = keep
    game["source"] = f"https://prts.wiki/w/{urllib.parse.quote(BANNER_PAGE)}"
    game["confidence"] = "auto"
    game["note"] = "由 tools/fetch_arknights.py 从 PRTS 自动同步"
    game["updatedAt"] = now.strftime("%Y-%m-%d")
    data["updatedAt"] = now.isoformat(timespec="seconds")

    for b in keep:
        print(f"  - {b['name']}  {b['start'][:16]} → {b['end'][:16]}")

    if dry:
        print("\n[dry-run] 未写入文件")
        return 0

    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n已写入 {data_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
