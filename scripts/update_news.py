import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# 基础配置
# =========================================================

DATA_FILE = Path("data/news.json")

MAX_ITEMS = 500
KEEP_DAYS = 45

# 图片抓取规则版本
# 升级这个数字后，旧数据会重新抓图
IMAGE_RULE_VERSION = 6

# 一次 Action 最多进入多少个详情页
DETAIL_FETCH_LIMIT = 220

# 并行数
DETAIL_WORKERS = 10


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
    "首次验证",
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
    "取得突破",
    "实现突破",
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
# AI关键词
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
# 文本
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
# 乱码检测
# =========================================================

def looks_mojibake(text):

    if not text:
        return False

    bad_tokens = [
        "Ã",
        "Â",
        "â€",
        "â€™",
        "â€œ",
        "â€˜",
        "å",
        "æ",
        "ç",
        "é",
        "ï",
        "ð",
        "锟斤拷",
        "�",
    ]

    score = sum(
        text.count(token)
        for token in bad_tokens
    )

    return score >= 2


def clean_summary(text):

    text = clean_text(
        text
    )

    if not text:
        return ""

    if looks_mojibake(
        text
    ):
        return ""

    # 只有一个句号之类
    if len(text) < 12:
        return ""

    if text in {
        ".",
        "。",
        "…",
        "...",
    }:
        return ""

    if len(text) > 260:

        text = (
            text[:257]
            .rstrip()
            + "..."
        )

    return text


# =========================================================
# 正确读取网页编码
# =========================================================

def decode_response(response):

    raw = response.content

    charset = None


    # -------------------------
    # HTTP Header
    # -------------------------

    content_type = (
        response.headers
        .get(
            "content-type",
            ""
        )
    )

    match = re.search(
        r"charset\s*=\s*['\"]?"
        r"([a-zA-Z0-9_\-]+)",
        content_type,
        flags=re.I
    )

    if match:

        charset = (
            match.group(1)
            .lower()
        )


    # -------------------------
    # HTML meta
    # -------------------------

    if not charset:

        head = raw[:8192]

        match = re.search(
            br"charset\s*=\s*[\"']?"
            br"([a-zA-Z0-9_\-]+)",
            head,
            flags=re.I
        )

        if match:

            try:

                charset = (
                    match.group(1)
                    .decode(
                        "ascii",
                        errors="ignore"
                    )
                    .lower()
                )

            except Exception:

                charset = None


    # -------------------------
    # 编码映射
    # -------------------------

    if charset in {
        "gb2312",
        "gbk",
        "gb_2312",
    }:

        charset = "gb18030"


    # -------------------------
    # 首先采用网页声明
    # -------------------------

    if charset:

        try:

            return raw.decode(
                charset,
                errors="replace"
            )

        except Exception:
            pass


    # -------------------------
    # UTF-8
    # -------------------------

    try:

        return raw.decode(
            "utf-8"
        )

    except UnicodeDecodeError:
        pass


    # -------------------------
    # 中文旧网页
    # -------------------------

    try:

        return raw.decode(
            "gb18030"
        )

    except Exception:
        pass


    return raw.decode(
        "utf-8",
        errors="replace"
    )


# =========================================================
# 标题处理
# =========================================================

def refine_title(title):

    title = clean_text(
        title
    )

    if not title:
        return ""

    title = re.sub(
        r"^#\s*\d+\s*",
        "",
        title
    )

    title = re.sub(
        r"^(AI日报|AI资讯)"
        r"[：:\s]*",
        "",
        title,
        flags=re.I
    )

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
# ID / 日期
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
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[:16]


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

        r"(\d{4}[-/.]\d{1,2}"
        r"[-/.]\d{1,2}"
        r"(?:\s+\d{1,2}:\d{2}"
        r"(?::\d{2})?)?)",

        r"(\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|"
        r"Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{4})",

        r"(\d{4}年\d{1,2}月"
        r"\d{1,2}日"
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
# 突破
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
# 图片 URL
# =========================================================

BAD_IMAGE_TOKENS = [

    "logo",
    "favicon",
    "avatar",

    "icon",
    "sprite",

    "placeholder",
    "default",

    "loading",
    "blank",

    "qrcode",
    "qr-code",
    "weixin",
    "wechat",

    "transparent",
    "pixel",
]


def normalize_image_url(
    image_url,
    page_url
):

    if not image_url:
        return ""

    image_url = (
        image_url
        .strip()
    )

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

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return ""

    return image_url


def image_is_bad(
    url,
    alt=""
):

    text = (
        f"{url} {alt}"
    ).lower()

    return any(
        token in text
        for token
        in BAD_IMAGE_TOKENS
    )


# =========================================================
# img src
# =========================================================

def get_img_src(
    img,
    page_url
):

    candidates = [

        img.get(
            "data-original"
        ),

        img.get(
            "data-src"
        ),

        img.get(
            "data-lazy-src"
        ),

        img.get(
            "data-url"
        ),

        img.get(
            "src"
        ),
    ]


    # srcset
    srcset = img.get(
        "srcset"
    )

    if srcset:

        parts = []

        for item in (
            srcset.split(",")
        ):

            url = (
                item.strip()
                .split(" ")[0]
            )

            if url:

                parts.append(
                    url
                )

        if parts:

            candidates.insert(
                0,
                parts[-1]
            )


    for candidate in candidates:

        url = normalize_image_url(
            candidate,
            page_url
        )

        if url:

            return url

    return ""


# =========================================================
# 图片评分
# =========================================================

def get_numeric_attr(
    img,
    name
):

    value = img.get(
        name
    )

    if not value:
        return 0

    match = re.search(
        r"\d+",
        str(value)
    )

    if not match:
        return 0

    try:

        return int(
            match.group(0)
        )

    except Exception:

        return 0


def image_score(
    img,
    page_url
):

    url = get_img_src(
        img,
        page_url
    )

    if not url:
        return -9999


    alt = clean_text(
        img.get(
            "alt",
            ""
        )
    )


    if image_is_bad(
        url,
        alt
    ):

        return -9999


    score = 0


    # -------------------------
    # header/footer/nav图排除
    # -------------------------

    for ancestor in (
        img.parents
    ):

        name = getattr(
            ancestor,
            "name",
            ""
        )

        if name in {
            "header",
            "footer",
            "nav",
            "aside",
        }:

            score -= 500

            break


    # -------------------------
    # figure 高优先级
    # -------------------------

    if img.find_parent(
        "figure"
    ):

        score += 140


    # -------------------------
    # article/main
    # -------------------------

    if img.find_parent(
        "article"
    ):

        score += 80


    if img.find_parent(
        "main"
    ):

        score += 40


    # -------------------------
    # class / id 语义
    # -------------------------

    ancestor_text = ""

    for ancestor in list(
        img.parents
    )[:6]:

        classes = (
            ancestor.get(
                "class",
                []
            )
            if hasattr(
                ancestor,
                "get"
            )
            else []
        )

        element_id = (
            ancestor.get(
                "id",
                ""
            )
            if hasattr(
                ancestor,
                "get"
            )
            else ""
        )

        ancestor_text += (
            " "
            + " ".join(
                classes
                if isinstance(
                    classes,
                    list
                )
                else [str(classes)]
            )
            + " "
            + str(
                element_id
            )
        )


    ancestor_text = (
        ancestor_text.lower()
    )


    good_context = [

        "article",
        "content",
        "detail",
        "正文",
        "news",
        "post",
        "body",
        "figure",
    ]


    if any(
        word in ancestor_text
        for word in good_context
    ):

        score += 80


    bad_context = [

        "recommend",
        "related",
        "sidebar",
        "footer",
        "header",
        "logo",
        "menu",
        "nav",
        "author",
    ]


    if any(
        word in ancestor_text
        for word in bad_context
    ):

        score -= 150


    # -------------------------
    # 尺寸
    # -------------------------

    width = get_numeric_attr(
        img,
        "width"
    )

    height = get_numeric_attr(
        img,
        "height"
    )


    if width >= 600:

        score += 80

    elif width >= 350:

        score += 45

    elif (
        width
        and width < 160
    ):

        score -= 100


    if height >= 300:

        score += 40

    elif (
        height
        and height < 100
    ):

        score -= 70


    # -------------------------
    # alt正文说明
    # -------------------------

    if len(alt) >= 6:

        score += 15


    # -------------------------
    # 常见正文图片路径
    # -------------------------

    path_lower = (
        urlparse(
            url
        ).path.lower()
    )

    good_path = [

        "/upload/",
        "/uploads/",
        "/image/",
        "/images/",
        "/media/",
        "/figure/",
    ]


    if any(
        token in path_lower
        for token
        in good_path
    ):

        score += 15


    return score


# =========================================================
# 正文图片
# =========================================================

def extract_best_content_image(
    soup,
    page_url
):

    candidates = []


    for img in soup.find_all(
        "img"
    ):

        score = image_score(
            img,
            page_url
        )

        if score < 20:
            continue

        url = get_img_src(
            img,
            page_url
        )

        if not url:
            continue

        candidates.append(
            (
                score,
                url
            )
        )


    if not candidates:

        return ""


    candidates.sort(
        key=lambda x:
            x[0],
        reverse=True
    )


    return candidates[
        0
    ][1]


# =========================================================
# OG 图片
# =========================================================

def extract_og_image(
    soup,
    page_url
):

    selectors = [

        'meta[property="og:image"]',

        'meta[property="og:image:secure_url"]',

        'meta[name="twitter:image"]',

        'meta[property="twitter:image"]',
    ]


    for selector in selectors:

        node = soup.select_one(
            selector
        )

        if not node:
            continue


        url = normalize_image_url(
            node.get(
                "content",
                ""
            ),
            page_url
        )


        if not url:
            continue


        if image_is_bad(
            url
        ):
            continue


        return url


    return ""


# =========================================================
# 正文摘要
# =========================================================

def extract_article_summary(
    soup
):

    # -------------------------
    # meta description
    # -------------------------

    selectors = [

        'meta[property="og:description"]',
        'meta[name="description"]',
        'meta[name="twitter:description"]',
    ]


    for selector in selectors:

        node = soup.select_one(
            selector
        )

        if not node:
            continue


        text = clean_summary(
            node.get(
                "content",
                ""
            )
        )


        if text:

            return text


    # -------------------------
    # 正文第一段
    # -------------------------

    paragraph_selectors = [

        "article p",

        ".article-content p",
        ".article_content p",

        ".article-body p",
        ".articleBody p",

        ".news-content p",
        ".news_content p",

        ".content p",
        ".detail p",

        "main p",
    ]


    for selector in paragraph_selectors:

        for p in soup.select(
            selector
        ):

            text = clean_summary(
                p.get_text(
                    " ",
                    strip=True
                )
            )

            if len(text) >= 30:

                return text


    return ""


# =========================================================
# 文章详情页
# =========================================================

def fetch_page_details(
    url,
    source
):

    result = {

        "image_url": "",
        "summary": "",
        "image_method": "",
    }


    if not url:

        return result


    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        response.raise_for_status()


        html = decode_response(
            response
        )


        soup = BeautifulSoup(
            html,
            "html.parser"
        )


        # =================================================
        # 1. 永远优先正文图片
        # =================================================

        image_url = (
            extract_best_content_image(
                soup,
                url
            )
        )


        if image_url:

            result[
                "image_url"
            ] = image_url

            result[
                "image_method"
            ] = "body"


        # =================================================
        # 2. 正文没有图片再尝试 OG
        #
        # 科学网禁用 OG：
        # 防止反复抓到科学网 Logo
        # =================================================

        allow_og = (
            source
            != "科学网"
        )


        if (
            not result[
                "image_url"
            ]
            and allow_og
        ):

            og_image = (
                extract_og_image(
                    soup,
                    url
                )
            )


            if og_image:

                result[
                    "image_url"
                ] = og_image

                result[
                    "image_method"
                ] = "og"


        # =================================================
        # 摘要
        # =================================================

        result[
            "summary"
        ] = (
            extract_article_summary(
                soup
            )
        )


    except Exception as e:

        print(
            "Detail failed:",
            source,
            url,
            e
        )


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
                or refine_title(
                    title
                )
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

        # 详情页后续补充
        "summary":
            clean_summary(
                summary
            ),

        "image_url":
            "",

        "image_method":
            "",

        "image_rule_version":
            IMAGE_RULE_VERSION,

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
# AI
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

    if is_breakthrough(
        text
    ):

        return "A"


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


    if any(
        word in low
        for word
        in strong
    ):

        return "A"


    return "B"


# =========================================================
# AIBase
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

        html = decode_response(
            response
        )


    except Exception as e:

        print(
            "AIBase failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        html,
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
            contains_chinese(
                title
            )
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


        if not useful_ai_text(
            title
        ):

            continue


        seen.add(
            url
        )


        results.append(

            make_item(

                title=title,

                source="AIBase",

                category="AI变现",

                url=url,

                priority=
                    ai_priority(
                        title
                    ),

                language="zh",

                is_breakthrough_item=
                    is_breakthrough(
                        title
                    ),
            )
        )


    print(
        "AIBase:",
        len(results)
    )

    return results[:45]


# =========================================================
# 量子位
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

        html = decode_response(
            response
        )


    except Exception as e:

        print(
            "量子位 failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        html,
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
            contains_chinese(
                title
            )
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


        if not useful_ai_text(
            title
        ):

            continue


        seen.add(
            url
        )


        breakthrough = (
            is_breakthrough(
                title
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

                priority=(
                    "A"
                    if breakthrough
                    else ai_priority(
                        title
                    )
                ),

                language="zh",

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
# 科技日报
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

        html = decode_response(
            response
        )


    except Exception as e:

        print(
            "科技日报 failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        html,
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
            contains_chinese(
                title
            )
            and
            6 <= len(title) <= 120
        ):

            continue


        url = urljoin(
            STD_BREAKTHROUGH_URL,
            node.get(
                "href"
            )
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


        results.append(

            make_item(

                title=title,

                source="科技日报",

                category="前沿动态",

                url=url,

                priority="A",

                language="zh",

                is_breakthrough_item=
                    is_breakthrough(
                        title
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

        html = decode_response(
            response
        )


    except Exception as e:

        print(
            "科学网 failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        html,
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


        if "/htmlnews/" not in url:

            continue


        title = clean_text(
            node.get_text(
                " ",
                strip=True
            )
        )


        if not (
            contains_chinese(
                title
            )
            and
            6 <= len(title) <= 120
        ):

            continue


        if url in seen:

            continue


        # 科学网只收突破类
        if not is_breakthrough(
            title
        ):

            continue


        seen.add(
            url
        )


        results.append(

            make_item(

                title=title,

                source="科学网",

                category="前沿动态",

                url=url,

                priority="A",

                language="zh",

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

        html = decode_response(
            response
        )


    except Exception as e:

        print(
            "DeepTech failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        html,
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
            contains_chinese(
                title
            )
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


        if not is_breakthrough(
            title
        ):

            continue


        seen.add(
            url
        )


        results.append(

            make_item(

                title=title,

                source="DeepTech深科技",

                category="前沿动态",

                url=url,

                priority="A",

                language="zh",

                is_breakthrough_item=True,
            )
        )


    print(
        "DeepTech:",
        len(results)
    )

    return results[:30]


# =========================================================
# Nature
# =========================================================

def fetch_nature_journal(
    feed_url,
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


            summary = clean_summary(
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


            results.append(

                make_item(

                    title=title,

                    source=source,

                    category=
                        "期刊论文",

                    url=url,

                    published_at=
                        published,

                    summary=
                        summary,

                    priority="A",

                    language="en",

                    is_breakthrough_item=
                        False,
                )
            )


    except Exception as e:

        print(
            source,
            "failed:",
            e
        )


    print(
        source,
        ":",
        len(results)
    )


    return results[:45]


# =========================================================
# GitHub
# =========================================================

def github_relevant(
    name,
    description
):

    text = (
        f"{name} "
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

                    category=
                        "提效工具",

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
# 历史数据
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
# 旧数据迁移
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


        summary = clean_summary(
            item.get(
                "summary",
                ""
            )
        )


        text = (
            f"{title} "
            f"{summary}"
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
                title,
                summary
            ):

                continue


            item[
                "category"
            ] = "提效工具"


        else:

            continue


        item[
            "summary"
        ] = summary


        if not item.get(
            "display_title"
        ):

            item[
                "display_title"
            ] = refine_title(
                title
            )


        # =================================================
        # 旧图片规则不是 V6
        # 全部清掉重新抓
        #
        # 这是解决当前 ScienceNet Logo
        # 和 TOOL 占位问题的关键
        # =================================================

        if (
            item.get(
                "image_rule_version"
            )
            != IMAGE_RULE_VERSION
        ):

            item[
                "image_url"
            ] = ""

            item[
                "image_method"
            ] = ""


        item[
            "image_rule_version"
        ] = IMAGE_RULE_VERSION


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
# 批量进入详情页
# =========================================================

def enrich_details(
    items
):

    # =====================================================
    # 需要进入详情页的：
    #
    # 1. 没有图片
    # 2. 摘要乱码
    # 3. 中文媒体没有摘要
    # =====================================================

    candidates = []


    for item in items:

        need_image = (
            not item.get(
                "image_url"
            )
        )


        need_summary = (
            not item.get(
                "summary"
            )

            or

            looks_mojibake(
                item.get(
                    "summary",
                    ""
                )
            )
        )


        if (
            need_image
            or need_summary
        ):

            candidates.append(
                item
            )


    # 去重URL
    unique = {}

    for item in candidates:

        url = item.get(
            "url"
        )

        if (
            url
            and url not in unique
        ):

            unique[
                url
            ] = item


    candidates = list(
        unique.values()
    )[:DETAIL_FETCH_LIMIT]


    print(
        "Detail pages:",
        len(candidates)
    )


    details_map = {}


    with ThreadPoolExecutor(
        max_workers=
            DETAIL_WORKERS
    ) as executor:


        futures = {

            executor.submit(
                fetch_page_details,
                item.get(
                    "url"
                ),
                item.get(
                    "source"
                )
            ):
            item

            for item in candidates
        }


        for future in as_completed(
            futures
        ):

            item = futures[
                future
            ]


            url = item.get(
                "url"
            )


            try:

                details_map[
                    url
                ] = future.result()

            except Exception:

                details_map[
                    url
                ] = {
                    "image_url": "",
                    "summary": "",
                    "image_method": "",
                }


    # =====================================================
    # 写回
    # =====================================================

    for item in items:

        details = details_map.get(
            item.get(
                "url"
            )
        )


        if not details:

            continue


        image_url = details.get(
            "image_url"
        )


        if image_url:

            item[
                "image_url"
            ] = image_url

            item[
                "image_method"
            ] = details.get(
                "image_method",
                ""
            )


        detail_summary = (
            clean_summary(
                details.get(
                    "summary",
                    ""
                )
            )
        )


        if (
            detail_summary
            and
            (
                not item.get(
                    "summary"
                )

                or

                looks_mojibake(
                    item.get(
                        "summary",
                        ""
                    )
                )
            )
        ):

            item[
                "summary"
            ] = detail_summary


    return items


# =========================================================
# 删除没有图片的资讯
# =========================================================

def only_items_with_images(
    items
):

    output = []


    for item in items:

        image_url = item.get(
            "image_url",
            ""
        )


        if not image_url:

            continue


        if image_is_bad(
            image_url
        ):

            continue


        output.append(
            item
        )


    return output


# =========================================================
# 图片不能重复
# =========================================================

def image_key(url):

    if not url:

        return ""


    parsed = urlparse(
        url
    )


    return (
        parsed.scheme
        + "://"
        + parsed.netloc
        + parsed.path
    ).lower()


def remove_duplicate_images(
    items
):

    seen_images = set()

    output = []


    for item in items:

        key = image_key(
            item.get(
                "image_url"
            )
        )


        if not key:

            continue


        # 同一张图已经出现
        # 后面的资讯不再收录
        if key in seen_images:

            continue


        seen_images.add(
            key
        )


        output.append(
            item
        )


    return output


# =========================================================
# 删除旧新闻
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


            old.update(
                item
            )


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
        "=" * 60
    )

    print(
        "ICAT Research Radar V6"
    )

    print(
        "=" * 60
    )


    # =====================================================
    # 旧数据
    # =====================================================

    old_items = (
        load_old_data()
    )


    old_items = (
        normalize_old_items(
            old_items
        )
    )


    # =====================================================
    # 新数据
    # =====================================================

    aibase_items = (
        fetch_aibase()
    )


    qbitai_items = (
        fetch_qbitai()
    )


    stdaily_items = (
        fetch_stdaily()
    )


    sciencenet_items = (
        fetch_sciencenet()
    )


    deeptech_items = (
        fetch_deeptech()
    )


    scientific_items = (
        fetch_nature_journal(
            SCIENTIFIC_DATA_RSS,
            "Scientific Data"
        )
    )


    nature_cities_items = (
        fetch_nature_journal(
            NATURE_CITIES_RSS,
            "Nature Cities"
        )
    )


    github_items = (
        fetch_github()
    )


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


    # =====================================================
    # 合并
    # =====================================================

    all_items = (
        merge_items(
            old_items,
            new_items
        )
    )


    print(
        "Before details:",
        len(all_items)
    )


    # =====================================================
    # 所有没有合格图片的内容
    # 进入详情页抓正文图
    # =====================================================

    all_items = (
        enrich_details(
            all_items
        )
    )


    # =====================================================
    # 乱码摘要再次清理
    # =====================================================

    for item in all_items:

        item[
            "summary"
        ] = clean_summary(
            item.get(
                "summary",
                ""
            )
        )


    # =====================================================
    # 没有真实图片
    # 直接淘汰
    # =====================================================

    all_items = (
        only_items_with_images(
            all_items
        )
    )


    # =====================================================
    # 图片重复
    # 只留第一条
    # =====================================================

    all_items = (
        remove_duplicate_images(
            all_items
        )
    )


    # =====================================================
    # 最终限制
    # =====================================================

    all_items = all_items[
        :MAX_ITEMS
    ]


    save_data(
        all_items
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
        "Visible with image:",
        len(all_items)
    )

    print(
        "=" * 60
    )


if __name__ == "__main__":

    main()
