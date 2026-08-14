import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# 基础配置
# =========================================================

DATA_FILE = Path("data/news.json")

# 最多保存多少条
MAX_ITEMS = 500

# 保留最近多少天
KEEP_DAYS = 45


# =========================================================
# 数据源
# =========================================================

AIBASE_URL = "https://news.aibase.com/zh/news"

QBITAI_URL = (
    "https://www.qbitai.com/category/%E8%B5%84%E8%AE%AF"
)

# 科技日报：科技新突破
STD_BREAKTHROUGH_URL = (
    "https://www.stdaily.com/web/spxw/node_706.html"
)

# 科学网
SCIENCENET_URL = (
    "https://news.sciencenet.cn/"
)

# DeepTech / MIT科技评论中文
DEEPTECH_URL = (
    "https://www.deeptechchina.com/"
)

# Scientific Data
SCIENTIFIC_DATA_URL = (
    "https://www.nature.com/sdata/articles"
)

# Nature Cities
NATURE_CITIES_URL = (
    "https://www.nature.com/natcities/articles"
)


# =========================================================
# HTTP
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
            504
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
# “突破雷达”关键词
# =========================================================

BREAKTHROUGH_KEYWORDS = [

    # 首次
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
    "首次验证",
    "首次完成",
    "首次构建",
    "首次研制",
    "首次突破",

    # 首个
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

    # 世界纪录
    "刷新世界纪录",
    "刷新纪录",
    "世界纪录",
    "新纪录",
    "创纪录",

    # 世界第一
    "世界第一",
    "全球第一",
    "世界最大",
    "全球最大",

    # 突破
    "重大突破",
    "关键突破",
    "取得突破",
    "实现突破",
    "新突破",

    # 进展
    "重大进展",
    "重要进展",

    # 其他高价值创新词
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
# AI相关关键词
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
    "api",

    "自动化",
    "浏览器",
    "搜索",
    "文档",
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
# 城市数据关键词
# =========================================================

CITY_KEYWORDS = [

    "urban",
    "city",
    "cities",
    "metropolitan",
    "urbanization",
    "urbanisation",

    "building",
    "buildings",
    "built environment",
    "urban morphology",
    "urban form",

    "road network",
    "street network",
    "street view",
    "streetscape",

    "human mobility",
    "urban mobility",
    "population",
    "human settlement",

    "traffic",
    "transport",
    "transportation",

    "urban heat",
    "heat island",
    "urban climate",

    "air pollution",
    "pm2.5",

    "green space",
    "greenspace",

    "urban land",
    "land use",
    "land cover",

    "geoai",
    "geospatial",

    "local climate zone",
    "lcz",

    "nighttime light",
    "night-time light",

    "remote sensing",
    "satellite",
]


DATA_KEYWORDS = [

    "dataset",
    "data set",
    "database",
    "data resource",
    "data product",
    "benchmark",
    "atlas",
]


# =========================================================
# GitHub 搜索
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

    '"urban data"',

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

    "urban",
    "city",
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
# 文本处理
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

    # 删除 #1 #2 之类
    title = re.sub(
        r"^#\s*\d+\s*",
        "",
        title
    )

    # 删除栏目文字
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

        # 2026-08-14
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
# 是否属于“突破”
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
# 获取节点上下文
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

        name = getattr(
            parent,
            "name",
            None
        )

        if name in {
            "article",
            "li"
        }:
            break

        parent = parent.parent

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
# AI 新闻过滤
# =========================================================

def useful_ai_text(text):

    low = clean_text(
        text
    ).lower()

    return any(
        keyword.lower()
        in low
        for keyword
        in AI_KEYWORDS
    )


def ai_priority(text):

    low = clean_text(
        text
    ).lower()

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

    if (
        is_breakthrough(text)
        or any(
            word in low
            for word
            in strong
        )
    ):

        return "A"

    return "B"


# =========================================================
# AIBase
# 固定 → AI变现
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

        # 只抓新闻文章
        if not re.search(
            r"/zh/news/\d+",
            href
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

        breakthrough = (
            is_breakthrough(
                f"{title} {context}"
            )
        )

        results.append(

            make_item(

                title=title,

                display_title=
                    refine_title(
                        title
                    ),

                source="AIBase",

                category="AI变现",

                url=url,

                summary=context,

                priority=
                    ai_priority(
                        f"{title} {context}"
                    ),

                language="zh",

                is_breakthrough_item=
                    breakthrough,
            )
        )

    print(
        "AIBase items:",
        len(results)
    )

    return results[:40]


# =========================================================
# 量子位
#
# 普通 → 提效工具
# 突破 → 前沿研究
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

    for node in soup.find_all(
        "a",
        href=True
    ):

        href = node.get(
            "href",
            ""
        )

        url = urljoin(
            QBITAI_URL,
            href
        )

        if (
            "qbitai.com"
            not in urlparse(url).netloc
        ):

            continue

        # 文章 URL
        if not re.search(
            r"/20\d{2}/\d{2}/\d+\.html",
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
            8 <= len(title) <= 120
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

        breakthrough = (
            is_breakthrough(
                f"{title} {context}"
            )
        )

        category = (
            "前沿研究"
            if breakthrough
            else "提效工具"
        )

        results.append(

            make_item(

                title=title,

                display_title=
                    refine_title(
                        title
                    ),

                source="量子位",

                category=
                    category,

                url=url,

                summary=context,

                priority=(
                    "A"
                    if breakthrough
                    else ai_priority(
                        f"{title} {context}"
                    )
                ),

                language="zh",

                is_breakthrough_item=
                    breakthrough,
            )
        )

    print(
        "量子位 items:",
        len(results)
    )

    return results[:40]


# =========================================================
# 科技日报 · 科技新突破
# =========================================================

def fetch_stdaily_breakthrough():

    print(
        "Fetching 科技日报·科技新突破..."
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

    # 该页面本身就是“科技新突破”
    # 所以栏目内文章全部允许进入

    for heading in soup.find_all(
        [
            "h2",
            "h3",
            "h4"
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
            node["href"]
        )

        if (
            "stdaily.com"
            not in urlparse(url).netloc
        ):

            continue

        if url in seen:
            continue

        context = extract_context(
            heading,
            title
        )

        published = (
            extract_date_from_text(
                context
            )
        )

        breakthrough = (
            is_breakthrough(
                f"{title} {context}"
            )
        )

        seen.add(
            url
        )

        results.append(

            make_item(

                title=title,

                display_title=
                    refine_title(
                        title
                    ),

                source="科技日报",

                category="前沿研究",

                url=url,

                published_at=
                    published,

                summary="",

                priority="A",

                language="zh",

                is_breakthrough_item=
                    breakthrough,
            )
        )

    print(
        "科技日报 items:",
        len(results)
    )

    return results[:30]


# =========================================================
# 科学网
#
# 只保留标题/简介命中“突破雷达”的新闻
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
            not in urlparse(url).netloc
        ):

            continue

        # 只接受实际新闻文章
        if not re.search(
            r"/htmlnews/\d{4}/\d+/\d+\.shtm",
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

        context = extract_context(
            node,
            title
        )

        # 科学网内容非常多
        # 必须命中突破关键词
        if not is_breakthrough(
            f"{title} {context}"
        ):

            continue

        if url in seen:
            continue

        seen.add(
            url
        )

        published = (
            extract_date_from_text(
                context
            )
        )

        results.append(

            make_item(

                title=title,

                display_title=
                    refine_title(
                        title
                    ),

                source="科学网",

                category="前沿研究",

                url=url,

                published_at=
                    published,

                summary=context,

                priority="A",

                language="zh",

                is_breakthrough_item=True,
            )
        )

    print(
        "科学网 items:",
        len(results)
    )

    return results[:30]


# =========================================================
# DeepTech 深科技
#
# 只保留明显突破型内容
# =========================================================

def fetch_deeptech():

    print(
        "Fetching DeepTech深科技..."
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

        href = node.get(
            "href",
            ""
        )

        url = urljoin(
            DEEPTECH_URL,
            href
        )

        if (
            "deeptechchina.com"
            not in urlparse(url).netloc
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
            8 <= len(title) <= 120
        ):

            continue

        context = extract_context(
            node,
            title
        )

        if not is_breakthrough(
            f"{title} {context}"
        ):

            continue

        if url in seen:
            continue

        seen.add(
            url
        )

        published = (
            extract_date_from_text(
                context
            )
        )

        results.append(

            make_item(

                title=title,

                display_title=
                    refine_title(
                        title
                    ),

                source=
                    "DeepTech深科技",

                category=
                    "前沿研究",

                url=url,

                published_at=
                    published,

                summary=context,

                priority="A",

                language="zh",

                is_breakthrough_item=True,
            )
        )

    print(
        "DeepTech items:",
        len(results)
    )

    return results[:30]


# =========================================================
# Scientific Data 相关性
# =========================================================

def scientific_data_relevant(
    title,
    summary=""
):

    text = (
        f"{title} {summary}"
    ).lower()

    city_hit = any(
        word in text
        for word
        in CITY_KEYWORDS
    )

    data_hit = any(
        word in text
        for word
        in DATA_KEYWORDS
    )

    return (
        city_hit
        and data_hit
    )


# =========================================================
# Nature 通用列表解析
# =========================================================

def parse_nature_cards(
    html,
    base_url
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    cards = soup.select(
        "li.app-article-list-row__item"
    )

    if not cards:

        cards = soup.select(
            "article"
        )

    if not cards:

        cards = []

        for heading in soup.find_all(
            [
                "h2",
                "h3"
            ]
        ):

            if heading.find(
                "a",
                href=re.compile(
                    r"/articles/"
                )
            ):

                cards.append(
                    heading.parent
                )

    results = []

    for card in cards:

        link = card.select_one(
            "h3 a[href*='/articles/'], "
            "h2 a[href*='/articles/']"
        )

        if not link:
            continue

        title = clean_text(
            link.get_text(
                " ",
                strip=True
            )
        )

        href = link.get(
            "href",
            ""
        )

        if (
            not title
            or not href
        ):

            continue

        url = urljoin(
            base_url,
            href
        )

        card_text = clean_text(
            card.get_text(
                " ",
                strip=True
            )
        )

        published = (
            extract_date_from_text(
                card_text
            )
        )

        summary = ""

        for paragraph in card.find_all(
            "p"
        ):

            text = clean_text(
                paragraph.get_text(
                    " ",
                    strip=True
                )
            )

            if len(text) >= 40:

                summary = text
                break

        results.append(
            {
                "title":
                    title,

                "url":
                    url,

                "published":
                    published,

                "summary":
                    summary,
            }
        )

    return results


# =========================================================
# Scientific Data
# =========================================================

def fetch_scientific_data():

    print(
        "Fetching Scientific Data..."
    )

    results = []
    seen = set()

    year = (
        datetime.now().year
    )

    # 最近5页
    for page in range(
        1,
        6
    ):

        params = {

            "type":
                "data-descriptor",

            "year":
                year,

            "sort":
                "PubDate",
        }

        if page > 1:

            params[
                "page"
            ] = page

        try:

            response = SESSION.get(
                SCIENTIFIC_DATA_URL,
                params=params,
                timeout=40
            )

            response.raise_for_status()

        except Exception as e:

            print(
                "Scientific Data page failed:",
                page,
                e
            )

            continue

        cards = parse_nature_cards(
            response.text,
            "https://www.nature.com"
        )

        for card in cards:

            if (
                card["url"]
                in seen
            ):

                continue

            seen.add(
                card["url"]
            )

            if not scientific_data_relevant(
                card["title"],
                card["summary"]
            ):

                continue

            results.append(

                make_item(

                    title=
                        card[
                            "title"
                        ],

                    source=
                        "Scientific Data",

                    category=
                        "多源数据",

                    url=
                        card[
                            "url"
                        ],

                    published_at=
                        card[
                            "published"
                        ],

                    summary=
                        card[
                            "summary"
                        ],

                    priority="A",

                    language="en",

                    is_breakthrough_item=
                        is_breakthrough(
                            card[
                                "title"
                            ]
                        ),
                )
            )

    print(
        "Scientific Data items:",
        len(results)
    )

    return results


# =========================================================
# Nature Cities
# =========================================================

def fetch_nature_cities():

    print(
        "Fetching Nature Cities..."
    )

    results = []
    seen = set()

    year = (
        datetime.now().year
    )

    # 最近2页
    for page in range(
        1,
        3
    ):

        params = {

            "year":
                year,

            "sort":
                "PubDate",
        }

        if page > 1:

            params[
                "page"
            ] = page

        try:

            response = SESSION.get(
                NATURE_CITIES_URL,
                params=params,
                timeout=40
            )

            response.raise_for_status()

        except Exception as e:

            print(
                "Nature Cities page failed:",
                page,
                e
            )

            continue

        cards = parse_nature_cards(
            response.text,
            "https://www.nature.com"
        )

        for card in cards:

            if (
                card["url"]
                in seen
            ):

                continue

            seen.add(
                card["url"]
            )

            results.append(

                make_item(

                    title=
                        card[
                            "title"
                        ],

                    source=
                        "Nature Cities",

                    category=
                        "前沿研究",

                    url=
                        card[
                            "url"
                        ],

                    published_at=
                        card[
                            "published"
                        ],

                    summary=
                        card[
                            "summary"
                        ],

                    priority="A",

                    language="en",

                    is_breakthrough_item=
                        is_breakthrough(
                            card[
                                "title"
                            ]
                        ),
                )
            )

    print(
        "Nature Cities items:",
        len(results)
    )

    return results


# =========================================================
# GitHub
# =========================================================

def github_relevant(
    name,
    description
):

    text = (
        f"{name} {description}"
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


def github_is_data(
    name,
    description
):

    text = (
        f"{name} {description}"
    ).lower()

    city_hit = any(
        word in text
        for word
        in CITY_KEYWORDS
    )

    data_hit = any(
        word in text
        for word
        in DATA_KEYWORDS
    )

    return (
        city_hit
        and data_hit
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

            created = (
                created.replace(
                    tzinfo=timezone.utc
                )
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

    if len(first) > 80:

        first = (
            first[:77]
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

            data = (
                response.json()
            )

        except Exception as e:

            print(
                "GitHub query failed:",
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

            seen.add(
                url
            )

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

            category = (

                "多源数据"

                if github_is_data(
                    full_name,
                    description
                )

                else "提效工具"
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

                    source=
                        "GitHub",

                    category=
                        category,

                    url=
                        url,

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

                    is_breakthrough_item=False,

                    meta={
                        "stars":
                            stars,

                        "language":
                            repo.get(
                                "language"
                            ),

                        "created_at":
                            created_at,

                        "updated_at":
                            repo.get(
                                "updated_at"
                            ),
                    },
                )
            )

    print(
        "GitHub items:",
        len(results)
    )

    return results


# =========================================================
# 读取旧数据
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

            data = json.load(f)

        return data.get(
            "items",
            []
        )

    except Exception as e:

        print(
            "Old data load error:",
            e
        )

        return []


# =========================================================
# 旧数据分类迁移
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

        title = item.get(
            "title",
            ""
        )

        summary = item.get(
            "summary",
            ""
        )

        text = (
            f"{title} {summary}"
        )

        # AIBase
        if source == "AIBase":

            item[
                "category"
            ] = "AI变现"


        # 量子位
        elif source == "量子位":

            item[
                "category"
            ] = (
                "前沿研究"
                if is_breakthrough(text)
                else "提效工具"
            )


        # 新增中文突破源
        elif source in {
            "科技日报",
            "科学网",
            "DeepTech深科技"
        }:

            item[
                "category"
            ] = "前沿研究"


        # Scientific Data
        elif (
            source
            == "Scientific Data"
        ):

            if not scientific_data_relevant(
                title,
                summary
            ):

                continue

            item[
                "category"
            ] = "多源数据"


        # Nature Cities
        elif (
            source
            == "Nature Cities"
        ):

            item[
                "category"
            ] = "前沿研究"


        # GitHub
        elif source == "GitHub":

            if not github_relevant(
                title,
                summary
            ):

                continue

            item[
                "category"
            ] = (

                "多源数据"

                if github_is_data(
                    title,
                    summary
                )

                else "提效工具"
            )


        # 淘汰旧AI-Bot等来源
        else:

            continue


        item[
            "is_breakthrough"
        ] = bool(

            item.get(
                "is_breakthrough"
            )

            or

            is_breakthrough(
                text
            )
        )


        if not item.get(
            "display_title"
        ):

            item[
                "display_title"
            ] = refine_title(
                title
            )


        output.append(
            item
        )

    return output


# =========================================================
# 删除旧内容
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
# 来源优先级
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
# 合并数据
# =========================================================

def merge_items(
    old_items,
    new_items
):

    merged = {}


    # 旧数据
    for item in old_items:

        item_id = item.get(
            "id"
        )

        if item_id:

            merged[
                item_id
            ] = item


    # 新数据
    for item in new_items:

        item_id = item[
            "id"
        ]

        if item_id in merged:

            old_item = merged[
                item_id
            ]

            old_detected = (
                old_item.get(
                    "detected_at"
                )
            )

            old_published = (
                old_item.get(
                    "published_at"
                )
            )

            merged[
                item_id
            ].update(
                item
            )

            # 保留第一次发现时间
            if old_detected:

                merged[
                    item_id
                ][
                    "detected_at"
                ] = old_detected

            # 同一篇文章发布日期不应该每小时变化
            if old_published:

                merged[
                    item_id
                ][
                    "published_at"
                ] = old_published

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
            )
        )


    items.sort(
        key=sort_key,
        reverse=True
    )

    return items[
        :MAX_ITEMS
    ]


# =========================================================
# 保存 JSON
# =========================================================

def save_data(items):

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    category_counts = {

        "AI变现": 0,

        "提效工具": 0,

        "多源数据": 0,

        "前沿研究": 0,
    }

    source_counts = {}

    breakthrough_count = 0


    for item in items:

        category = item.get(
            "category"
        )

        if (
            category
            in category_counts
        ):

            category_counts[
                category
            ] += 1


        source = item.get(
            "source",
            "未知"
        )

        source_counts[
            source
        ] = (
            source_counts.get(
                source,
                0
            )
            + 1
        )


        if item.get(
            "is_breakthrough"
        ):

            breakthrough_count += 1


    output = {

        # 这是“雷达最后一次扫描时间”
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
        "=" * 50
    )

    print(
        "ICAT Research Radar V4"
    )

    print(
        "=" * 50
    )


    # -------------------------
    # 历史数据
    # -------------------------

    old_items = (
        load_old_data()
    )

    old_items = (
        normalize_old_items(
            old_items
        )
    )

    print(
        "Old normalized:",
        len(old_items)
    )


    # -------------------------
    # 抓取
    # -------------------------

    aibase_items = (
        fetch_aibase()
    )

    qbitai_items = (
        fetch_qbitai()
    )

    stdaily_items = (
        fetch_stdaily_breakthrough()
    )

    sciencenet_items = (
        fetch_sciencenet()
    )

    deeptech_items = (
        fetch_deeptech()
    )

    scientific_items = (
        fetch_scientific_data()
    )

    nature_city_items = (
        fetch_nature_cities()
    )

    github_items = (
        fetch_github()
    )


    # -------------------------
    # 合并
    # -------------------------

    new_items = (

        aibase_items
        + qbitai_items
        + stdaily_items
        + sciencenet_items
        + deeptech_items
        + scientific_items
        + nature_city_items
        + github_items
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
        len(nature_city_items)
    )

    print(
        "GitHub:",
        len(github_items)
    )


    print(
        "--------------------------------"
    )


    final_items = (
        merge_items(
            old_items,
            new_items
        )
    )


    save_data(
        final_items
    )


    # -------------------------
    # 输出分类统计
    # -------------------------

    counts = {

        "AI变现": 0,

        "提效工具": 0,

        "多源数据": 0,

        "前沿研究": 0,
    }


    for item in final_items:

        category = item.get(
            "category"
        )

        if category in counts:

            counts[
                category
            ] += 1


    print(
        "CATEGORY COUNTS:"
    )

    print(
        counts
    )

    print(
        "Final items:",
        len(final_items)
    )

    print(
        "=" * 50
    )


if __name__ == "__main__":

    main()
