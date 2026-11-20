"""校验 datasource/games.json 的结构与时间，并输出状态报告。

用法：
    python tools/validate.py [json路径]

退出码：0 = 通过（可能带警告），1 = 有错误
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BJ = timezone(timedelta(hours=8))
KNOWN_IDS = {"genshin", "hsr", "zzz", "wuwa", "arknights", "endfield", "nikki"}
REQUIRED_GAME_FIELDS = {"id", "name"}


def parse_time(value):
    """解析 ISO 8601；只给日期时按北京时间当天 00:00 处理。"""
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if len(raw) == 10:  # YYYY-MM-DD
        raw += "T00:00:00+08:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BJ)
    return dt


def fmt(dt):
    return dt.astimezone(BJ).strftime("%Y-%m-%d %H:%M") if dt else "?"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv[1:]
    path = Path(args[0]) if args else Path("datasource/games.json")
    errors, warnings, stale = [], [], []
    now = datetime.now(BJ)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"找不到文件：{path}")
        return 1
    except json.JSONDecodeError as e:
        print(f"JSON 语法错误：{e}")
        return 1

    if data.get("schema") != 1:
        warnings.append(f"schema 字段应为 1，当前为 {data.get('schema')!r}")

    updated = parse_time(data.get("updatedAt"))
    if not updated:
        warnings.append("顶层 updatedAt 缺失或无法解析")
    else:
        age_days = (now - updated).total_seconds() / 86400
        if age_days > 14:
            stale.append(f"数据已经 {age_days:.0f} 天没更新（updatedAt={data.get('updatedAt')}）")

    games = data.get("games")
    if not isinstance(games, list) or not games:
        print("错误：games 必须是非空数组")
        return 1

    seen_ids = set()
    for game in games:
        gid = game.get("id")
        gname = game.get("name") or gid
        prefix = f"[{gid}]"

        if not isinstance(game, dict):
            errors.append(f"{prefix} 不是对象")
            continue
        missing = REQUIRED_GAME_FIELDS - set(game)
        if missing:
            errors.append(f"{prefix} 缺少字段 {sorted(missing)}")
        if gid in seen_ids:
            errors.append(f"{prefix} id 重复")
        seen_ids.add(gid)
        if gid not in KNOWN_IDS:
            warnings.append(f"{prefix} 不是预置 id，组件里需要作为自定义游戏添加")

        version = game.get("version") or {}
        vend = parse_time(version.get("end"))
        if version.get("end") and not vend:
            errors.append(f"{prefix} version.end 无法解析：{version.get('end')!r}")
        if vend and vend <= now:
            stale.append(f"{prefix} 版本已于 {fmt(vend)} 结束，需要更新下一版本")

        pools = game.get("pools") or []
        if not isinstance(pools, list):
            errors.append(f"{prefix} pools 必须是数组")
            continue

        for i, pool in enumerate(pools):
            pname = pool.get("name") or f"#{i}"
            pp = f"{prefix} 卡池「{pname}」"
            start = parse_time(pool.get("start"))
            end = parse_time(pool.get("end"))
            if pool.get("start") and not start:
                errors.append(f"{pp} start 无法解析：{pool.get('start')!r}")
            if pool.get("end") and not end:
                errors.append(f"{pp} end 无法解析：{pool.get('end')!r}")
            if start and end and start >= end:
                errors.append(f"{pp} 开始时间不早于结束时间")
            if end and end <= now:
                pass  # 已结束属于正常现象，不报警
            if not end:
                warnings.append(f"{pp} 没有结束时间，组件里会显示「待公布」")

        active = sum(1 for p in pools
                     if (parse_time(p.get("start")) or datetime.min.replace(tzinfo=BJ)) <= now < (parse_time(p.get("end")) or datetime.max.replace(tzinfo=BJ)))
        upcoming = sum(1 for p in pools if (parse_time(p.get("start")) or now) > now)
        print(f"{gname:<12} 版本 {str(version.get('name','?')):<8} 结束 {fmt(vend):<16} 进行中 {active} / 即将 {upcoming}")

    print()
    for w in warnings:
        print("提示：" + w)
    for s in stale:
        print("过期：" + s)
    for e in errors:
        print("错误：" + e)

    if errors or (strict and stale):
        print(f"\n校验失败：{len(errors)} 个错误，{len(stale)} 个过期项"
              + (f"，{len(warnings)} 个提示" if warnings else ""))
        return 1
    print(f"校验通过：{len(games)} 款游戏，{len(stale)} 个过期项，{len(warnings)} 个提示")
    return 0


if __name__ == "__main__":
    sys.exit(main())
