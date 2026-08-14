import os
import re
import json
import math
import hashlib

from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# ICAT Research Radar V8
#
# 功能：
#
# 1. AIBase              → AI变现
# 2. 量子位              → 提效工具 / 前沿动态
# 3. 科技日报            → 前沿动态
# 4. 科学网              → 前沿动态
# 5. DeepTech            → 前沿动态
# 6. GitHub              → 提效工具
# 7. Scientific Data     → 独立期刊入口
# 8. Nature Cities       → 独立期刊入口
#
# 9. 百度热搜
#       ↓
#    科研热点筛选
#       ↓
#    Nature Portfolio近期论文匹配
#       ↓
#    公众号热点候选
#
# =========================================================


# =========================================================
# 基础路径
# =========================================================

DATA_FILE = Path("data/news.json")


# =========================================================
# 基础参数
# =========================================================

MAX_ITEMS = 500

KEEP_DAYS = 45


# 普通资讯详情页最大抓取数量
DETAIL_FETCH_LIMIT = 220


# Nature热点论文池最大详情页抓取量
HOT_PAPER_DETAIL_LIMIT = 60


# 并发数量
DETAIL_WORKERS = 10


# 图片规则版本
#
# 如果以后修改图片抓取逻辑，
# 将数字改成9、10……
# 旧图片会重新抓取
IMAGE_RULE_VERSION = 8


# 最多保存热点数量
MAX_HOTSPOTS = 12


# 每个热点最多关联几篇论文
MAX_RELATED_PAPERS = 3


# =========================================================
# HTTP
# =========================================================

HEADERS = {

    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
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

        allowed_methods=[
            "GET"
        ],
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
# 数据源
# =========================================================

AIBASE_URL = (
    "https://news.aibase.com/zh/news"
)


QBITAI_URL = (
    "https://www.qbitai.com/"
    "category/%E8%B5%84%E8%AE%AF"
)


STD_BREAKTHROUGH_URL = (
    "https://www.stdaily.com/"
    "web/spxw/node_706.html"
)


SCIENCENET_URL = (
    "https://news.sciencenet.cn/"
)


DEEPTECH_URL = (
    "https://www.deeptechchina.com/"
)


BAIDU_HOT_URL = (
    "https://top.baidu.com/"
    "board?tab=realtime"
)


# =========================================================
# Nature两个固定栏目
# =========================================================

SCIENTIFIC_DATA_URL = (
    "https://www.nature.com/"
    "sdata/articles"
)


NATURE_CITIES_URL = (
    "https://www.nature.com/"
    "natcities/research-articles"
)


# =========================================================
# Nature热点论文池
#
# 用于：
# 百度热点 → Nature相关文章
# =========================================================

NATURE_POOL_SOURCES = [

    {
        "name":
            "Nature",

        "url":
            "https://www.nature.com/"
            "nature/research-articles",
    },

    {
        "name":
            "Nature Communications",

        "url":
            "https://www.nature.com/"
            "ncomms/articles",
    },

    {
        "name":
            "Nature Climate Change",

        "url":
            "https://www.nature.com/"
            "nclimate/research-articles",
    },

    {
        "name":
            "Nature Human Behaviour",

        "url":
            "https://www.nature.com/"
            "nathumbehav/research-articles",
    },

    {
        "name":
            "Nature Medicine",

        "url":
            "https://www.nature.com/"
            "nm/research-articles",
    },

    {
        "name":
            "Scientific Reports",

        "url":
            "https://www.nature.com/"
            "srep/articles",
    },

    {
        "name":
            "Scientific Data",

        "url":
            SCIENTIFIC_DATA_URL,
    },

    {
        "name":
            "Nature Cities",

        "url":
            NATURE_CITIES_URL,
    },

]


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
# GitHub搜索
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
# 热点主题规则
#
# cn:
# 百度热搜匹配
#
# en:
# Nature英文论文匹配
# =========================================================

HOT_TOPIC_RULES = [

    # -----------------------------------------------------
    # AI / 机器人
    # -----------------------------------------------------

    {

        "label":
            "人工智能",

        "cn": [

            "人工智能",
            "AI",
            "大模型",
            "机器人",
            "智能体",
            "算法",

            "自动驾驶",
            "无人驾驶",

            "脑机接口",

            "ChatGPT",
            "DeepSeek",
            "Claude",
            "Gemini",

        ],

        "en": [

            "artificial intelligence",
            "machine learning",
            "deep learning",

            "large language model",
            "language model",

            "generative ai",

            "robot",
            "robotics",

            "autonomous vehicle",
            "autonomous driving",

            "brain computer interface",
            "brain-computer interface",

        ],

        "angle":
            "从热点事件切入，讨论AI技术真正发生了什么变化，"
            "再用近期Nature研究解释其能力边界、社会影响与未来趋势。",

    },


    # -----------------------------------------------------
    # 气候 / 极端天气
    # -----------------------------------------------------

    {

        "label":
            "气候环境",

        "cn": [

            "高温",
            "热浪",

            "暴雨",
            "洪水",
            "山洪",
            "泥石流",

            "台风",

            "极端天气",

            "气候",
            "全球变暖",

            "空气污染",
            "PM2.5",
            "臭氧",

            "碳排放",
            "碳中和",

            "污染",
            "环保",

        ],

        "en": [

            "climate change",
            "global warming",

            "extreme heat",
            "heatwave",
            "heat wave",

            "extreme weather",

            "flood",
            "flooding",

            "rainfall",
            "precipitation",

            "landslide",

            "air pollution",
            "PM2.5",
            "ozone",

            "carbon emission",
            "carbon emissions",

        ],

        "angle":
            "从正在发生的天气或环境事件切入，"
            "利用Nature研究解释极端事件形成机制、风险变化和长期趋势。",

    },


    # -----------------------------------------------------
    # 城市 / 人口 / 社会
    # -----------------------------------------------------

    {

        "label":
            "城市社会",

        "cn": [

            "城市",
            "住房",
            "房价",

            "交通",
            "通勤",

            "人口",
            "老龄化",
            "生育",

            "就业",
            "工作",
            "职场",

            "城市更新",

            "社区",

            "教育",
            "大学",
            "博士",
            "高校",

        ],

        "en": [

            "urban",
            "city",
            "cities",

            "housing",

            "transport",
            "mobility",
            "commuting",

            "population",

            "ageing",
            "aging",

            "fertility",
            "birth rate",

            "employment",
            "workplace",

            "education",
            "university",

        ],

        "angle":
            "从公众正在讨论的城市或社会问题切入，"
            "用Nature相关研究解释个体现象背后的结构性变化。",

    },


    # -----------------------------------------------------
    # 健康医学
    # -----------------------------------------------------

    {

        "label":
            "健康医学",

        "cn": [

            "健康",

            "睡眠",
            "熬夜",

            "肥胖",
            "减肥",

            "癌症",
            "肿瘤",

            "糖尿病",

            "心脏",
            "心血管",

            "抑郁",
            "焦虑",

            "疾病",
            "病毒",
            "疫苗",

            "衰老",
            "长寿",
            "寿命",

            "饮食",
            "营养",

            "运动",

            "保健品",

        ],

        "en": [

            "health",

            "sleep",

            "obesity",
            "weight loss",

            "cancer",
            "tumour",
            "tumor",

            "diabetes",

            "cardiovascular",
            "heart",

            "depression",
            "anxiety",

            "disease",
            "virus",
            "vaccine",

            "ageing",
            "aging",
            "longevity",

            "diet",
            "nutrition",

            "exercise",

        ],

        "angle":
            "从大众健康焦虑或生活方式热点切入，"
            "用Nature论文区分科学证据、相关性与网络流行说法。",

    },


    # -----------------------------------------------------
    # 能源 / 材料 / 芯片
    # -----------------------------------------------------

    {

        "label":
            "前沿科技",

        "cn": [

            "新能源",

            "电池",
            "储能",

            "光伏",
            "太阳能",

            "钙钛矿",

            "核能",
            "核聚变",

            "芯片",
            "半导体",

            "量子",

            "超导",

            "材料",

        ],

        "en": [

            "battery",
            "energy storage",

            "solar",
            "photovoltaic",

            "perovskite",

            "nuclear energy",
            "fusion energy",

            "semiconductor",
            "chip",

            "quantum",

            "superconduct",

            "materials science",

        ],

        "angle":
            "从技术突破或产业热点切入，"
            "结合Nature论文解释关键技术路线、性能提升以及距离实际应用还有多远。",

    },


    # -----------------------------------------------------
    # 生态 / 生物多样性
    # -----------------------------------------------------

    {

        "label":
            "生态生命",

        "cn": [

            "动物",
            "植物",

            "物种",
            "生物多样性",

            "森林",

            "海洋",

            "昆虫",

            "生态",

            "野生动物",

        ],

        "en": [

            "biodiversity",

            "species",

            "forest",

            "marine",
            "ocean",

            "insect",

            "ecosystem",

            "wildlife",

            "ecology",

        ],

        "angle":
            "从公众关注的自然现象或物种新闻切入，"
            "结合Nature生态研究解释其背后的生态过程和环境意义。",

    },

]


# =========================================================
# 热点明显排除词
#
# 避免娱乐体育占满栏目
# =========================================================

HOT_EXCLUDE_WORDS = [

    "票房",
    "电影",

    "电视剧",

    "明星",
    "演员",

    "路演",

    "演唱会",

    "综艺",

    "发型",

    "婚礼",

    "离婚",

    "恋情",

    "国乒",
    "足球",
    "篮球",

    "NBA",
    "WTT",

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


# =========================================================
# 中文判断
# =========================================================

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
# 乱码判断
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

        "锟斤拷",

        "�",
    ]

    score = sum(

        text.count(
            token
        )

        for token
        in bad_tokens
    )

    return (
        score >= 2
    )


# =========================================================
# 摘要清理
# =========================================================

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

    if len(text) < 12:

        return ""

    if len(text) > 280:

        text = (
            text[:277]
            .rstrip()
            + "..."
        )

    return text


# =========================================================
# 网页编码
# =========================================================

def decode_response(
    response
):

    raw = response.content

    charset = None


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


    # HTML meta
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


    if charset in {

        "gb2312",
        "gbk",
        "gb_2312",

    }:

        charset = "gb18030"


    if charset:

        try:

            return raw.decode(
                charset,
                errors="replace"
            )

        except Exception:

            pass


    try:

        return raw.decode(
            "utf-8"
        )

    except Exception:

        pass


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
# 标题精炼
# =========================================================

def refine_title(
    title
):

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
        raw.encode(
            "utf-8"
        )
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
# 从文字提取日期
# =========================================================

def extract_date_from_text(
    text
):

    if not text:

        return None


    patterns = [

        # 2026-08-14

        r"(\d{4}[-/.]\d{1,2}"
        r"[-/.]\d{1,2}"
        r"(?:\s+\d{1,2}:\d{2}"
        r"(?::\d{2})?)?)",


        # 14 Aug 2026

        r"(\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|"
        r"Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{4})",


        # 2026年8月14日

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
# 突破判断
# =========================================================

def is_breakthrough(
    text
):

    text = clean_text(
        text
    )


    return any(

        keyword in text

        for keyword
        in BREAKTHROUGH_KEYWORDS

    )


# =========================================================
# 图片过滤
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

    "wechat",

    "weixin",

    "transparent",

    "pixel",

]


# =========================================================
# 图片URL标准化
# =========================================================

def normalize_image_url(
    image_url,
    page_url
):

    if not image_url:

        return ""


    image_url = (
        str(
            image_url
        )
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


# =========================================================
# 坏图片判断
# =========================================================

def image_is_bad(
    url,
    alt=""
):

    text = (
        f"{url} "
        f"{alt}"
    ).lower()


    return any(

        token in text

        for token
        in BAD_IMAGE_TOKENS

    )


# =========================================================
# 获取img地址
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


    # picture/source
    picture = img.find_parent(
        "picture"
    )


    if picture:

        sources = picture.find_all(
            "source"
        )


        for source in sources:

            srcset = source.get(
                "srcset"
            )


            if not srcset:

                continue


            parts = []


            for item in (
                srcset.split(",")
            ):

                candidate = (
                    item.strip()
                    .split(" ")[0]
                )


                if candidate:

                    parts.append(
                        candidate
                    )


            if parts:

                candidates.insert(
                    0,
                    parts[-1]
                )


    # img srcset
    srcset = img.get(
        "srcset"
    )


    if srcset:

        parts = []


        for item in (
            srcset.split(",")
        ):

            candidate = (
                item.strip()
                .split(" ")[0]
            )


            if candidate:

                parts.append(
                    candidate
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
# 数值属性
# =========================================================

def get_numeric_attr(
    node,
    name
):

    value = node.get(
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


# =========================================================
# 图片评分
# =========================================================

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


    # figure 优先
    if img.find_parent(
        "figure"
    ):

        score += 150


    # article
    if img.find_parent(
        "article"
    ):

        score += 80


    # main
    if img.find_parent(
        "main"
    ):

        score += 40


    ancestor_text = ""


    for ancestor in list(
        img.parents
    )[:7]:

        if not hasattr(
            ancestor,
            "get"
        ):

            continue


        classes = ancestor.get(
            "class",
            []
        )


        if not isinstance(
            classes,
            list
        ):

            classes = [
                str(classes)
            ]


        element_id = ancestor.get(
            "id",
            ""
        )


        ancestor_text += (

            " "

            + " ".join(
                classes
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

        "news",

        "body",

        "post",

        "figure",

    ]


    if any(

        word in ancestor_text

        for word
        in good_context

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

        for word
        in bad_context

    ):

        score -= 180


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
        and
        width < 160
    ):

        score -= 100


    if height >= 300:

        score += 40


    elif (
        height
        and
        height < 100
    ):

        score -= 70


    if len(alt) >= 6:

        score += 15


    return score


# =========================================================
# 正文最佳图片
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
# OG图片
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
# 文章摘要
# =========================================================

def extract_article_summary(
    soup
):

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
# 文章详情抓取
# =========================================================

def fetch_page_details(
    url,
    source=""
):

    result = {

        "image_url":
            "",

        "summary":
            "",

        "image_method":
            "",

    }


    if not url:

        return result


    try:

        response = requests.get(

            url,

            headers=HEADERS,

            timeout=12

        )


        response.raise_for_status()


        html = decode_response(
            response
        )


        soup = BeautifulSoup(
            html,
            "html.parser"
        )


        # ---------------------------------
        # 正文图优先
        # ---------------------------------

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


        # ---------------------------------
        # 没正文图再使用OG
        #
        # 科学网禁用OG
        # 防止Logo
        # ---------------------------------

        allow_og = (
            source != "科学网"
        )


        if (

            not result[
                "image_url"
            ]

            and

            allow_og

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
# 普通资讯item
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

                or

                refine_title(
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
            meta
            or {},

    }


# =========================================================
# AI判断
# =========================================================

def useful_ai_text(
    text
):

    low = clean_text(
        text
    ).lower()


    return any(

        keyword.lower()
        in low

        for keyword
        in AI_KEYWORDS

    )


# =========================================================
# AI优先级
# =========================================================

def ai_priority(
    text
):

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

                source=
                    "AIBase",

                category=
                    "AI变现",

                url=url,

                priority=
                    ai_priority(
                        title
                    ),

                language=
                    "zh",

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

            and

            href

        ):

            continue


        url = urljoin(
            QBITAI_URL,
            href
        )


        if (

            "qbitai.com"

            not in

            urlparse(
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

                source=
                    "量子位",

                category=
                    category,

                url=url,

                priority=(

                    "A"

                    if breakthrough

                    else ai_priority(
                        title
                    )

                ),

                language=
                    "zh",

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

            not in

            urlparse(
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

                source=
                    "科技日报",

                category=
                    "前沿动态",

                url=url,

                priority=
                    "A",

                language=
                    "zh",

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

            not in

            urlparse(
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

                source=
                    "科学网",

                category=
                    "前沿动态",

                url=url,

                priority=
                    "A",

                language=
                    "zh",

                is_breakthrough_item=
                    True,

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

            not in

            urlparse(
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

                source=
                    "DeepTech深科技",

                category=
                    "前沿动态",

                url=url,

                priority=
                    "A",

                language=
                    "zh",

                is_breakthrough_item=
                    True,

            )

        )


    print(
        "DeepTech:",
        len(results)
    )


    return results[:30]


# =========================================================
# Nature文章列表解析
# =========================================================

def parse_nature_cards(

    html,

    source,

    page_url

):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    results = []


    # Nature新版常见结构
    cards = soup.select(
        "li.app-article-list-row__item"
    )


    if not cards:

        cards = soup.select(
            "article"
        )


    # 再fallback
    if not cards:

        cards = []


        for heading in soup.find_all(
            [
                "h2",
                "h3",
            ]
        ):

            link = heading.find(
                "a",
                href=True
            )


            if (

                link

                and

                "/articles/"
                in link.get(
                    "href",
                    ""
                )

            ):

                cards.append(
                    heading.parent
                )


    seen = set()


    for card in cards:

        link = card.select_one(

            'h3 a[href*="/articles/"], '
            'h2 a[href*="/articles/"]'

        )


        if not link:

            # fallback
            link = card.find(
                "a",
                href=re.compile(
                    r"/articles/"
                )
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


        if not title or not href:

            continue


        url = urljoin(
            "https://www.nature.com",
            href
        )


        if url in seen:

            continue


        seen.add(
            url
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


        for p in card.find_all(
            "p"
        ):

            candidate = clean_summary(
                p.get_text(
                    " ",
                    strip=True
                )
            )


            if len(candidate) >= 35:

                summary = candidate

                break


        results.append(

            {

                "id":
                    make_id(
                        source,
                        title,
                        url
                    ),

                "title":
                    title,

                "source":
                    source,

                "url":
                    url,

                "published_at":
                    parse_date(
                        published
                    ),

                "summary":
                    summary,

                "image_url":
                    "",

            }

        )


    return results


# =========================================================
# Nature页面抓取
# =========================================================

def fetch_nature_page(

    source,

    page_url,

    max_pages=2

):

    print(
        "Fetching Nature:",
        source
    )


    results = []

    seen = set()


    for page in range(
        1,
        max_pages + 1
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

                page_url,

                params=params,

                timeout=35

            )


            response.raise_for_status()


            html = decode_response(
                response
            )


        except Exception as e:

            print(
                source,
                "page failed:",
                page,
                e
            )

            continue


        page_items = (
            parse_nature_cards(

                html,

                source,

                page_url

            )
        )


        for item in page_items:

            if item[
                "url"
            ] in seen:

                continue


            seen.add(
                item[
                    "url"
                ]
            )


            results.append(
                item
            )


    print(
        source,
        ":",
        len(results)
    )


    return results


# =========================================================
# Scientific Data / Nature Cities
# 转为普通资讯卡
# =========================================================

def nature_items_to_news(

    papers,

    source

):

    output = []


    for paper in papers:

        output.append(

            make_item(

                title=
                    paper[
                        "title"
                    ],

                source=
                    source,

                category=
                    "期刊论文",

                url=
                    paper[
                        "url"
                    ],

                published_at=
                    paper[
                        "published_at"
                    ],

                summary=
                    paper[
                        "summary"
                    ],

                priority=
                    "A",

                language=
                    "en",

                is_breakthrough_item=
                    False,

            )

        )


    return output


# =========================================================
# GitHub相关性
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


# =========================================================
# GitHub优先级
# =========================================================

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
            ).days
            + 1

        )


        speed = (
            stars
            / days
        )


    except Exception:

        speed = 0


    if (

        stars >= 500

        or

        speed >= 50

    ):

        return "A"


    if (

        stars >= 100

        or

        speed >= 10

    ):

        return "B"


    return "C"


# =========================================================
# GitHub标题
# =========================================================

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


# =========================================================
# GitHub
# =========================================================

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

                or

                url in seen

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

                    source=
                        "GitHub",

                    category=
                        "提效工具",

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

                    language=
                        "en",

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
# 百度热点：
# 找主题
# =========================================================

def identify_hot_topic(
    title,
    summary=""
):

    text = (
        f"{title} "
        f"{summary}"
    )


    # 先排除明显娱乐体育
    if any(

        word in text

        for word
        in HOT_EXCLUDE_WORDS

    ):

        return None


    best_rule = None

    best_hits = 0


    for rule in HOT_TOPIC_RULES:

        hits = sum(

            1

            for keyword
            in rule["cn"]

            if keyword
            in text

        )


        if hits > best_hits:

            best_hits = hits

            best_rule = rule


    if best_hits == 0:

        return None


    return best_rule


# =========================================================
# 百度热搜
# =========================================================

def fetch_baidu_hotspots():

    print(
        "Fetching 百度热搜..."
    )


    results = []


    try:

        response = SESSION.get(

            BAIDU_HOT_URL,

            timeout=30

        )


        response.raise_for_status()


        html = decode_response(
            response
        )


    except Exception as e:

        print(
            "百度热搜 failed:",
            e
        )

        return results


    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    # =====================================================
    # 方案1：
    # 百度当前常见卡片结构
    # =====================================================

    cards = soup.select(
        "div.category-wrap_iQLoo"
    )


    rank_counter = 0


    for card in cards:

        title_node = (
            card.select_one(
                ".c-single-text-ellipsis"
            )
        )


        if not title_node:

            continue


        title = clean_text(
            title_node.get_text(
                " ",
                strip=True
            )
        )


        if not title:

            continue


        rank_counter += 1


        link = card.find(
            "a",
            href=True
        )


        url = (

            link.get(
                "href",
                ""
            )

            if link

            else BAIDU_HOT_URL

        )


        desc_node = (

            card.select_one(
                ".hot-desc_1m_jR"
            )

            or

            card.select_one(
                ".c-font-normal"
            )

        )


        summary = (

            clean_summary(
                desc_node.get_text(
                    " ",
                    strip=True
                )
            )

            if desc_node

            else ""

        )


        index_node = (

            card.select_one(
                ".hot-index_1Bl1a"
            )

            or

            card.select_one(
                "[class*='hot-index']"
            )

        )


        hot_index = 0


        if index_node:

            match = re.search(

                r"\d+",

                index_node.get_text(
                    "",
                    strip=True
                )

            )


            if match:

                try:

                    hot_index = int(
                        match.group(0)
                    )

                except Exception:

                    hot_index = 0


        rule = identify_hot_topic(
            title,
            summary
        )


        if not rule:

            continue


        image_url = ""


        image_node = card.find(
            "img"
        )


        if image_node:

            image_url = get_img_src(
                image_node,
                BAIDU_HOT_URL
            )


        results.append(

            {

                "title":
                    title,

                "summary":
                    summary,

                "url":
                    url,

                "rank":
                    rank_counter,

                "hot_index":
                    hot_index,

                "topic":
                    rule[
                        "label"
                    ],

                "angle":
                    rule[
                        "angle"
                    ],

                "topic_rule":
                    rule,

                "image_url":
                    image_url,

            }

        )


    # =====================================================
    # fallback：
    # 如果百度CSS类变化
    # 从搜索链接中找标题
    # =====================================================

    if not results:

        rank = 0


        seen = set()


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

                5 <= len(title) <= 45

            ):

                continue


            if (

                "baidu.com"

                not in href

            ):

                continue


            if title in seen:

                continue


            rule = identify_hot_topic(
                title
            )


            if not rule:

                continue


            seen.add(
                title
            )


            rank += 1


            results.append(

                {

                    "title":
                        title,

                    "summary":
                        "",

                    "url":
                        href,

                    "rank":
                        rank,

                    "hot_index":
                        0,

                    "topic":
                        rule[
                            "label"
                        ],

                    "angle":
                        rule[
                            "angle"
                        ],

                    "topic_rule":
                        rule,

                    "image_url":
                        "",

                }

            )


            if rank >= 50:

                break


    print(
        "百度科研相关热点:",
        len(results)
    )


    return results


# =========================================================
# Nature论文匹配分数
# =========================================================

def nature_match_score(

    hotspot,

    paper

):

    rule = hotspot.get(
        "topic_rule"
    )


    if not rule:

        return 0


    text = (

        f"{paper.get('title', '')} "

        f"{paper.get('summary', '')}"

    ).lower()


    score = 0


    # 英文关键词命中
    for keyword in rule[
        "en"
    ]:

        if keyword.lower() in text:

            score += 8


    # Nature主刊加分
    journal = paper.get(
        "source",
        ""
    )


    journal_bonus = {

        "Nature":
            10,

        "Nature Climate Change":
            9,

        "Nature Medicine":
            9,

        "Nature Human Behaviour":
            9,

        "Nature Cities":
            8,

        "Nature Communications":
            7,

        "Scientific Data":
            5,

        "Scientific Reports":
            3,

    }


    score += journal_bonus.get(
        journal,
        0
    )


    # 近期加分
    try:

        dt = dtparser.parse(
            paper.get(
                "published_at",
                ""
            )
        )


        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )


        age = (

            datetime.now(
                timezone.utc
            )

            - dt

        ).days


        if age <= 7:

            score += 10


        elif age <= 14:

            score += 7


        elif age <= 30:

            score += 4


        elif age <= 60:

            score += 2


    except Exception:

        pass


    return score


# =========================================================
# 匹配Nature论文
# =========================================================

def match_nature_papers(

    hotspot,

    nature_pool

):

    scored = []


    for paper in nature_pool:

        score = nature_match_score(
            hotspot,
            paper
        )


        # 至少有比较明确的主题匹配
        if score < 12:

            continue


        scored.append(
            (
                score,
                paper
            )
        )


    scored.sort(

        key=lambda x:
            x[0],

        reverse=True

    )


    output = []


    for score, paper in scored[
        :MAX_RELATED_PAPERS
    ]:

        copied = dict(
            paper
        )


        copied[
            "match_score"
        ] = score


        output.append(
            copied
        )


    return output


# =========================================================
# 热点传播潜力
# =========================================================

def calculate_hot_score(

    hotspot,

    related_papers

):

    rank = hotspot.get(
        "rank",
        50
    )


    hot_index = hotspot.get(
        "hot_index",
        0
    )


    # ---------------------------------
    # 热榜排名 0–40
    # ---------------------------------

    rank_score = max(

        5,

        42
        - (
            rank * 0.8
        )

    )


    # ---------------------------------
    # 百度指数 0–20
    # ---------------------------------

    index_score = 0


    if hot_index > 0:

        index_score = min(

            20,

            math.log10(
                hot_index + 1
            )
            * 3

        )


    # ---------------------------------
    # Nature证据 0–30
    # ---------------------------------

    paper_score = min(

        30,

        len(
            related_papers
        )
        * 8

        +

        (
            related_papers[
                0
            ].get(
                "match_score",
                0
            )
            * 0.25

            if related_papers

            else 0
        )

    )


    # ---------------------------------
    # 科研账号适配
    # ---------------------------------

    fit_score = 8


    final_score = (

        rank_score

        + index_score

        + paper_score

        + fit_score

    )


    final_score = min(
        98,
        final_score
    )


    return int(
        round(
            final_score
        )
    )


# =========================================================
# 公众号标题
# =========================================================

def build_wechat_title(

    hotspot

):

    title = hotspot.get(
        "title",
        ""
    )


    topic = hotspot.get(
        "topic",
        ""
    )


    if topic == "人工智能":

        return (
            f"{title}刷屏之后："
            f"Nature研究正在回答哪些关键问题？"
        )


    if topic == "气候环境":

        return (
            f"{title}背后："
            f"Nature研究揭示了怎样的风险链条？"
        )


    if topic == "健康医学":

        return (
            f"{title}为什么值得关注？"
            f"从Nature研究看真正的科学证据"
        )


    if topic == "城市社会":

        return (
            f"{title}背后，"
            f"Nature研究如何解释正在发生的社会变化？"
        )


    if topic == "前沿科技":

        return (
            f"{title}意味着什么？"
            f"Nature研究中的技术路线与现实边界"
        )


    if topic == "生态生命":

        return (
            f"{title}背后的科学问题："
            f"Nature研究给出了哪些线索？"
        )


    return (
        f"{title}背后，"
        f"Nature最近在研究什么？"
    )


# =========================================================
# 构建初始热点
# =========================================================

def build_hotspots(

    baidu_items,

    nature_pool

):

    hotspots = []


    for hot in baidu_items:

        related = (
            match_nature_papers(
                hot,
                nature_pool
            )
        )


        # =================================
        # 没有Nature研究支撑
        # 不进入
        # =================================

        if not related:

            continue


        score = calculate_hot_score(
            hot,
            related
        )


        hotspots.append(

            {

                "id":
                    hashlib.sha1(
                        hot[
                            "title"
                        ].encode(
                            "utf-8"
                        )
                    ).hexdigest()[:16],

                "title":
                    hot[
                        "title"
                    ],

                "summary":
                    hot.get(
                        "summary",
                        ""
                    ),

                "url":
                    hot.get(
                        "url",
                        ""
                    ),

                "rank":
                    hot.get(
                        "rank",
                        0
                    ),

                "hot_index":
                    hot.get(
                        "hot_index",
                        0
                    ),

                "topic":
                    hot.get(
                        "topic",
                        ""
                    ),

                "score":
                    score,

                "recommended_title":
                    build_wechat_title(
                        hot
                    ),

                "angle":
                    hot.get(
                        "angle",
                        ""
                    ),

                "image_url":
                    hot.get(
                        "image_url",
                        ""
                    ),

                "related_papers":
                    related,

                "updated_at":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),

            }

        )


    # 传播潜力高的优先
    hotspots.sort(

        key=lambda x:
            (
                x.get(
                    "score",
                    0
                ),

                -x.get(
                    "rank",
                    99
                )
            ),

        reverse=True

    )


    return hotspots[
        :MAX_HOTSPOTS
    ]


# =========================================================
# 为热点相关Nature论文抓图片
# =========================================================

def enrich_hotspot_papers(
    hotspots
):

    # 所有论文URL去重
    paper_map = {}


    for hotspot in hotspots:

        for paper in hotspot.get(
            "related_papers",
            []
        ):

            url = paper.get(
                "url"
            )


            if url:

                paper_map[
                    url
                ] = paper


    urls = list(
        paper_map.keys()
    )[
        :HOT_PAPER_DETAIL_LIMIT
    ]


    print(
        "Hot Nature paper details:",
        len(urls)
    )


    detail_results = {}


    with ThreadPoolExecutor(
        max_workers=DETAIL_WORKERS
    ) as executor:

        futures = {

            executor.submit(

                fetch_page_details,

                url,

                paper_map[
                    url
                ].get(
                    "source",
                    ""
                )

            ):
            url

            for url in urls

        }


        for future in as_completed(
            futures
        ):

            url = futures[
                future
            ]


            try:

                detail_results[
                    url
                ] = future.result()


            except Exception:

                detail_results[
                    url
                ] = {

                    "image_url":
                        "",

                    "summary":
                        "",

                    "image_method":
                        "",

                }


    # 写回
    for hotspot in hotspots:

        papers = hotspot.get(
            "related_papers",
            []
        )


        for paper in papers:

            details = detail_results.get(
                paper.get(
                    "url"
                )
            )


            if not details:

                continue


            if details.get(
                "image_url"
            ):

                paper[
                    "image_url"
                ] = details[
                    "image_url"
                ]


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

                not paper.get(
                    "summary"
                )

            ):

                paper[
                    "summary"
                ] = detail_summary


        # =================================
        # 热点主图优先：
        #
        # 1 百度热点图
        # 2 第一篇Nature论文图片
        # =================================

        if not hotspot.get(
            "image_url"
        ):

            for paper in papers:

                if paper.get(
                    "image_url"
                ):

                    hotspot[
                        "image_url"
                    ] = paper[
                        "image_url"
                    ]

                    break


    # 没图片不进入热点
    hotspots = [

        hot

        for hot in hotspots

        if hot.get(
            "image_url"
        )

    ]


    return hotspots


# =========================================================
# 读取旧新闻
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
# 旧新闻迁移
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


        # V8重新抓旧图
        if (

            item.get(
                "image_rule_version"
            )

            !=

            IMAGE_RULE_VERSION

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
# 合并新旧资讯
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


            detected = old.get(
                "detected_at"
            )


            published = old.get(
                "published_at"
            )


            image_url = old.get(
                "image_url"
            )


            old.update(
                item
            )


            if detected:

                old[
                    "detected_at"
                ] = detected


            if published:

                old[
                    "published_at"
                ] = published


            # 旧图有效就先继承
            if (

                image_url

                and

                item.get(
                    "image_rule_version"
                )
                == IMAGE_RULE_VERSION

            ):

                old[
                    "image_url"
                ] = image_url


            merged[
                item_id
            ] = old


        else:

            merged[
                item_id
            ] = item


    return list(
        merged.values()
    )


# =========================================================
# 普通资讯详情页补图
# =========================================================

def enrich_news_details(
    items
):

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


    unique = {}


    for item in candidates:

        url = item.get(
            "url"
        )


        if url and url not in unique:

            unique[
                url
            ] = item


    candidates = list(
        unique.values()
    )[
        :DETAIL_FETCH_LIMIT
    ]


    print(
        "News detail pages:",
        len(candidates)
    )


    results = {}


    with ThreadPoolExecutor(
        max_workers=DETAIL_WORKERS
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

            for item
            in candidates

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

                results[
                    url
                ] = future.result()


            except Exception:

                results[
                    url
                ] = {

                    "image_url":
                        "",

                    "summary":
                        "",

                    "image_method":
                        "",

                }


    for item in items:

        details = results.get(
            item.get(
                "url"
            )
        )


        if not details:

            continue


        if details.get(
            "image_url"
        ):

            item[
                "image_url"
            ] = details[
                "image_url"
            ]


            item[
                "image_method"
            ] = details.get(
                "image_method",
                ""
            )


        detail_summary = clean_summary(
            details.get(
                "summary",
                ""
            )
        )


        if detail_summary:

            if (

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

            ):

                item[
                    "summary"
                ] = detail_summary


    return items


# =========================================================
# 旧资讯删除
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
# 无图删除
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
# 图片去重
# =========================================================

def image_key(
    url
):

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

    seen = set()

    output = []


    for item in items:

        key = image_key(
            item.get(
                "image_url"
            )
        )


        if not key:

            continue


        if key in seen:

            continue


        seen.add(
            key
        )


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

        "Nature Cities":
            90,

        "Scientific Data":
            90,

        "GitHub":
            70,

    }


    return ranks.get(
        source,
        50
    )


# =========================================================
# 排序
# =========================================================

def sort_news(
    items
):

    def key(
        item
    ):

        try:

            timestamp = (
                dtparser.parse(
                    item.get(
                        "published_at",
                        ""
                    )
                )
                .timestamp()
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
        key=key,
        reverse=True
    )


    return items


# =========================================================
# 保存JSON
# =========================================================

def save_data(

    items,

    hotspots

):

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

        "hotspot_count":
            len(hotspots),

        "breakthrough_count":
            breakthrough_count,

        "category_counts":
            category_counts,

        "source_counts":
            source_counts,

        # =================================
        # 新增
        # =================================

        "hotspots":
            hotspots,

        # =================================
        # 原来的资讯
        # =================================

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
        "=" * 65
    )

    print(
        "ICAT Research Radar V8"
    )

    print(
        "=" * 65
    )


    # =====================================================
    # 1. 原来的普通资讯
    # =====================================================

    old_items = (
        normalize_old_items(
            load_old_data()
        )
    )


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


    github_items = (
        fetch_github()
    )


    # =====================================================
    # Scientific Data
    # =====================================================

    scientific_papers = (
        fetch_nature_page(

            "Scientific Data",

            SCIENTIFIC_DATA_URL,

            max_pages=2

        )
    )


    scientific_items = (
        nature_items_to_news(

            scientific_papers,

            "Scientific Data"

        )
    )


    # =====================================================
    # Nature Cities
    # =====================================================

    city_papers = (
        fetch_nature_page(

            "Nature Cities",

            NATURE_CITIES_URL,

            max_pages=2

        )
    )


    city_items = (
        nature_items_to_news(

            city_papers,

            "Nature Cities"

        )
    )


    new_items = (

        aibase_items

        + qbitai_items

        + stdaily_items

        + sciencenet_items

        + deeptech_items

        + scientific_items

        + city_items

        + github_items

    )


    all_items = merge_items(

        old_items,

        new_items

    )


    # =====================================================
    # 补正文图片
    # =====================================================

    all_items = (
        enrich_news_details(
            all_items
        )
    )


    # 摘要清理
    for item in all_items:

        item[
            "summary"
        ] = clean_summary(
            item.get(
                "summary",
                ""
            )
        )


    # 过期删除
    all_items = (
        remove_old_items(
            all_items
        )
    )


    # 无图片删除
    all_items = (
        only_items_with_images(
            all_items
        )
    )


    # 重复图片删除
    all_items = (
        remove_duplicate_images(
            all_items
        )
    )


    all_items = (
        sort_news(
            all_items
        )
    )


    all_items = all_items[
        :MAX_ITEMS
    ]


    # =====================================================
    # 2. Nature热点论文池
    # =====================================================

    nature_pool = []


    nature_seen = set()


    for source in NATURE_POOL_SOURCES:

        papers = fetch_nature_page(

            source[
                "name"
            ],

            source[
                "url"
            ],

            max_pages=1

        )


        for paper in papers:

            url = paper.get(
                "url"
            )


            if not url:

                continue


            if url in nature_seen:

                continue


            nature_seen.add(
                url
            )


            nature_pool.append(
                paper
            )


    print(
        "Nature hotspot paper pool:",
        len(nature_pool)
    )


    # =====================================================
    # 3. 百度热点
    # =====================================================

    baidu_hot = (
        fetch_baidu_hotspots()
    )


    # =====================================================
    # 4. 热点 × Nature
    # =====================================================

    hotspots = (
        build_hotspots(

            baidu_hot,

            nature_pool

        )
    )


    # =====================================================
    # 5. 给热点论文补正文图
    # =====================================================

    hotspots = (
        enrich_hotspot_papers(
            hotspots
        )
    )


    # 再按传播潜力排序
    hotspots.sort(

        key=lambda x:
            x.get(
                "score",
                0
            ),

        reverse=True

    )


    hotspots = hotspots[
        :MAX_HOTSPOTS
    ]


    # =====================================================
    # 6. 保存
    # =====================================================

    save_data(

        all_items,

        hotspots

    )


    print(
        "--------------------------------"
    )


    print(
        "普通资讯:",
        len(all_items)
    )


    print(
        "热点:",
        len(hotspots)
    )


    print(
        "Nature论文池:",
        len(nature_pool)
    )


    print(
        "=" * 65
    )


    print(
        "ICAT Research Radar V8 Done"
    )


    print(
        "=" * 65
    )


if __name__ == "__main__":

    main()
