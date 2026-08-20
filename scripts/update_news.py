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
# ICAT Research Radar V9
#
# V9 调整：
#
# 1. AI变现
#    AIBase重新解析
#    只保留商业化、付费、创业、营收等相关内容
#
# 2. 提效工具
#    删除GitHub
#    增加：
#    - 小众软件
#    - 少数派
#    - 量子位部分实用工具内容
#
# 3. 热点
#    增加：
#    - 百度热搜
#    - 百度民生
#    - 微博热搜
#
#    多平台重复热点自动合并
#
# 4. 热点图片
#    不再使用百度/微博缩略图
#    主图只使用匹配Nature论文的真实文章图片
#
# 5. 没有有效图片
#    不收录
#
# =========================================================


# =========================================================
# 基础配置
# =========================================================

DATA_FILE = Path(
    "data/news.json"
)

MAX_ITEMS = 500

KEEP_DAYS = 45

DETAIL_FETCH_LIMIT = 260

DETAIL_WORKERS = 10

IMAGE_RULE_VERSION = 9

MAX_HOTSPOTS = 12

MAX_RELATED_PAPERS = 3

HOT_PAPER_DETAIL_LIMIT = 80


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
            "GET",
            "HEAD",
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

APPINN_URL = (
    "https://www.appinn.com/"
)

SSPAI_URL = (
    "https://sspai.com/"
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


# =========================================================
# 热点来源
# =========================================================

BAIDU_REALTIME_URL = (
    "https://top.baidu.com/"
    "board?tab=realtime"
)

BAIDU_LIVELIHOOD_URL = (
    "https://top.baidu.com/"
    "board?tab=livelihood"
)

WEIBO_HOT_URL = (
    "https://s.weibo.com/"
    "top/summary?"
    "Refer=top_hot&topnav=1&wvr=6"
)


# =========================================================
# Nature
# =========================================================

SCIENTIFIC_DATA_URL = (
    "https://www.nature.com/"
    "sdata/articles"
)

NATURE_CITIES_URL = (
    "https://www.nature.com/"
    "natcities/research-articles"
)


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
# AI变现关键词
#
# 不再把AIBase所有内容全部塞进AI变现
# =========================================================

AI_MONEY_KEYWORDS = [

    "变现",
    "商业化",
    "赚钱",

    "收入",
    "营收",
    "利润",
    "盈利",

    "创业",
    "个体创业",

    "融资",
    "估值",
    "IPO",

    "付费",
    "订阅",
    "收费",
    "价格",
    "套餐",

    "广告",
    "营销",

    "电商",
    "带货",

    "获客",
    "用户增长",

    "商业模式",

    "应用上架",
    "上架",
    "分发",

    "平台",
    "产品",

    "企业服务",

    "降本",
    "增效",

    "市场份额",

    "销售",
    "订单",

]


# =========================================================
# 提效工具关键词
# =========================================================

TOOL_KEYWORDS = [

    "效率",
    "工具",
    "软件",
    "应用",

    "App",

    "PDF",
    "Markdown",
    "OCR",

    "文档",

    "笔记",

    "Obsidian",
    "Notion",
    "Zotero",
    "Readwise",

    "浏览器",

    "搜索",

    "阅读器",

    "翻译",

    "写作",

    "论文",
    "文献",
    "学术",
    "科研",

    "学习",

    "知识库",

    "整理",

    "自动化",

    "Agent",
    "智能体",

    "工作流",

    "数据分析",
    "可视化",

    "代码",
    "编程",

    "表格",

    "PPT",
    "Word",
    "Excel",

    "会议记录",

    "录音",
    "转写",

    "文件管理",

    "剪贴板",

    "截图",

    "云盘",

]


# =========================================================
# 工具栏目排除
# =========================================================

TOOL_EXCLUDE = [

    "游戏",

    "直播",
    "看球",

    "影视",

    "小说资源",

    "破解",
    "盗版",

    "彩票",
    "博彩",

]


# =========================================================
# 热点排除
#
# 避免娱乐体育和口号型话题进入科研热点
# =========================================================

HOT_EXCLUDE_WORDS = [

    "票房",

    "电影",

    "电视剧",

    "明星",

    "演员",

    "演唱会",

    "综艺",

    "恋情",

    "婚礼",

    "离婚",

    "国乒",

    "足球",

    "篮球",

    "NBA",

    "WTT",

    "夺冠",

    "进球",

    "比分",

    "总书记",

    "重要讲话",

    "庆祝大会",

    "最美的天使",

    "广大医务人员",

    "致敬",

    "纪念大会",

]


# =========================================================
# 热点主题
#
# 这里比V8严格很多
#
# 不再使用：
# “工作”
# “大学”
# “社会”
# “动物”
# “植物”
#
# 这类过宽关键词
# =========================================================

HOT_TOPIC_RULES = [


    # =====================================================
    # AI
    # =====================================================

    {

        "label":
            "人工智能",

        "cn": [

            "人工智能",

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

            "brain-computer interface",

        ],

        "angle":
            "从公众正在讨论的AI事件切入，"
            "用近期Nature研究解释能力边界、现实影响和未来趋势。",

    },


    # =====================================================
    # 气候环境
    # =====================================================

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

            "全球变暖",

            "气候变化",

            "空气污染",

            "PM2.5",

            "臭氧污染",

            "碳排放",

            "碳中和",

            "城市内涝",

        ],

        "en": [

            "climate change",

            "global warming",

            "extreme heat",

            "heatwave",

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

        ],

        "angle":
            "从极端天气或环境事件切入，"
            "用Nature研究解释风险形成机制、暴露变化与长期趋势。",

    },


    # =====================================================
    # 城市民生
    # =====================================================

    {

        "label":
            "城市社会",

        "cn": [

            "城市更新",

            "房价",

            "住房",

            "通勤",

            "交通拥堵",

            "人口老龄化",

            "老龄化",

            "生育率",

            "出生率",

            "就业率",

            "失业率",

            "灵活就业",

            "城市人口",

            "租房",

            "社区治理",

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

            "unemployment",

            "community",

        ],

        "angle":
            "从民生和城市议题切入，"
            "用Nature研究解释个体现象背后的结构性变化。",

    },


    # =====================================================
    # 健康医学
    # =====================================================

    {

        "label":
            "健康医学",

        "cn": [

            "睡眠",

            "失眠",

            "熬夜",

            "肥胖",

            "减肥",

            "癌症",

            "肿瘤",

            "糖尿病",

            "心血管",

            "心脏病",

            "抑郁",

            "焦虑",

            "病毒",

            "疫苗",

            "衰老",

            "长寿",

            "寿命",

            "饮食",

            "营养",

            "运动健康",

            "传染病",

        ],

        "en": [

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

            "virus",

            "vaccine",

            "ageing",

            "aging",

            "longevity",

            "diet",

            "nutrition",

            "exercise",

            "infectious disease",

        ],

        "angle":
            "从大众健康关注切入，"
            "用Nature论文区分科学证据、相关性与流行说法。",

    },


    # =====================================================
    # 前沿科技
    # =====================================================

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

            "核聚变",

            "核能",

            "芯片",

            "半导体",

            "量子计算",

            "量子通信",

            "超导",

            "新材料",

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
            "从产业或技术热点切入，"
            "结合Nature论文解释技术路线、性能提升和现实应用边界。",

    },


    # =====================================================
    # 生态
    # =====================================================

    {

        "label":
            "生态生命",

        "cn": [

            "生物多样性",

            "物种灭绝",

            "濒危物种",

            "森林火灾",

            "珊瑚白化",

            "海洋生态",

            "野生动物",

            "外来物种",

            "生态系统",

            "候鸟",

            "昆虫减少",

        ],

        "en": [

            "biodiversity",

            "species extinction",

            "endangered species",

            "forest fire",

            "coral bleaching",

            "marine",

            "ocean",

            "wildlife",

            "invasive species",

            "ecosystem",

            "ecology",

        ],

        "angle":
            "从公众关注的自然事件切入，"
            "结合Nature生态研究解释生态过程和环境意义。",

    },

]


# =========================================================
# 不合格图片关键词
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

    "aibase-logo",

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

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def contains_chinese(text):

    return bool(

        text

        and

        re.search(
            r"[\u4e00-\u9fff]",
            text
        )

    )


def looks_mojibake(text):

    if not text:

        return False

    bad = [

        "Ã",
        "Â",

        "â€",
        "â€™",
        "â€œ",

        "å",
        "æ",
        "ç",
        "é",

        "锟斤拷",

        "�",

    ]

    return (

        sum(
            text.count(x)
            for x in bad
        )

        >= 2

    )


def clean_summary(text):

    text = clean_text(
        text
    )

    if (

        not text

        or

        looks_mojibake(
            text
        )

        or

        len(text) < 12

    ):

        return ""

    if len(text) > 280:

        return (
            text[:277]
            .rstrip()
            + "..."
        )

    return text


# =========================================================
# 正确读取网页编码
# =========================================================

def decode_response(
    response
):

    raw = response.content

    content_type = (
        response.headers.get(
            "content-type",
            ""
        )
    )

    charset = None


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


    if not charset:

        match = re.search(

            br"charset\s*=\s*[\"']?"
            br"([a-zA-Z0-9_\-]+)",

            raw[:8192],

            flags=re.I

        )


        if match:

            charset = (

                match.group(1)

                .decode(
                    "ascii",
                    errors="ignore"
                )

                .lower()

            )


    if charset in {

        "gb2312",
        "gbk",
        "gb_2312",

    }:

        charset = "gb18030"


    for encoding in [

        charset,
        "utf-8",
        "gb18030",

    ]:

        if not encoding:

            continue

        try:

            return raw.decode(
                encoding,
                errors="replace"
            )

        except Exception:

            pass


    return raw.decode(
        "utf-8",
        errors="replace"
    )


# =========================================================
# 标题
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

def parse_date(
    value
):

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


def extract_date_from_text(
    text
):

    if not text:

        return None


    patterns = [

        r"(\d{4}[-/.]\d{1,2}"
        r"[-/.]\d{1,2}"
        r"(?:\s+\d{1,2}:\d{2}"
        r"(?::\d{2})?)?)",

        r"(\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|"
        r"Jul|Aug|Sep|Oct|Nov|Dec)"
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
# 关键词工具
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


def has_any(
    text,
    keywords
):

    low = clean_text(
        text
    ).lower()

    return any(

        keyword.lower()
        in low

        for keyword
        in keywords

    )


# =========================================================
# 创建普通资讯
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
            meta or {},

    }


# =========================================================
# 图片
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
# img地址
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


    srcsets = []


    if img.get(
        "srcset"
    ):

        srcsets.append(
            img.get(
                "srcset"
            )
        )


    picture = img.find_parent(
        "picture"
    )


    if picture:

        srcsets.extend(

            source.get(
                "srcset"
            )

            for source
            in picture.find_all(
                "source"
            )

            if source.get(
                "srcset"
            )

        )


    for srcset in srcsets:

        parts = [

            item.strip()
            .split(" ")[0]

            for item
            in srcset.split(",")

            if item.strip()

        ]


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


    return int(
        match.group(0)
    )


# =========================================================
# 正文图片评分
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


    if (

        image_is_bad(
            url,
            alt
        )

        or

        alt.lower()
        in {
            "aibase",
            "logo",
        }

    ):

        return -9999


    score = 0


    if img.find_parent(
        "figure"
    ):

        score += 160


    if img.find_parent(
        "article"
    ):

        score += 90


    if img.find_parent(
        "main"
    ):

        score += 45


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


        ancestor_text += (

            " "

            + " ".join(
                classes
            )

            + " "

            + str(
                ancestor.get(
                    "id",
                    ""
                )
            )

        )


    ancestor_text = (
        ancestor_text.lower()
    )


    if any(

        word in ancestor_text

        for word in [

            "article",
            "content",
            "detail",
            "news",
            "body",
            "post",
            "figure",

        ]

    ):

        score += 80


    if any(

        word in ancestor_text

        for word in [

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

    ):

        score -= 200


    width = get_numeric_attr(
        img,
        "width"
    )


    height = get_numeric_attr(
        img,
        "height"
    )


    if width >= 800:

        score += 100


    elif width >= 500:

        score += 70


    elif width >= 300:

        score += 35


    elif (

        width

        and

        width < 180

    ):

        score -= 100


    if height >= 400:

        score += 50


    elif (

        height

        and

        height < 120

    ):

        score -= 70


    if len(alt) >= 6:

        score += 15


    return score


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


        if url:

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


        if (

            url

            and

            not image_is_bad(
                url
            )

        ):

            return url


    return ""


# =========================================================
# 摘要
# =========================================================

def extract_article_summary(
    soup
):

    for selector in [

        'meta[property="og:description"]',

        'meta[name="description"]',

        'meta[name="twitter:description"]',

    ]:

        node = soup.select_one(
            selector
        )


        if node:

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

        ".news-content p",

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
# 页面标题
# =========================================================

def extract_article_title(
    soup
):

    for selector in [

        "article h1",

        "main h1",

        "h1",

    ]:

        node = soup.select_one(
            selector
        )


        if node:

            title = clean_text(
                node.get_text(
                    " ",
                    strip=True
                )
            )


            if 5 <= len(title) <= 160:

                return title


    return ""


# =========================================================
# 抓文章详情
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

        "page_title":
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


        soup = BeautifulSoup(

            decode_response(
                response
            ),

            "html.parser"

        )


        result[
            "page_title"
        ] = extract_article_title(
            soup
        )


        # =================================================
        # 正文图片优先
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
        # 正文没找到再用OG
        #
        # 科学网继续禁止OG
        # 防止Logo
        # =================================================

        elif source != "科学网":

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
        ] = extract_article_summary(
            soup
        )


    except Exception as error:

        print(
            "Detail failed:",
            source,
            url,
            error
        )


    return result


# =========================================================
# AIBase
#
# AI变现
# =========================================================

def fetch_aibase():

    print(
        "Fetching AIBase monetization..."
    )


    results = []

    seen = set()


    try:

        response = SESSION.get(
            AIBASE_URL,
            timeout=30
        )


        response.raise_for_status()


        soup = BeautifulSoup(

            decode_response(
                response
            ),

            "html.parser"

        )


    except Exception as error:

        print(
            "AIBase failed:",
            error
        )

        return results


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


        url = urljoin(
            AIBASE_URL,
            href
        )


        if url in seen:

            continue


        raw = clean_text(
            node.get_text(
                " ",
                strip=True
            )
        )


        title_node = node.select_one(

            "h1,"
            "h2,"
            "h3,"
            "h4,"
            "[class*='title'],"
            "[class*='Title']"

        )


        if title_node:

            title = clean_text(
                title_node.get_text(
                    " ",
                    strip=True
                )
            )


        else:

            title = raw


        # =================================================
        # AIBase有时整个卡片文本都在a标签里
        # 防止标题变成标题+摘要
        # =================================================

        if len(title) > 130:

            title = re.split(

                r"(?<=[。！？!])",

                title

            )[0].strip()


        if (

            not contains_chinese(
                title
            )

            or

            len(title) < 6

        ):

            continue


        if node.parent:

            card_text = clean_text(
                node.parent.get_text(
                    " ",
                    strip=True
                )
            )


        else:

            card_text = raw


        combined = (
            f"{title} "
            f"{card_text}"
        )


        # =================================================
        # 只有与商业应用有关才进入AI变现
        # =================================================

        if not has_any(

            combined,

            AI_MONEY_KEYWORDS

        ):

            continue


        seen.add(
            url
        )


        high_value = any(

            word in combined

            for word in [

                "变现",
                "商业化",
                "营收",
                "盈利",
                "付费",
                "创业",
                "融资",
                "IPO",

            ]

        )


        results.append(

            make_item(

                title=
                    title,

                source=
                    "AIBase",

                category=
                    "AI变现",

                url=
                    url,

                summary=
                    card_text,

                priority=
                    (
                        "A"
                        if high_value
                        else "B"
                    ),

                language=
                    "zh",

                is_breakthrough_item=
                    is_breakthrough(
                        combined
                    ),

            )

        )


    print(
        "AIBase monetization:",
        len(results)
    )


    return results[:35]


# =========================================================
# 提效工具判断
# =========================================================

def tool_relevant(
    text
):

    if has_any(
        text,
        TOOL_EXCLUDE
    ):

        return False


    return has_any(
        text,
        TOOL_KEYWORDS
    )


# =========================================================
# 小众软件
# =========================================================

def fetch_appinn():

    print(
        "Fetching 小众软件..."
    )


    results = []

    seen = set()


    try:

        response = SESSION.get(
            APPINN_URL,
            timeout=30
        )


        response.raise_for_status()


        soup = BeautifulSoup(

            decode_response(
                response
            ),

            "html.parser"

        )


    except Exception as error:

        print(
            "小众软件 failed:",
            error
        )

        return results


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


        if not link:

            continue


        title = clean_text(
            link.get_text(
                " ",
                strip=True
            )
        )


        url = urljoin(
            APPINN_URL,
            link.get(
                "href",
                ""
            )
        )


        parsed = urlparse(
            url
        )


        # =================================================
        # 去掉广告跳转域名
        # =================================================

        if parsed.netloc not in {

            "www.appinn.com",
            "appinn.com",

        }:

            continue


        if url in seen:

            continue


        if heading.parent:

            context = clean_text(
                heading.parent.get_text(
                    " ",
                    strip=True
                )
            )


        else:

            context = title


        if not tool_relevant(
            f"{title} {context}"
        ):

            continue


        seen.add(
            url
        )


        strong = has_any(

            title,

            [

                "AI",
                "科研",

                "PDF",

                "文档",

                "Obsidian",

                "Notion",

                "OCR",

                "学习",

                "效率",

            ]

        )


        results.append(

            make_item(

                title=
                    title,

                source=
                    "小众软件",

                category=
                    "提效工具",

                url=
                    url,

                published_at=
                    extract_date_from_text(
                        context
                    ),

                summary=
                    context,

                priority=
                    (
                        "A"
                        if strong
                        else "B"
                    ),

                language=
                    "zh",

            )

        )


    print(
        "小众软件:",
        len(results)
    )


    return results[:35]


# =========================================================
# 少数派
# =========================================================

def fetch_sspai():

    print(
        "Fetching 少数派..."
    )


    results = []

    seen = set()


    try:

        response = SESSION.get(
            SSPAI_URL,
            timeout=30
        )


        response.raise_for_status()


        soup = BeautifulSoup(

            decode_response(
                response
            ),

            "html.parser"

        )


    except Exception as error:

        print(
            "少数派 failed:",
            error
        )

        return results


    for link in soup.find_all(
        "a",
        href=True
    ):

        href = link.get(
            "href",
            ""
        )


        if "/post/" not in href:

            continue


        url = urljoin(
            SSPAI_URL,
            href
        )


        if url in seen:

            continue


        title = clean_text(
            link.get_text(
                " ",
                strip=True
            )
        )


        if (

            not contains_chinese(
                title
            )

            or

            not (
                8
                <=
                len(title)
                <=
                100
            )

        ):

            continue


        if link.parent:

            context = clean_text(
                link.parent.get_text(
                    " ",
                    strip=True
                )
            )


        else:

            context = title


        if not tool_relevant(
            f"{title} {context}"
        ):

            continue


        seen.add(
            url
        )


        strong = has_any(

            title,

            [

                "App+1",

                "Obsidian",

                "Notion",

                "AI",

                "效率",

                "笔记",

                "写作",

                "阅读",

            ]

        )


        results.append(

            make_item(

                title=
                    title,

                source=
                    "少数派",

                category=
                    "提效工具",

                url=
                    url,

                summary=
                    context,

                priority=
                    (
                        "A"
                        if strong
                        else "B"
                    ),

                language=
                    "zh",

            )

        )


    print(
        "少数派:",
        len(results)
    )


    return results[:30]


# =========================================================
# 量子位
#
# 突破 → 前沿动态
# 工具 → 提效工具
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


        soup = BeautifulSoup(

            decode_response(
                response
            ),

            "html.parser"

        )


    except Exception as error:

        print(
            "量子位 failed:",
            error
        )

        return results


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


        if (

            not href

            or

            not contains_chinese(
                title
            )

            or

            not (
                8
                <=
                len(title)
                <=
                120
            )

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


        if (

            node.parent

            and

            node.parent.parent

        ):

            context = clean_text(
                node.parent.parent.get_text(
                    " ",
                    strip=True
                )
            )


        else:

            context = title


        combined = (
            f"{title} "
            f"{context}"
        )


        breakthrough = (
            is_breakthrough(
                combined
            )
        )


        if (

            not breakthrough

            and

            not tool_relevant(
                combined
            )

        ):

            continue


        category = (

            "前沿动态"

            if breakthrough

            else "提效工具"

        )


        seen.add(
            url
        )


        results.append(

            make_item(

                title=
                    title,

                source=
                    "量子位",

                category=
                    category,

                url=
                    url,

                summary=
                    context,

                priority=
                    (
                        "A"
                        if breakthrough
                        else "B"
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
# 前沿动态
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


        soup = BeautifulSoup(

            decode_response(
                response
            ),

            "html.parser"

        )


    except Exception as error:

        print(
            "科技日报 failed:",
            error
        )

        return results


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


        url = urljoin(

            STD_BREAKTHROUGH_URL,

            node.get(
                "href",
                ""
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


        if not contains_chinese(
            title
        ):

            continue


        seen.add(
            url
        )


        results.append(

            make_item(

                title=
                    title,

                source=
                    "科技日报",

                category=
                    "前沿动态",

                url=
                    url,

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


        soup = BeautifulSoup(

            decode_response(
                response
            ),

            "html.parser"

        )


    except Exception as error:

        print(
            "科学网 failed:",
            error
        )

        return results


    for node in soup.find_all(
        "a",
        href=True
    ):

        url = urljoin(

            SCIENCENET_URL,

            node.get(
                "href",
                ""
            )

        )


        title = clean_text(
            node.get_text(
                " ",
                strip=True
            )
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


        if url in seen:

            continue


        if (

            not contains_chinese(
                title
            )

            or

            not (
                6
                <=
                len(title)
                <=
                120
            )

            or

            not is_breakthrough(
                title
            )

        ):

            continue


        seen.add(
            url
        )


        results.append(

            make_item(

                title=
                    title,

                source=
                    "科学网",

                category=
                    "前沿动态",

                url=
                    url,

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


        soup = BeautifulSoup(

            decode_response(
                response
            ),

            "html.parser"

        )


    except Exception as error:

        print(
            "DeepTech failed:",
            error
        )

        return results


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


        url = urljoin(

            DEEPTECH_URL,

            node.get(
                "href",
                ""
            )

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


        if (

            not contains_chinese(
                title
            )

            or

            not (
                8
                <=
                len(title)
                <=
                120
            )

            or

            not is_breakthrough(
                title
            )

        ):

            continue


        seen.add(
            url
        )


        results.append(

            make_item(

                title=
                    title,

                source=
                    "DeepTech深科技",

                category=
                    "前沿动态",

                url=
                    url,

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
# Nature列表解析
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


    cards = (
        soup.select(
            "li.app-article-list-row__item"
        )

        or

        soup.select(
            "article"
        )
    )


    results = []

    seen = set()


    for card in cards:

        link = (

            card.select_one(

                'h3 a[href*="/articles/"], '
                'h2 a[href*="/articles/"]'

            )

            or

            card.find(

                "a",

                href=re.compile(
                    r"/articles/"
                )

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


        url = urljoin(

            "https://www.nature.com",

            link.get(
                "href",
                ""
            )

        )


        if (

            not title

            or

            not url

            or

            url in seen

        ):

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


        summary = ""


        for paragraph in card.find_all(
            "p"
        ):

            candidate = clean_summary(
                paragraph.get_text(
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
                        extract_date_from_text(
                            card_text
                        )
                    ),

                "summary":
                    summary,

                "image_url":
                    "",

            }

        )


    return results


# =========================================================
# Nature抓取
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


            page_items = (
                parse_nature_cards(

                    decode_response(
                        response
                    ),

                    source,

                    page_url

                )
            )


        except Exception as error:

            print(
                source,
                "page failed:",
                page,
                error
            )

            continue


        for item in page_items:

            if item[
                "url"
            ] not in seen:

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

            )

        )


    return output


# =========================================================
# 热点主题判断
#
# V9只根据“标题”判断
#
# 不再根据百度摘要判断
#
# 这样可以避免：
# “剩饭喂猪”
# 被摘要里的“生态”误判
# =========================================================

def identify_hot_topic(
    title
):

    title = clean_text(
        title
    )


    if not title:

        return None


    if any(

        word in title

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
            in rule[
                "cn"
            ]

            if keyword.lower()
            in title.lower()

        )


        if hits > best_hits:

            best_rule = rule

            best_hits = hits


    if best_hits < 1:

        return None


    return best_rule


# =========================================================
# 百度热榜通用
# =========================================================

def fetch_baidu_board(

    url,

    platform

):

    print(
        "Fetching",
        platform,
        "..."
    )


    results = []


    try:

        response = SESSION.get(
            url,
            timeout=30
        )


        response.raise_for_status()


        soup = BeautifulSoup(

            decode_response(
                response
            ),

            "html.parser"

        )


    except Exception as error:

        print(
            platform,
            "failed:",
            error
        )

        return results


    cards = soup.select(
        "div.category-wrap_iQLoo"
    )


    for index, card in enumerate(
        cards,
        start=1
    ):

        title_node = card.select_one(
            ".c-single-text-ellipsis"
        )


        if not title_node:

            continue


        title = clean_text(
            title_node.get_text(
                " ",
                strip=True
            )
        )


        rule = identify_hot_topic(
            title
        )


        if not rule:

            continue


        link = card.find(
            "a",
            href=True
        )


        if link:

            target_url = link.get(
                "href",
                ""
            )


        else:

            target_url = url


        desc_node = (

            card.select_one(
                ".hot-desc_1m_jR"
            )

            or

            card.select_one(
                ".c-font-normal"
            )

        )


        if desc_node:

            summary = clean_summary(
                desc_node.get_text(
                    " ",
                    strip=True
                )
            )


        else:

            summary = ""


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

                index_node
                .get_text(
                    "",
                    strip=True
                )
                .replace(
                    ",",
                    ""
                )

            )


            if match:

                hot_index = int(
                    match.group(0)
                )


        results.append(

            {

                "title":
                    title,

                "summary":
                    summary,

                "url":
                    target_url,

                "rank":
                    index,

                "hot_index":
                    hot_index,

                "platform":
                    platform,

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

            }

        )


    print(
        platform,
        "relevant:",
        len(results)
    )


    return results


# =========================================================
# 微博热搜
#
# 微博可能偶尔触发反爬
#
# 抓不到时返回空数组
# 不会让整个Action失败
# =========================================================

def fetch_weibo_hotspots():

    print(
        "Fetching 微博热搜..."
    )


    results = []


    headers = dict(
        HEADERS
    )


    headers.update(

        {

            "Referer":
                "https://weibo.com/",

            "Accept":
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "image/avif,"
                "image/webp,"
                "*/*;q=0.8",

        }

    )


    try:

        response = requests.get(

            WEIBO_HOT_URL,

            headers=headers,

            timeout=30

        )


        response.raise_for_status()


        soup = BeautifulSoup(

            decode_response(
                response
            ),

            "html.parser"

        )


    except Exception as error:

        print(
            "微博热搜 failed:",
            error
        )

        return results


    rows = soup.select(
        "table tbody tr"
    )


    rank_fallback = 0


    for row in rows:

        title_node = row.select_one(
            "td.td-02 a"
        )


        if not title_node:

            continue


        title = clean_text(
            title_node.get_text(
                " ",
                strip=True
            )
        ).strip(
            "#"
        )


        rule = identify_hot_topic(
            title
        )


        if not rule:

            continue


        rank_node = row.select_one(
            "td.td-01"
        )


        if rank_node:

            rank_text = clean_text(
                rank_node.get_text(
                    " ",
                    strip=True
                )
            )


        else:

            rank_text = ""


        match = re.search(
            r"\d+",
            rank_text
        )


        rank_fallback += 1


        if match:

            rank = int(
                match.group(0)
            )


        else:

            rank = rank_fallback


        href = title_node.get(
            "href",
            ""
        )


        url = urljoin(
            "https://s.weibo.com",
            href
        )


        heat = 0


        row_text = clean_text(
            row.get_text(
                " ",
                strip=True
            )
        )


        numbers = re.findall(

            r"\b\d{4,}\b",

            row_text.replace(
                ",",
                ""
            )

        )


        if numbers:

            heat = int(
                numbers[-1]
            )


        results.append(

            {

                "title":
                    title,

                "summary":
                    "",

                "url":
                    url,

                "rank":
                    rank,

                "hot_index":
                    heat,

                "platform":
                    "微博热搜",

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

            }

        )


    print(
        "微博热搜 relevant:",
        len(results)
    )


    return results


# =========================================================
# 热点标题标准化
# =========================================================

def normalize_hot_title(
    title
):

    return re.sub(

        r"[#\s，。！？、：:；;"
        r"（）()\[\]【】\-—_]+",

        "",

        clean_text(
            title
        )

    ).lower()


# =========================================================
# 二元字符
#
# 用于判断两个平台是不是同一个热点
# =========================================================

def bigrams(
    text
):

    text = normalize_hot_title(
        text
    )


    if len(text) < 2:

        return {
            text
        }


    return {

        text[index:index + 2]

        for index
        in range(
            len(text) - 1
        )

    }


def title_similarity(
    title_a,
    title_b
):

    set_a = bigrams(
        title_a
    )

    set_b = bigrams(
        title_b
    )


    if (

        not set_a

        or

        not set_b

    ):

        return 0


    return (

        len(
            set_a
            &
            set_b
        )

        /

        len(
            set_a
            |
            set_b
        )

    )


# =========================================================
# 多平台热点合并
# =========================================================

def merge_hotspot_platforms(
    items
):

    groups = []


    items = sorted(

        items,

        key=lambda item:
            item.get(
                "rank",
                99
            )

    )


    for item in items:

        matched = None


        for group in groups:

            similarity = title_similarity(

                item[
                    "title"
                ],

                group[
                    "title"
                ]

            )


            if similarity >= 0.62:

                matched = group

                break


        if matched is None:

            copied = dict(
                item
            )


            copied[
                "platforms"
            ] = [

                item[
                    "platform"
                ]

            ]


            copied[
                "platform_ranks"
            ] = {

                item[
                    "platform"
                ]:
                    item.get(
                        "rank",
                        99
                    )

            }


            groups.append(
                copied
            )


        else:

            if (

                item[
                    "platform"
                ]

                not in

                matched[
                    "platforms"
                ]

            ):

                matched[
                    "platforms"
                ].append(

                    item[
                        "platform"
                    ]

                )


            matched[
                "platform_ranks"
            ][
                item[
                    "platform"
                ]
            ] = item.get(
                "rank",
                99
            )


            matched[
                "rank"
            ] = min(

                matched.get(
                    "rank",
                    99
                ),

                item.get(
                    "rank",
                    99
                )

            )


            matched[
                "hot_index"
            ] = max(

                matched.get(
                    "hot_index",
                    0
                ),

                item.get(
                    "hot_index",
                    0
                )

            )


            if (

                len(
                    item.get(
                        "summary",
                        ""
                    )
                )

                >

                len(
                    matched.get(
                        "summary",
                        ""
                    )
                )

            ):

                matched[
                    "summary"
                ] = item[
                    "summary"
                ]


            # 微博热点链接更适合点击
            if (

                matched.get(
                    "platform"
                )

                !=

                "微博热搜"

                and

                item.get(
                    "platform"
                )

                ==

                "微博热搜"

            ):

                matched[
                    "url"
                ] = item[
                    "url"
                ]


    return groups


# =========================================================
# Nature匹配分数
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


    keyword_hits = sum(

        1

        for keyword
        in rule[
            "en"
        ]

        if keyword.lower()
        in text

    )


    # 必须真正命中Nature论文关键词
    if keyword_hits == 0:

        return 0


    score = (
        keyword_hits
        * 9
    )


    journal_bonus = {

        "Nature":
            12,

        "Nature Climate Change":
            11,

        "Nature Medicine":
            11,

        "Nature Human Behaviour":
            10,

        "Nature Cities":
            10,

        "Nature Communications":
            8,

        "Scientific Data":
            6,

        "Scientific Reports":
            4,

    }


    score += journal_bonus.get(

        paper.get(
            "source",
            ""
        ),

        0

    )


    try:

        published = dtparser.parse(
            paper.get(
                "published_at",
                ""
            )
        )


        if published.tzinfo is None:

            published = published.replace(
                tzinfo=timezone.utc
            )


        age = (

            datetime.now(
                timezone.utc
            )

            - published

        ).days


        if age <= 7:

            score += 12


        elif age <= 14:

            score += 8


        elif age <= 30:

            score += 5


        elif age <= 60:

            score += 2


    except Exception:

        pass


    return score


# =========================================================
# Nature论文匹配
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


        if score < 20:

            continue


        scored.append(
            (
                score,
                paper
            )
        )


    scored.sort(

        key=lambda item:
            item[0],

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
# 传播潜力
#
# 新增：
# 多平台同时出现会明显加分
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


    rank_score = max(

        5,

        40
        -
        rank
        * 0.65

    )


    if hot_index > 0:

        index_score = min(

            15,

            math.log10(
                hot_index + 1
            )
            * 2.5

        )


    else:

        index_score = 0


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


    platform_count = len(
        hotspot.get(
            "platforms",
            []
        )
    )


    # 一个平台5分
    # 每多一个平台+7
    platform_score = min(

        15,

        5

        +

        max(
            0,
            platform_count - 1
        )
        * 7

    )


    final = (

        rank_score

        + index_score

        + paper_score

        + platform_score

        + 8

    )


    return int(

        round(

            min(
                98,
                final
            )

        )

    )


# =========================================================
# 推荐公众号标题
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


    mapping = {

        "人工智能":
            (
                f"{title}刷屏之后："
                f"Nature研究正在回答哪些关键问题？"
            ),

        "气候环境":
            (
                f"{title}背后："
                f"Nature研究揭示了怎样的风险链条？"
            ),

        "健康医学":
            (
                f"{title}为什么值得关注？"
                f"从Nature研究看真正的科学证据"
            ),

        "城市社会":
            (
                f"{title}背后，"
                f"Nature研究如何解释正在发生的城市与社会变化？"
            ),

        "前沿科技":
            (
                f"{title}意味着什么？"
                f"Nature研究中的技术路线与现实边界"
            ),

        "生态生命":
            (
                f"{title}背后的科学问题："
                f"Nature研究给出了哪些线索？"
            ),

    }


    return mapping.get(

        topic,

        (
            f"{title}背后，"
            f"Nature最近在研究什么？"
        )

    )


# =========================================================
# 构建热点
# =========================================================

def build_hotspots(

    platform_items,

    nature_pool

):

    merged = (
        merge_hotspot_platforms(
            platform_items
        )
    )


    hotspots = []


    for hot in merged:

        related = (
            match_nature_papers(
                hot,
                nature_pool
            )
        )


        if not related:

            continue


        hotspots.append(

            {

                "id":
                    hashlib.sha1(

                        normalize_hot_title(
                            hot[
                                "title"
                            ]
                        ).encode(
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

                "platform":
                    hot.get(
                        "platform",
                        ""
                    ),

                "platforms":
                    hot.get(
                        "platforms",
                        []
                    ),

                "platform_ranks":
                    hot.get(
                        "platform_ranks",
                        {}
                    ),

                "topic":
                    hot.get(
                        "topic",
                        ""
                    ),

                "score":
                    calculate_hot_score(
                        hot,
                        related
                    ),

                "recommended_title":
                    build_wechat_title(
                        hot
                    ),

                "angle":
                    hot.get(
                        "angle",
                        ""
                    ),

                # =================================
                # 不使用百度/微博缩略图
                # 稍后从Nature文章获取
                # =================================

                "image_url":
                    "",

                "related_papers":
                    related,

                "updated_at":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),

            }

        )


    hotspots.sort(

        key=lambda item:
            (

                item[
                    "score"
                ],

                len(
                    item.get(
                        "platforms",
                        []
                    )
                ),

                -
                item.get(
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
# 热点Nature论文图片
#
# 关键变化：
#
# 热点左侧大图只来源于Nature论文
#
# 百度缩略图
# 微博缩略图
#
# 都不再作为主图
# =========================================================

def enrich_hotspot_papers(
    hotspots
):

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
        paper_map
    )[
        :HOT_PAPER_DETAIL_LIMIT
    ]


    print(
        "Hot Nature paper details:",
        len(urls)
    )


    details = {}


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

            for url
            in urls

        }


        for future in as_completed(
            futures
        ):

            url = futures[
                future
            ]


            try:

                details[
                    url
                ] = future.result()


            except Exception:

                details[
                    url
                ] = {

                    "image_url":
                        "",

                    "summary":
                        "",

                    "image_method":
                        "",

                    "page_title":
                        "",

                }


    for hotspot in hotspots:

        valid_papers = []


        for paper in hotspot.get(
            "related_papers",
            []
        ):

            detail = details.get(
                paper.get(
                    "url"
                ),
                {}
            )


            image_url = detail.get(
                "image_url",
                ""
            )


            if image_url:

                paper[
                    "image_url"
                ] = image_url


            if (

                detail.get(
                    "summary"
                )

                and

                not paper.get(
                    "summary"
                )

            ):

                paper[
                    "summary"
                ] = clean_summary(
                    detail[
                        "summary"
                    ]
                )


            valid_papers.append(
                paper
            )


        hotspot[
            "related_papers"
        ] = valid_papers


        # =================================================
        # 第一篇真正有图的Nature论文
        # 作为热点主图
        # =================================================

        for paper in valid_papers:

            image_url = paper.get(
                "image_url"
            )


            if (

                image_url

                and

                not image_is_bad(
                    image_url
                )

            ):

                hotspot[
                    "image_url"
                ] = image_url

                break


    # =====================================================
    # 没有Nature主图
    # 不报道
    # =====================================================

    return [

        hotspot

        for hotspot
        in hotspots

        if hotspot.get(
            "image_url"
        )

    ]


# =========================================================
# 旧数据
# =========================================================

def load_old_data():

    if not DATA_FILE.exists():

        return []


    try:

        with DATA_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(
                file
            )


        return data.get(
            "items",
            []
        )


    except Exception:

        return []


# =========================================================
# 旧数据标准化
#
# GitHub在这里正式被删除
# =========================================================

def normalize_old_items(
    items
):

    output = []


    allowed_sources = {

        "AIBase",

        "量子位",

        "科技日报",

        "科学网",

        "DeepTech深科技",

        "Scientific Data",

        "Nature Cities",

        "小众软件",

        "少数派",

    }


    for item in items:

        source = item.get(
            "source",
            ""
        )


        # GitHub等旧来源全部删除
        if source not in allowed_sources:

            continue


        if source == "AIBase":

            item[
                "category"
            ] = "AI变现"


        elif source in {

            "小众软件",
            "少数派",

        }:

            item[
                "category"
            ] = "提效工具"


        elif source == "量子位":

            item[
                "category"
            ] = (

                "前沿动态"

                if item.get(
                    "is_breakthrough"
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


        item[
            "summary"
        ] = clean_summary(
            item.get(
                "summary",
                ""
            )
        )


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


        # V9重新抓一次所有图片
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


        output.append(
            item
        )


    return output


# =========================================================
# 合并
# =========================================================

def merge_items(

    old_items,

    new_items

):

    merged = {

        item.get(
            "id"
        ):
            item

        for item
        in old_items

        if item.get(
            "id"
        )

    }


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


    return list(
        merged.values()
    )


# =========================================================
# 普通新闻详情页补图
# =========================================================

def enrich_news_details(
    items
):

    candidates = []


    for item in items:

        if (

            not item.get(
                "image_url"
            )

            or

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

            candidates.append(
                item
            )


    unique = {}


    for item in candidates:

        url = item.get(
            "url"
        )


        if url:

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

                item[
                    "url"
                ],

                item.get(
                    "source",
                    ""
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


            try:

                results[
                    item[
                        "url"
                    ]
                ] = future.result()


            except Exception:

                results[
                    item[
                        "url"
                    ]
                ] = {

                    "image_url":
                        "",

                    "summary":
                        "",

                    "image_method":
                        "",

                    "page_title":
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


        # =================================================
        # 修复AIBase等卡片标题解析异常
        # =================================================

        if (

            details.get(
                "page_title"
            )

            and

            (

                not item.get(
                    "title"
                )

                or

                len(
                    item.get(
                        "title",
                        ""
                    )
                )
                > 130

            )

        ):

            item[
                "title"
            ] = details[
                "page_title"
            ]


            item[
                "display_title"
            ] = refine_title(
                details[
                    "page_title"
                ]
            )


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


        if (

            details.get(
                "summary"
            )

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
            ] = clean_summary(
                details[
                    "summary"
                ]
            )


    return items


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

            published = dtparser.parse(
                item.get(
                    "published_at",
                    ""
                )
            )


            if published.tzinfo is None:

                published = published.replace(
                    tzinfo=timezone.utc
                )


            if published >= cutoff:

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

    return [

        item

        for item
        in items

        if (

            item.get(
                "image_url"
            )

            and

            not image_is_bad(
                item[
                    "image_url"
                ]
            )

        )

    ]


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
                "image_url",
                ""
            )
        )


        if (

            not key

            or

            key in seen

        ):

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

        "少数派":
            92,

        "小众软件":
            91,

        "量子位":
            90,

        "Scientific Data":
            90,

        "Nature Cities":
            90,

    }


    return ranks.get(
        source,
        50
    )


# =========================================================
# 普通资讯排序
# =========================================================

def sort_news(
    items
):

    def sort_key(
        item
    ):

        try:

            timestamp = dtparser.parse(
                item.get(
                    "published_at",
                    ""
                )
            ).timestamp()


        except Exception:

            timestamp = 0


        return (

            timestamp,

            (
                1

                if item.get(
                    "is_breakthrough"
                )

                else 0
            ),

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


    return items


# =========================================================
# 保存
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

        "hotspots":
            hotspots,

        "items":
            items,

    }


    with DATA_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(

            output,

            file,

            ensure_ascii=False,

            indent=2

        )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=" * 64
    )

    print(
        "ICAT Research Radar V9"
    )

    print(
        "=" * 64
    )


    # =====================================================
    # 原数据
    # =====================================================

    old_items = normalize_old_items(
        load_old_data()
    )


    # =====================================================
    # AI变现
    # =====================================================

    aibase_items = (
        fetch_aibase()
    )


    # =====================================================
    # 提效工具
    #
    # GitHub已删除
    # =====================================================

    appinn_items = (
        fetch_appinn()
    )


    sspai_items = (
        fetch_sspai()
    )


    qbitai_items = (
        fetch_qbitai()
    )


    # =====================================================
    # 前沿动态
    # =====================================================

    stdaily_items = (
        fetch_stdaily()
    )


    sciencenet_items = (
        fetch_sciencenet()
    )


    deeptech_items = (
        fetch_deeptech()
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


    # =====================================================
    # 合并普通资讯
    # =====================================================

    new_items = (

        aibase_items

        + appinn_items

        + sspai_items

        + qbitai_items

        + stdaily_items

        + sciencenet_items

        + deeptech_items

        + scientific_items

        + city_items

    )


    all_items = merge_items(

        old_items,

        new_items

    )


    # =====================================================
    # 进入详情页抓真正图片
    # =====================================================

    all_items = (
        enrich_news_details(
            all_items
        )
    )


    for item in all_items:

        item[
            "summary"
        ] = clean_summary(
            item.get(
                "summary",
                ""
            )
        )


    all_items = (
        remove_old_items(
            all_items
        )
    )


    all_items = (
        only_items_with_images(
            all_items
        )
    )


    all_items = (
        remove_duplicate_images(
            all_items
        )
    )


    all_items = (
        sort_news(
            all_items
        )
    )[
        :MAX_ITEMS
    ]


    # =====================================================
    # Nature热点论文池
    # =====================================================

    nature_pool = []

    nature_seen = set()


    for source in NATURE_POOL_SOURCES:

        papers = (
            fetch_nature_page(

                source[
                    "name"
                ],

                source[
                    "url"
                ],

                max_pages=1

            )
        )


        for paper in papers:

            url = paper.get(
                "url"
            )


            if (

                url

                and

                url not in nature_seen

            ):

                nature_seen.add(
                    url
                )


                nature_pool.append(
                    paper
                )


    # =====================================================
    # 多平台热点
    # =====================================================

    hotspot_sources = []


    hotspot_sources += (
        fetch_baidu_board(

            BAIDU_REALTIME_URL,

            "百度热搜"

        )
    )


    hotspot_sources += (
        fetch_baidu_board(

            BAIDU_LIVELIHOOD_URL,

            "百度民生"

        )
    )


    hotspot_sources += (
        fetch_weibo_hotspots()
    )


    # =====================================================
    # 热点 × Nature
    # =====================================================

    hotspots = (
        build_hotspots(

            hotspot_sources,

            nature_pool

        )
    )


    # =====================================================
    # Nature正文图片作为热点主图
    # =====================================================

    hotspots = (
        enrich_hotspot_papers(
            hotspots
        )
    )


    hotspots.sort(

        key=lambda item:
            (

                item.get(
                    "score",
                    0
                ),

                len(
                    item.get(
                        "platforms",
                        []
                    )
                )

            ),

        reverse=True

    )


    hotspots = hotspots[
        :MAX_HOTSPOTS
    ]


    # =====================================================
    # 保存
    # =====================================================

    save_data(

        all_items,

        hotspots

    )


    print(
        "--------------------------------"
    )


    print(

        "AI变现:",

        sum(

            1

            for item
            in all_items

            if item.get(
                "category"
            )
            == "AI变现"

        )

    )


    print(

        "提效工具:",

        sum(

            1

            for item
            in all_items

            if item.get(
                "category"
            )
            == "提效工具"

        )

    )


    print(

        "前沿动态:",

        sum(

            1

            for item
            in all_items

            if item.get(
                "category"
            )
            == "前沿动态"

        )

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
        "普通资讯总数:",
        len(all_items)
    )


    print(
        "=" * 64
    )


if __name__ == "__main__":

    main()
