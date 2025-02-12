import random
import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Image, Plain
from astrbot.api.star import Context, Star, register

from .exception import RequestError
from .mihoyo_cos import FORUM_TYPE_MAP, ForumType, Search


@register(
    "astrbot_plugin_mohoyo_cos",
    "Cvandia",
    "一个从米游社社区获取cos的插件",
    "1.0.0",
    "https://github.com/Cvandia/astrbot_plugin_mohoyo_cos",
)
class MihoyoCos(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.help_str = """
米游社社区cos查询插件
使用方法：
- /hoyocos [角色名] [张数] - 获取指定角色的cos图片
- 使用LLM识别角色名和张数
- /coshelp - 获取帮助信息
例如：
- /hoyocos 钟离 1
- 来2张钟离的cos图片
- /coshelp
        """
        self.config = config
        self.timeout = config.get("timeout", 60)
        if self.timeout == 0:
            self.timeout = 60

    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("hoyocos")
    async def hoyocos(
        self, event: AstrMessageEvent, name: str = "可莉", count: int = 1
    ):
        sender_id = event.get_sender_id() if event.message_obj.group_id else None
        count = max(1, min(count, 5))
        message_chain = [
            Plain(f" 正在搜索{count}张{name}的cos图片"),
        ]
        if sender_id:
            message_chain.insert(0, At(qq=sender_id))

        yield event.chain_result(message_chain)

        forum_type = ForumType.GenshinCos  # Default forum type
        for key, value in FORUM_TYPE_MAP.items():
            if key in name:
                name = re.sub(key, "", name)
                forum_type = value
                break
        cos = Search(forum_type, name, self.timeout)
        try:
            result = await cos.async_get_urls()
        except RequestError as e:
            logger.error(e)
            yield event.plain_result("获取cos图片失败，请稍后再试")
            return
        yield event.plain_result(f"共找到{len(result)}张{name}的cos图片")
        if len(result) == 0:
            return
        random.shuffle(result)
        for i in range(count):
            try:
                path = await cos.url2path(result[i])
                logger.info(f"cos_pic - {path}")
                yield event.image_result(path)
                cos.delete_path(path)
            except Exception as e:
                logger.error(e)
                yield event.plain_result("获取cos图片失败，请稍后再试")

    @filter.command("coshelp")
    async def help(self, event: AstrMessageEvent):
        yield event.plain_result(self.help_str)

    @filter.llm_tool(name="get_cos_pic")
    async def get_cos_pic(self, event: AstrMessageEvent, count: int, name: str):
        """获取cos图片

        Args:
            name (string): 获取照片的角色名
            count (number): 获取的数量
        """
        count = max(1, min(count, 5))
        await self.context.send_message(
            event.unified_msg_origin, Plain(f"正在搜索{count}张{name}的cos图片")
        )

        forum_type = ForumType.GenshinCos  # Default forum type
        for key, value in FORUM_TYPE_MAP.items():
            if key in name:
                name = re.sub(key, "", name)
                forum_type = value
                break
        cos = Search(forum_type, name, self.timeout)
        result = await cos.async_get_urls()
        count = min(count, len(result))
        await self.context.send_message(
            event.unified_msg_origin, Plain(f"共找到{len(result)}张{name}的cos图片")
        )
        if len(result) == 0:
            return
        random.shuffle(result)
        for i in range(count):
            try:
                path = await cos.url2path(result[i])
                logger.info(f"cos_pic - {path}")
                yield event.image_result(path)
                cos.delete_path(path)
            except Exception as e:
                logger.error(e)
                await self.context.send_message(
                    event.unified_msg_origin, Plain("获取cos图片失败，请稍后再试")
                )
        return "已发送图片，请查收"
