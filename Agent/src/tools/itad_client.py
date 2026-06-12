"""
IsThereAnyDeal API 客户端 (v2 — 2026-06 更新)

Steam + GOG + Epic + 20+ 商店聚合折扣数据。
免费申请 Key: https://isthereanydeal.com/apps/

端点（2026年新版）:
  GET  /games/search/v1     — 搜索游戏 → 获取游戏 ID
  POST /games/prices/v3     — 当前各商店价格 + 折扣
  POST /games/historylow/v1 — 历史最低价

环境变量:
  ITAD_API_KEY — 你的 IsThereAnyDeal API Key (免费申请)
"""

import json
import logging
import os
import time
from functools import lru_cache

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.isthereanydeal.com"
CACHE_TTL = 600   # 搜索缓存 10 分钟
PRICE_TTL = 300   # 价格缓存 5 分钟

_cache: dict[str, tuple[float, dict]] = {}


def _cached(key: str, ttl: int = CACHE_TTL):
    """简单内存缓存"""
    now = time.time()
    if key in _cache:
        ts, val = _cache[key]
        if now - ts < ttl:
            return val
    return None


def _set_cache(key: str, val):
    _cache[key] = (time.time(), val)


def _api_key() -> str:
    """从环境变量获取 API Key，禁止硬编码"""
    return os.getenv("ITAD_API_KEY", "")


def _headers() -> dict:
    return {
        "User-Agent": "Gamebti/1.0",
        "Accept": "application/json",
    }


def _get(endpoint: str, params: dict = None) -> dict | list | None:
    """通用 GET 请求，key 自动附加到 query string"""
    if not _api_key():
        logger.warning("ITAD_API_KEY 未设置，跳过 IsThereAnyDeal 查询")
        return None

    params = params or {}
    params["key"] = _api_key()

    try:
        r = httpx.get(
            f"{BASE_URL}{endpoint}",
            params=params,
            headers=_headers(),
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning(f"ITAD GET {endpoint}: HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as e:
        logger.warning(f"ITAD GET 失败 ({endpoint}): {e}")
        return None


def _post(endpoint: str, body: list, params: dict = None) -> list | None:
    """通用 POST 请求，body 为 JSON 数组，key 附加到 query string"""
    if not _api_key():
        logger.warning("ITAD_API_KEY 未设置，跳过 IsThereAnyDeal 查询")
        return None

    params = params or {}
    params["key"] = _api_key()

    try:
        r = httpx.post(
            f"{BASE_URL}{endpoint}",
            params=params,
            json=body,
            headers={**_headers(), "Content-Type": "application/json"},
            timeout=10,
        )
        if r.status_code != 200:
            logger.warning(f"ITAD POST {endpoint}: HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as e:
        logger.warning(f"ITAD POST 失败 ({endpoint}): {e}")
        return None


# ========================
# 核心 API 函数
# ========================

def search_game(title: str, limit: int = 5) -> list[dict]:
    """
    搜索游戏 → 返回含 id/slug/title 的游戏列表。

    新版返回格式: [{id, slug, title, type, mature, assets}]
    """
    cache_key = f"search_{title}"
    cached = _cached(cache_key)
    if cached:
        return cached

    data = _get("/games/search/v1", {"title": title, "results": limit})
    if not data:
        return []

    games = []
    for g in (data if isinstance(data, list) else [data]):
        games.append({
            "id": g.get("id", ""),
            "slug": g.get("slug", ""),
            "title": g.get("title", ""),
            "type": g.get("type", ""),
        })

    _set_cache(cache_key, games)
    return games


def get_price(game_id: str, country: str = "CN") -> dict | None:
    """
    获取游戏当前在各商店的价格和折扣。

    参数:
      game_id — 游戏 ID (来自 search_game 的 id 字段，UUID 格式)
      country — 国家代码 (CN/US/...)

    返回: {id, historyLow, deals: [{shop, price, regular, cut, drm, url, ...}]}
    """
    cache_key = f"price_{game_id}_{country}"
    cached = _cached(cache_key, PRICE_TTL)
    if cached:
        return cached

    data = _post("/games/prices/v3", [game_id])
    if not data or not isinstance(data, list) or not data:
        return None

    result = _parse_price(data[0])
    _set_cache(cache_key, result)
    return result


def get_history(game_id: str, country: str = "CN") -> dict | None:
    """
    获取游戏历史最低价。

    参数:
      game_id — 游戏 ID (UUID 格式)
      country — 国家代码

    返回: {id, low: {shop, price, regular, cut, timestamp}}
    """
    cache_key = f"history_{game_id}_{country}"
    cached = _cached(cache_key, CACHE_TTL)
    if cached:
        return cached

    data = _post("/games/historylow/v1", [game_id])
    if not data or not isinstance(data, list) or not data:
        return None

    result = _parse_history(data[0])
    _set_cache(cache_key, result)
    return result


# ========================
# 便捷组合函数
# ========================

def query_game(query: str, country: str = "CN") -> dict | None:
    """
    一站式查询：搜索游戏 → 获取价格 + 史低。

    返回: {game, id, slug, price, history}
    """
    if not _api_key():
        return None

    results = search_game(query)
    if not results:
        logger.info(f"ITAD 未找到: '{query}'")
        return None

    best = results[0]
    game_id = best["id"]

    price_data = get_price(game_id, country)
    history_data = get_history(game_id, country)

    return {
        "game": best["title"],
        "id": game_id,
        "slug": best["slug"],
        "price": price_data,
        "history": history_data,
    }


def get_deals(country: str = "CN", shop: str = "steam", limit: int = 10) -> list[dict]:
    """
    获取当前热门折扣列表（多游戏聚合）。

    实现：搜索热门关键词 → 并行获取价格 → 聚合所有折扣。
    """
    cache_key = f"deals_{country}_{shop}"
    cached = _cached(cache_key, PRICE_TTL)
    if cached:
        return cached

    # 搜索热门游戏获取一批 ID
    popular = ["Elden Ring", "Cyberpunk 2077", "Baldur's Gate 3",
               "Red Dead Redemption 2", "Hogwarts Legacy"]
    all_deals = []

    for title in popular:
        games = search_game(title, 2)
        for g in games[:1]:  # 每款只取第一个
            price_data = get_price(g["id"], country)
            if price_data:
                for d in (price_data.get("deals") or [])[:3]:
                    d["_game"] = g["title"]
                    all_deals.append(d)
                    if len(all_deals) >= limit:
                        _set_cache(cache_key, all_deals)
                        return all_deals

    _set_cache(cache_key, all_deals)
    return all_deals


# ========================
# 向后兼容别名
# ========================

def get_prices(plain_id: str, country: str = "CN") -> dict | None:
    """[已弃用] 请使用 get_price(game_id)"""
    return get_price(plain_id, country)


def get_lowest(plain_id: str, country: str = "CN") -> dict | None:
    """[已弃用] 请使用 get_history(game_id)"""
    return get_history(plain_id, country)


# ========================
# 响应解析
# ========================

def _parse_price(item: dict) -> dict:
    """解析 /games/prices/v3 的单个游戏价格数据"""
    result = {"id": item.get("id", ""), "deals": [], "history_low": {}}

    # 史低
    hl = item.get("historyLow") or {}
    result["history_low"] = {
        "all_time": _fmt_price(hl.get("all")),
        "year": _fmt_price(hl.get("y1")),
        "3months": _fmt_price(hl.get("m3")),
    }

    # 当前折扣
    for d in (item.get("deals") or [])[:10]:
        shop = d.get("shop", {})
        price = d.get("price", {})
        regular = d.get("regular", {})
        drm_list = [dr.get("name", "") for dr in (d.get("drm") or [])]
        platforms = [p.get("name", "") for p in (d.get("platforms") or [])]

        result["deals"].append({
            "shop": shop.get("name", ""),
            "price": _fmt_price(price),
            "regular": _fmt_price(regular),
            "cut": d.get("cut", 0),
            "drm": ", ".join(drm_list) if drm_list else "",
            "platforms": ", ".join(platforms) if platforms else "",
            "url": d.get("url", ""),
            "updated": str(d.get("timestamp", ""))[:10],
        })

    return result


def _parse_history(item: dict) -> dict:
    """解析 /games/historylow/v1 的单个游戏史低数据"""
    result = {"id": item.get("id", ""), "low": None}

    low = item.get("low")
    if low:
        shop = low.get("shop", {})
        result["low"] = {
            "shop": shop.get("name", ""),
            "price": _fmt_price(low.get("price")),
            "regular": _fmt_price(low.get("regular")),
            "cut": low.get("cut", 0),
            "date": str(low.get("timestamp", ""))[:10],
        }

    return result


def _fmt_price(p: dict | None) -> str:
    """格式化价格 →  'USD 29.95'"""
    if not p:
        return "N/A"
    return f"{p.get('currency', '')} {p.get('amount', '?')}"
