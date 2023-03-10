from dataclasses import dataclass
import aiohttp
import requests
import asyncio
from bs4 import BeautifulSoup
import base64

from .driver import Episodes, BaseDriver, BaseDriverData, get as cget
from .manga import Manga, SimpleManga


@dataclass
class MHGData(BaseDriverData):
    episodes_ids: list
    serial_len: int
    manga_id: str

    @property
    def dict(self):
        return {
            "episodes_ids": self.episodes_ids,
            "serial_len": self.serial_len,
            "manga_id": self.manga_id,
        }

    @staticmethod
    def from_dict(dict):
        return MHGData(
            episodes_ids=dict["episodes_ids"],
            serial_len=dict["serial_len"],
            manga_id=dict["manga_id"],
        )

    @staticmethod
    def from_compressed(compressed):
        return MHGData._from_compresssed(MHGData, compressed)


class MHG(BaseDriver):
    identifier = "MHG"
    categories = {
        "rexue": Manga.categories_list[0],
        "aiqing": Manga.categories_list[1],
        "xiaoyuan": Manga.categories_list[2],
        "baihe": Manga.categories_list[3],
        "danmei": Manga.categories_list[4],
        "maoxian": Manga.categories_list[5],
        "hougong": Manga.categories_list[6],
        "kehuan": Manga.categories_list[7],
        "zhanzheng": Manga.categories_list[8],
        "xuanyi": Manga.categories_list[9],
        "tuili": Manga.categories_list[10],
        "gaoxiao": Manga.categories_list[11],
        "mohuan": Manga.categories_list[12],
        "mofa": Manga.categories_list[13],
        "kongbu": Manga.categories_list[14],
        "shengui": Manga.categories_list[15],
        "lishi": Manga.categories_list[16],
        "jingji": Manga.categories_list[18],
        "jizhan": Manga.categories_list[20],
        "weiniang": Manga.categories_list[21],
    }
    supported_categories = list(categories.values())
    support_recommendation = False

    @staticmethod
    def get_details(ids: list):
        if len(ids) > 6:
            length = len(ids)
            return MHG.get_details(ids[: length // 2]) + MHG.get_details(
                ids[length // 2 :]
            )

        async def extract_details(session, id):
            text = cget(session, f"https://www.manhuagui.com/comic/{id}/")

            soup = BeautifulSoup(text, "lxml")
            thumbnail = soup.find("p", class_="hcover")
            is_end = "finish" in thumbnail.find_all("span")[-1]["class"]
            thumbnail = "https:" + thumbnail.find("img")["src"]
            title = soup.find("div", class_="book-title").find("h1").text.strip()
            info = soup.find("ul", class_="detail-list cf").find_all("li")
            categories = [
                MHG.categories[i["href"][6:-1]]
                for i in info[1].find("span").find_all("a")
                if i["href"][6:-1] in MHG.categories.keys()
            ]
            author = [i.text.strip() for i in info[1].find_all("span")[1].find_all("a")]
            description = soup.find("div", id="intro-cut").text.strip()

            chapter_list = soup.find_all("div", class_="chapter-list")

            def extract_episode(raw):
                try:
                    episodes = {}
                    for i in raw.find_all("ul"):
                        temp_dict = {}
                        for j in i.find_all("a"):
                            temp_dict[j["title"].strip()] = j["href"].replace(id, "")[
                                8:-5
                            ]
                        episodes = {**temp_dict, **episodes}
                    return list(episodes.keys()), list(episodes.values())
                except:
                    return [], []

            serial, episodes_ids = extract_episode(chapter_list[0])
            extra = []
            for i in chapter_list[1:]:
                result = extract_episode(i)
                extra.extend(result[0])
                episodes_ids.extend(result[1])

            return Manga(
                driver=MHG,
                driver_data=MHGData(
                    manga_id=id,
                    episodes_ids=episodes_ids,
                    serial_len=len(serial),
                ),
                id=id,
                episodes=Episodes(serial=serial, extra=extra),
                thumbnail=thumbnail,
                title=title,
                author=author,
                description=description,
                is_end=is_end,
                categories=categories,
            )

        async def fetch_details():
            async with aiohttp.ClientSession() as session:
                manga = []
                for i in ids:
                    manga.append(asyncio.ensure_future(extract_details(session, i)))
                return await asyncio.gather(*manga)

        return asyncio.run(fetch_details())

    @staticmethod
    def get_episode(episode: int, is_extra: bool, data: str):
        data = MHGData.from_compressed(data)
        id = data.episodes_ids[episode + (data.serial_len if is_extra else 0)]
        details = get(f"https://www.manhuagui.com/comic/{data.manga_id}/{id}.html")
        urls = list(
            map(
                lambda x: f"https://i.hamreus.com{details['path']}{x}", details["files"]
            )
        )

        def get_img(urls):
            async def extract_img(session, url):
                async with session.get(url) as resp:
                    return (
                        "data:image/webp;charset=utf-8;base64,"
                        + base64.b64encode(await resp.read()).decode()
                    )

            async def fetch_imgs():
                async with aiohttp.ClientSession(
                    headers={"referer": "https://www.manhuagui.com"}
                ) as session:
                    manga = []
                    for i in urls:
                        manga.append(asyncio.ensure_future(extract_img(session, i)))
                    return await asyncio.gather(*manga)

            return asyncio.run(fetch_imgs())

        return get_img(urls)

    @staticmethod
    def get_list(category=None, page=None):
        category = (
            ""
            if category not in MHG.supported_categories
            else list(MHG.categories.keys())[
                list(MHG.categories.values()).index(category)
            ]
            + "/"
        )
        page = f"index_p{page if page else 1}.html"

        response = requests.get(
            f"https://www.manhuagui.com/list/{category}{page}",
        )
        soup = BeautifulSoup(response.text, "lxml")

        result = []
        for i in soup.find("ul", id="contList").find_all("li"):
            details = i.find("a")
            id = details["href"][7:-1]
            try:
                src = details.find("img")["src"]
            except:
                src = details.find("img")["data-src"]
            thumbnail = "https:" + src
            latest = (
                details.find("span", class_="tt")
                .text.replace("?????????", "")
                .replace("[???]", "")
                .strip()
            )
            is_end = "fd" in details.find_all("span")[-1]["class"]
            title = i.find("p").find("a").text.strip()

            result.append(
                SimpleManga(
                    driver=MHG,
                    id=id,
                    title=title,
                    thumbnail=thumbnail,
                    is_end=is_end,
                    latest=latest,
                    author=[],
                )
            )

        return result

    @staticmethod
    def search(text, page=1):
        response = requests.get(
            f"https://www.manhuagui.com/s/{text}_p{page}.html",
        )
        soup = BeautifulSoup(response.text, "lxml")

        result = []
        for i in soup.find_all("li", class_="cf"):
            details = i.find("a")
            id = details["href"][7:-1]
            try:
                src = details.find("img")["src"]
            except:
                src = details.find("img")["data-src"]
            thumbnail = "https:" + src
            title = i.find("dt").find("a").text.strip()
            is_end = i.find("dd").find("span")
            latest = is_end.find("a").text.strip()
            is_end = is_end.find("span").text == "?????????"
            author = list(
                map(
                    lambda x: x.text.strip(),
                    i.find_all("dd", class_="tags")[-2].find("span").find_all("a"),
                )
            )

            result.append(
                SimpleManga(
                    driver=MHG,
                    id=id,
                    title=title,
                    thumbnail=thumbnail,
                    is_end=is_end,
                    latest=latest,
                    author=author,
                )
            )

        return result


# Development by HSSLCreative
# link: https://github.com/HSSLC/manhuagui-dlr
# Modified for this project

import re, json, lzstring

lz = lzstring.LZString()

# get.py
def get(url):
    try:
        res = requests.get(url)
    except:
        return False
    m = re.match(r"^.*\}\(\'(.*)\',(\d*),(\d*),\'([\w|\+|\/|=]*)\'.*$", res.text)
    return packed(
        m.group(1),
        int(m.group(2)),
        int(m.group(3)),
        lz.decompressFromBase64(m.group(4)).split("|"),
    )


# parse.py
def packed(functionFrame, a, c, data):
    def e(innerC):
        return ("" if innerC < a else e(int(innerC / a))) + (
            chr(innerC % a + 29) if innerC % a > 35 else tr(innerC % a, 36)
        )

    c -= 1
    d = {}
    while c + 1:
        d[e(c)] = e(c) if data[c] == "" else data[c]
        c -= 1
    pieces = re.split(r"(\b\w+\b)", functionFrame)
    js = "".join([d[x] if x in d else x for x in pieces]).replace("\\'", "'")
    return json.loads(re.search(r"^.*\((\{.*\})\).*$", js).group(1))


# tran.py
def itr(value, num):
    d = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "" if value <= 0 else itr(int(value / num), num) + d[value % num]


def tr(value, num):
    tmp = itr(value, num)
    return "0" if tmp == "" else tmp
