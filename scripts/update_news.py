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
KEEP_DAYS = 30


# =========================================================
# 中文信息源
# =========================================================

AIBASE_URLS = [
    "https://news.aibase.com/zh/news",
    "https://news.aibase.com/zh/",
]

QBITAI_URL = (
    "https://www.qbitai.com/category/%E8%B5%84%E8%AE%AF"
)


# =========================================================
# Nature RSS
# =========================================================

NATURE_FEEDS = [
    {
        "name": "Scientific Data",
        "url": "https://www.nature.com/sdata.rss",
        "category": "城市数据",
    },
    {
        "name": "Nature Cities",
        "url": "https://www.nature.com/natcities.rss",
        "category": "城市前沿",
    },
]


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
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
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
# Scientific Data：
# 必须真正与城市、多源数据有关
# =========================================================

CITY_STRONG_KEYWORDS = [

    # 城市
    "urban",
    "city",
    "cities",
    "urbanization",
    "urbanisation",
    "metropolitan",

    # 建成环境
    "building",
    "buildings",
    "built environment",
    "urban morphology",
    "urban form",

    # 道路 / 街景
    "road network",
    "street network",
    "street view",
    "streetscape",

    # 人口 / 活动
    "human mobility",
    "urban mobility",
    "population",
    "human settlement",

    # 交通
    "urban transport",
    "transportation",
    "traffic",

    # 城市环境
    "urban heat",
    "heat island",
    "urban climate",
    "air pollution",
    "pm2.5",
    "urban green space",

    # 城市空间
    "local climate zone",
    "lcz",
]


CITY_DATA_SECONDARY = [

    "remote sensing",
    "satellite",
    "geospatial",
    "gis",
    "land use",
    "land cover",
    "nighttime light",
    "night-time light",
    "lidar",
    "dem",
]


DATA_KEYWORDS = [
    "dataset",
    "data set",
    "database",
    "data product",
    "benchmark dataset",
    "geodatabase",
]


# =========================================================
# GitHub 搜索
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

    # 城市 / 地理
    '"urban data"',
    '"geoai"',
    '"geospatial" AI',
    '"GIS" agent',
    '"remote sensing" AI',
]


# GitHub必须包含至少一个
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
    "browser",
    "automation",

    "urban",
    "city",
    "geoai",
    "geospatial",
    "gis",
    "remote sensing",
    "satellite",
]


# 明显不需要的方向
GITHUB_NEGATIVE = [

    "lipid",
    "protein",
    "genome",
    "genomic",
    "clinical",
    "medical imaging",
    "drug discovery",
    "molecule",
    "molecular",
    "cancer",
    "tumor",

    "crypto",
    "cryptocurrency",
    "blockchain",
    "casino",
    "betting",

    "game cheat",
    "hack game",
]


# =========================================================
# AI资讯筛选
# =========================================================

AI_USEFUL_KEYWORDS = [

    # 中文
    "ai",
    "人工智能",
    "大模型",
    "模型",
    "智能体",
    "agent",
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
    "ppt",
    "代码",
    "编程",
    "数据分析",
    "可视化",
    "图像",
    "视频生成",
    "办公",

    # 产品名
    "chatgpt",
    "openai",
    "claude",
    "anthropic",
    "gemini",
    "deepseek",
    "qwen",
    "千问",
    "豆包",
    "cursor",
    "copilot",
    "notebooklm",
    "manus",
]


# =========================================================
# AI变现关键词
# =========================================================

AI_MONETIZATION_KEYWORDS = [

    "变现",
    "赚钱",
    "副业",
    "商业化",
    "商业模式",
    "收费",
    "付费",
    "收入",

    "电商",
    "带货",
    "商家",
    "交易",
    "订单",
    "获客",
    "营销",
    "广告",

    "自媒体",
    "短视频",
    "内容创作",
    "数字人",
    "创业",
    "接单",

    "monetization",
    "monetize",
    "ecommerce",
    "e-commerce",
    "marketing",
    "advertising",
    "creator economy",
    "revenue",
    "sales",
    "lead generation",
]


# =========================================================
# 文本函数
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

    """
    不进行翻译。
    只删除明显营销词和冗余格式。
    """

    if not title:
        return ""

    title = clean_text(title)

    # -------------------------
    # 删除常见栏目头
    # -------------------------

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

    # -------------------------
    # 删除标题开头营销词
    # -------------------------

    hype_patterns = [

        r"^刚刚[！!，,:：\s]*",
        r"^重磅[！!，,:：\s]*",
        r"^突发[！!，,:：\s]*",
        r"^震撼[！!，,:：\s]*",
        r"^炸裂[！!，,:：\s]*",
        r"^官宣[！!，,:：\s]*",
        r"^最新[！!，,:：\s]*",
        r"^独家[！!，,:：\s]*",
    ]

    for pattern in hype_patterns:

        title = re.sub(
            pattern,
            "",
            title
        )

    # -------------------------
    # 删除重复空格
    # -------------------------

    title = re.sub(
        r"\s+",
        " ",
        title
    ).strip()

    # -------------------------
    # 去除部分媒体后缀
    # -------------------------

    title = re.sub(
        r"[｜|]\s*(量子位|AIBase)\s*$",
        "",
        title,
        flags=re.I
    )

    return title.strip(
        " -—_|｜"
    )


# =========================================================
# GitHub 展示标题
# =========================================================

def build_github_display_title(
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

    # 只取description第一句
    first_sentence = re.split(
        r"[。.!?！？]",
        description
    )[0].strip()

    if not first_sentence:
        return repo_name

    # 控制过长
    if len(first_sentence) > 90:
        first_sentence = (
            first_sentence[:87]
            + "..."
        )

    return (
        f"{repo_name}："
        f"{first_sentence}"
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


# =========================================================
# 创建item
# =========================================================

def make_item(
    title,
    display_title,
    source,
    category,
    url,
    published_at=None,
    summary="",
    priority="B",
    language="zh",
    meta=None,
):

    return {

        "id":
            make_id(
                source,
                title,
                url
            ),

        # 原始标题
        "title":
            clean_text(title),

        # 网页显示的精炼标题
        "display_title":
            clean_text(
                display_title
                or title
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
            clean_text(summary),

        "priority":
            priority,

        "language":
            language,

        "meta":
            meta or {},
    }


# =========================================================
# 自动判断分类
# =========================================================

def classify_category(
    source,
    title,
    summary=""
):

    text = (
        f"{title} {summary}"
    ).lower()

    # Nature固定
    if source == "Nature Cities":
        return "城市前沿"

    if source == "Scientific Data":
        return "城市数据"

    # 城市数据
    city_hit = any(
        word in text
        for word in
        CITY_STRONG_KEYWORDS
        + CITY_DATA_SECONDARY
    )

    data_hit = any(
        word in text
        for word in DATA_KEYWORDS
    )

    if city_hit and data_hit:
        return "城市数据"

    # AI变现
    if any(
        word.lower() in text
        for word
        in AI_MONETIZATION_KEYWORDS
    ):
        return "AI变现"

    # 其他工具
    return "提效工具"


# =========================================================
# AI新闻是否值得进入网站
# =========================================================

def is_useful_ai_news(
    title,
    summary=""
):

    text = (
        f"{title} {summary}"
    ).lower()

    return any(
        word.lower() in text
        for word in AI_USEFUL_KEYWORDS
    )


# =========================================================
# 新闻优先级
# =========================================================

def news_priority(
    title,
    summary=""
):

    text = (
        f"{title} {summary}"
    ).lower()

    strong_words = [
        "开源",
        "免费",
        "发布",
        "推出",
        "上线",
        "重大更新",
        "新功能",
        "agent",
        "智能体",
        "数据集",
        "dataset",
        "github",
        "api",
    ]

    if any(
        x.lower() in text
        for x in strong_words
    ):
        return "A"

    return "B"


# =========================================================
# 从父节点获取简短介绍
# =========================================================

def extract_context(
    node,
    title
):

    parent = node.find_parent(
        ["article", "li"]
    )

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
            ""
        ).strip()

    # 太长容易把整个页面抓进去
    if len(text) > 220:
        text = text[:220]

    return text


# =========================================================
# AIBase
# =========================================================

def fetch_aibase():

    print(
        "Fetching AIBase..."
    )

    results = []

    html = None
    final_url = None

    for page_url in AIBASE_URLS:

        try:

            response = SESSION.get(
                page_url,
                timeout=30
            )

            response.raise_for_status()

            response.encoding = "utf-8"

            html = response.text
            final_url = page_url

            break

        except Exception as e:

            print(
                "AIBase failed:",
                page_url,
                e
            )

    if not html:

        return results

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    candidates = []

    # 优先标题区域
    selectors = [
        "article h2 a",
        "article h3 a",
        "article h4 a",
        "h2 a",
        "h3 a",
        "h4 a",
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
                final_url,
                href
            )

            # 只接受AIBase内容页面
            if (
                "news.aibase.com"
                not in url
            ):
                continue

            summary = extract_context(
                node,
                title
            )

            candidates.append(
                (
                    title,
                    url,
                    summary
                )
            )

    # 如果标准selector没抓到
    if not candidates:

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
                "href"
            )

            if not title:
                continue

            if not contains_chinese(
                title
            ):
                continue

            if not (
                8 <= len(title) <= 100
            ):
                continue

            url = urljoin(
                final_url,
                href
            )

            if (
                "news.aibase.com"
                not in url
            ):
                continue

            summary = extract_context(
                node,
                title
            )

            candidates.append(
                (
                    title,
                    url,
                    summary
                )
            )

    seen = set()

    for (
        title,
        url,
        summary
    ) in candidates:

        key = (
            title.strip(),
            url
        )

        if key in seen:
            continue

        seen.add(key)

        if not is_useful_ai_news(
            title,
            summary
        ):
            continue

        display_title = refine_title(
            title
        )

        category = classify_category(
            "AIBase",
            title,
            summary
        )

        results.append(
            make_item(
                title=title,
                display_title=display_title,
                source="AIBase",
                category=category,
                url=url,
                summary=summary,
                priority=news_priority(
                    title,
                    summary
                ),
                language="zh",
            )
        )

    print(
        "AIBase:",
        len(results)
    )

    return results[:30]


# =========================================================
# 量子位
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

    # 量子位主要文章标题
    selectors = [
        "h4 a",
        "h3 a",
        "article a",
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

            if not (
                8 <= len(title) <= 100
            ):
                continue

            url = urljoin(
                QBITAI_URL,
                href
            )

            parsed = urlparse(
                url
            )

            if (
                "qbitai.com"
                not in parsed.netloc
            ):
                continue

            # 排除栏目/标签
            if any(
                part in url
                for part in [
                    "/category/",
                    "/tag/",
                    "/author/",
                    "/关于我们",
                ]
            ):
                continue

            summary = extract_context(
                node,
                title
            )

            candidates.append(
                (
                    title,
                    url,
                    summary
                )
            )

    seen = set()

    for (
        title,
        url,
        summary
    ) in candidates:

        if url in seen:
            continue

        seen.add(url)

        # 商业变现信息允许进入
        monetization = any(
            word.lower()
            in (
                title
                + " "
                + summary
            ).lower()
            for word
            in AI_MONETIZATION_KEYWORDS
        )

        if (
            not monetization
            and
            not is_useful_ai_news(
                title,
                summary
            )
        ):
            continue

        display_title = refine_title(
            title
        )

        category = classify_category(
            "量子位",
            title,
            summary
        )

        results.append(
            make_item(
                title=title,
                display_title=display_title,
                source="量子位",
                category=category,
                url=url,
                summary=summary,
                priority=news_priority(
                    title,
                    summary
                ),
                language="zh",
            )
        )

    print(
        "量子位:",
        len(results)
    )

    return results[:30]


# =========================================================
# Scientific Data相关性
# =========================================================

def scientific_data_relevant(
    title,
    summary
):

    text = (
        f"{title} {summary}"
    ).lower()

    # 必须出现dataset类词
    data_hit = any(
        keyword in text
        for keyword in DATA_KEYWORDS
    )

    if not data_hit:
        return False

    # 强城市词
    strong_hit = any(
        keyword in text
        for keyword
        in CITY_STRONG_KEYWORDS
    )

    if strong_hit:
        return True

    # 次级空间数据词不能单独命中
    secondary_hit = any(
        keyword in text
        for keyword
        in CITY_DATA_SECONDARY
    )

    # 必须同时具有城市语境
    city_context = any(
        keyword in text
        for keyword in [
            "urban",
            "city",
            "cities",
            "building",
            "population",
            "settlement",
            "mobility",
            "transport",
        ]
    )

    return (
        secondary_hit
        and city_context
    )


# =========================================================
# Nature
# =========================================================

def fetch_nature():

    print(
        "Fetching Nature..."
    )

    results = []

    for config in NATURE_FEEDS:

        print(
            "Fetching",
            config["name"]
        )

        feed = feedparser.parse(
            config["url"]
        )

        if getattr(
            feed,
            "bozo",
            False
        ):

            print(
                config["name"],
                "RSS warning:",
                getattr(
                    feed,
                    "bozo_exception",
                    ""
                )
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

            if (
                not title
                or not url
            ):
                continue

            # Scientific Data严格筛选
            if (
                config["name"]
                == "Scientific Data"
            ):

                if not scientific_data_relevant(
                    title,
                    summary
                ):
                    continue

            display_title = refine_title(
                title
            )

            results.append(
                make_item(
                    title=title,
                    display_title=display_title,
                    source=config[
                        "name"
                    ],
                    category=config[
                        "category"
                    ],
                    url=url,
                    published_at=published,
                    summary=summary,
                    priority="A",
                    language="en",
                )
            )

    print(
        "Nature total:",
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

    # 排除
    if any(
        keyword in text
        for keyword
        in GITHUB_NEGATIVE
    ):
        return False

    # 至少命中一个相关词
    return any(
        keyword in text
        for keyword
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

        now = datetime.now(
            timezone.utc
        )

        age_days = max(
            1,
            (
                now - created
            ).days + 1
        )

        speed = (
            stars / age_days
        )

    except Exception:

        speed = 0

    # 新项目增长非常快
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
            "application/vnd.github+json",
        "User-Agent":
            "icat-research-radar",
    }

    if token:

        headers[
            "Authorization"
        ] = f"Bearer {token}"

    since = (
        datetime.now(
            timezone.utc
        )
        - timedelta(days=21)
    ).strftime(
        "%Y-%m-%d"
    )

    seen_urls = set()

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
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 10,
                },
                timeout=30,
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

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            stars = repo.get(
                "stargazers_count",
                0
            )

            # 避免大量无人关注项目
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

            category = classify_category(
                "GitHub",
                full_name,
                description
            )

            display_title = (
                build_github_display_title(
                    full_name,
                    description
                )
            )

            created_at = repo.get(
                "created_at"
            )

            results.append(
                make_item(
                    title=full_name,
                    display_title=
                        display_title,
                    source="GitHub",
                    category=category,
                    url=url,
                    published_at=
                        created_at,
                    summary=description,
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
        "GitHub:",
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
            "Old data error:",
            e
        )

        return []


# =========================================================
# 清理过旧数据
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

def source_rank(
    source
):

    ranks = {

        # 中文优先
        "AIBase": 100,
        "量子位": 95,

        # 专业英文原始源
        "Nature Cities": 80,
        "Scientific Data": 80,

        # GitHub最后补漏
        "GitHub": 60,
    }

    return ranks.get(
        source,
        50
    )


# =========================================================
# 合并去重
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

            old_detected = (
                merged[
                    item_id
                ].get(
                    "detected_at"
                )
            )

            merged[
                item_id
            ].update(
                item
            )

            if old_detected:

                merged[
                    item_id
                ][
                    "detected_at"
                ] = old_detected

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

    # 日期优先；
    # 同等日期中文媒体优先
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

def save_data(
    items
):

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # 各栏目数量
    category_counts = {
        "AI变现": 0,
        "提效工具": 0,
        "城市数据": 0,
        "城市前沿": 0,
    }

    for item in items:

        category = item.get(
            "category"
        )

        if category in category_counts:

            category_counts[
                category
            ] += 1

    output = {

        "updated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "count":
            len(items),

        "category_counts":
            category_counts,

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
        "Research Radar V2 Start"
    )

    print(
        "================================"
    )

    old_items = load_old_data()

    print(
        "Existing items:",
        len(old_items)
    )

    new_items = []

    # -------------------------
    # 中文来源优先
    # -------------------------

    aibase_items = (
        fetch_aibase()
    )

    qbitai_items = (
        fetch_qbitai()
    )

    # -------------------------
    # 专业原始来源
    # -------------------------

    nature_items = (
        fetch_nature()
    )

    github_items = (
        fetch_github()
    )

    new_items.extend(
        aibase_items
    )

    new_items.extend(
        qbitai_items
    )

    new_items.extend(
        nature_items
    )

    new_items.extend(
        github_items
    )

    print(
        "--------------------------------"
    )

    print(
        "New candidates:",
        len(new_items)
    )

    final_items = merge_items(
        old_items,
        new_items
    )

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
        "Research Radar V2 Done"
    )

    print(
        "================================"
    )


if __name__ == "__main__":

    main()
