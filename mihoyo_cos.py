from httpx import AsyncClient, Response
from enum import Enum, unique
from typing import overload


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
        return {
            "gids": self.gids,
            "size": page_size,
            "keyword": self.keyword,
            "forum_id": self.forum_id,
        }

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
}
