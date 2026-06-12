"""
Bilibili 官方号内容获取 — 双通道策略

通道1: bilibili-api (直连, 快速但有反爬风险)
通道2: DDG 精搜 Bilibili 官方内容 (稳定, 不依赖B站API)
"""

import json
import logging
import time
from datetime import datetime
from langchain.tools import tool
from ddgs import DDGS

logger = logging.getLogger(__name__)

# 游戏→Bilibili UID+搜索关键词
GAME_BILIBILI: dict[str, dict] = {
    "原神": {"uid": 401742377, "bili_name": "原神官方"},
    "星穹铁道": {"uid": 1340190821, "bili_name": "崩坏星穹铁道官方"},
    "绝区零": {"uid": 1636375920, "bili_name": "绝区零官方"},
    "鸣潮": {"uid": 354136791, "bili_name": "鸣潮官方"},
    "明日方舟": {"uid": 161775301, "bili_name": "明日方舟官方"},
    "崩坏3": {"uid": 27534330, "bili_name": "崩坏3官方"},
    "战双": {"uid": 10165841, "bili_name": "战双帕弥什官方"},
    "蔚蓝档案": {"uid": 16535831, "bili_name": "蔚蓝档案官方"},
    "碧蓝航线": {"uid": 8352461, "bili_name": "碧蓝航线官方"},
    "少女前线": {"uid": 1523727, "bili_name": "少女前线官方"},
    "尘白禁区": {"uid": 3493095719732591, "bili_name": "尘白禁区官方"},
    "无期迷途": {"uid": 1861995594, "bili_name": "无期迷途官方"},
}

CACHE_TTL = 600  # 10分钟
_cache: dict[str, tuple[float, dict]] = {}


def _get_uid(query: str) -> int | None:
    """从查询中识别游戏 → Bilibili UID"""
    q = query.lower()
    for game in GAME_BILIBILI:
        if game in q:
            return GAME_BILIBILI[game]["uid"]
    return None


def _get_bilibili_info(query: str) -> dict | None:
    """获取游戏 Bilibili 信息"""
    q = query.lower()
    for game, info in GAME_BILIBILI.items():
        if game in q:
            return info
    return None


def _search_bilibili_content(bili_name: str, query: str) -> list[dict]:
    """
    DDG 精准搜索 B 站官方内容。

    策略：用 "B站官方号名 + 用户查询关键词" 搜，DDG 返回的 snippet
    直接包含 B 站动态/视频的标题和描述文本。
    """
    cache_key = f"ddg_bili_{bili_name}"
    now = time.time()
    if cache_key in _cache:
        ts, val = _cache[cache_key]
        if now - ts < CACHE_TTL:
            return val

    search_q = f"{bili_name} B站 {query} site:bilibili.com"
    results = []

    try:
        ddg = DDGS()
        for r in ddg.text(search_q, max_results=8):
            title = r.get("title", "")
            href = r.get("href", "")
            body = r.get("body", "") or ""

            results.append({
                "title": title,
                "url": href,
                "snippet": body[:300],
                "source": "T1-Bilibili官方号" if "space.bilibili.com" in href else "Bilibili搜索结果",
            })
    except Exception as e:
        logger.warning(f"DDG Bilibili 搜索失败: {e}")

    if results:
        _cache[cache_key] = (now, results)
    return results


def _try_bilibili_api(uid: int) -> dict:
    """尝试 bilibili-api 直连（可能被 412 拦截）"""
    try:
        from bilibili_api import user, sync
        u = user.User(uid)
        videos = sync(u.get_videos(ps=5, pn=1))
        vlist = videos.get("list", {}).get("vlist", [])
        result_videos = []
        for v in vlist[:5]:
            created = datetime.fromtimestamp(v.get("created", 0))
            result_videos.append({
                "title": v.get("title", ""),
                "desc": v.get("description", "")[:200],
                "url": f"https://www.bilibili.com/video/{v.get('bvid', '')}",
                "created": created.strftime("%Y-%m-%d"),
                "plays": v.get("play", 0),
                "source": "Bilibili官方号-视频",
            })
        return {"ok": True, "videos": result_videos}
    except Exception:
        return {"ok": False, "videos": []}


@tool
def bilibili_fetch(query: str) -> str:
    """
    获取指定游戏的 Bilibili 官方号最新内容（版本更新/角色/活动资讯）。

    双通道策略：
    1. 优先 bilibili-api 直连（快速准确）
    2. 失败则 DDG 精准搜索 B 站内容（稳定可靠）

    支持：原神、星穹铁道、绝区零、鸣潮、明日方舟、崩坏3、战双、蔚蓝档案等
    """
    info = _get_bilibili_info(query)
    if not info:
        return json.dumps({"error": "未识别到支持的游戏"}, ensure_ascii=False)

    uid = info["uid"]
    bili_name = info["bili_name"]
    space_url = f"https://space.bilibili.com/{uid}/dynamic"
    logger.info(f"Bilibili: {bili_name} query='{query[:40]}'")

    # 通道1: 尝试 API
    api_result = _try_bilibili_api(uid)

    # 通道2: DDG 精搜（无论API是否成功都搜，补充动态文本）
    ddg_results = _search_bilibili_content(bili_name, query)

    return json.dumps({
        "bilibili_name": bili_name,
        "space_url": space_url,
        "api_videos": api_result.get("videos", []),
        "ddg_results": ddg_results,
    }, ensure_ascii=False, indent=2)
