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

logger = logging.getLogger(__name__)

# ========================
# 配置
# ========================

MAX_WEB = 5           # Bing 快速，可以多取几条
STEAM_TTL = 300
DEALS_TTL = 600
TIMEOUT = 8
SEARCH_TIMEOUT = 8    # Bing 搜索超时

# ========================
# 任务1: TRUST_TIERS — 信源等级（T0 > T1 > T2 > T3）
# ========================
TRUST_TIERS = {
    "steampowered.com":     "T0_OFFICIAL",
    "store.steampowered":   "T0_OFFICIAL",
    "playstation.com":      "T0_OFFICIAL",
    "xbox.com":             "T0_OFFICIAL",
    "nintendo.com":         "T0_OFFICIAL",
    "epicgames.com":        "T0_OFFICIAL",
    "gog.com":              "T0_OFFICIAL",
    "humblebundle.com":     "T0_OFFICIAL",
    "fromsoftware":         "T0_OFFICIAL",
    "capcom.com":           "T0_OFFICIAL",
    "bandainamco":          "T0_OFFICIAL",
    "square-enix":          "T0_OFFICIAL",
    "ubisoft.com":          "T0_OFFICIAL",
    "ea.com":               "T0_OFFICIAL",
    "activision":           "T0_OFFICIAL",
    "blizzard.com":         "T0_OFFICIAL",
    "bethesda":             "T0_OFFICIAL",
    "rockstargames":        "T0_OFFICIAL",
    "cdprojektred":         "T0_OFFICIAL",
    "larian.com":           "T0_OFFICIAL",
    "pocketpair":           "T0_OFFICIAL",
    "gamescience":          "T0_OFFICIAL",
    "hoyoverse.com":        "T0_OFFICIAL",
    "mihoyo.com":           "T0_OFFICIAL",
    "kurogames.com":        "T0_OFFICIAL",
    "hypergryph.com":       "T0_OFFICIAL",
    "igdb.com":             "T1_DATABASE",
    "rawg.io":              "T1_DATABASE",
    "metacritic.com":       "T1_DATABASE",
    "ign.com":              "T2_MEDIA",
    "gamespot.com":         "T2_MEDIA",
    "pcgamer.com":          "T2_MEDIA",
    "eurogamer.net":        "T2_MEDIA",
    "gamersky.com":         "T2_MEDIA",
    "3dmgame.com":          "T2_MEDIA",
    "reddit.com":           "T3_COMMUNITY",
    "steamcommunity.com":   "T3_COMMUNITY",
}
TRUST_ORDER = {"T0_OFFICIAL": 0, "T1_DATABASE": 1, "T2_MEDIA": 2, "T3_COMMUNITY": 3}

# ========================
# 游戏别名映射（中文→英文官方名）
# ========================
NICKNAME_MAP: dict[str, str] = {
    # 怪物猎人系列
    "怪物猎人荒野": "Monster Hunter Wilds", "怪猎荒野": "Monster Hunter Wilds",
    "怪物猎人世界": "Monster Hunter World", "怪猎世界": "Monster Hunter World",
    "怪物猎人崛起": "Monster Hunter Rise", "怪猎崛起": "Monster Hunter Rise",
    "猛汉王": "Monster Hunter World", "猛汉": "Monster Hunter",
    # 艾尔登法环
    "老头环": "Elden Ring", "艾尔登法环": "Elden Ring", "法环": "Elden Ring",
    # 博德之门
    "博德3": "Baldur's Gate 3", "博德之门3": "Baldur's Gate 3",
    "博德之门": "Baldur's Gate", "bg3": "Baldur's Gate 3",
    # Rockstar
    "大表哥": "Red Dead Redemption 2", "大表哥2": "Red Dead Redemption 2",
    "给他爱": "GTA V", "给他爱5": "Grand Theft Auto V", "gta5": "Grand Theft Auto V",
    # 热门单机
    "黑神话": "Black Myth: Wukong", "黑神话悟空": "Black Myth: Wukong",
    "赛博朋克": "Cyberpunk 2077", "2077": "Cyberpunk 2077",
    "只狼": "Sekiro: Shadows Die Twice",
    "鬼泣5": "Devil May Cry 5", "巫师3": "The Witcher 3: Wild Hunt",
    "魂3": "Dark Souls III", "空洞骑士": "Hollow Knight",
    "丝之歌": "Hollow Knight: Silksong",
    "星际战甲": "Warframe", "命运2": "Destiny 2",
    "战神": "God of War", "地平线": "Horizon",
    "美末": "The Last of Us", "P5": "Persona 5",
    "如龙": "Yakuza", "生化": "Resident Evil", "FF": "Final Fantasy",
    # 热门网游/手游
    "原神": "Genshin Impact", "崩铁": "Honkai: Star Rail",
    "星穹铁道": "Honkai: Star Rail", "绝区零": "Zenless Zone Zero",
    "鸣潮": "Wuthering Waves", "明日方舟": "Arknights",
    "幻兽帕鲁": "Palworld",
    "彩六": "Rainbow Six Siege", "APEX": "Apex Legends",
    "瓦罗": "VALORANT", "LOL": "League of Legends",
    "野炊": "The Legend of Zelda: Breath of the Wild",
    "王泪": "The Legend of Zelda: Tears of the Kingdom",
    # 任天堂
    "塞尔达": "The Legend of Zelda", "宝可梦": "Pokemon",
    # 其他
    "星露谷": "Stardew Valley", "星露谷物语": "Stardew Valley",
    "荒野之息": "Breath of the Wild", "王国之泪": "Tears of the Kingdom",
    # Valve + 新兴游戏
    "死锁": "Deadlock", "deadlock": "Deadlock", "DeadLock": "Deadlock",
    # 杀戮尖塔
    "杀戮尖塔2": "Slay the Spire 2", "杀戮尖塔": "Slay the Spire",
    "尖塔": "Slay the Spire",
}
DISCOUNT_KW = ["折扣", "打折", "优惠", "促销", "特惠", "史低",
               "降价", "discount", "sale", "榜单", "排行"]
PRICE_KW = ["价格", "多少钱", "price", "售价", "发售", "上线了", "出了吗", "上架"]

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
    """搜索特定游戏，返回 Steam 商店页完整数据"""
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
    release = g.get("release_date", {})
    # 判断发售状态
    is_released = not release.get("coming_soon", False)
    return {
        "name": g.get("name", ""),
        "steam_appid": app_id,
        "final_price": p.get("final_formatted", "免费" if g.get("is_free") else "N/A"),
        "original_price": p.get("initial_formatted", ""),
        "discount_percent": p.get("discount_percent", 0),
        "description": str(g.get("short_description", ""))[:300],
        "release_date": release.get("date", ""),
        "is_released": is_released,
        "coming_soon": release.get("coming_soon", False),
        "developers": g.get("developers", [])[:3],
        "publishers": g.get("publishers", [])[:3],
        "platforms": {k: v for k, v in [
            ("windows", g.get("platforms", {}).get("windows", False)),
            ("mac", g.get("platforms", {}).get("mac", False)),
            ("linux", g.get("platforms", {}).get("linux", False)),
        ] if v},
        "genres": [genre.get("description", "") for genre in g.get("genres", [])[:5]],
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


def _bing_search(query: str, max_results: int = MAX_WEB) -> list:
    """Bing 搜索（0.1秒 vs DDGS 30秒）。返回 [{title, href, body}]"""
    import re
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://www.bing.com/search?q={encoded}&count={max_results}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        results = []
        # 解析 Bing 搜索结果（提取标题、链接、摘要）
        # Bing 的搜索结果在 <li class="b_algo"> 中
        blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
        for block in blocks[:max_results]:
            title_m = re.search(r'<h2[^>]*><a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
            snippet_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            if title_m:
                href = title_m.group(1)
                title = re.sub(r'<[^>]+>', '', title_m.group(2)).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet_m.group(1) if snippet_m else '').strip()
                results.append({"title": title, "href": href, "body": snippet[:300]})
        return results
    except Exception as e:
        logger.debug(f"Bing search failed: {e}")
        return []

# 保留 DDGS 作为备份（Bing 失败时降级）
_ddg_search = _bing_search


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
    # AAA 厂商官方号
    if any(k in q for k in ["怪猎", "怪物猎人", "monster hunter", "mhw", "capcom"]):
        return "706772479"  # Capcom 官方
    if any(k in q for k in ["艾尔登法环", "elden ring", "黑暗之魂", "fromsoftware", "只狼"]):
        return "342022727"  # FromSoftware 官方

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


def _classify_source(url: str) -> str:
    """按 TRUST_TIERS 分级：T0官方>T1数据库>T2媒体>T3社区"""
    tier = _get_trust_tier(url)
    u = url.lower()
    if "space.bilibili.com" in u and "/video/" not in u:
        tier = "T0_OFFICIAL"  # B站官方号空间 = T0
    return tier


def _rank_results(results: list[dict]) -> list[dict]:
    """按 TRUST_TIERS 排序：T0 > T1 > T2 > T3。有 T0/T1 时丢弃 T3"""
    sorted_results = sorted(results, key=lambda r: TRUST_ORDER.get(
        r.get("source", "T3_COMMUNITY"), 3))

    # 有 T0/T1 结果时丢弃 T3 社区源
    high_trust = [r for r in sorted_results
                  if r.get("source", "").startswith(("T0", "T1"))]
    if len(high_trust) >= 1:
        return [r for r in sorted_results
                if not r.get("source", "").startswith("T3")]
    return sorted_results


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
    """按来源可信度排序：T1 > T2 > T3。有T1/T2时完全丢弃T3。"""
    order = {"T1-官方/权威": 0, "T1-Bilibili官方号": 1,
             "T2-知名媒体/社区": 2, "T2-Bilibili": 3,
             "T3-自媒体/论坛": 4, "T3-一般来源": 5}
    sorted_results = sorted(results, key=lambda r: order.get(r.get("source", "T3"), 5))

    # 有 T1/T2 结果时，完全丢弃 T3（自媒体/营销号/论坛不可信）
    t1_t2 = [r for r in sorted_results if r.get("source", "").startswith(("T1", "T2"))]
    t3 = [r for r in sorted_results if r.get("source", "").startswith("T3")]
    if len(t1_t2) >= 1:
        return t1_t2  # 有官方/媒体源就完全不用 T3
    return t3[:2]  # 实在没数据时最多保留 2 条 T3 兜底

# ========================
# 任务3: 时间衰减 — 发售类查询丢弃90天以上结果
# ========================
RELEASE_KW = ["发售", "上线", "出了吗", "上架", "release", "launch", "available", "coming soon"]

def _check_time_decay(snippet: str, is_release_query: bool = False) -> tuple[bool, str]:
    """检查搜索结果时效性。发售查询：>90天直接丢弃。"""
    import re
    from datetime import datetime, timedelta

    m = re.search(r'(\d{4})[年/-](\d{1,2})[月/-]?(\d{1,2})?', snippet)
    if not m:
        return (False, "未知时效")

    year, month = int(m.group(1)), int(m.group(2))
    try:
        day = int(m.group(3)) if m.group(3) else 1
        d = datetime(year, month, day)
    except ValueError:
        return (False, "未知时效")

    age = (datetime.now() - d).days
    cutoff = 90 if is_release_query else 180

    if age > cutoff:
        return (True, f"过期丢弃({age}天前)") if is_release_query else (True, f"降权({age}天前)")
    if age > 60:
        return (False, f"较旧({age}天前)")
    return (False, f"近期({age}天前)")

# ========================
# 任务4: 公告型新闻识别 — T0事实锁定时忽略旧公告
# ========================
ANNOUNCEMENT_KW = [
    "announced", "revealed", "trailer", "preview", "teaser",
    "TGS", "gamescom", "E3", "showcase", "direct", "state of play",
    "公布", "预告", "宣传片", "发布会", "演示", "首曝", "曝光",
]

def _is_announcement(text: str) -> bool:
    """判断内容是否为公告/预告型（非事实型）"""
    return any(kw.lower() in text.lower() for kw in ANNOUNCEMENT_KW)

# ========================
# 任务2: search_release_truth — 发售状态专项搜索
# ========================
RELEASE_CONFIRMED_KW = [
    "available now", "released", "out now", "launch", "已发售",
    "正式发售", "已上线", "现已推出", "现已登陆", "now available",
    "release date", "发售日期", "发售日",
]
RELEASE_PENDING_KW = [
    "coming soon", "wishlist now", "planned release", "to be released",
    "即将推出", "即将发售", "预定", "预购", "尚未发售",
    "未公布", "TBA", "TBD", "待定",
]

def search_release_truth(game_name: str) -> dict:
    """
    专项查询游戏发售状态。返回 {released, confidence, evidence, sources}

    优先级: T0官方源 > T1数据库 > T2媒体。T0锁定后旧新闻不可覆盖。
    """
    results = {
        "released": None,        # True/False/None(未知)
        "confidence": "low",
        "evidence": [],
        "sources": [],
        "release_date": None,
    }
    release_locked = False

    # Phase 1: 搜 T0 官方源
    t0_queries = [
        f"{game_name} Steam",
        f"{game_name} official release date",
        f"{game_name} site:steampowered.com",
    ]
    t0_results = []
    for q in t0_queries:
        for r in _ddg_search(q, max_results=3):
            url = r.get("href", "")
            tier = _get_trust_tier(url)
            if tier == "T0_OFFICIAL":
                expired, label = _check_time_decay(r.get("body", ""), is_release_query=True)
                if expired:
                    continue  # >90天直接丢弃
                r["_trust_tier"] = tier
                r["_time_label"] = label
                r["_is_announcement"] = _is_announcement(r.get("body", ""))
                t0_results.append(r)

    # Phase 2: 分析 T0 结果
    for r in t0_results:
        text = (r.get("title", "") + " " + r.get("body", ""))
        is_ann = r.get("_is_announcement", False)

        # 检查已发售关键词
        if any(kw.lower() in text.lower() for kw in RELEASE_CONFIRMED_KW):
            if not is_ann:  # 不是旧公告 → 可信
                results["released"] = True
                results["confidence"] = "high"
                results["evidence"].append(f"T0确认已发售: {r.get('title','')[:80]}")
                results["sources"].append(r.get("href", ""))
                release_locked = True
                # 提取发售日期
                import re
                dm = re.search(r'(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})', text)
                if dm:
                    results["release_date"] = f"{dm.group(1)}年{dm.group(2)}月{dm.group(3)}日"
                break  # T0 锁定，不再看其他

        # 检查未发售关键词
        if any(kw.lower() in text.lower() for kw in RELEASE_PENDING_KW):
            if is_ann:
                continue  # 公告型未发售 = 旧新闻，跳过
            # 真正未发售
            if not release_locked:
                results["released"] = False
                results["confidence"] = "medium"
                results["evidence"].append(f"T0确认未发售: {r.get('title','')[:80]}")

    # Phase 3: 如果 T0 未锁定，补充 T1+T2
    if not release_locked and not results["released"]:
        extra_queries = [game_name]
        for q in extra_queries:
            for r in _ddg_search(q, max_results=4):
                url = r.get("href", "")
                tier = _get_trust_tier(url)
                if tier.startswith("T0"):
                    continue  # 已处理
                text = (r.get("title", "") + " " + r.get("body", ""))
                if any(kw.lower() in text.lower() for kw in RELEASE_CONFIRMED_KW):
                    expired, _ = _check_time_decay(r.get("body", ""), is_release_query=True)
                    if expired:
                        continue
                    if not _is_announcement(text):
                        results["released"] = True
                        results["confidence"] = "medium" if tier.startswith("T1") else "low"
                        results["evidence"].append(f"{tier}确认已发售: {r.get('title','')[:80]}")
                        results["sources"].append(url)
                        break
            if results["released"]:
                break

    # Phase 4: ITAD 交叉验证 — 有价格 = 已发售
    if results["released"] is None or results["released"] is False:
        try:
            from tools.itad_client import search_game as itad_search
            itad_results = itad_search(game_name, 2)
            if itad_results:
                # ITAD 返回价格数据 → 游戏已发售
                results["released"] = True
                results["confidence"] = "high"
                results["evidence"].append(f"ITAD确认已发售（多商店有实时价格）: {itad_results[0].get('title','')}")
                results["sources"].append("https://isthereanydeal.com")
                release_locked = True
        except Exception:
            pass

    return results


def _get_trust_tier(url: str) -> str:
    """根据 URL 返回 TRUST_TIERS 等级"""
    u = url.lower()
    for domain, tier in TRUST_TIERS.items():
        if domain in u:
            return tier
    # 兜底
    if "bilibili.com" in u:
        return "T2_MEDIA" if "/video/" in u else "T1_DATABASE"
    if any(d in u for d in ["wikipedia.org", "zh.wikipedia.org"]):
        return "T1_DATABASE"
    return "T3_COMMUNITY"

# ========================
# 昵称解析
# ========================
def _resolve_name(q: str) -> tuple[str | None, str | None]:
    qs = q.strip()
    for nick, official in NICKNAME_MAP.items():
        if nick in qs:
            return (nick, official)

    # 先尝试提取英文游戏名（大写开头单词，如 Deadlock, Valorant）
    import re
    eng_matches = re.findall(r'\b([A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,})?)\b', qs)
    if eng_matches:
        # 过滤掉常见非游戏词
        skip_words = {"Steam", "Xbox", "PlayStation", "Nintendo", "Epic", "GOG", "ITAD", "IGN", "GameSpot", "Windows", "Linux", "MacOS", "Intel", "AMD", "Nvidia", "Bilibili", "YouTube", "Twitter"}
        for m in eng_matches:
            if m not in skip_words:
                return (m, m)  # 直接作为英文名

    # 中文名提取：剥离前缀和修饰词
    name = qs
    for w in ["查询", "搜索", "帮我查", "请问", "今天", "昨天",
              "本周", "热门", "最新", "推荐", "游戏名", "这个游戏",
              "这款游戏", "新上线", "新出的", "最近"]:
        name = name.replace(w, "")
    for w in ["的价格", "多少钱", "价格", "打折吗", "折扣", "优惠",
              "促销", "榜单", "排行", "怎么样", "好玩吗", "值得买吗",
              "Steam", "steam", "新上线", "上线了", "发售", "出了吗"]:
        name = name.replace(w, "")
    # 去除标点
    name = re.sub(r'[，,。．、！!？?：:；;]', '', name)
    name = name.strip()
    return (name, None) if 2 < len(name) < 40 else (None, None)

# ========================
# 意图检测
# ========================
def _has(q: str, keywords: list[str]) -> bool:
    return any(k in q.lower() for k in keywords)

# 推荐类关键词（"推荐解谜游戏"、"有什么好玩的"）
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
    发售类查询走 search_release_truth 专项通道。
    返回结构: {success, itad, steam_specials, cheapshark_deals, steam_info, web_results, note, release_truth}
    """
    logger.info(f"🔍 '{query[:60]}'")

    cn, en = _resolve_name(query)
    has_discount = _has(query, DISCOUNT_KW)
    has_price = _has(query, PRICE_KW) or has_discount
    has_game_name = bool(en or cn)  # 能解析出游戏名就搜

    # 任务5: 发售状态意图检测 → 走专项通道
    is_release_query = _has(query, RELEASE_KW)
    release_truth = None
    if is_release_query:
        release_name = en or cn or query
        release_truth = search_release_truth(release_name)
        logger.info(f"发售真相: released={release_truth['released']} conf={release_truth['confidence']}")

    result = {
        "query": query, "success": False,
        "itad": None,
        "steam_specials": None, "cheapshark_deals": None,
        "steam_info": None, "web_results": [], "note": "",
        "release_truth": release_truth,
    }

    # 并行执行所有搜索
    futures = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        # Steam 折扣 + 价格（主力：DDG + Steam API）
        if has_discount:
            futures["steam_specials"] = pool.submit(_steam_specials)
            futures["cheapshark"] = pool.submit(_cheapshark_deals)

        # 网页搜索（通用）— Bing 0.1秒，始终执行
        sq = en or query
        futures["web"] = pool.submit(_search_web, sq)

        # Steam 单款游戏搜索（有游戏名就查，不只看价格）
        if has_game_name:
            search_name = en or cn
            if search_name:
                futures["steam_info"] = pool.submit(_search_steam_game, search_name)

        # ITAD 跨商店聚合 — 有游戏名就搜，不只看价格关键词
        if has_price or has_game_name:
            itad_query_text = en or cn or query
            futures["itad"] = pool.submit(_search_itad, itad_query_text)

        # 收集结果 — 关键源优先，Web 搜索限时 5 秒
        FAST_TIMEOUT = 5   # Web 搜索限制 5 秒（网络受限时快速放弃）
        SLOW_TIMEOUT = 12  # ITAD/Steam/CheapShark 多等一会

        for key, fut in futures.items():
            t = FAST_TIMEOUT if key in ("web", "web_price") else SLOW_TIMEOUT
            try:
                val = fut.result(timeout=t)
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
