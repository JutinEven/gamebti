"""
Gamebti 游戏搜索工具 — 多源实时搜索 + 并行 + 缓存

数据源:
  1. Steam 公开 API (免费)
     - storesearch?specials=1 → 所有折扣游戏 (稳定!)
     - storesearch → 搜索特定游戏
     - appdetails → 价格/简介/发售日
  2. CheapShark API (免费, 无需 Key)
     - /deals → 多平台折扣聚合 (Steam/Epic/GOG 等)
  3. DuckDuckGo 网页搜索
     - 攻略/评测/新闻/百科

优化:
  - 并行搜索 (ThreadPoolExecutor) — 速度快 3x
  - 5分钟缓存 — 防限流
  - 中英文双搜
  - 30+ 游戏昵称映射
"""

import json
import logging
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain.tools import tool
from ddgs import DDGS

logger = logging.getLogger(__name__)

# ========================
# 配置
# ========================

MAX_WEB = 6
STEAM_TTL = 300       # Steam 缓存5分钟
DEALS_TTL = 600       # 折扣缓存10分钟
TIMEOUT = 10
DDG_RETRIES = 2
NICKNAME_MAP: dict[str, str] = {
    "老头环": "Elden Ring", "大表哥": "Red Dead Redemption 2",
    "大表哥2": "Red Dead Redemption 2", "给他爱": "GTA V",
    "给他爱5": "Grand Theft Auto V", "猛汉": "Monster Hunter",
    "猛汉王": "Monster Hunter World", "怪猎荒野": "Monster Hunter Wilds",
    "怪猎世界": "Monster Hunter World", "怪猎崛起": "Monster Hunter Rise",
    "野炊": "The Legend of Zelda: Breath of the Wild",
    "王泪": "The Legend of Zelda: Tears of the Kingdom",
    "魂3": "Dark Souls III", "只狼": "Sekiro: Shadows Die Twice",
    "鬼泣5": "Devil May Cry 5", "巫师3": "The Witcher 3: Wild Hunt",
    "赛博朋克": "Cyberpunk 2077", "原神": "Genshin Impact",
    "崩铁": "Honkai: Star Rail", "黑神话": "Black Myth: Wukong",
    "丝之歌": "Hollow Knight: Silksong", "空洞骑士": "Hollow Knight",
    "星际战甲": "Warframe", "命运2": "Destiny 2",
    "彩六": "Rainbow Six Siege", "APEX": "Apex Legends",
    "瓦罗": "VALORANT", "LOL": "League of Legends",
    "战神": "God of War", "地平线": "Horizon",
    "美末": "The Last of Us", "P5": "Persona 5",
    "如龙": "Yakuza", "生化": "Resident Evil",
    "FF": "Final Fantasy",
}
DISCOUNT_KW = ["折扣", "打折", "优惠", "促销", "特惠", "史低",
               "降价", "discount", "sale", "榜单", "排行"]
PRICE_KW = ["价格", "多少钱", "price", "售价"]

# ========================
# 缓存
# ========================
_cache: dict[str, tuple[float, any]] = {}

def _cached_get(key: str, ttl: int, factory):
    now = time.time()
    if key in _cache:
        ts, val = _cache[key]
        if now - ts < ttl:
            return val
    result = factory()
    if result:
        _cache[key] = (now, result)
    return result

# ========================
# HTTP
# ========================
def _fetch(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Gamebti/1.0")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.debug(f"HTTP({url[:50]}): {e}")
        return None

# ========================
# 数据源 1: CheapShark (免费, 多平台折扣聚合)
# ========================
def _cheapshark_deals() -> list[dict]:
    """CheapShark 折扣聚合 — 网络不通时静默失败"""
    def fetch():
        try:
            data = _fetch(
                "https://www.cheapshark.com/api/1.0/deals"
                "?storeID=1,25,7,13&sortBy=Deal%20Rating&pageSize=10"
            )
            if not data:
                return []
            results = []
            for d in data[:10]:
                results.append({
                    "name": d.get("title", ""),
                    "sale_price": f"${d.get('salePrice', '0')}",
                    "normal_price": f"${d.get('normalPrice', '0')}",
                    "discount_percent": round(float(d.get("savings", 0))),
                    "rating": d.get("dealRating", ""),
                    "url": f"https://www.cheapshark.com/redirect?dealID={d.get('dealID')}",
                })
            return results
        except Exception:
            return []  # CheapShark 不可用时静默失败，不影响其他数据源
    return _cached_get("cheapshark_deals", DEALS_TTL, fetch)

# ========================
# 数据源 2: Steam API
# ========================
def _steam_specials() -> list[dict]:
    """Steam 折扣游戏 — featuredcategories 包含完整价格，storesearch 兜底"""
    def fetch():
        # 主数据源: featuredcategories (含完整价格/折扣信息)
        data = _fetch(
            "https://store.steampowered.com/api/featuredcategories?cc=cn&l=zh"
        )
        items = []
        if data:
            items = data.get("specials", {}).get("items", [])

        if not items:
            # 备用: storesearch?specials (不含折扣信息，但能证实有折扣)
            logger.info("featuredcategories 为空，尝试 storesearch...")
            data2 = _fetch(
                "https://store.steampowered.com/api/storesearch/"
                "?specials=1&cc=cn&l=zh&max=15"
            )
            items = (data2 or {}).get("items", [])

        results = []
        for item in items[:15]:
            discount = item.get("discount_percent", 0)
            price = item.get("final_price", 0)
            original = item.get("original_price", 0)
            # storesearch 返回的 items 没有价格字段，跳过
            if discount <= 0 and not price:
                continue
            results.append({
                "name": item.get("name", ""),
                "discount_percent": discount or 0,
                "final_price": f"¥{price / 100:.2f}" if price else "N/A",
                "original_price": f"¥{original / 100:.2f}" if original else "N/A",
                "url": f"https://store.steampowered.com/app/{item.get('id')}",
            })
            if len(results) >= 10:
                break
        return results
    return _cached_get("steam_specials", STEAM_TTL, fetch)


def _search_steam_game(name: str) -> dict | None:
    """搜索特定游戏"""
    data = _fetch(
        "https://store.steampowered.com/api/storesearch/"
        f"?term={urllib.parse.quote(name)}&l=zh&cc=cn"
    )
    if not data or not data.get("items"):
        return None
    app_id = data["items"][0].get("id")
    if not app_id:
        return None
    detail = _fetch(
        f"https://store.steampowered.com/api/appdetails/"
        f"?appids={app_id}&cc=cn&l=zh"
    )
    if not detail:
        return None
    g = detail.get(str(app_id), {}).get("data", {})
    if not g:
        return None
    p = g.get("price_overview", {})
    return {
        "name": g.get("name", ""),
        "final_price": p.get("final_formatted", "免费"),
        "original_price": p.get("initial_formatted", ""),
        "discount_percent": p.get("discount_percent", 0),
        "description": str(g.get("short_description", ""))[:200],
        "release_date": g.get("release_date", {}).get("date", ""),
        "url": f"https://store.steampowered.com/app/{app_id}",
    }

# ========================
# 数据源 3: DuckDuckGo 网页搜索
# ========================
def _search_web(query: str) -> list[dict]:
    """
    DuckDuckGo 搜索。

    策略：
    1. 核心搜索：用原始查询
    2. 如命中二游 → 追加 Bilibili 定向搜索
    3. 合并去重
    """
    results = []
    seen_urls = set()

    # 第一轮：核心搜索
    for r in _ddg_search(query):
        url = r.get("href", "")
        if url not in seen_urls:
            seen_urls.add(url)
            results.append({
                "title": r.get("title", ""),
                "url": url,
                "snippet": (r.get("body") or "")[:250],
                "source": _classify_source(url),
            })

    # 第二轮：二游 Bilibili 官方号定向搜索
    bili_uid = _get_bilibili_uid(query)
    if bili_uid:
        bili_query = f"{query} site:bilibili.com"
        for r in _ddg_search(bili_query, max_results=4):
            url = r.get("href", "")
            if url not in seen_urls:
                seen_urls.add(url)
                results.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": (r.get("body") or "")[:250],
                    "source": "T1-Bilibili官方号" if "space.bilibili.com" in url else _classify_source(url),
                })

    return _rank_results(results)


def _ddg_search(query: str, max_results: int = MAX_WEB) -> list:
    """底层 DDG 搜索，带重试"""
    for attempt in range(DDG_RETRIES + 1):
        try:
            ddg = DDGS()
            results = list(ddg.text(query, max_results=max_results))
            if results:
                return results
        except Exception as e:
            if attempt < DDG_RETRIES:
                time.sleep(0.5 * (attempt + 1))
    return []


def _get_bilibili_uid(query: str) -> str | None:
    """获取游戏的 Bilibili 官方号 UID 和空间链接"""
    q = query.lower()
    mapping = {
        "原神": ("401742377", "space.bilibili.com/401742377"),
        "genshin": ("401742377", "space.bilibili.com/401742377"),
        "星穹铁道": ("1340190821", "space.bilibili.com/1340190821"),
        "崩坏": ("1340190821", "space.bilibili.com/1340190821"),
        "honkai": ("1340190821", "space.bilibili.com/1340190821"),
        "绝区零": ("1636375920", "space.bilibili.com/1636375920"),
        "zzz": ("1636375920", "space.bilibili.com/1636375920"),
        "鸣潮": ("354136791", "space.bilibili.com/354136791"),
        "wuthering": ("354136791", "space.bilibili.com/354136791"),
        "明日方舟": ("161775301", "space.bilibili.com/161775301"),
        "arknights": ("161775301", "space.bilibili.com/161775301"),
        "崩坏3": ("27534330", "space.bilibili.com/27534330"),
        "战双": ("10165841", "space.bilibili.com/10165841"),
        "蔚蓝档案": ("16535831", "space.bilibili.com/16535831"),
        "碧蓝航线": ("8352461", "space.bilibili.com/8352461"),
        "少女前线": ("1523727", "space.bilibili.com/1523727"),
        "尘白禁区": ("3493095719732591", "space.bilibili.com/3493095719732591"),
        "无期迷途": ("1861995594", "space.bilibili.com/1861995594"),
    }
    for game, (uid, space_url) in mapping.items():
        if game in q:
            return uid
    return None


def _get_bilibili_space_url(query: str) -> str | None:
    """获取游戏 Bilibili 官方号空间链接"""
    q = query.lower()
    mapping = {
        "原神": "https://space.bilibili.com/401742377/dynamic",
        "genshin": "https://space.bilibili.com/401742377/dynamic",
        "星穹铁道": "https://space.bilibili.com/1340190821/dynamic",
        "崩坏": "https://space.bilibili.com/1340190821/dynamic",
        "honkai": "https://space.bilibili.com/1340190821/dynamic",
        "绝区零": "https://space.bilibili.com/1636375920/dynamic",
        "zzz": "https://space.bilibili.com/1636375920/dynamic",
        "鸣潮": "https://space.bilibili.com/354136791/dynamic",
        "wuthering": "https://space.bilibili.com/354136791/dynamic",
        "明日方舟": "https://space.bilibili.com/161775301/dynamic",
        "arknights": "https://space.bilibili.com/161775301/dynamic",
        "崩坏3": "https://space.bilibili.com/27534330/dynamic",
        "战双": "https://space.bilibili.com/10165841/dynamic",
        "蔚蓝档案": "https://space.bilibili.com/16535831/dynamic",
        "碧蓝航线": "https://space.bilibili.com/8352461/dynamic",
        "少女前线": "https://space.bilibili.com/1523727/dynamic",
        "尘白禁区": "https://space.bilibili.com/3493095719732591/dynamic",
        "无期迷途": "https://space.bilibili.com/1861995594/dynamic",
    }
    for game, url in mapping.items():
        if game in q:
            return url
    return None

    for attempt in range(DDG_RETRIES + 1):
        try:
            ddg = DDGS()
            results = []
            for r in ddg.text(search_q, max_results=MAX_WEB):
                url = r.get("href", "")
                results.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": (r.get("body") or "")[:250],
                    "source": _classify_source(url),
                    "freshness": _check_freshness(r.get("body", "")),
                })
            if results:
                return _rank_results(results)
        except Exception as e:
            if attempt < DDG_RETRIES:
                time.sleep(0.5 * (attempt + 1))
    return []


def _get_official_sources(query: str) -> list[str]:
    """根据查询内容返回官方信息源，二游优先 Bilibili 官方号"""
    sources = []
    q = query.lower()

    # Bilibili 官方号映射（二次元手游核心信源）
    bilibili_official: dict[str, str] = {
        "原神": "space.bilibili.com/401742377",
        "genshin": "space.bilibili.com/401742377",
        "崩坏": "space.bilibili.com/1340190821",
        "星穹铁道": "space.bilibili.com/1340190821",
        "honkai": "space.bilibili.com/1340190821",
        "绝区零": "space.bilibili.com/1636375920",
        "zzz": "space.bilibili.com/1636375920",
        "鸣潮": "space.bilibili.com/354136791",
        "wuthering": "space.bilibili.com/354136791",
        "明日方舟": "space.bilibili.com/161775301",
        "arknights": "space.bilibili.com/161775301",
        "崩坏3": "space.bilibili.com/27534330",
        "战双": "space.bilibili.com/10165841",
        "蔚蓝档案": "space.bilibili.com/16535831",
        "碧蓝航线": "space.bilibili.com/8352461",
        "少女前线": "space.bilibili.com/1523727",
        "重返未来1999": "space.bilibili.com/3493130552012982",
        "无期迷途": "space.bilibili.com/1861995594",
        "白夜极光": "space.bilibili.com/69991609",
        "尘白禁区": "space.bilibili.com/3493095719732591",
    }

    for game, bili_uid in bilibili_official.items():
        if game in q:
            sources.append(f"site:{bili_uid}")
            break  # 只加最匹配的那个

    # 米哈游系列
    if any(k in q for k in ["原神", "genshin", "崩坏", "honkai", "星穹铁道", "绝区零", "zzz"]):
        sources.extend(["site:genshin.hoyoverse.com", "site:hsr.hoyoverse.com",
                        "site:zenless.hoyoverse.com", "site:bbs.mihoyo.com"])

    # 腾讯/网易等
    if any(k in q for k in ["王者荣耀", "和平精英", "lol", "英雄联盟"]):
        sources.extend(["site:pvp.qq.com", "site:lol.qq.com"])

    # 通用：Steam + Wikipedia
    sources.extend(["site:steampowered.com", "site:wikipedia.org"])

    return sources[:3]


def _classify_source(url: str) -> str:
    """根据 URL 对来源分级。Bilibili 官方号 = T1"""
    u = url.lower()
    # T1: 官方渠道
    if any(d in u for d in ["hoyoverse.com", "mihoyo.com", "steampowered.com",
                              "playstation.com", "xbox.com", "nintendo.com",
                              "epicgames.com", "wikipedia.org"]):
        return "T1-官方/权威"
    # Bilibili 官方号 = T1（游戏厂商直接发布）
    if "space.bilibili.com" in u:
        return "T1-Bilibili官方号"
    if any(d in u for d in ["ign.com", "gamespot.com", "pcgamer.com",
                              "nga.cn", "gamersky.com"]):
        return "T2-知名媒体/社区"
    if "bilibili.com" in u:
        return "T2-Bilibili"
    return "T3-一般来源"


def _check_freshness(text: str) -> str:
    """从文本中检测时间信息判断新鲜度，标注过期信息"""
    import re
    from datetime import datetime

    # 匹配日期格式: 2024年6月 / 2024-06 / 2024/06
    m = re.search(r'(\d{4})[年/-](\d{1,2})[月/-]?(\d{1,2})?', text)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        now = datetime.now()
        if year < now.year - 1:
            return f"过期({year}年)"
        if year == now.year and month < now.month - 2:
            return f"较旧({year}年{month}月)"
        return f"较新({year}年{month}月)"

    if any(w in text for w in ["今天", "昨日", "本周", "最新", "刚刚", "updated"]):
        return "近期"
    return "未知时效"


def _rank_results(results: list[dict]) -> list[dict]:
    """按来源可信度排序：T1 > T2 > T3"""
    order = {"T1-官方/权威": 0, "T2-知名媒体/社区": 1, "T3-一般来源": 2}
    return sorted(results, key=lambda r: order.get(r.get("source", "T3"), 2))

# ========================
# 昵称解析
# ========================
def _resolve_name(q: str) -> tuple[str | None, str | None]:
    qs = q.strip()
    for nick, official in NICKNAME_MAP.items():
        if nick in qs:
            return (nick, official)
    # 直接提取
    name = qs
    for w in ["查询", "搜索", "帮我查", "请问", "今天", "昨天",
              "本周", "热门", "最新", "推荐"]:
        name = name.replace(w, "")
    for w in ["的价格", "多少钱", "价格", "打折吗", "折扣", "优惠",
              "促销", "榜单", "排行", "怎么样", "好玩吗", "值得买吗"]:
        name = name.replace(w, "")
    name = name.strip()
    return (name, None) if 2 < len(name) < 40 else (None, None)

# ========================
# 意图检测
# ========================
def _has(q: str, keywords: list[str]) -> bool:
    return any(k in q.lower() for k in keywords)

# ========================
# 数据源 4: IsThereAnyDeal (主力)
# ========================

def _search_itad(query: str) -> dict | None:
    """IsThereAnyDeal API — 跨商店聚合折扣数据（主力数据源）"""
    try:
        from tools.itad_client import query_game as itad_query, get_deals as itad_deals
    except ImportError:
        return None

    has_discount = _has(query, DISCOUNT_KW)

    # 单款游戏查询（始终执行）
    game_info = itad_query(query, "CN")

    # 折扣榜单（仅涉及优惠类关键词时触发）
    deals = None
    if has_discount:
        deals = itad_deals("CN", "steam", 10)

    if not deals and not game_info:
        return None

    return {
        "deals": deals,
        "game": game_info,
    }


# ========================
# 主工具 — 并行搜索所有数据源
# ========================
@tool
def game_search(query: str) -> str:
    """
    搜索游戏信息。并行查询 ITAD + Steam + CheapShark + DuckDuckGo。
    ITAD 作为主力数据源（跨商店聚合，稳定可靠）。
    返回结构: {success, itad, steam_specials, cheapshark_deals, steam_info, web_results, note}
    """
    logger.info(f"🔍 '{query[:60]}'")

    cn, en = _resolve_name(query)
    has_discount = _has(query, DISCOUNT_KW)
    has_price = _has(query, PRICE_KW) or has_discount

    result = {
        "query": query, "success": False,
        "itad": None,
        "steam_specials": None, "cheapshark_deals": None,
        "steam_info": None, "web_results": [], "note": "",
    }

    # 并行执行所有搜索
    futures = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        # Steam 折扣 + 价格（主力：DDG + Steam API）
        if has_discount:
            futures["steam_specials"] = pool.submit(_steam_specials)
            futures["cheapshark"] = pool.submit(_cheapshark_deals)

        # 网页搜索（通用）
        sq = en or query
        futures["web"] = pool.submit(_search_web, sq)

        # 价格查询：DDG 精准搜 Steam 商店
        if has_price:
            price_q = f"{query} site:store.steampowered.com"
            futures["web_price"] = pool.submit(_search_web, price_q)

        # Steam 单款查价
        if has_price and (cn or en):
            futures["steam_info_cn"] = pool.submit(_search_steam_game, cn or query)
            if en and en != cn:
                futures["steam_info_en"] = pool.submit(_search_steam_game, en)

        # ITAD 跨商店聚合（主力价格数据源）
        if has_price:
            futures["itad"] = pool.submit(_search_itad, query)

        # 收集结果
        for key, fut in futures.items():
            try:
                val = fut.result(timeout=TIMEOUT + 3)
            except Exception:
                val = None

            if key == "steam_specials" and val:
                result["steam_specials"] = val; result["success"] = True
            elif key == "cheapshark" and val:
                result["cheapshark_deals"] = val; result["success"] = True
            elif key == "itad" and val:
                result["itad"] = val; result["success"] = True
            elif key in ("web", "web_price") and val:
                # 合并网页结果，去重
                existing = {r.get("url","") for r in result["web_results"]}
                for r in val:
                    if r.get("url","") not in existing:
                        result["web_results"].append(r)
                        existing.add(r.get("url",""))
                result["success"] = True
            elif key in ("steam_info_cn", "steam_info_en") and val:
                if not result["steam_info"]:
                    result["steam_info"] = val; result["success"] = True

    if not result["success"]:
        result["note"] = "所有渠道均无数据。"

    return json.dumps(result, ensure_ascii=False, indent=2)
