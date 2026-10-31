from httpx import AsyncClient, Response
from enum import Enum, unique
from typing import overload
import tempfile as tp
import os


@unique
class GameType(Enum):
    """
    游戏类型
    """

    Genshin = 2  # 原神
    Honkai3rd = 1  # 崩坏3
    DBY = 5  # 大别野
    StarRail = 6  # 星穹铁道
    Honkai2 = 3  # 崩坏2
    ZZZ = 8  # 绝区零


@unique
class ForumType(Enum):
    """
    论坛类型
    """

    GenshinCos = 49  # 原神cos
    GenshinPic = 29  # 原神同人图
    Honkai3rdPic = 4  # 崩坏3同人图
    DBYCOS = 47  # 大别野cos
    DBYPIC = 39  # 大别野同人图
    StarRailPic = 56  # 星穹铁道同人图
    StarRailCos = 62  # 星穹铁道cos
    Honkai2Pic = 40  # 崩坏2同人图
    ZZZ = 65  # 绝区零


def get_gids(forum: str) -> GameType:
    """
    根据论坛名获取游戏id
    """
    forum2gids = {
        "GenshinCos": GameType.Genshin,
        "GenshinPic": GameType.Genshin,
        "Honkai3rdPic": GameType.Honkai3rd,
        "DBYCOS": GameType.DBY,
        "DBYPIC": GameType.DBY,
        "StarRailPic": GameType.StarRail,
        "Honkai2Pic": GameType.Honkai2,
        "StarRailCos": GameType.StarRail,
        "ZZZ": GameType.ZZZ,
    }
    return forum2gids[forum]


def has_cos_forum(game: int) -> bool:
    """
    根据游戏id区分是否具有cos分区，用于使用不同的搜索策略
    """
    has_cos = [GameType.Genshin.value, GameType.DBY.value, GameType.StarRail.value]
    return game in has_cos


class Search:
    """
    搜索帖子
    url: https://bbs.mihoyo.com/ys/searchPost?keyword=原神
    """

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.0.0",
        "Referer": "https://bbs.mihoyo.com/",
        "origin": "https://bbs.mihoyo.com",
        "Host": "bbs-api.mihoyo.com",
        "Connection": "keep-alive",
    }
    base_url = "https://bbs-api.mihoyo.com/post/wapi/"

    def __init__(self, forum_id: ForumType, keyword: str, timeout: int = 30) -> None:
        self.api = self.base_url + "searchPosts"
        gametype = get_gids(forum_id.name)
        self.gids = gametype.value
        self.game_name = gametype.name
        self.keyword = keyword
        self.forum_id = forum_id.value
        self.timeout = timeout

    @staticmethod
    def _get_response_name(response: Response, is_good: bool = False) -> list:
        """
        获取响应的帖子名称

        参数:
            - response: 响应
            - is_good: 是否精品
        返回:
            - names
        """
        if is_good:
            posts = response.json()["data"]["posts"]
        else:
            posts = response.json()["data"]["list"]
        return [post["post"]["subject"] for post in posts]

    @staticmethod
    def _get_response_url(response: Response, is_good: bool = False) -> list:
        """
        获取响应的帖子url

        参数:
            - response: 响应
            - is_good: 是否精品
        返回:
            - urls
        """
        if is_good:
            posts = response.json()["data"]["posts"]
        else:
            posts = response.json()["data"]["list"]
        return [image for post in posts for image in post["post"]["images"]]

    def _get_params(self, page_size: int = 10) -> dict:
        params = {
            "gids": self.gids,
            "size": page_size,
            # 如果没有专属cos区，加上"cos"在总分区进行搜索
            "keyword": self.keyword if has_cos_forum(self.gids) else self.keyword + 'cos',
        }
        if has_cos_forum(self.gids):
            params["forum_id"] = self.forum_id
        return params

    async def async_get_urls(self, page_size: int = 10) -> list:
        params = self._get_params(page_size)
        async with AsyncClient(headers=self.headers) as client:
            response = await client.get(self.api, params=params, timeout=self.timeout)
            return self._get_response_url(response, True)

    async def async_get_name(self, page_size: int = 10) -> list:
        params = self._get_params(page_size)
        async with AsyncClient(headers=self.headers) as client:
            response = await client.get(self.api, params=params, timeout=self.timeout)
            return self._get_response_name(response, True)

    async def url2path(self, url: str) -> str:
        async with AsyncClient() as client:
            response = await client.get(url, timeout=self.timeout)
            with tp.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
                f.write(response.content)
            return f.name

    def delete_path(self, path: str) -> None:
        os.remove(path)


class Rank(Search):
    """
    获取排行榜
    url: https://bbs.mihoyo.com/ys/rankList?forum_id=49
    """

    def __init__(self, forum_id: ForumType, timeout: int = 30) -> None:
        super().__init__(forum_id, "")
        self.api = self.base_url + "getImagePostList"
        self.timeout = timeout

    @overload
    def get_params(self, page_size: int) -> dict:
        return {
            "forum_id": self.forum_id,
            "gids": self.gids,
            "page_size": page_size,
            "type": 1,  # 1 日榜 2 周榜 3 月榜
        }

    @overload
    async def async_get_url(self, page_size: int = 10) -> list:
        params = self.get_params(page_size)
        async with AsyncClient(headers=self.headers) as client:
            response = await client.get(self.api, params=params, timeout=self.timeout)
            return self._get_response_url(response, False)


FORUM_TYPE_MAP = {
    "原神": ForumType.GenshinCos,
    "大别野": ForumType.DBYCOS,
    "星穹铁道": ForumType.StarRailCos,
    "崩铁": ForumType.StarRailCos,
    "崩坏3": ForumType.Honkai3rdPic,
    "崩坏三": ForumType.Honkai3rdPic,
    "崩三": ForumType.Honkai3rdPic,
    "绝区零": ForumType.ZZZ,
    "zzz": ForumType.ZZZ,
    "ZZZ": ForumType.ZZZ,
    "崩坏2": ForumType.Honkai2Pic,
    "崩二": ForumType.Honkai2Pic
}
