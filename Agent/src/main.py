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
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
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
            lines.append(f"--- ITAD: {game.get('game','')} ---")
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

    # Steam 单款
    si = data.get("steam_info")
    if si:
        lines.append(f"--- {si['name']} ---")
        lines.append(f"价格:{si['final_price']} 原价:{si['original_price']} 折扣:{si['discount_percent']}%")
        if si.get("description"):
            lines.append(f"简介:{si['description'][:150]}")

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


# ---- OpenAI 兼容接口 (前端使用) ----

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

    # ---- 搜索数据注入 + 代码层拒答守卫 ----
    search_system_msg = ""
    search_insufficient = False
    bilibili_data = {}
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

            has_data = any([cs, ss, si, web])
            all_text = " ".join([
                r.get("snippet", "") + " " + r.get("title", "") for r in (web or [])
            ])
            # 检查是否为高风险查询类型（容易触发幻觉的资讯/版本类问题）
            high_risk = any(kw in user_content for kw in [
                "最新", "版本", "角色", "更新", "新闻", "资讯", "最近",
                "新出", "刚出", "刚刚", "今天", "这次"
            ])
            # 只有高风险 + 全是T1泛化结果 + 无实质信息 → 才拒答
            has_bilibili = bool(
                bilibili_data.get("api_videos") or bilibili_data.get("ddg_results")
            )
            only_t1_generic = (
                high_risk and not has_bilibili and
                web and not ss and not si and not cs and
                all(r.get("source", "").startswith("T1") for r in web) and
                not any(kw in all_text.lower() for kw in [
                    "更新", "patch", "release", "news", "新闻", "新角色",
                    "版本", "version", "update", "character", "角色",
                    "价格", "price", "折扣", "discount", "攻略", "guide",
                    "评测", "review", "推荐", "排行", "发售"
                ])
            )

            if only_t1_generic:
                search_insufficient = True
                logger.info(f"仅T1泛化({len(web)}条)，高危拒答: '{user_content[:50]}'")
            else:
                search_system_msg = _format_search_results(data, user_content, bilibili_data)
    except Exception as e:
        logger.warning(f"game_search 失败: {e}")
        # 搜索异常不拒答，让 LLM 基于系统提示词处理（禁止幻觉）

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

    # 构建消息列表
    msg_list = []
    # 追加 Bilibili 官方号链接（如适用）
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
