import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# 基础设置
# =========================================================

DATA_FILE = Path("data/news.json")

MAX_ITEMS = 400

# 页面保留最近45天
KEEP_DAYS = 45


# =========================================================
# 数据源
# =========================================================

AIBASE_URL = "https://news.aibase.com/zh/news"

QBITAI_URL = (
    "https://www.qbitai.com/category/%E8%B5%84%E8%AE%AF"
)

SCIENTIFIC_DATA_URL = (
    "https://www.nature.com/sdata/articles"
)

NATURE_CITIES_URL = (
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
# Scientific Data 城市相关关键词
# =========================================================

CITY_STRONG_KEYWORDS = [

    # 城市
    "urban",
    "city",
    "cities",
    "metropolitan",
    "urbanization",
    "urbanisation",

    # 建筑
    "building",
    "buildings",
    "built environment",
    "urban morphology",
    "urban form",

    # 道路 / 交通
    "urban road",
    "road map",
    "road network",
    "street network",
    "street view",
    "streetscape",
    "traffic",
    "transport",
    "transportation",

    # 人口 / 活动
    "population",
    "human mobility",
    "urban mobility",
    "human settlement",

    # 城市环境
    "urban heat",
    "heat island",
    "urban climate",
    "air pollution",
    "pm2.5",
    "green space",
    "greenspace",

    # 土地
    "urban land",
    "land use",
    "land cover",

    # 地理空间
    "geoai",
    "geospatial",
    "local climate zone",
    "lcz",

    # 灯光
    "nighttime light",
    "night-time light",
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
# GitHub搜索词
# =========================================================

GITHUB_TOPICS = [

    # 科研效率
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

    # 城市空间
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

    # 医学、生物
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

    # 金融投机
    "crypto",
    "cryptocurrency",
    "casino",
    "betting",

    # 游戏外挂
    "game cheat",
    "hack game",
]


# =========================================================
# 中文AI资讯关键词
# =========================================================

AI_KEYWORDS = [

    "AI",
    "人工智能",
    "大模型",
    "模型",
    "智能体",
    "Agent",

    "ChatGPT",
    "OpenAI",
    "Claude",
    "Anthropic",
    "Gemini",
    "DeepSeek",
    "Qwen",
    "千问",
    "豆包",
    "Manus",

    "开源",
    "发布",
    "推出",
    "上线",
    "更新",
    "新功能",
    "工具",
    "API",

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
# 基础文本处理
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

    if not title:
        return ""

    title = clean_text(title)

    # AIBase日报的 #1 #2 等
    title = re.sub(
        r"^#\s*\d+\s*",
        "",
        title
    )

    # 删除部分媒体栏目头
    title = re.sub(
        r"^AI日报[：:\s]*",
        "",
        title,
        flags=re.I
    )

    title = re.sub(
        r"^AI资讯[：:\s]*",
        "",
        title,
        flags=re.I
    )

    # 删除明显营销前缀
    patterns = [
        r"^刚刚[！!，,:：\s]*",
        r"^重磅[！!，,:：\s]*",
        r"^震撼[！!，,:：\s]*",
        r"^炸裂[！!，,:：\s]*",
        r"^官宣[！!，,:：\s]*",
        r"^独家[！!，,:：\s]*",
        r"^最新[！!，,:：\s]*",
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

    """
    Nature列表中的：
    12 Aug 2026
    05 Aug 2026
    """

    if not text:
        return None

    match = re.search(
        r"\b("
        r"\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|"
        r"Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{4}"
        r")\b",
        text,
        flags=re.I
    )

    if match:

        return match.group(1)

    return None


# =========================================================
# 创建资讯
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
    meta=None
):

    return {

        "id":
            make_id(
                source,
                title,
                url
            ),

        "title":
            clean_text(title),

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

        "meta":
            meta or {}
    }


# =========================================================
# AI标题价值判断
# =========================================================

def useful_ai_title(title):

    text = title.lower()

    return any(
        keyword.lower() in text
        for keyword in AI_KEYWORDS
    )


def ai_priority(title):

    text = title.lower()

    strong = [

        "开源",
        "免费",
        "发布",
        "推出",
        "上线",
        "agent",
        "智能体",
        "api",
        "重大更新",
        "新功能",
    ]

    if any(
        word.lower() in text
        for word in strong
    ):

        return "A"

    return "B"


# =========================================================
# AIBase
#
# 用户当前设定：
# AIBase → AI变现
# =========================================================

def fetch_aibase():

    print(
        "Fetching AIBase..."
    )

    results = []

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

    candidates = []

    # -------------------------
    # 优先标题元素
    # -------------------------

    selectors = [

        "h2 a[href*='/zh/news/']",
        "h3 a[href*='/zh/news/']",
        "h4 a[href*='/zh/news/']",
    ]

    for selector in selectors:

        for node in soup.select(
            selector
        ):

            title = clean_text(
                node.get_text(
                    " ",
                    strip=True
                )
            )

            href = node.get(
                "href"
            )

            if (
                not title
                or not href
            ):

                continue

            if not contains_chinese(
                title
            ):

                continue

            if len(title) < 8:

                continue

            url = urljoin(
                AIBASE_URL,
                href
            )

            candidates.append(
                (
                    title,
                    url
                )
            )

    # -------------------------
    # fallback
    # -------------------------

    if not candidates:

        for node in soup.select(
            "a[href*='/zh/news/']"
        ):

            raw = clean_text(
                node.get_text(
                    " ",
                    strip=True
                )
            )

            href = node.get(
                "href"
            )

            if (
                not raw
                or not href
            ):

                continue

            if not contains_chinese(
                raw
            ):

                continue

            # 如果card内文字非常长，
            # 尽量取前面的标题
            title = raw

            if len(title) > 100:

                # 根据常见中文句号截断
                parts = re.split(
                    r"[。]",
                    title
                )

                title = parts[0]

            if not (
                8 <= len(title) <= 120
            ):

                continue

            url = urljoin(
                AIBASE_URL,
                href
            )

            candidates.append(
                (
                    title,
                    url
                )
            )

    seen = set()

    for title, url in candidates:

        # URL去重
        if url in seen:
            continue

        seen.add(url)

        if not useful_ai_title(
            title
        ):

            continue

        display_title = refine_title(
            title
        )

        results.append(

            make_item(

                title=title,

                display_title=
                    display_title,

                source="AIBase",

                # =====================================
                # 固定归入AI变现
                # =====================================
                category="AI变现",

                url=url,

                summary="",

                priority=
                    ai_priority(
                        title
                    ),

                language="zh",
            )
        )

    print(
        "AIBase items:",
        len(results)
    )

    return results[:30]


# =========================================================
# 量子位
#
# 固定作为“提效工具”中文补充源
# =========================================================

def fetch_qbitai():

    print(
        "Fetching 量子位..."
    )

    results = []

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

    candidates = []

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
            "href"
        )

        if (
            not title
            or not href
        ):

            continue

        if not contains_chinese(
            title
        ):

            continue

        if not (
            8 <= len(title) <= 120
        ):

            continue

        url = urljoin(
            QBITAI_URL,
            href
        )

        if (
            "qbitai.com"
            not in url
        ):

            continue

        if any(
            x in url
            for x in [
                "/category/",
                "/tag/",
                "/author/"
            ]
        ):

            continue

        candidates.append(
            (
                title,
                url
            )
        )

    seen = set()

    for title, url in candidates:

        if url in seen:
            continue

        seen.add(url)

        if not useful_ai_title(
            title
        ):

            continue

        results.append(

            make_item(

                title=title,

                display_title=
                    refine_title(
                        title
                    ),

                source="量子位",

                category=
                    "提效工具",

                url=url,

                priority=
                    ai_priority(
                        title
                    ),

                language="zh",
            )
        )

    print(
        "量子位 items:",
        len(results)
    )

    return results[:30]


# =========================================================
# Scientific Data 城市数据判断
# =========================================================

def scientific_data_relevant(
    title,
    summary=""
):

    text = (
        f"{title} {summary}"
    ).lower()

    city_hit = any(
        keyword in text
        for keyword
        in CITY_STRONG_KEYWORDS
    )

    data_hit = any(
        keyword in text
        for keyword
        in DATA_KEYWORDS
    )

    return (
        city_hit
        and data_hit
    )


# =========================================================
# Nature文章列表通用解析
# =========================================================

def parse_nature_cards(
    html,
    base_url
):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    results = []

    # Nature主要列表结构
    cards = soup.select(
        "li.app-article-list-row__item"
    )

    # 页面结构变化fallback
    if not cards:

        cards = soup.select(
            "article"
        )

    # 再fallback
    if not cards:

        cards = []

        for heading in soup.select(
            "h3"
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

    for card in cards:

        link = card.select_one(
            "h3 a[href*='/articles/']"
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
            "href"
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

        # 尝试找摘要
        summary = ""

        paragraphs = card.find_all(
            "p"
        )

        for paragraph in paragraphs:

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
#
# 不再使用RSS
# 直接抓最近5页Data Descriptor
# =========================================================

def fetch_scientific_data():

    print(
        "Fetching Scientific Data..."
    )

    results = []

    seen = set()

    # 最近5页
    # 足以覆盖一段时间，同时不会请求过多
    for page in range(
        1,
        6
    ):

        params = {
            "type":
                "data-descriptor",

            "year":
                datetime.now().year,

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
                "Scientific Data page",
                page,
                "failed:",
                e
            )

            continue

        cards = parse_nature_cards(
            response.text,
            "https://www.nature.com"
        )

        for card in cards:

            title = card[
                "title"
            ]

            url = card[
                "url"
            ]

            summary = card[
                "summary"
            ]

            if url in seen:

                continue

            seen.add(url)

            if not scientific_data_relevant(
                title,
                summary
            ):

                continue

            results.append(

                make_item(

                    title=title,

                    display_title=
                        refine_title(
                            title
                        ),

                    source=
                        "Scientific Data",

                    category=
                        "城市数据",

                    url=url,

                    published_at=
                        card[
                            "published"
                        ],

                    summary=
                        summary,

                    priority="A",

                    language="en",
                )
            )

    print(
        "Scientific Data urban items:",
        len(results)
    )

    return results


# =========================================================
# Nature Cities
#
# 不使用RSS
# =========================================================

def fetch_nature_cities():

    print(
        "Fetching Nature Cities..."
    )

    results = []

    seen = set()

    # 抓前两页即可覆盖近期文章
    for page in range(
        1,
        3
    ):

        params = {
            "year":
                datetime.now().year,

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
                "Nature Cities page",
                page,
                "failed:",
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

                    display_title=
                        refine_title(
                            card[
                                "title"
                            ]
                        ),

                    source=
                        "Nature Cities",

                    category=
                        "城市前沿",

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
                )
            )

    print(
        "Nature Cities items:",
        len(results)
    )

    return results


# =========================================================
# GitHub判断
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


def github_is_city_data(
    full_name,
    description
):

    text = (
        f"{full_name} "
        f"{description}"
    ).lower()

    city_hit = any(
        word in text
        for word
        in CITY_STRONG_KEYWORDS
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

        now = datetime.now(
            timezone.utc
        )

        days = max(
            1,
            (
                now - created
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
        full_name
        .split("/")[-1]
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
            + "..."
        )

    return (
        f"{repo_name}："
        f"{first}"
    )


# =========================================================
# GitHub
# =========================================================

def fetch_github():

    print(
        "Fetching GitHub..."
    )

    results = []

    token = os.environ.get(
        "GITHUB_TOKEN"
    )

    headers = {

        "Accept":
            "application/"
            "vnd.github+json",

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

    seen = set()

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

            seen.add(url)

            stars = repo.get(
                "stargazers_count",
                0
            )

            # 至少30 stars
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

            if github_is_city_data(
                full_name,
                description
            ):

                category = (
                    "城市数据"
                )

            else:

                category = (
                    "提效工具"
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
# 旧数据迁移
#
# 解决现在：
# AIBase → 提效工具
# Scientific Data → 新数据
# 这些旧分类残留的问题
# =========================================================

def normalize_old_items(
    items
):

    normalized = []

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

        # -------------------------
        # AIBase
        # -------------------------

        if source == "AIBase":

            item[
                "category"
            ] = "AI变现"


        # -------------------------
        # 量子位
        # -------------------------

        elif source == "量子位":

            item[
                "category"
            ] = "提效工具"


        # -------------------------
        # Scientific Data
        # -------------------------

        elif (
            source
            == "Scientific Data"
        ):

            # 删除以前误抓的
            # granular layer等非城市数据
            if not scientific_data_relevant(
                title,
                summary
            ):

                continue

            item[
                "category"
            ] = "城市数据"


        # -------------------------
        # Nature Cities
        # -------------------------

        elif source == "Nature Cities":

            item[
                "category"
            ] = "城市前沿"


        # -------------------------
        # GitHub
        # -------------------------

        elif source == "GitHub":

            if not github_relevant(
                title,
                summary
            ):

                continue

            if github_is_city_data(
                title,
                summary
            ):

                item[
                    "category"
                ] = "城市数据"

            else:

                item[
                    "category"
                ] = "提效工具"


        # -------------------------
        # 老AI-Bot等旧来源
        # 直接淘汰
        # -------------------------

        else:

            continue


        if not item.get(
            "display_title"
        ):

            item[
                "display_title"
            ] = refine_title(
                title
            )

        normalized.append(
            item
        )

    return normalized


# =========================================================
# 删除过旧
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

        "AIBase": 100,

        "量子位": 95,

        "Scientific Data": 90,

        "Nature Cities": 90,

        "GitHub": 70,
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

    # -------------------------
    # 旧数据
    # -------------------------

    for item in old_items:

        item_id = item.get(
            "id"
        )

        if item_id:

            merged[
                item_id
            ] = item


    # -------------------------
    # 新数据
    # -------------------------

    for item in new_items:

        item_id = item[
            "id"
        ]

        if item_id in merged:

            old = merged[
                item_id
            ]

            # 第一次发现时间保留
            detected = old.get(
                "detected_at"
            )

            # 中文网站没有可靠文章日期时，
            # 不要每小时刷新成当前日期
            old_published = old.get(
                "published_at"
            )

            merged[
                item_id
            ].update(
                item
            )

            if detected:

                merged[
                    item_id
                ][
                    "detected_at"
                ] = detected

            if (
                item.get("source")
                in [
                    "AIBase",
                    "量子位"
                ]
                and old_published
            ):

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

        return (
            timestamp,
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
# 保存JSON
# =========================================================

def save_data(items):

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    category_counts = {

        "AI变现": 0,

        "提效工具": 0,

        "城市数据": 0,

        "城市前沿": 0,
    }

    source_counts = {}

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


    output = {

        "updated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "count":
            len(items),

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
        "================================"
    )

    print(
        "Research Radar V3"
    )

    print(
        "================================"
    )


    # -------------------------
    # 读取并迁移旧数据
    # -------------------------

    old_items = (
        load_old_data()
    )

    print(
        "Old raw items:",
        len(old_items)
    )

    old_items = (
        normalize_old_items(
            old_items
        )
    )

    print(
        "Old normalized items:",
        len(old_items)
    )


    # -------------------------
    # 抓新数据
    # -------------------------

    aibase_items = (
        fetch_aibase()
    )

    qbitai_items = (
        fetch_qbitai()
    )

    scientific_items = (
        fetch_scientific_data()
    )

    city_items = (
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
        + scientific_items
        + city_items
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
        "Scientific Data:",
        len(scientific_items)
    )

    print(
        "Nature Cities:",
        len(city_items)
    )

    print(
        "GitHub:",
        len(github_items)
    )

    print(
        "New total:",
        len(new_items)
    )


    final_items = (
        merge_items(
            old_items,
            new_items
        )
    )


    # -------------------------
    # 输出栏目统计
    # -------------------------

    counts = {

        "AI变现": 0,

        "提效工具": 0,

        "城市数据": 0,

        "城市前沿": 0,
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
        "--------------------------------"
    )

    print(
        "CATEGORY COUNTS:"
    )

    for key, value in counts.items():

        print(
            key,
            ":",
            value
        )


    # -------------------------
    # 保存
    # -------------------------

    save_data(
        final_items
    )


    print(
        "Final items:",
        len(final_items)
    )

    print(
        "================================"
    )

    print(
        "Research Radar V3 Done"
    )

    print(
        "================================"
    )


if __name__ == "__main__":

    main()
