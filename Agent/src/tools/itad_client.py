"""
IsThereAnyDeal API 客户端 (v2 — 2026-06 更新)

Steam + GOG + Epic + 20+ 商店聚合折扣数据。
免费申请 Key: https://isthereanydeal.com/apps/

端点（2026年新版）:
  GET  /games/search/v1     — 搜索游戏 → 获取游戏 ID
  POST /games/prices/v3     — 当前各商店价格 + 折扣
  POST /games/historylow/v1 — 历史最低价

注：使用 curl 子进程而非 Python HTTP 库，因为 Python 的 SSL 层
在此网络下到 ITAD 延迟 64 秒，curl 只需 1.8 秒。
"""

import json
import logging
import os
import subprocess
import time
import urllib.parse

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


def _curl_request(method: str, endpoint: str, params: dict = None, body: list = None) -> dict | list | None:
    """通过 curl 子进程发 HTTP 请求（绕过 Python SSL 层）"""
    if not _api_key():
        logger.warning("ITAD_API_KEY 未设置")
        return None

    url = f"{BASE_URL}{endpoint}"
    if params is None:
        params = {}
    params["key"] = _api_key()
    qs = urllib.parse.urlencode(params)
    url = f"{url}?{qs}"

    cmd = [
        "curl", "-s", "--max-time", "15",
        "-H", "User-Agent: Gamebti/1.0",
        "-H", "Accept: application/json",
    ]
    if method == "POST":
        cmd += ["-X", "POST", "-H", "Content-Type: application/json"]
        if body:
            cmd += ["-d", json.dumps(body, ensure_ascii=False)]
    cmd.append(url)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            logger.warning(f"ITAD curl 失败 ({endpoint}): {result.stderr[:100]}")
            return None
        if not result.stdout.strip():
            return None
        data = json.loads(result.stdout)
        # HTTP 错误码在响应 JSON 中
        if isinstance(data, dict) and data.get("status_code", 200) >= 400:
            logger.warning(f"ITAD {endpoint}: {data.get('reason_phrase', 'error')}")
            return None
        return data
    except subprocess.TimeoutExpired:
        logger.warning(f"ITAD curl 超时 ({endpoint})")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"ITAD JSON 解析失败 ({endpoint}): {e}")
        return None
    except Exception as e:
        logger.warning(f"ITAD curl 异常 ({endpoint}): {e}")
        return None


# ========================
# 核心 API 函数
# ========================

def search_game(title: str, limit: int = 5) -> list[dict]:
    """搜索游戏 → 返回含 id/slug/title 的游戏列表"""
    cache_key = f"search_{title}"
    cached = _cached(cache_key)
    if cached:
        return cached

    data = _curl_request("GET", "/games/search/v1", {"title": title, "results": limit})
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
    """获取游戏当前在各商店的价格和折扣"""
    cache_key = f"price_{game_id}"
    cached = _cached(cache_key, PRICE_TTL)
    if cached:
        return cached

    data = _curl_request("POST", "/games/prices/v3", body=[game_id])
    if not data or not isinstance(data, list) or not data:
        return None

    result = _parse_price(data[0])
    _set_cache(cache_key, result)
    return result


def get_history(game_id: str, country: str = "CN") -> dict | None:
    """获取游戏历史最低价"""
    cache_key = f"history_{game_id}"
    cached = _cached(cache_key, CACHE_TTL)
    if cached:
        return cached

    data = _curl_request("POST", "/games/historylow/v1", body=[game_id])
    if not data or not isinstance(data, list) or not data:
        return None

    result = _parse_history(data[0])
    _set_cache(cache_key, result)
    return result


# ========================
# 便捷组合函数
# ========================

def query_game(query: str, country: str = "CN") -> dict | None:
    """一站式查询：搜索游戏 → 获取价格 + 史低"""
    if not _api_key():
        return None

    results = search_game(query)
    if not results:
        logger.info(f"ITAD 未找到: '{query}'")
        return None

    best = results[0]
    game_id = best["id"]

    price_data = get_price(game_id)
    history_data = get_history(game_id)

    return {
        "game": best["title"],
        "id": game_id,
        "slug": best["slug"],
        "price": price_data,
        "history": history_data,
    }


def get_deals(country: str = "CN", shop: str = "steam", limit: int = 10) -> list[dict]:
    """获取当前热门折扣列表（多游戏聚合）"""
    cache_key = f"deals_{country}_{shop}"
    cached = _cached(cache_key, PRICE_TTL)
    if cached:
        return cached

    popular = ["Elden Ring", "Cyberpunk 2077", "Baldur's Gate 3",
               "Red Dead Redemption 2", "Hogwarts Legacy"]
    all_deals = []

    for title in popular:
        games = search_game(title, 2)
        for g in games[:1]:
            price_data = get_price(g["id"])
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

    hl = item.get("historyLow") or {}
    result["history_low"] = {
        "all_time": _fmt_price(hl.get("all")),
        "year": _fmt_price(hl.get("y1")),
        "3months": _fmt_price(hl.get("m3")),
    }

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
