import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# 基础设置
# =========================================================

DATA_FILE = Path("data/news.json")

MAX_ITEMS = 500
KEEP_DAYS = 45

# 每次 Action 最多额外访问多少篇文章获取封面图
# 防止第一次运行请求过多
IMAGE_FETCH_LIMIT = 60


# =========================================================
# 数据源
# =========================================================

AIBASE_URL = "https://news.aibase.com/zh/news"

QBITAI_URL = (
    "https://www.qbitai.com/category/%E8%B5%84%E8%AE%AF"
)

STD_BREAKTHROUGH_URL = (
    "https://www.stdaily.com/web/spxw/node_706.html"
)

SCIENCENET_URL = (
    "https://news.sciencenet.cn/"
)

DEEPTECH_URL = (
    "https://www.deeptechchina.com/"
)

SCIENTIFIC_DATA_RSS = (
    "https://www.nature.com/sdata.rss"
)

NATURE_CITIES_RSS = (
    "https://www.nature.com/natcities.rss"
)

SCIENTIFIC_DATA_HTML = (
    "https://www.nature.com/sdata/articles"
)

NATURE_CITIES_HTML = (
    "https://www.nature.com/natcities/articles"
)


# =========================================================
# HTTP Session
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language":
        "zh-CN,zh;q=0.9,en;q=0.8",
}


def build_session():

    session = requests.Session()

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504,
        ],
        allowed_methods=["GET"],
    )

    adapter = HTTPAdapter(
        max_retries=retry
    )

    session.mount(
        "https://",
        adapter
    )

    session.mount(
        "http://",
        adapter
    )

    session.headers.update(
        HEADERS
    )

    return session


SESSION = build_session()


# =========================================================
# 突破关键词
# =========================================================

BREAKTHROUGH_KEYWORDS = [

    "世界首次",
    "全球首次",
    "国际首次",
    "国内首次",
    "我国首次",

    "首次实现",
    "首次发现",
    "首次证实",
    "首次观测",
    "首次揭示",
    "首次完成",
    "首次构建",
    "首次研制",

    "全球首个",
    "世界首个",
    "国内首个",
    "我国首个",
    "首个",

    "首例",
    "首台",
    "首套",
    "首颗",
    "首款",
    "首现",

    "刷新世界纪录",
    "刷新纪录",
    "世界纪录",
    "新纪录",
    "创纪录",

    "世界第一",
    "全球第一",
    "世界最大",
    "全球最大",

    "重大突破",
    "关键突破",
    "实现突破",
    "取得突破",
    "新突破",

    "重大进展",
    "重要进展",

    "里程碑",
    "问世",
    "面世",
    "诞生",
    "攻克",
    "破解",

    "新发现",
    "新方法",
    "新策略",
]


# =========================================================
# AI / 工具相关关键词
# =========================================================

AI_KEYWORDS = [

    "ai",
    "人工智能",
    "大模型",
    "模型",
    "智能体",
    "agent",

    "chatgpt",
    "openai",
    "claude",
    "anthropic",
    "gemini",
    "deepseek",
    "qwen",
    "千问",
    "豆包",
    "manus",

    "开源",
    "发布",
    "推出",
    "上线",
    "更新",
    "新功能",

    "工具",
    "平台",
    "api",

    "自动化",
    "浏览器",

    "搜索",
    "文献",
    "论文",
    "写作",

    "代码",
    "编程",

    "数据分析",
    "可视化",

    "视频",
    "图像",
]


# =========================================================
# GitHub
# =========================================================

GITHUB_TOPICS = [

    '"research agent"',
    '"paper agent"',
    '"literature review" AI',
    '"academic writing" AI',
    '"scientific writing" AI',

    '"research workflow"',
    '"zotero" AI',

    '"data visualization" AI',
    '"scientific visualization"',

    '"browser agent"',

    '"geoai"',
    '"geospatial" AI',
    '"GIS" agent',
    '"remote sensing" AI',
]


GITHUB_POSITIVE = [

    "agent",
    "ai",
    "llm",

    "research",
    "paper",
    "literature",
    "academic",
    "scientific",

    "zotero",
    "citation",

    "workflow",
    "visualization",
    "automation",
    "browser",

    "geoai",
    "geospatial",
    "gis",
    "remote sensing",
    "satellite",
]


GITHUB_NEGATIVE = [

    "lipid",
    "protein",
    "genome",
    "genomic",
    "clinical",
    "cancer",
    "tumor",

    "molecule",
    "molecular",
    "drug discovery",

    "crypto",
    "cryptocurrency",
    "casino",
    "betting",

    "game cheat",
    "hack game",
]


# =========================================================
# 基础文本
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = BeautifulSoup(
        str(text),
        "html.parser"
    ).get_text(
        " ",
        strip=True
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def contains_chinese(text):

    if not text:
        return False

    return bool(
        re.search(
            r"[\u4e00-\u9fff]",
            text
        )
    )


# =========================================================
# 标题精炼
# =========================================================

def refine_title(title):

    title = clean_text(
        title
    )

    if not title:
        return ""

    # 删除 #1 #2
    title = re.sub(
        r"^#\s*\d+\s*",
        "",
        title
    )

    # 删除栏目头
    title = re.sub(
        r"^(AI日报|AI资讯)[：:\s]*",
        "",
        title,
        flags=re.I
    )

    # 删除营销前缀
    patterns = [

        r"^刚刚[！!，,:：\s]*",
        r"^重磅[！!，,:：\s]*",
        r"^震撼[！!，,:：\s]*",
        r"^炸裂[！!，,:：\s]*",
        r"^官宣[！!，,:：\s]*",
        r"^独家[！!，,:：\s]*",
    ]

    for pattern in patterns:

        title = re.sub(
            pattern,
            "",
            title
        )

    title = re.sub(
        r"\s+",
        " ",
        title
    )

    return title.strip(
        " -—_|｜"
    )


# =========================================================
# ID
# =========================================================

def make_id(
    source,
    title,
    url
):

    raw = (
        f"{source}|"
        f"{title}|"
        f"{url}"
    )

    return hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:16]


# =========================================================
# 日期
# =========================================================

def parse_date(value):

    if not value:

        return datetime.now(
            timezone.utc
        ).isoformat()

    try:

        dt = dtparser.parse(
            value
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.isoformat()

    except Exception:

        return datetime.now(
            timezone.utc
        ).isoformat()


def extract_date_from_text(text):

    if not text:
        return None

    patterns = [

        # 2026-08-14 12:30
        r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
        r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)",

        # 14 Aug 2026
        r"(\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|"
        r"Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{4})",

        # 2026年8月14日
        r"(\d{4}年\d{1,2}月\d{1,2}日"
        r"(?:\s*\d{1,2}:\d{2})?)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.I
        )

        if match:

            return match.group(1)

    return None


# =========================================================
# 突破判断
# =========================================================

def is_breakthrough(text):

    text = clean_text(
        text
    )

    return any(
        keyword in text
        for keyword
        in BREAKTHROUGH_KEYWORDS
    )


# =========================================================
# URL 图片
# =========================================================

def normalize_image_url(
    image_url,
    page_url
):

    if not image_url:
        return ""

    image_url = image_url.strip()

    if image_url.startswith(
        "data:"
    ):
        return ""

    image_url = urljoin(
        page_url,
        image_url
    )

    parsed = urlparse(
        image_url
    )

    if parsed.scheme not in (
        "http",
        "https"
    ):
        return ""

    return image_url


def extract_image_from_container(
    container,
    page_url
):

    if container is None:
        return ""

    image = container.find(
        "img"
    )

    if not image:
        return ""

    candidate = (
        image.get("data-src")
        or image.get("data-original")
        or image.get("src")
        or ""
    )

    return normalize_image_url(
        candidate,
        page_url
    )


# =========================================================
# 获取文章 OG 图片 / description
# =========================================================

PAGE_META_CACHE = {}


def fetch_page_meta(url):

    if not url:
        return {
            "image_url": "",
            "description": "",
        }

    if url in PAGE_META_CACHE:

        return PAGE_META_CACHE[
            url
        ]

    result = {
        "image_url": "",
        "description": "",
    }

    try:

        response = SESSION.get(
            url,
            timeout=12
        )

        response.raise_for_status()

        if not response.encoding:

            response.encoding = (
                response.apparent_encoding
                or "utf-8"
            )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        # -------------------------
        # OG image
        # -------------------------

        image_selectors = [

            'meta[property="og:image"]',
            'meta[property="og:image:secure_url"]',
            'meta[name="twitter:image"]',
            'meta[property="twitter:image"]',
            'meta[itemprop="image"]',
        ]

        for selector in image_selectors:

            node = soup.select_one(
                selector
            )

            if node:

                image_url = (
                    node.get("content")
                    or ""
                )

                image_url = (
                    normalize_image_url(
                        image_url,
                        url
                    )
                )

                if image_url:

                    result[
                        "image_url"
                    ] = image_url

                    break


        # -------------------------
        # description
        # -------------------------

        description_selectors = [

            'meta[property="og:description"]',
            'meta[name="description"]',
            'meta[name="twitter:description"]',
        ]

        for selector in description_selectors:

            node = soup.select_one(
                selector
            )

            if node:

                description = clean_text(
                    node.get("content")
                )

                if description:

                    result[
                        "description"
                    ] = description

                    break

    except Exception as e:

        print(
            "Page meta failed:",
            url,
            e
        )


    PAGE_META_CACHE[
        url
    ] = result

    return result


# =========================================================
# 创建 item
# =========================================================

def make_item(
    title,
    source,
    category,
    url,
    published_at=None,
    summary="",
    priority="B",
    language="zh",
    display_title=None,
    image_url="",
    is_breakthrough_item=False,
    meta=None,
):

    return {

        "id":
            make_id(
                source,
                title,
                url
            ),

        "title":
            clean_text(
                title
            ),

        "display_title":
            clean_text(
                display_title
                or refine_title(title)
            ),

        "source":
            source,

        "category":
            category,

        "url":
            url,

        "published_at":
            parse_date(
                published_at
            ),

        "detected_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "summary":
            clean_text(
                summary
            ),

        "image_url":
            image_url or "",

        "priority":
            priority,

        "language":
            language,

        "is_breakthrough":
            bool(
                is_breakthrough_item
            ),

        "meta":
            meta or {},
    }


# =========================================================
# 上下文
# =========================================================

def extract_context(
    node,
    title,
    max_len=220
):

    parent = node

    for _ in range(4):

        if parent is None:
            break

        if getattr(
            parent,
            "name",
            None
        ) in {
            "article",
            "li",
        }:
            break

        parent = parent.parent


    if parent is None:

        parent = node.parent


    if parent is None:
        return ""


    text = clean_text(
        parent.get_text(
            " ",
            strip=True
        )
    )

    if title:

        text = text.replace(
            title,
            "",
            1
        ).strip()

    if len(text) > max_len:

        text = (
            text[:max_len]
            .rstrip()
            + "…"
        )

    return text


# =========================================================
# AI判断
# =========================================================

def useful_ai_text(text):

    text = clean_text(
        text
    ).lower()

    return any(
        keyword.lower()
        in text
        for keyword
        in AI_KEYWORDS
    )


def ai_priority(text):

    text_lower = clean_text(
        text
    ).lower()

    if is_breakthrough(
        text
    ):
        return "A"

    strong = [
        "开源",
        "免费",
        "发布",
        "推出",
        "上线",
        "agent",
        "智能体",
        "api",
    ]

    if any(
        keyword in text_lower
        for keyword
        in strong
    ):
        return "A"

    return "B"


# =========================================================
# AIBase
# → AI变现
# =========================================================

def fetch_aibase():

    print(
        "Fetching AIBase..."
    )

    results = []
    seen = set()

    try:

        response = SESSION.get(
            AIBASE_URL,
            timeout=30
        )

        response.raise_for_status()

        response.encoding = "utf-8"

    except Exception as e:

        print(
            "AIBase failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    for node in soup.find_all(
        "a",
        href=True
    ):

        href = node.get(
            "href",
            ""
        )

        if not re.search(
            r"/zh/news/\d+",
            href
        ):
            continue


        # 优先寻找真正的标题元素
        heading = node.find(
            [
                "h2",
                "h3",
                "h4",
            ]
        )

        if heading:

            title = clean_text(
                heading.get_text(
                    " ",
                    strip=True
                )
            )

        else:

            title = clean_text(
                node.get_text(
                    " ",
                    strip=True
                )
            )


        if not (
            contains_chinese(title)
            and
            8 <= len(title) <= 120
        ):
            continue


        url = urljoin(
            AIBASE_URL,
            href
        )


        if url in seen:
            continue


        context = extract_context(
            node,
            title
        )


        if not useful_ai_text(
            f"{title} {context}"
        ):
            continue


        seen.add(
            url
        )


        parent = node.find_parent(
            [
                "article",
                "li",
            ]
        )

        image_url = (
            extract_image_from_container(
                parent,
                AIBASE_URL
            )
        )


        breakthrough = (
            is_breakthrough(
                f"{title} {context}"
            )
        )


        results.append(

            make_item(

                title=title,

                source="AIBase",

                category="AI变现",

                url=url,

                summary=context,

                priority=
                    ai_priority(
                        f"{title} {context}"
                    ),

                language="zh",

                image_url=
                    image_url,

                is_breakthrough_item=
                    breakthrough,
            )
        )


    print(
        "AIBase:",
        len(results)
    )

    return results[:40]


# =========================================================
# 量子位
# 普通工具 → 提效工具
# 突破 → 前沿动态
# =========================================================

def fetch_qbitai():

    print(
        "Fetching 量子位..."
    )

    results = []
    seen = set()

    try:

        response = SESSION.get(
            QBITAI_URL,
            timeout=30
        )

        response.raise_for_status()

        response.encoding = (
            response.apparent_encoding
            or "utf-8"
        )

    except Exception as e:

        print(
            "量子位 failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    for node in soup.select(
        "h2 a, h3 a, h4 a"
    ):

        title = clean_text(
            node.get_text(
                " ",
                strip=True
            )
        )

        href = node.get(
            "href",
            ""
        )

        if not (
            contains_chinese(title)
            and
            8 <= len(title) <= 120
            and href
        ):
            continue


        url = urljoin(
            QBITAI_URL,
            href
        )


        if (
            "qbitai.com"
            not in urlparse(
                url
            ).netloc
        ):
            continue


        if url in seen:
            continue


        context = extract_context(
            node,
            title
        )


        if not useful_ai_text(
            f"{title} {context}"
        ):
            continue


        seen.add(
            url
        )


        parent = node.find_parent(
            [
                "article",
                "li",
            ]
        )

        image_url = (
            extract_image_from_container(
                parent,
                QBITAI_URL
            )
        )


        breakthrough = (
            is_breakthrough(
                f"{title} {context}"
            )
        )


        category = (
            "前沿动态"
            if breakthrough
            else "提效工具"
        )


        results.append(

            make_item(

                title=title,

                source="量子位",

                category=category,

                url=url,

                summary=context,

                priority=
                    (
                        "A"
                        if breakthrough
                        else ai_priority(
                            f"{title} {context}"
                        )
                    ),

                language="zh",

                image_url=
                    image_url,

                is_breakthrough_item=
                    breakthrough,
            )
        )


    print(
        "量子位:",
        len(results)
    )

    return results[:40]


# =========================================================
# 科技日报：科技新突破
# → 前沿动态
# =========================================================

def fetch_stdaily():

    print(
        "Fetching 科技日报..."
    )

    results = []
    seen = set()

    try:

        response = SESSION.get(
            STD_BREAKTHROUGH_URL,
            timeout=30
        )

        response.raise_for_status()

        response.encoding = (
            response.apparent_encoding
            or "utf-8"
        )

    except Exception as e:

        print(
            "科技日报 failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    for heading in soup.find_all(
        [
            "h2",
            "h3",
            "h4",
        ]
    ):

        node = heading.find(
            "a",
            href=True
        )

        if not node:
            continue


        title = clean_text(
            node.get_text(
                " ",
                strip=True
            )
        )


        if not (
            contains_chinese(title)
            and
            6 <= len(title) <= 120
        ):
            continue


        url = urljoin(
            STD_BREAKTHROUGH_URL,
            node.get("href")
        )


        if (
            "stdaily.com"
            not in urlparse(
                url
            ).netloc
        ):
            continue


        if url in seen:
            continue


        seen.add(
            url
        )


        context = extract_context(
            heading,
            title
        )


        published = (
            extract_date_from_text(
                context
            )
        )


        parent = heading.find_parent(
            [
                "article",
                "li",
            ]
        )

        image_url = (
            extract_image_from_container(
                parent,
                STD_BREAKTHROUGH_URL
            )
        )


        results.append(

            make_item(

                title=title,

                source="科技日报",

                category="前沿动态",

                url=url,

                published_at=
                    published,

                summary="",

                priority="A",

                language="zh",

                image_url=
                    image_url,

                is_breakthrough_item=
                    is_breakthrough(
                        f"{title} {context}"
                    ),
            )
        )


    print(
        "科技日报:",
        len(results)
    )

    return results[:35]


# =========================================================
# 科学网
# 只保留突破信息
# =========================================================

def fetch_sciencenet():

    print(
        "Fetching 科学网..."
    )

    results = []
    seen = set()

    try:

        response = SESSION.get(
            SCIENCENET_URL,
            timeout=30
        )

        response.raise_for_status()

        response.encoding = (
            response.apparent_encoding
            or "utf-8"
        )

    except Exception as e:

        print(
            "科学网 failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    for node in soup.find_all(
        "a",
        href=True
    ):

        href = node.get(
            "href",
            ""
        )

        url = urljoin(
            SCIENCENET_URL,
            href
        )


        if (
            "news.sciencenet.cn"
            not in urlparse(
                url
            ).netloc
        ):
            continue


        if not re.search(
            r"/htmlnews/",
            url
        ):
            continue


        title = clean_text(
            node.get_text(
                " ",
                strip=True
            )
        )


        if not (
            contains_chinese(title)
            and
            6 <= len(title) <= 120
        ):
            continue


        if url in seen:
            continue


        context = extract_context(
            node,
            title
        )


        combined = (
            f"{title} {context}"
        )


        if not is_breakthrough(
            combined
        ):
            continue


        seen.add(
            url
        )


        published = (
            extract_date_from_text(
                context
            )
        )


        parent = node.find_parent(
            [
                "article",
                "li",
            ]
        )

        image_url = (
            extract_image_from_container(
                parent,
                SCIENCENET_URL
            )
        )


        results.append(

            make_item(

                title=title,

                source="科学网",

                category="前沿动态",

                url=url,

                published_at=
                    published,

                summary=context,

                priority="A",

                language="zh",

                image_url=
                    image_url,

                is_breakthrough_item=True,
            )
        )


    print(
        "科学网:",
        len(results)
    )

    return results[:35]


# =========================================================
# DeepTech
# 仅突破类
# =========================================================

def fetch_deeptech():

    print(
        "Fetching DeepTech..."
    )

    results = []
    seen = set()

    try:

        response = SESSION.get(
            DEEPTECH_URL,
            timeout=30
        )

        response.raise_for_status()

        response.encoding = (
            response.apparent_encoding
            or "utf-8"
        )

    except Exception as e:

        print(
            "DeepTech failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    for node in soup.find_all(
        "a",
        href=True
    ):

        title = clean_text(
            node.get_text(
                " ",
                strip=True
            )
        )

        href = node.get(
            "href",
            ""
        )


        if not (
            contains_chinese(title)
            and
            8 <= len(title) <= 120
            and href
        ):
            continue


        url = urljoin(
            DEEPTECH_URL,
            href
        )


        if (
            "deeptechchina.com"
            not in urlparse(
                url
            ).netloc
        ):
            continue


        if url in seen:
            continue


        context = extract_context(
            node,
            title
        )


        if not is_breakthrough(
            f"{title} {context}"
        ):
            continue


        seen.add(
            url
        )


        parent = node.find_parent(
            [
                "article",
                "li",
            ]
        )

        image_url = (
            extract_image_from_container(
                parent,
                DEEPTECH_URL
            )
        )


        results.append(

            make_item(

                title=title,

                source="DeepTech深科技",

                category="前沿动态",

                url=url,

                summary=context,

                priority="A",

                language="zh",

                image_url=
                    image_url,

                is_breakthrough_item=True,
            )
        )


    print(
        "DeepTech:",
        len(results)
    )

    return results[:25]


# =========================================================
# Nature RSS 图片
# =========================================================

def extract_feed_image(
    entry
):

    media_content = entry.get(
        "media_content"
    )

    if media_content:

        try:

            url = media_content[
                0
            ].get(
                "url",
                ""
            )

            if url:
                return url

        except Exception:
            pass


    media_thumbnail = entry.get(
        "media_thumbnail"
    )

    if media_thumbnail:

        try:

            url = media_thumbnail[
                0
            ].get(
                "url",
                ""
            )

            if url:
                return url

        except Exception:
            pass


    return ""


# =========================================================
# Nature HTML fallback
# =========================================================

def fetch_nature_html(
    page_url,
    source
):

    results = []

    try:

        response = SESSION.get(
            page_url,
            params={
                "year":
                    datetime.now().year,

                "sort":
                    "PubDate",
            },
            timeout=40
        )

        response.raise_for_status()

    except Exception as e:

        print(
            source,
            "HTML fallback failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )


    cards = soup.select(
        "li.app-article-list-row__item"
    )


    if not cards:

        cards = soup.select(
            "article"
        )


    for card in cards:

        link = card.select_one(
            'h3 a[href*="/articles/"], '
            'h2 a[href*="/articles/"]'
        )

        if not link:
            continue


        title = clean_text(
            link.get_text(
                " ",
                strip=True
            )
        )


        url = urljoin(
            "https://www.nature.com",
            link.get(
                "href",
                ""
            )
        )


        if not title or not url:
            continue


        text = clean_text(
            card.get_text(
                " ",
                strip=True
            )
        )


        published = (
            extract_date_from_text(
                text
            )
        )


        summary = ""

        for p in card.find_all(
            "p"
        ):

            candidate = clean_text(
                p.get_text(
                    " ",
                    strip=True
                )
            )

            if len(
                candidate
            ) >= 40:

                summary = candidate

                break


        image_url = (
            extract_image_from_container(
                card,
                page_url
            )
        )


        results.append(

            make_item(

                title=title,

                source=source,

                category="期刊论文",

                url=url,

                published_at=
                    published,

                summary=summary,

                priority="A",

                language="en",

                image_url=
                    image_url,

                is_breakthrough_item=
                    False,
            )
        )


    return results


# =========================================================
# Nature RSS
# =========================================================

def fetch_nature_journal(
    feed_url,
    html_url,
    source
):

    print(
        "Fetching",
        source,
        "..."
    )

    results = []


    try:

        feed = feedparser.parse(
            feed_url
        )


        for entry in feed.entries:

            title = clean_text(
                entry.get(
                    "title",
                    ""
                )
            )

            url = entry.get(
                "link",
                ""
            )


            if not title or not url:
                continue


            summary = clean_text(
                entry.get(
                    "summary",
                    ""
                )
            )


            published = (
                entry.get(
                    "published"
                )
                or
                entry.get(
                    "updated"
                )
            )


            image_url = (
                extract_feed_image(
                    entry
                )
            )


            results.append(

                make_item(

                    title=title,

                    source=source,

                    category="期刊论文",

                    url=url,

                    published_at=
                        published,

                    summary=summary,

                    priority="A",

                    language="en",

                    image_url=
                        image_url,

                    is_breakthrough_item=
                        False,
                )
            )


    except Exception as e:

        print(
            source,
            "RSS failed:",
            e
        )


    # RSS失效时自动回退网页
    if not results:

        results = (
            fetch_nature_html(
                html_url,
                source
            )
        )


    print(
        source,
        ":",
        len(results)
    )

    return results[:40]


# =========================================================
# GitHub
# =========================================================

def github_relevant(
    full_name,
    description
):

    text = (
        f"{full_name} "
        f"{description}"
    ).lower()


    if any(
        word in text
        for word
        in GITHUB_NEGATIVE
    ):

        return False


    return any(
        word in text
        for word
        in GITHUB_POSITIVE
    )


def github_priority(
    stars,
    created_at
):

    try:

        created = dtparser.parse(
            created_at
        )

        if created.tzinfo is None:

            created = created.replace(
                tzinfo=timezone.utc
            )


        days = max(
            1,
            (
                datetime.now(
                    timezone.utc
                )
                - created
            ).days + 1
        )


        speed = (
            stars / days
        )


    except Exception:

        speed = 0


    if (
        stars >= 500
        or speed >= 50
    ):
        return "A"


    if (
        stars >= 100
        or speed >= 10
    ):
        return "B"


    return "C"


def github_display_title(
    full_name,
    description
):

    repo_name = (
        full_name.split("/")[-1]
        if full_name
        else "GitHub项目"
    )


    description = clean_text(
        description
    )


    if not description:
        return repo_name


    first = re.split(
        r"[.!?。！？]",
        description
    )[0].strip()


    if len(first) > 75:

        first = (
            first[:72]
            .rstrip()
            + "..."
        )


    return (
        f"{repo_name}："
        f"{first}"
    )


def fetch_github():

    print(
        "Fetching GitHub..."
    )

    results = []
    seen = set()


    token = os.environ.get(
        "GITHUB_TOKEN"
    )


    headers = {

        "Accept":
            "application/vnd.github+json",

        "User-Agent":
            "icat-research-radar",
    }


    if token:

        headers[
            "Authorization"
        ] = (
            f"Bearer {token}"
        )


    since = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            days=21
        )
    ).strftime(
        "%Y-%m-%d"
    )


    for topic in GITHUB_TOPICS:

        query = (
            f"{topic} "
            f"in:name,description,readme "
            f"created:>={since} "
            f"archived:false"
        )


        try:

            response = SESSION.get(

                "https://api.github.com/"
                "search/repositories",

                headers=headers,

                params={
                    "q":
                        query,

                    "sort":
                        "stars",

                    "order":
                        "desc",

                    "per_page":
                        10,
                },

                timeout=30
            )


            response.raise_for_status()

            data = response.json()


        except Exception as e:

            print(
                "GitHub failed:",
                topic,
                e
            )

            continue


        for repo in data.get(
            "items",
            []
        ):

            url = repo.get(
                "html_url"
            )


            if (
                not url
                or url in seen
            ):
                continue


            stars = repo.get(
                "stargazers_count",
                0
            )


            if stars < 30:
                continue


            full_name = repo.get(
                "full_name",
                ""
            )


            description = (
                repo.get(
                    "description"
                )
                or ""
            )


            if not github_relevant(
                full_name,
                description
            ):
                continue


            seen.add(
                url
            )


            created_at = repo.get(
                "created_at"
            )


            results.append(

                make_item(

                    title=
                        full_name,

                    display_title=
                        github_display_title(
                            full_name,
                            description
                        ),

                    source="GitHub",

                    category="提效工具",

                    url=url,

                    published_at=
                        created_at,

                    summary=
                        description,

                    priority=
                        github_priority(
                            stars,
                            created_at
                        ),

                    language="en",

                    image_url="",

                    is_breakthrough_item=
                        False,

                    meta={
                        "stars":
                            stars,

                        "language":
                            repo.get(
                                "language"
                            ),
                    },
                )
            )


    print(
        "GitHub:",
        len(results)
    )

    return results


# =========================================================
# 旧数据
# =========================================================

def load_old_data():

    if not DATA_FILE.exists():

        return []


    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(
                f
            )


        return data.get(
            "items",
            []
        )


    except Exception:

        return []


# =========================================================
# 旧分类迁移
# =========================================================

def normalize_old_items(
    items
):

    output = []


    for item in items:

        source = item.get(
            "source",
            ""
        )


        text = (
            f"{item.get('title', '')} "
            f"{item.get('summary', '')}"
        )


        if source == "AIBase":

            item[
                "category"
            ] = "AI变现"


        elif source == "量子位":

            item[
                "category"
            ] = (
                "前沿动态"
                if is_breakthrough(
                    text
                )
                else "提效工具"
            )


        elif source in {
            "科技日报",
            "科学网",
            "DeepTech深科技",
        }:

            item[
                "category"
            ] = "前沿动态"


        elif source in {
            "Scientific Data",
            "Nature Cities",
        }:

            item[
                "category"
            ] = "期刊论文"


        elif source == "GitHub":

            if not github_relevant(
                item.get(
                    "title",
                    ""
                ),
                item.get(
                    "summary",
                    ""
                )
            ):

                continue


            item[
                "category"
            ] = "提效工具"


        else:

            # 淘汰以前的AI-Bot等旧来源
            continue


        if not item.get(
            "display_title"
        ):

            item[
                "display_title"
            ] = refine_title(
                item.get(
                    "title",
                    ""
                )
            )


        if not item.get(
            "image_url"
        ):

            item[
                "image_url"
            ] = ""


        item[
            "is_breakthrough"
        ] = bool(

            item.get(
                "is_breakthrough"
            )

            or

            (
                source
                not in {
                    "Scientific Data",
                    "Nature Cities",
                    "GitHub",
                }
                and
                is_breakthrough(
                    text
                )
            )
        )


        output.append(
            item
        )


    return output


# =========================================================
# 新资讯 / 旧资讯封面补全
# =========================================================

def enrich_images(
    old_items,
    new_items
):

    old_map = {

        item.get("id"):
            item

        for item in old_items

        if item.get(
            "id"
        )
    }


    request_count = 0


    # -------------------------
    # 新数据优先
    # -------------------------

    for item in new_items:

        old = old_map.get(
            item.get(
                "id"
            )
        )


        # 旧图片直接继承
        if old:

            if old.get(
                "image_url"
            ):

                item[
                    "image_url"
                ] = old[
                    "image_url"
                ]


            if (
                not item.get(
                    "summary"
                )
                and old.get(
                    "summary"
                )
            ):

                item[
                    "summary"
                ] = old[
                    "summary"
                ]


        # 没图片才访问文章页
        if (
            not item.get(
                "image_url"
            )
            and
            request_count
            <
            IMAGE_FETCH_LIMIT
        ):

            meta = fetch_page_meta(
                item.get(
                    "url"
                )
            )

            request_count += 1


            if meta.get(
                "image_url"
            ):

                item[
                    "image_url"
                ] = meta[
                    "image_url"
                ]


            if (
                not item.get(
                    "summary"
                )
                and meta.get(
                    "description"
                )
            ):

                item[
                    "summary"
                ] = meta[
                    "description"
                ]


    # -------------------------
    # 如果还有额度，给历史数据补图
    # -------------------------

    if request_count < IMAGE_FETCH_LIMIT:

        for item in old_items:

            if request_count >= IMAGE_FETCH_LIMIT:
                break


            if item.get(
                "image_url"
            ):
                continue


            meta = fetch_page_meta(
                item.get(
                    "url"
                )
            )

            request_count += 1


            if meta.get(
                "image_url"
            ):

                item[
                    "image_url"
                ] = meta[
                    "image_url"
                ]


            if (
                not item.get(
                    "summary"
                )
                and meta.get(
                    "description"
                )
            ):

                item[
                    "summary"
                ] = meta[
                    "description"
                ]


    print(
        "Page metadata requests:",
        request_count
    )


    return (
        old_items,
        new_items
    )


# =========================================================
# 删除旧数据
# =========================================================

def remove_old_items(
    items
):

    cutoff = (

        datetime.now(
            timezone.utc
        )

        - timedelta(
            days=KEEP_DAYS
        )
    )


    output = []


    for item in items:

        try:

            dt = dtparser.parse(
                item.get(
                    "published_at",
                    ""
                )
            )


            if dt.tzinfo is None:

                dt = dt.replace(
                    tzinfo=timezone.utc
                )


            if dt >= cutoff:

                output.append(
                    item
                )


        except Exception:

            output.append(
                item
            )


    return output


# =========================================================
# 来源排序
# =========================================================

def source_rank(source):

    ranks = {

        "科技日报":
            110,

        "科学网":
            105,

        "DeepTech深科技":
            100,

        "AIBase":
            95,

        "量子位":
            90,

        "Scientific Data":
            90,

        "Nature Cities":
            90,

        "GitHub":
            70,
    }


    return ranks.get(
        source,
        50
    )


# =========================================================
# 合并
# =========================================================

def merge_items(
    old_items,
    new_items
):

    merged = {}


    for item in old_items:

        item_id = item.get(
            "id"
        )

        if item_id:

            merged[
                item_id
            ] = item


    for item in new_items:

        item_id = item[
            "id"
        ]


        if item_id in merged:

            old = merged[
                item_id
            ]


            detected_at = old.get(
                "detected_at"
            )


            published_at = old.get(
                "published_at"
            )


            image_url = (
                item.get(
                    "image_url"
                )
                or
                old.get(
                    "image_url"
                )
                or ""
            )


            old.update(
                item
            )


            old[
                "image_url"
            ] = image_url


            if detected_at:

                old[
                    "detected_at"
                ] = detected_at


            if published_at:

                old[
                    "published_at"
                ] = published_at


            merged[
                item_id
            ] = old


        else:

            merged[
                item_id
            ] = item


    items = list(
        merged.values()
    )


    items = remove_old_items(
        items
    )


    def sort_key(item):

        try:

            timestamp = (
                dtparser.parse(
                    item.get(
                        "published_at",
                        ""
                    )
                ).timestamp()
            )

        except Exception:

            timestamp = 0


        breakthrough = (
            1
            if item.get(
                "is_breakthrough"
            )
            else 0
        )


        return (
            timestamp,
            breakthrough,
            source_rank(
                item.get(
                    "source",
                    ""
                )
            ),
        )


    items.sort(
        key=sort_key,
        reverse=True
    )


    return items[
        :MAX_ITEMS
    ]


# =========================================================
# 保存
# =========================================================

def save_data(items):

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    category_counts = {

        "AI变现":
            0,

        "提效工具":
            0,

        "前沿动态":
            0,
    }


    source_counts = {

        "Scientific Data":
            0,

        "Nature Cities":
            0,
    }


    breakthrough_count = 0


    for item in items:

        category = item.get(
            "category"
        )


        if category in category_counts:

            category_counts[
                category
            ] += 1


        source = item.get(
            "source"
        )


        if source in source_counts:

            source_counts[
                source
            ] += 1


        if item.get(
            "is_breakthrough"
        ):

            breakthrough_count += 1


    output = {

        "updated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "count":
            len(items),

        "breakthrough_count":
            breakthrough_count,

        "category_counts":
            category_counts,

        "source_counts":
            source_counts,

        "items":
            items,
    }


    with open(
        DATA_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=" * 55
    )

    print(
        "ICAT Research Radar V5"
    )

    print(
        "=" * 55
    )


    old_items = load_old_data()

    old_items = normalize_old_items(
        old_items
    )


    print(
        "Old items:",
        len(old_items)
    )


    aibase_items = fetch_aibase()

    qbitai_items = fetch_qbitai()

    stdaily_items = fetch_stdaily()

    sciencenet_items = fetch_sciencenet()

    deeptech_items = fetch_deeptech()


    scientific_items = (
        fetch_nature_journal(
            SCIENTIFIC_DATA_RSS,
            SCIENTIFIC_DATA_HTML,
            "Scientific Data"
        )
    )


    nature_cities_items = (
        fetch_nature_journal(
            NATURE_CITIES_RSS,
            NATURE_CITIES_HTML,
            "Nature Cities"
        )
    )


    github_items = fetch_github()


    new_items = (

        aibase_items
        + qbitai_items
        + stdaily_items
        + sciencenet_items
        + deeptech_items
        + scientific_items
        + nature_cities_items
        + github_items
    )


    old_items, new_items = (
        enrich_images(
            old_items,
            new_items
        )
    )


    final_items = merge_items(
        old_items,
        new_items
    )


    save_data(
        final_items
    )


    print(
        "--------------------------------"
    )

    print(
        "AIBase:",
        len(aibase_items)
    )

    print(
        "量子位:",
        len(qbitai_items)
    )

    print(
        "科技日报:",
        len(stdaily_items)
    )

    print(
        "科学网:",
        len(sciencenet_items)
    )

    print(
        "DeepTech:",
        len(deeptech_items)
    )

    print(
        "Scientific Data:",
        len(scientific_items)
    )

    print(
        "Nature Cities:",
        len(nature_cities_items)
    )

    print(
        "GitHub:",
        len(github_items)
    )

    print(
        "Final:",
        len(final_items)
    )

    print(
        "=" * 55
    )


if __name__ == "__main__":

    main()
