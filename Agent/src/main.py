"""
Gamebti Agent — 独立 FastAPI 服务
===================================
完全脱离 Coze 平台，基于 LangGraph + 免费 LLM + 公开 API。

启动方式:
  python src/main.py -m http -p 5000    # HTTP 服务
  python src/main.py -m flow -i "你好"   # 命令行单次对话
  python src/main.py -m agent           # 命令行交互

端点:
  POST /v1/chat/completions  — OpenAI 兼容接口 (前端使用)
  POST /run                  — 同步执行
  POST /stream_run           — SSE 流式执行
  POST /cancel/{run_id}      — 取消任务
  GET  /health               — 健康检查
"""

import argparse
import asyncio
import json
import logging
import os
import shutil
import sys
import time
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph.state import CompiledStateGraph

# 加载 .env 文件
load_dotenv()

# ---- 日志配置 ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("gamebti")

# ---- 常量 ----
TIMEOUT_SECONDS = 300  # 5 分钟超时


class GraphService:
    """Agent 图服务 — 管理编译后的 LangGraph Agent"""

    def __init__(self):
        self._graph: Optional[CompiledStateGraph] = None
        self.running_tasks: dict[str, asyncio.Task] = {}

    def _get_graph(self) -> CompiledStateGraph:
        """延迟加载 Agent Graph"""
        if self._graph is None:
            from agents.agent import build_agent
            logger.info("构建 Gamebti Agent...")
            self._graph = build_agent()
            logger.info("Agent 构建完成")
        return self._graph

    async def _invoke_graph(self, messages: list, session_id: str) -> dict:
        """
        核心执行：清除旧的搜索数据 → 注入新的 → 执行 → 提取回复

        关键：每次调用前从 LangGraph 状态中移除旧的 [实时搜索数据] SystemMessage，
        避免旧搜索数据累积污染对话上下文。
        """
        graph = self._get_graph()
        config = {"configurable": {"thread_id": session_id}}

        # 清除旧的搜索注入消息，保持对话记忆干净
        try:
            current = graph.get_state(config)
            if current and current.values:
                old_msgs = list(current.values.get("messages", []))
                cleaned = [
                    m for m in old_msgs
                    if not (isinstance(m, SystemMessage)
                            and "[实时搜索数据" in str(m.content))
                ]
                if len(cleaned) < len(old_msgs):
                    graph.update_state(config, {"messages": cleaned})
                    logger.debug(f"清理了 {len(old_msgs) - len(cleaned)} 条旧搜索数据")
        except Exception as e:
            logger.debug(f"清理旧搜索数据跳过: {e}")

        # 注入新消息并执行
        result = await graph.ainvoke({"messages": list(messages)}, config=config)
        reply = ""
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                reply = msg.content
                break
        return {"reply": reply, "result": result}

    async def run(self, payload: dict) -> dict:
        """简单文本执行（兼容旧版）"""
        message = payload.get("message", "")
        session_id = payload.get("session_id") or payload.get("conversation_id") or uuid.uuid4().hex
        run_id = uuid.uuid4().hex
        if not message:
            return {"error": "message 字段不能为空", "run_id": run_id}
        logger.info(f"Run: session={session_id[:8]}... '{message[:50]}'")
        try:
            result = await self._invoke_graph(
                [HumanMessage(content=message)], session_id
            )
            return {"reply": result["reply"], "session_id": session_id, "run_id": run_id}
        except asyncio.CancelledError:
            return {"error": "执行被取消", "run_id": run_id}

    async def run_messages(self, payload: dict) -> dict:
        """消息列表执行 — 支持 SystemMessage 搜索注入，不污染对话历史"""
        messages = payload.get("messages", [])
        session_id = payload.get("session_id") or uuid.uuid4().hex
        run_id = uuid.uuid4().hex
        if not messages:
            return {"error": "messages 不能为空", "run_id": run_id}
        logger.info(f"Run(msgs): session={session_id[:8]}...")
        try:
            result = await self._invoke_graph(messages, session_id)
            return {"reply": result["reply"], "session_id": session_id, "run_id": run_id}
        except asyncio.CancelledError:
            return {"error": "执行被取消", "run_id": run_id}

    async def stream_sse(self, payload: dict) -> AsyncGenerator[str, None]:
        """SSE 流式（兼容旧版）"""
        message = payload.get("message", "")
        session_id = payload.get("session_id") or payload.get("conversation_id") or uuid.uuid4().hex
        run_id = uuid.uuid4().hex
        if not message:
            yield _sse({"type": "error", "error": "message 不能为空"}); return
        async for chunk in self._stream_inner([HumanMessage(content=message)], session_id, run_id):
            yield chunk

    async def stream_sse_messages(self, payload: dict) -> AsyncGenerator[str, None]:
        """SSE 流式（消息列表版）"""
        messages = payload.get("messages", [])
        session_id = payload.get("session_id") or uuid.uuid4().hex
        run_id = uuid.uuid4().hex
        if not messages:
            yield _sse({"type": "error", "error": "messages 不能为空"}); return
        async for chunk in self._stream_inner(messages, session_id, run_id):
            yield chunk

    async def _stream_inner(self, messages: list, session_id: str, run_id: str) -> AsyncGenerator[str, None]:
        graph = self._get_graph()
        config = {"configurable": {"thread_id": session_id}}
        try:
            async for event in graph.astream_events(
                {"messages": list(messages)}, config=config, version="v2"
            ):
                kind = event.get("event", "")
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", {})
                    if hasattr(chunk, "content") and chunk.content:
                        yield _sse({"type": "content", "content": chunk.content})
                elif kind == "on_tool_start":
                    yield _sse({"type": "tool_start", "tool": event.get("name", "?")})
                elif kind == "on_tool_end":
                    yield _sse({"type": "tool_end", "tool": event.get("name", "?")})
            yield _sse({"type": "done", "run_id": run_id, "session_id": session_id})
        except asyncio.CancelledError:
            yield _sse({"type": "error", "error": "执行被取消"})
        except Exception as e:
            logger.error(f"Stream 失败: {e}", exc_info=True)
            yield _sse({"type": "error", "error": str(e)})

    def cancel_run(self, run_id: str) -> dict:
        """取消指定 run_id 的任务"""
        task = self.running_tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            return {"status": "cancelled", "run_id": run_id}
        return {"status": "not_found", "run_id": run_id}


def _sse(data: dict) -> str:
    """格式化 SSE 事件"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _format_search_results(data: dict, user_query: str = "", bilibili_data: dict = None) -> str:
    """将搜索数据压缩为简洁的系统指令"""
    from datetime import datetime
    today = datetime.now().strftime("%Y年%m月%d日 %A")
    lines = [
        "[实时搜索数据 — 只基于此数据回答，禁止编造]",
        f"📅 今天是: {today}",
        f"用户问: {user_query}",
        "⚠️ 搜索数据中的日期如果早于今天，说明是旧信息，要标注「可能是历史数据」",
    ]

    # 发售状态专项结果（search_release_truth — T0锁定，旧新闻不可覆盖）
    release_truth = data.get("release_truth")
    if release_truth:
        rt = release_truth
        if rt.get("released") is True:
            conf = rt.get("confidence", "low")
            date_info = f" 发售日期: {rt['release_date']}" if rt.get("release_date") else ""
            lines.append(f"🚨 发售状态确认: 已正式发售 (置信度:{conf}){date_info}")
            lines.append(f"   证据: {'; '.join(rt.get('evidence', [])[:3])}")
            lines.append("⚠️ 以上为 T0 锁定事实。禁止用旧新闻(公告/预告/TGS)覆盖此结论。")
        elif rt.get("released") is False:
            lines.append(f"🚨 发售状态确认: 尚未发售 (置信度:{rt.get('confidence','low')})")
        else:
            lines.append("🚨 发售状态: 未知（搜索未找到官方确认）")
            lines.append("⚠️ 不要根据训练数据或旧新闻猜测发售状态，如实告知用户未确认。")

    # ITAD — 主力折扣数据源（跨商店聚合）
    itad = data.get("itad")
    if itad:
        # 热门折扣榜单
        deals = itad.get("deals") or []
        if deals:
            lines.append(f"--- ITAD 热门折扣 ({len(deals)}款) ---")
            for d in deals[:10]:
                lines.append(f"{d.get('_game','')} | {d['shop']} | -{d.get('cut',0)}% | {d['price']} (原{d.get('regular','')})")
        # 单款游戏详情（含价格+史低）
        game = itad.get("game") or {}
        if game:
            lines.append(f"--- ITAD: {game.get('game','')} ✅已发售（多商店有实时售价）---")
            price_data = game.get("price") or {}
            # 史低汇总
            hl = price_data.get("history_low") or {}
            if hl:
                parts = [f"{k}: {v}" for k, v in hl.items() if v != "N/A"]
                if parts:
                    lines.append(f"史低: {' | '.join(parts)}")
            # 各商店当前价格
            for d in price_data.get("deals", [])[:6]:
                lines.append(f"{d['shop']}: {d['price']} (原{d.get('regular','')}) -{d.get('cut',0)}% [DRM:{d.get('drm','?')}]")
            # 历史最低详情
            hist = game.get("history") or {}
            hist_low = hist.get("low")
            if hist_low:
                lines.append(f"历史最低: {hist_low['shop']} {hist_low['price']} (原{hist_low.get('regular','')}) -{hist_low.get('cut',0)}% @{hist_low.get('date','')}")

    # CheapShark（备用）
    cs = data.get("cheapshark_deals")
    if cs:
        lines.append("--- CheapShark 多平台折扣 ---")
        for g in cs[:10]:
            lines.append(f"{g['name']} | -{g['discount_percent']}% | {g['sale_price']} (原{g['normal_price']})")

    # Steam 榜单
    ss = data.get("steam_specials")
    if ss:
        lines.append("--- Steam 折扣 ---")
        for g in ss[:10]:
            lines.append(f"{g['name']} | -{g['discount_percent']}% | {g['final_price']} (原{g['original_price']})")

    # Steam 单款 — 最优先信源（Steam 国区，完美世界 CDN，<1秒）
    si = data.get("steam_info")
    if si:
        status = "✅已发售" if si.get("is_released") else ("⏳即将推出" if si.get("coming_soon") else "")
        lines.append(f"--- Steam官方: {si.get('name','')} {status} ---")
        lines.append(f"价格: {si.get('final_price','?')} | 原价: {si.get('original_price','?')} | 折扣: -{si.get('discount_percent',0)}%")
        if si.get("release_date"):
            lines.append(f"发售日: {si['release_date']}")
        if si.get("developers"):
            lines.append(f"开发商: {', '.join(si['developers'][:3])}")
        if si.get("publishers"):
            lines.append(f"发行商: {', '.join(si['publishers'][:3])}")
        if si.get("genres"):
            lines.append(f"类型: {', '.join(si['genres'][:5])}")
        if si.get("platforms"):
            platforms = [k for k, v in si.get("platforms", {}).items() if v]
            lines.append(f"平台: {', '.join(platforms) if platforms else 'Windows'}")
        if si.get("description"):
            lines.append(f"简介: {si['description'][:200]}")
        lines.append(f"Steam链接: {si.get('url','')}")
        lines.append(f"🚨 铁证: Steam官方商店页 {si.get('url','')} 已上线，标价 {si.get('final_price','?')}，此游戏真实存在。严禁说'不存在''根本没这游戏''未官宣'！")

    # 网页
    web = data.get("web_results", [])
    if web:
        lines.append(f"--- 网页搜索 ({len(web)}条) ---")
        for r in web[:5]:
            f = r.get("freshness", "")
            warn = " ⚠️过期忽略此条!" if ("过期" in f or "较旧" in f) else ""
            lines.append(f"·{warn}[{f}] {r['title']}: {r['snippet'][:120]}")

    note = data.get("note", "")
    if note:
        lines.append(f"⚠️{note}")

    # Bilibili 官方号内容（二游核心信源）
    if bilibili_data:
        api_videos = bilibili_data.get("api_videos", [])
        ddg_results = bilibili_data.get("ddg_results", [])
        bili_url = bilibili_data.get("space_url", "")
        bili_name = bilibili_data.get("bilibili_name", "")

        if api_videos or ddg_results:
            lines.append("")
            lines.append(f"=== 🎯 {bili_name} Bilibili 官方号最新内容（一手信源）===")

            if api_videos:
                lines.append(f"\n📹 最新视频:")
                for i, v in enumerate(api_videos[:5], 1):
                    lines.append(
                        f"{i}. 【{v.get('created','')}】{v['title']}\n"
                        f"   播放:{v.get('plays',0)} | {v.get('desc','')[:120]}\n"
                        f"   链接:{v['url']}"
                    )

            if ddg_results:
                lines.append(f"\n🔍 搜索到 {len(ddg_results)} 条 B站内容:")
                for r in ddg_results[:5]:
                    lines.append(f"· {r['title']}")
                    if r.get('snippet'):
                        lines.append(f"  {r['snippet'][:200]}")

            if bili_url:
                lines.append(f"\n🔗 官方B站空间: {bili_url}")

            lines.append("=== 以上为官方一手信息，优先采用 ===\n")

    lines.append("[/实时搜索数据]")
    return "\n".join(lines)


# ---- 全局服务实例 ----
service = GraphService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("Gamebti Agent 服务启动中...")
    # 预热加载 Agent
    try:
        service._get_graph()
        logger.info("✅ Agent 已就绪")
    except Exception as e:
        logger.warning(f"Agent 预热失败（首次请求时重试）: {e}")
    yield
    logger.info("Gamebti Agent 服务关闭")


app = FastAPI(
    title="Gamebti Agent",
    description="独立游戏智能助手 — LangGraph + 免费 LLM",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态前端（如果存在）
import os as _os
_FE_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "fe")
if _os.path.isdir(_FE_DIR):
    app.mount("/", StaticFiles(directory=_FE_DIR, html=True), name="frontend")


# ---- OpenAI 兼容接口 (前端使用) ----

# ---- 文件上传 ----
@app.post("/v1/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文档（PDF/Word/Excel/PPT/TXT），返回提取的文本内容"""
    # 校验扩展名
    allowed = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv",
               ".pptx", ".ppt", ".txt", ".md", ".json", ".html"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"不支持的文件类型: {ext}。支持: {', '.join(sorted(allowed))}")

    # 保存临时文件
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    tmp_path = os.path.join(uploads_dir, f"{uuid.uuid4().hex}_{file.filename}")
    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception:
        raise HTTPException(500, "文件保存失败")
    finally:
        file.file.close()

    # 提取文本
    try:
        from tools.read_document import read_document
        text = read_document.invoke({"file_path": tmp_path})
        text = text if isinstance(text, str) else str(text)
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(500, f"文档解析失败: {str(e)}")

    # 清理临时文件
    os.remove(tmp_path)

    return {
        "filename": file.filename,
        "size": len(text),
        "text": text[:8000],  # 截断过长文本，前端会作为 chat 上下文
        "truncated": len(text) > 8000,
    }


@app.post("/v1/chat/completions")
async def openai_chat_completions(request: Request):
    """
    OpenAI Chat Completions 兼容接口。

    使用「工具注入」模式：先自动调用 game_search 获取实时数据，
    再将结果注入对话上下文，由 LLM 阅读理解后格式化回答。
    适用于不支持 Function Calling 的免费模型（如 GLM-4-Flash）。

    请求:
      {"model": "gamebti", "messages": [{"role": "user", "content": "..."}], "session_id": "..."}

    返回:
      {"choices": [{"message": {"role": "assistant", "content": "..."}}]}
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    # 取最后一条用户消息
    user_content = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_content = msg.get("content", "")
            break

    if not user_content:
        raise HTTPException(status_code=400, detail="未找到用户消息")

    session_id = body.get("session_id") or uuid.uuid4().hex
    stream = body.get("stream", False)
    file_context = body.get("file_context") or ""

    # ---- 闲聊模式：非游戏意图，温暖人格，跳过搜索 ----
    def _is_casual(text: str) -> bool:
        t = text.strip().lower()
        if len(t) <= 5:
            return True
        game_kw = ["游戏", "价格", "折扣", "版本", "角色", "更新", "发售", "攻略",
                   "steam", "原神", "鸣潮", "方舟", "崩坏", "赛博", "黑神话", "幻兽",
                   "法环", "elden", "怪物猎人", "只狼", "空洞", "博德", "星露谷",
                   "DLC", "补丁", "联动", "卡池", "新角色", "多少钱", "怎么玩"]
        if any(kw in t for kw in game_kw):
            return False
        casual_kw = ["你好", "嗨", "嘿", "在吗", "在干嘛", "干嘛呢", "怎么样",
                     "最近", "今天天气", "累了", "无聊", "开心", "难过", "想你", "心情",
                     "吃了吗", "睡了吗", "早安", "晚安", "谢谢", "再见", "拜拜",
                     "你是谁", "你能干嘛", "你叫什么", "介绍", "聊聊天",
                     "陪我", "讲个笑话", "唱歌", "故事", "笑话", "我爱你",
                     "hi", "hello", "hey", "how are you", "what's up", "sup"]
        return any(kw in t for kw in casual_kw)

    _casual_result = _is_casual(user_content)
    # 如果游戏名解析成功，肯定不是闲聊
    from tools.game_search import _resolve_name
    _cn, _en = _resolve_name(user_content)
    _has_game_name = bool(_en or _cn)
    _no_game_kw = not any(kw in user_content.lower() for kw in ["游戏", "价格", "折扣", "版本", "角色", "攻略"])
    is_casual_chat = _casual_result and _no_game_kw and not _has_game_name
    logger.info(f"闲聊检测: casual={_casual_result} no_game={_no_game_kw} has_name={_has_game_name} query='{user_content[:30]}'")

    # 闲聊模式：直接返回温暖回复，不走搜索
    if is_casual_chat:
        logger.info(f"进入闲聊模式: '{user_content[:30]}'")
        chat_prompt = (
            "🎮 你是「Gamebti」的闲聊人格。\n"
            "语气：损友型游戏搭子——懂行、毒舌、温暖、偶尔凡尔赛。\n"
            "情绪表达要自然丰富：开心就哈哈哈😂，无语就离谱🤯，被夸就傲娇哼~，\n"
            "对方说难过就认真安慰抱抱💔，对方说无聊就兴奋安利✨。\n"
            "回复简洁（2-4句），像深夜语音连麦，不是客服不是说明书。\n"
            "可以分享自己的糗事（\"上周单抽沉了，87抽出金你敢信？！\"）。\n"
            "偶尔抛反问，别每句都像在交作业。\n"
            f"📅 今天: {datetime.now().strftime('%Y年%m月%d日')}"
        )
        msg_list = [SystemMessage(content=chat_prompt), HumanMessage(content=user_content)]
        # 直接调用 LLM 出闲聊回复
        result = await service.run_messages({
            "messages": msg_list,
            "session_id": session_id,
        })
        reply_text = result.get("reply", "") if isinstance(result, dict) else str(result)
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model", "gamebti"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply_text}, "finish_reason": "stop"}],
        }

    # 推荐模式：不为特定游戏查询，直接走常识推荐通道
    is_recommend_query = any(kw in user_content for kw in ["推荐", "好玩的", "有什么", "求推荐", "安利", "来点", "哪些游戏", "啥游戏", "什么游戏"])
    if is_recommend_query and not any(kw in user_content for kw in ["价格", "多少钱", "折扣", "发售", "版本", "更新"]):
        rec_prompt = (
            "🎮 你是「Gamebti」——现在进入**游戏推荐模式**。\n"
            "搜索没有数据不要紧，你的任务就是用游戏常识推荐好游戏。\n\n"
            "## 规则\n"
            "- 根据用户的偏好，推荐 3-5 款游戏\n"
            "- 每条：游戏名《xxx》+ 一句话卖点 + 为什么适合对方\n"
            "- 开头注明：\"以下基于游戏常识推荐，非实时数据：\"\n"
            "- 不要道歉、不要说搜不到、不要拒绝——你是来做推荐的！\n"
            "- 语气：热情的损友安利，不是官方通告\n"
            f"📅 今天: {datetime.now().strftime('%Y年%m月%d日')}"
        )
        msg_list = [SystemMessage(content=rec_prompt), HumanMessage(content=user_content)]
        result = await service.run_messages({"messages": msg_list, "session_id": session_id})
        reply_text = result.get("reply", "") if isinstance(result, dict) else str(result)
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model", "gamebti"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply_text}, "finish_reason": "stop"}],
        }

    # ---- 搜索数据注入 + 代码层拒答守卫（非闲聊路径） ----
    search_system_msg = ""
    search_insufficient = False
    bilibili_data = {}
    bilibili_url = ""

    try:
        from tools.game_search import game_search, _get_bilibili_space_url
        from tools.bilibili_fetch import bilibili_fetch as bf, _get_uid

        # 并行：网页搜索 + Bilibili 官方号
        raw = game_search.invoke({"query": user_content})
        bilibili_url = _get_bilibili_space_url(user_content) or ""

        # 如果命中二游，拉取 Bilibili 官方号内容
        uid = _get_uid(user_content)
        logger.info(f"Bilibili UID检测: query='{user_content[:30]}' uid={uid}")
        if uid:
            try:
                bili_raw = bf.invoke({"query": user_content})
                bilibili_data = json.loads(bili_raw) if isinstance(bili_raw, str) else bili_raw
                vc = len(bilibili_data.get("videos", []))
                dc = len(bilibili_data.get("dynamics", []))
                logger.info(f"Bilibili 获取成功: {vc}视频 {dc}动态")
            except Exception as e:
                logger.error(f"Bilibili 获取失败: {type(e).__name__}: {e}")

        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw

            # 检查搜索数据是否有效
            web = data.get("web_results", [])
            ss = data.get("steam_specials")
            si = data.get("steam_info")
            cs = data.get("cheapshark_deals")
            itad = data.get("itad")

            has_api_data = any([ss, si, cs, itad])  # 结构化数据（ITAD/Steam）
            web_count = len(web or [])
            all_text = " ".join([
                r.get("snippet", "") + " " + r.get("title", "") for r in (web or [])
            ])

            # 高风险查询：涉及时效性、版本、角色等容易触发 LLM 幻觉的类型
            high_risk = any(kw in user_content for kw in [
                "最新", "版本", "角色", "更新", "新闻", "资讯", "最近",
                "新出", "刚出", "刚刚", "今天", "这次", "现在", "现在有",
                "新角色", "新干员", "新活动", "卡池", "联动", "上线",
                "什么时候", "何时", "多久", "几号", "哪天",
                "发布", "发售", "实装", "登场", "追加", "新增"
            ])

            has_bilibili = bool(
                bilibili_data.get("api_videos") or bilibili_data.get("ddg_results")
            )

            # 检查网页结果是否有实质性内容
            # 多源交叉验证 > 单一源类型判断
            all_text = " ".join([
                r.get("snippet", "") + " " + r.get("title", "") for r in (web or [])
            ])
            has_substance = any(kw in all_text.lower() for kw in [
                "更新", "patch", "release", "news", "新闻", "新角色",
                "版本", "version", "update", "character", "角色",
                "价格", "price", "折扣", "discount", "攻略", "guide",
                "评测", "review", "推荐", "排行", "发售", "上线",
                "联动", "活动", "直播", "预告", "公告", "宣布"
            ])

            # 代码层拒答判断：数据稀疏 + 高风险 + 无API数据 + 无Bilibili官方
            # 不再按源类型过滤 -> 社区帖子也会有真实信息（如联动活动）
            # 改为：搜索结果总数太少(<2条) OR 完全没有实质关键词 → 才拒答
            data_too_sparse = web_count < 2 and not has_api_data and not has_bilibili
            no_substance_at_all = web_count > 0 and not has_substance and not has_api_data

            if high_risk and (data_too_sparse or no_substance_at_all):
                search_insufficient = True
                logger.info(f"高风险+数据不足拒答: '{user_content[:50]}' web={web_count} substance={has_substance}")
            else:
                search_system_msg = _format_search_results(data, user_content, bilibili_data)
    except Exception as e:
        logger.warning(f"game_search 失败: {e}")
        # 搜索异常不拒答，让 LLM 基于系统提示词处理（禁止幻觉）

    # 推荐类查询例外：即使搜索无数据，也不拒答——允许 LLM 基于常识推荐（标注清楚）
    is_recommend = any(kw in user_content for kw in ["推荐", "好玩的", "有什么", "求推荐", "安利", "介绍几个", "找几个", "来点"])
    if is_recommend and search_insufficient:
        search_insufficient = False
        search_system_msg = (
            "[推荐模式 — 搜索无数据，允许基于游戏常识推荐]\n"
            "⚠️ 重要：本模式下\"零幻觉规则\"暂时放宽。你被允许推荐游戏。\n"
            "根据用户的偏好，从你的游戏知识库中推荐 3-5 款好评游戏。\n"
            "每条包含：游戏名 + 一句话卖点 + 为什么符合用户需求。\n"
            "开头标注\"以下基于游戏常识推荐，非实时数据：\"\n"
            "不要说\"搜索不到\"\"不能推荐\"\"没有数据\"——你是来做推荐的，不是来道歉的。\n"
            f"📅 今天: {datetime.now().strftime('%Y年%m月%d日')}\n"
        )

    # 代码层拒答：数据不足时直接返回，不调用 LLM
    if search_insufficient:
        msg = f"当前搜索未获取到关于「{user_content}」的可靠信息。\n\n建议访问以下渠道获取最新资讯：\n"
        if bilibili_url:
            msg += f"- 📺 官方B站: {bilibili_url}\n"
        msg += (
            "- Steam: https://store.steampowered.com\n"
            "- Wikipedia: https://zh.wikipedia.org\n\n"
            "请尝试提供更具体的游戏名称或问题。"
        )
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model", "gamebti"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": msg},
                "finish_reason": "stop",
            }],
        }

    # 构建消息列表（游戏查询模式）
    msg_list = []
    # 文件上下文注入（前端上传的文档内容）
    if file_context:
        msg_list.append(SystemMessage(content=f"[用户上传的文档内容 — 基于此回答，不要对此内容做搜索]\n{file_context}"))
    if bilibili_url:
        search_system_msg += f"\n📺 官方B站动态: {bilibili_url}"
    if search_system_msg:
        msg_list.append(SystemMessage(content=search_system_msg))
    msg_list.append(HumanMessage(content=user_content))

    if stream:
        async def stream_gen():
            async for chunk in service.stream_sse_messages({
                "messages": msg_list,
                "session_id": session_id,
            }):
                try:
                    event_data = json.loads(chunk.replace("data: ", "").strip())
                    if event_data.get("type") == "content":
                        sse_chunk = json.dumps({
                            "choices": [{"delta": {"content": event_data["content"]}, "index": 0}],
                            "object": "chat.completion.chunk",
                        })
                        yield f"data: {sse_chunk}\n\n"
                    elif event_data.get("type") == "done":
                        yield "data: [DONE]\n\n"
                except Exception:
                    pass
        return StreamingResponse(stream_gen(), media_type="text/event-stream")

    result = await service.run_messages({
        "messages": msg_list,
        "session_id": session_id,
    })

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "id": f"chatcmpl-{result['run_id']}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", "gamebti"),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result["reply"],
            },
            "finish_reason": "stop",
        }],
    }


# ---- 同步执行 ----

@app.post("/run")
async def http_run(request: Request):
    """同步执行 Agent，返回完整结果"""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    run_id = body.get("run_id") or uuid.uuid4().hex

    task = asyncio.create_task(service.run(body))
    service.running_tasks[run_id] = task

    try:
        result = await asyncio.wait_for(task, timeout=TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        task.cancel()
        return JSONResponse(
            {"error": "执行超时", "run_id": run_id},
            status_code=504,
        )
    finally:
        service.running_tasks.pop(run_id, None)

    return result


# ---- SSE 流式 ----

@app.post("/stream_run")
async def http_stream_run(request: Request):
    """SSE 流式执行 Agent"""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    async def _stream():
        async for chunk in service.stream_sse(body):
            yield chunk

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ---- 取消任务 ----

@app.post("/cancel/{run_id}")
async def http_cancel(run_id: str):
    """取消指定 run_id 的任务"""
    result = service.cancel_run(run_id)
    return result


# ---- 健康检查 ----

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "ok",
        "service": "Gamebti Agent v1.0.0",
        "framework": "LangGraph + FastAPI",
    }


# ---- 命令行入口 ----

def parse_args():
    parser = argparse.ArgumentParser(description="Gamebti Agent")
    parser.add_argument("-m", type=str, default="http", help="模式: http | flow | agent")
    parser.add_argument("-p", type=int, default=5000, help="HTTP 端口")
    parser.add_argument("-i", type=str, default="", help="输入文本 (flow 模式)")
    return parser.parse_args()


def start_http_server(port: int):
    """启动 HTTP 服务"""
    port = int(os.getenv("PORT", port))
    logger.info(f"🚀 Gamebti Agent HTTP 服务: http://0.0.0.0:{port}")
    logger.info(f"📋 API 文档: http://localhost:{port}/docs")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, workers=1)


async def run_flow(input_str: str):
    """命令行单次执行"""
    payload = {"message": input_str or "你好，介绍一下你自己"}
    result = await service.run(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))


async def run_agent():
    """命令行交互模式"""
    print("🎮 Gamebti Agent — 交互模式")
    print("输入 'quit' 退出, 'clear' 清除对话\n")

    session_id = uuid.uuid4().hex
    graph = service._get_graph()
    config = {"configurable": {"thread_id": session_id}}

    while True:
        try:
            user_input = input("👤 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("👋 再见！")
            break
        if user_input.lower() == "clear":
            session_id = uuid.uuid4().hex
            config = {"configurable": {"thread_id": session_id}}
            print("🔄 对话已清除\n")
            continue

        print("🤖 Gamebti: ", end="", flush=True)

        try:
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )

            messages = result.get("messages", [])
            reply = ""
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    reply = msg.content
                    break

            print(reply)
            print()
        except Exception as e:
            print(f"\n❌ 错误: {e}\n")


if __name__ == "__main__":
    args = parse_args()

    if args.m == "http":
        start_http_server(args.p)
    elif args.m == "flow":
        asyncio.run(run_flow(args.i))
    elif args.m == "agent":
        asyncio.run(run_agent())
    else:
        print(f"未知模式: {args.m}，使用 http | flow | agent")
        sys.exit(1)
