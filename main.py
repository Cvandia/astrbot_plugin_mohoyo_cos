"""AstrBot entry point; HTTP implementation adapted from nonebot-plugin-genshin-cos."""

import asyncio
import json
import random
import re
import shlex
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Image, Node, Nodes, Plain
from astrbot.api.star import Context, Star, StarTools

from .mihoyo_cos import HoyoClient, MiyousheError, game_name, image_urls
from .utils import Cooldown, parse_count, parse_time

HELP = """米游社图片
/热门cos 原神 x3（也支持最新、日榜、周榜、月榜、精品）
/搜索cos 崩铁 流萤 x2
/hoyocos 钟离 2（兼容旧指令）
/下载cos 原神（管理员）
/开启每日推送 原神 08:30（群内管理员）
/关闭每日推送 原神
/查看本群推送
游戏：原神、崩坏3、大别野、星穹铁道、绝区零。
数量支持 3、x3、X3、*3；含空格的搜索词请加引号。
精品不支持原神、星穹铁道；上游精品接口可能不可用。
每日推送仅支持原神、大别野，默认时区 Asia/Shanghai。"""
QUERY_PATTERN = r"^/?(?:热门|最新|日榜|周榜|月榜|精品|搜索)cos(?:er|图)?(?:\s|$)"


class MihoyoCos(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.maximum = max(1, min(100, int(config.get("cos_max", 10))))
        self.delay = max(0.0, float(config.get("cos_delay", 0.5)))
        self.cooldown = Cooldown(max(0, int(config.get("cos_cd", 10))))
        timeout = float(config.get("cos_timeout", config.get("timeout", 20)))
        self.timeout = timeout if timeout > 0 else 20
        self.client = None
        self.requests = asyncio.Semaphore(4)
        self.download_lock = asyncio.Lock()
        self.subscription_lock = asyncio.Lock()
        self.data_dir = StarTools.get_data_dir("astrbot_plugin_mohoyo_cos")
        self.save_path = Path(config.get("cos_path") or self.data_dir / "images")
        self.subscriptions = {}
        self.scheduler = AsyncIOScheduler(
            timezone=ZoneInfo(config.get("cos_timezone", "Asia/Shanghai"))
        )

    def get_client(self) -> HoyoClient:
        if self.client is None:
            self.client = HoyoClient(self.timeout)
        return self.client

    async def initialize(self):
        path = self.data_dir / "subscriptions.json"
        if path.exists():
            rows = await asyncio.to_thread(lambda: json.loads(path.read_text("utf-8")))
            if not isinstance(rows, dict):
                raise ValueError("订阅文件必须是对象，请修复 subscriptions.json")
            for key, row in rows.items():
                if not isinstance(row, dict) or not isinstance(row.get("origin"), str):
                    raise TypeError("订阅记录格式错误")
                game = game_name(row["game"])
                if game not in {"原神", "大别野"} or key != self.subscription_key(
                    row["origin"], game
                ):
                    raise ValueError("订阅游戏或标识无效")
                parse_time(row["time"])
            self.subscriptions = rows
        for key, row in self.subscriptions.items():
            self.add_job(key, row)
        self.scheduler.add_job(self.prune_cooldowns, "interval", minutes=1)
        self.scheduler.start()

    async def prune_cooldowns(self):
        self.cooldown.prune()

    async def terminate(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            # APScheduler schedules shutdown on the event loop.
            await asyncio.sleep(0)
        if self.client is not None:
            await self.client.close()
            self.client = None

    def is_admin(self, event):
        if event.is_admin():
            return True
        # Group roles are adapter-specific; unknown adapters require AstrBot admin.
        raw = event.message_obj.raw_message
        return bool(
            event.get_group_id()
            and isinstance(raw, dict)
            and (raw.get("sender") or {}).get("role") in {"owner", "admin"}
        )

    async def send_images(self, event, urls):
        images = [Image.fromURL(url) for url in urls]
        if self.config.get("cos_forward_msg", False):
            nodes = [
                Node(name="米游社cos", uin=str(event.get_self_id()), content=[img])
                for img in images
            ]
            await event.send(MessageChain([Nodes(nodes)]))
        else:
            for index, image in enumerate(images):
                if index and self.delay:
                    await asyncio.sleep(self.delay)
                await event.send(MessageChain([image]))

    async def query(self, event, game, kind="热门", keyword="", count="1"):
        try:
            game = game_name(game)
            count = parse_count(str(count), self.maximum)
            if kind == "搜索" and not keyword.strip():
                raise ValueError("请指定搜索内容")
            if kind == "精品" and game in {"原神", "星穹铁道"}:
                raise ValueError(f"{game}暂不支持精品cos")
        except ValueError as exc:
            return str(exc)
        remaining = self.cooldown.acquire(event.get_platform_id(), event.get_sender_id())
        if remaining:
            return f"冷却中，还剩{remaining}秒"
        try:
            async with self.requests:
                urls = image_urls(await self.get_client().fetch(game, kind, keyword))
                if not urls:
                    return "没有找到相关图片"
                selected = random.sample(urls, min(count, len(urls)))
                await self.send_images(event, selected)
                return f"已发送{len(selected)}张{game}图片"
        except (httpx.HTTPError, MiyousheError) as exc:
            logger.warning(f"米游社请求失败：{exc}")
            return "米游社请求失败，请稍后重试"
        except Exception as exc:  # Adapter exceptions have no shared public base class.
            logger.exception(f"图片发送失败：{exc}")
            return "图片发送失败，请检查适配器是否支持当前发送模式"

    @filter.regex(QUERY_PATTERN)
    async def query_command(self, event: AstrMessageEvent):
        event.stop_event()
        try:
            args = shlex.split(event.message_str.lstrip("/"))
            kind = re.match(r"^(热门|最新|日榜|周榜|月榜|精品|搜索)", args[0])[1]
            if kind == "搜索":
                if len(args) not in {3, 4}:
                    raise ValueError('用法：/搜索cos 原神 "甘雨 cosplay" x2')
                game, keyword = args[1:3]
                count = args[3] if len(args) == 4 else "1"
            else:
                if len(args) not in {2, 3}:
                    raise ValueError("用法：/热门cos 原神 x3")
                game, keyword = args[1], ""
                count = args[2] if len(args) == 3 else "1"
            result = await self.query(event, game, kind, keyword, count)
        except ValueError as exc:
            result = str(exc)
        yield event.plain_result(result)

    @filter.command("hoyocos")
    async def hoyocos(self, event: AstrMessageEvent, name: str = "可莉", count: int = 1):
        game, keyword = self.legacy_search(name)
        yield event.plain_result(await self.query(event, game, "搜索", keyword, count))

    @staticmethod
    def legacy_search(name):
        for prefix in ("星穹铁道", "崩坏3", "大别野", "绝区零", "原神", "崩铁"):
            if name.startswith(prefix):
                return game_name(prefix), name[len(prefix) :].strip()
        return "原神", name

    @filter.command("coshelp")
    async def help(self, event: AstrMessageEvent):
        yield event.plain_result(HELP)

    @filter.llm_tool(name="get_cos_pic")
    async def get_cos_pic(
        self, event: AstrMessageEvent, count: int, name: str, game: str = "原神", kind: str = "搜索"
    ) -> str:
        """获取米游社角色 cos 图片并发送给用户。

        Args:
            count(number): 图片数量，正整数。
            name(string): 搜索的角色名。
            game(string): 游戏名，原神、崩坏3、大别野、星穹铁道、绝区零。
            kind(string): 搜索、热门、最新、日榜、周榜、月榜或精品。
        """
        if kind not in {"搜索", "热门", "最新", "日榜", "周榜", "月榜", "精品"}:
            return "不支持的榜单类型"
        return await self.query(event, game, kind, name, count)

    @filter.regex(r"^/?(?:下载cos|保存cos|cos保存)(?:\s|$)")
    async def download(self, event: AstrMessageEvent):
        event.stop_event()
        if not self.is_admin(event):
            yield event.plain_result("需要 AstrBot 管理员或群管理员权限")
            return
        try:
            args = shlex.split(event.message_str)
            if len(args) != 2:
                raise ValueError("用法：/下载cos 原神")
            game = game_name(args[1])
            if self.download_lock.locked():
                yield event.plain_result("已有下载任务进行中，请稍后重试")
                return
            async with self.download_lock, self.requests:
                urls = image_urls(await self.get_client().fetch(game))
                if not urls:
                    yield event.plain_result("没有找到相关图片")
                    return
                success, failed = await self.get_client().download(
                    urls, self.save_path / f"{game}cos"
                )
            result = f"保存完成：成功{success}张，失败{failed}张"
        except (ValueError, httpx.HTTPError, MiyousheError, OSError) as exc:
            logger.warning(f"米游社下载失败：{exc}")
            result = str(exc) if isinstance(exc, ValueError) else "下载失败，请检查网络和存储目录"
        yield event.plain_result(result)

    @staticmethod
    def subscription_key(origin, game):
        return f"{origin}:{game}"

    def add_job(self, key, row):
        hour, minute = parse_time(row["time"])
        self.scheduler.add_job(
            self.push,
            "cron",
            hour=hour,
            minute=minute,
            id=key,
            args=[row],
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )

    async def push(self, row):
        try:
            async with self.requests:
                posts = await self.get_client().fetch(row["game"], "日榜", page_size=5)
                urls = image_urls(posts)[: self.maximum]
                if not urls:
                    return
                title = f"米游社{row['game']}cos每日榜单\n" + "\n".join(p.title for p in posts)
                # Public unified-session API preserves the platform/bot/session identity.
                await self.context.send_message(row["origin"], MessageChain([Plain(title)]))
                for url in urls:
                    await self.context.send_message(
                        row["origin"], MessageChain([Image.fromURL(url)])
                    )
        except Exception as exc:  # Adapter exceptions have no shared public base class.
            logger.exception(f"每日推送失败：{exc}")

    async def update_subscription(self, origin, game, time, enabled):
        key = self.subscription_key(origin, game)
        async with self.subscription_lock:
            updated = self.subscriptions.copy()
            row = {"origin": origin, "game": game, "time": time}
            if enabled:
                updated[key] = row
            else:
                updated.pop(key, None)

            def write():
                self.data_dir.mkdir(parents=True, exist_ok=True)
                target = self.data_dir / "subscriptions.json"
                tmp = target.with_suffix(".tmp")
                try:
                    tmp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), "utf-8")
                    tmp.replace(target)
                finally:
                    tmp.unlink(missing_ok=True)

            # Finish the atomic disk + memory commit even if the caller is cancelled.
            task = asyncio.create_task(asyncio.to_thread(write))
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                self.subscriptions = updated
                self.sync_job(key, row, enabled)
                raise
            self.subscriptions = updated
            self.sync_job(key, row, enabled)

    def sync_job(self, key, row, enabled):
        if enabled:
            self.add_job(key, row)
        elif self.scheduler.get_job(key):
            self.scheduler.remove_job(key)

    @filter.regex(r"^/?(?:开启|关闭)每日推送(?:\s|$)")
    async def subscription(self, event: AstrMessageEvent):
        event.stop_event()
        if not event.get_group_id():
            yield event.plain_result("每日推送只能在群聊中设置")
            return
        if not self.is_admin(event):
            yield event.plain_result("需要 AstrBot 管理员或群管理员权限")
            return
        try:
            args = shlex.split(event.message_str.lstrip("/"))
            enabled = args[0] == "开启每日推送"
            if len(args) != (3 if enabled else 2):
                raise ValueError("用法：/开启每日推送 原神 08:30 或 /关闭每日推送 原神")
            game = game_name(args[1])
            if game not in {"原神", "大别野"}:
                raise ValueError("每日推送仅支持原神和大别野")
            hour, minute = parse_time(args[2]) if enabled else (0, 0)
            time = f"{hour:02}:{minute:02}"
            await self.update_subscription(event.unified_msg_origin, game, time, enabled)
            result = f"已{'开启' if enabled else '关闭'}{game}每日推送"
            if enabled:
                result += f"（{time}，{self.scheduler.timezone}）"
        except (ValueError, OSError) as exc:
            result = f"订阅更新失败：{exc}"
        yield event.plain_result(result)

    @filter.command("查看本群推送", alias={"查看推送", "查看订阅"})
    async def show_subscriptions(self, event: AstrMessageEvent):
        rows = [
            f"{row['game']}：每天 {row['time']}"
            for row in self.subscriptions.values()
            if row["origin"] == event.unified_msg_origin
        ]
        yield event.plain_result("本群订阅：\n" + "\n".join(rows) if rows else "本群尚未开启推送")
