from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from astrbot.api.message_components import Image, Nodes
from astrbot_plugin_mohoyo_cos.main import MihoyoCos
from astrbot_plugin_mohoyo_cos.mihoyo_cos import MiyousheError, Post
from astrbot_plugin_mohoyo_cos.utils import parse_count


class Event:
    def __init__(self, text="", group="group", admin=False, role="member"):
        self.message_str = text
        self.unified_msg_origin = "adapter:GroupMessage:group"
        self.message_obj = SimpleNamespace(raw_message={"sender": {"role": role}})
        self.group, self.admin = group, admin
        self.send = AsyncMock()
        self.stopped = False

    def get_group_id(self):
        return self.group

    def get_platform_id(self):
        return "adapter"

    def get_sender_id(self):
        return "user"

    def get_self_id(self):
        return "bot"

    def is_admin(self):
        return self.admin

    def stop_event(self):
        self.stopped = True

    def plain_result(self, text):
        return text


@pytest.fixture
async def plugin(tmp_path, monkeypatch):
    monkeypatch.setattr("astrbot_plugin_mohoyo_cos.main.StarTools.get_data_dir", lambda _: tmp_path)
    plugin = MihoyoCos(SimpleNamespace(send_message=AsyncMock()), {"cos_cd": 0, "cos_delay": 0})
    plugin.client = SimpleNamespace(
        fetch=AsyncMock(return_value=[Post("title", ("https://example.org/a.jpg",))]),
        close=AsyncMock(),
        download=AsyncMock(return_value=(1, 0)),
    )
    yield plugin
    await plugin.terminate()


async def collect(generator):
    return [item async for item in generator]


@pytest.mark.parametrize("kind", ["热门", "最新", "日榜", "周榜", "月榜", "精品", "搜索"])
async def test_commands(plugin, kind):
    text = f"/{kind}cos 崩三" + (' "角色 cosplay"' if kind == "搜索" else "") + " x3"
    event = Event(text)
    result = await collect(plugin.query_command(event))
    assert result == ["已发送1张崩坏3图片"]
    assert event.stopped
    assert isinstance(event.send.call_args.args[0].chain[0], Image)
    plugin.client.fetch.assert_awaited_once_with(
        "崩坏3", kind, "角色 cosplay" if kind == "搜索" else ""
    )


async def test_legacy_and_llm(plugin):
    event = Event()
    assert await collect(plugin.hoyocos(event, "崩铁流萤", 5)) == ["已发送1张星穹铁道图片"]
    assert await plugin.get_cos_pic(event, 1, "甘雨") == "已发送1张原神图片"
    assert "/热门cos" in (await collect(plugin.help(event)))[0]


@pytest.mark.parametrize("count", ["0", "-1", "x0", "abc", "1.5"])
async def test_invalid_counts(plugin, count):
    assert "正整数" in await plugin.query(Event(), "原神", count=count)
    plugin.client.fetch.assert_not_awaited()


@pytest.mark.parametrize("error", [httpx.ReadTimeout("timeout"), MiyousheError("bad data")])
async def test_upstream_error(plugin, error):
    plugin.client.fetch.side_effect = error
    assert "请求失败" in await plugin.query(Event(), "原神")


async def test_empty_send_failure_and_forward(plugin):
    event = Event()
    plugin.client.fetch.return_value = []
    assert await plugin.query(event, "原神") == "没有找到相关图片"
    plugin.client.fetch.return_value = [Post("t", ("https://example.org/a.jpg",))]
    plugin.config["cos_forward_msg"] = True
    assert "已发送" in await plugin.query(event, "原神")
    assert isinstance(event.send.call_args.args[0].chain[0], Nodes)
    event.send.side_effect = RuntimeError("adapter rejected")
    assert "发送失败" in await plugin.query(event, "原神")


async def test_cooldown(plugin):
    plugin.cooldown.seconds = 10
    assert "已发送" in await plugin.query(Event(), "原神")
    assert "冷却中" in await plugin.query(Event(), "原神")
    assert plugin.client.fetch.await_count == 1


async def test_download_permissions_and_serialization(plugin):
    assert "权限" in (await collect(plugin.download(Event("/下载cos 原神"))))[0]
    plugin.client.fetch.assert_not_awaited()
    assert "成功1张" in (await collect(plugin.download(Event("/下载cos 原神", role="admin"))))[0]
    async with plugin.download_lock:
        assert "已有下载" in (await collect(plugin.download(Event("/下载cos 原神", admin=True))))[0]


async def test_subscriptions_restart_isolation_and_push(plugin):
    await plugin.initialize()
    event = Event("/开启每日推送 原神 08:30", admin=True)
    assert "已开启" in (await collect(plugin.subscription(event)))[0]
    assert len(plugin.subscriptions) == 1
    key, row = next(iter(plugin.subscriptions.items()))
    assert plugin.scheduler.get_job(key)
    assert "08:30" in (await collect(plugin.show_subscriptions(event)))[0]
    other = Event()
    other.unified_msg_origin = "other:GroupMessage:group"
    assert "尚未" in (await collect(plugin.show_subscriptions(other)))[0]
    await plugin.push(row)
    assert plugin.context.send_message.await_count == 2
    await plugin.terminate()
    plugin.client = None
    await plugin.initialize()
    assert key in plugin.subscriptions
    event.message_str = "/关闭每日推送 原神"
    assert "已关闭" in (await collect(plugin.subscription(event)))[0]
    assert not plugin.subscriptions
    assert not plugin.scheduler.get_job(key)


async def test_subscription_invalid_or_unauthorized(plugin):
    for event in [
        Event("/开启每日推送 原神 08:30"),
        Event("/开启每日推送 原神 08:30", group="", admin=True),
    ]:
        await collect(plugin.subscription(event))
    assert not plugin.subscriptions
    event = Event("/开启每日推送 原神 25:00", admin=True)
    assert "失败" in (await collect(plugin.subscription(event)))[0]
    assert not plugin.subscriptions


async def test_corrupt_storage_not_overwritten(plugin):
    target = plugin.data_dir / "subscriptions.json"
    target.write_text("{broken")
    with pytest.raises(ValueError):
        await plugin.initialize()
    assert target.read_text() == "{broken"


async def test_failed_storage_keeps_memory(plugin, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(type(plugin.data_dir), "write_text", fail)
    with pytest.raises(OSError):
        await plugin.update_subscription("a", "原神", "08:30", True)
    assert plugin.subscriptions == {}


def test_count_limit():
    assert parse_count("X999", 10) == 10


@pytest.mark.parametrize(
    ("text", "handler"),
    [
        ("/热门cos 原神 x3", "query_command"),
        ("最新coser 崩铁 2", "query_command"),
        ('/搜索cos图 原神 "甘雨 cosplay" x2', "query_command"),
        ("/下载cos 原神", "download"),
        ("/开启每日推送 原神 08:30", "subscription"),
    ],
)
async def test_registered_regex_dispatch(plugin, text, handler):
    from astrbot.core.star.filter.regex import RegexFilter
    from astrbot.core.star.star_handler import star_handlers_registry

    event = Event(text, admin=True)
    event.get_message_str = lambda: event.message_str
    matches = []
    for metadata in star_handlers_registry:
        if metadata.handler_module_path != MihoyoCos.__module__:
            continue
        for rule in metadata.event_filters:
            if isinstance(rule, RegexFilter) and rule.filter(event, {}):
                matches.append(metadata)
    assert [md.handler_name for md in matches] == [handler]
    result = await collect(matches[0].handler(plugin, event))
    assert result and event.stopped


async def test_registered_legacy_command_parsing(plugin):
    from astrbot.core.star.filter.command import CommandFilter
    from astrbot.core.star.star_handler import star_handlers_registry

    event = Event("hoyocos 崩铁流萤 2")
    event.is_at_or_wake_command = True
    event.get_message_str = lambda: event.message_str
    extras = {}
    event.set_extra = extras.__setitem__
    metadata = next(
        md
        for md in star_handlers_registry
        if md.handler_module_path == MihoyoCos.__module__ and md.handler_name == "hoyocos"
    )
    command = next(rule for rule in metadata.event_filters if isinstance(rule, CommandFilter))
    assert command.filter(event, {})
    assert extras["parsed_params"] == {"name": "崩铁流萤", "count": 2}
    assert (
        "已发送" in (await collect(metadata.handler(plugin, event, **extras["parsed_params"])))[0]
    )


async def test_scheduler_runs_push(plugin):
    import asyncio

    completed = asyncio.Event()

    async def send(*args):
        completed.set()

    plugin.context.send_message.side_effect = send
    await plugin.initialize()
    plugin.scheduler.add_job(
        plugin.push,
        "date",
        args=[{"origin": "adapter:GroupMessage:group", "game": "原神", "time": "08:30"}],
    )
    await asyncio.wait_for(completed.wait(), timeout=3)
    assert plugin.client.fetch.await_count == 1
