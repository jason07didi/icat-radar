import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparser


# =========================================================
# 基础设置
# =========================================================

DATA_FILE = Path("data/news.json")

AI_BOT_URL = "https://ai-bot.cn/daily-ai-news/"

NATURE_FEEDS = [
    {
        "name": "Scientific Data",
        "url": "https://www.nature.com/sdata.rss",
        "category": "新数据"
    },
    {
        "name": "Nature Cities",
        "url": "https://www.nature.com/natcities.rss",
        "category": "新研究"
    }
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124 Safari/537.36"
    )
}


# =========================================================
# Scientific Data 城市相关关键词
# =========================================================

URBAN_KEYWORDS = [
    "urban",
    "city",
    "cities",
    "building",
    "buildings",
    "road",
    "roads",
    "street",
    "street view",
    "mobility",
    "human mobility",
    "transport",
    "transportation",
    "traffic",
    "population",
    "land use",
    "land cover",
    "remote sensing",
    "satellite",
    "geospatial",
    "spatial",
    "gis",
    "geoai",
    "air pollution",
    "pm2.5",
    "ozone",
    "climate",
    "temperature",
    "heat",
    "urban heat",
    "green space",
    "greenspace",
    "human settlement",
    "nighttime light",
    "night-time light",
    "dem",
    "lidar",
    "poi",
    "built environment",
    "urban morphology",
    "urbanization"
]


# =========================================================
# GitHub 搜索关键词
# =========================================================

GITHUB_TOPICS = [
    "geoai",
    '"geospatial" AI',
    '"urban data"',
    '"remote sensing" AI',
    '"GIS" agent',
    '"research agent"',
    '"paper agent"',
    '"literature review" AI',
    '"scientific writing" AI',
    '"academic research" AI',
    '"data visualization" AI',
    '"zotero" AI'
]


# =========================================================
# 工具函数
# =========================================================

def clean_text(text):
    if not text:
        return ""

    text = BeautifulSoup(
        str(text),
        "html.parser"
    ).get_text(" ", strip=True)

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def make_id(source, title, url):

    raw = f"{source}|{title}|{url}"

    return hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:16]


def parse_date(value):

    if not value:
        return datetime.now(
            timezone.utc
        ).isoformat()

    try:

        dt = dtparser.parse(value)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.isoformat()

    except Exception:

        return datetime.now(
            timezone.utc
        ).isoformat()


def make_item(
    title,
    source,
    category,
    url,
    published_at=None,
    summary="",
    priority="B",
    meta=None
):

    return {
        "id": make_id(
            source,
            title,
            url
        ),

        "title": title,

        "source": source,

        "category": category,

        "url": url,

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

        "meta":
            meta or {}
    }


# =========================================================
# Nature
# =========================================================

def fetch_nature():

    results = []

    for config in NATURE_FEEDS:

        print(
            f"Fetching {config['name']}..."
        )

        try:

            feed = feedparser.parse(
                config["url"]
            )

        except Exception as e:

            print(
                f"{config['name']} failed:",
                e
            )

            continue

        print(
            f"{config['name']} RSS entries:",
            len(feed.entries)
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
                entry.get("published")
                or entry.get("updated")
            )

            if not title or not url:
                continue

            # Scientific Data范围非常大，只保留城市相关
            if config["name"] == "Scientific Data":

                searchable = (
                    title
                    + " "
                    + summary
                ).lower()

                relevant = any(
                    keyword.lower()
                    in searchable
                    for keyword
                    in URBAN_KEYWORDS
                )

                if not relevant:
                    continue

            item = make_item(
                title=title,
                source=config["name"],
                category=config["category"],
                url=url,
                published_at=published,
                summary=summary,
                priority="A"
            )

            results.append(item)

    return results


# =========================================================
# AI工具集
# =========================================================

def fetch_ai_bot():

    print("Fetching AI工具集...")

    results = []

    try:

        response = requests.get(
            AI_BOT_URL,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

    except Exception as e:

        print(
            "AI工具集访问失败:",
            e
        )

        return results

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    main = (
        soup.find("main")
        or soup.find("article")
        or soup
    )

    candidates = []

    # 第一版尽量兼容不同网页结构
    selectors = [
        "h2",
        "h3",
        "h4",
        "li"
    ]

    for selector in selectors:

        for node in main.select(selector):

            title = clean_text(
                node.get_text(
                    " ",
                    strip=True
                )
            )

            # 排除太短或太长的网页元素
            if len(title) < 12:
                continue

            if len(title) > 120:
                continue

            # 排除导航菜单
            exclude_words = [
                "AI工具集",
                "AI导航",
                "AI教程",
                "联系我们",
                "友情链接",
                "热门工具",
                "最新工具",
                "网站导航",
                "登录",
                "注册"
            ]

            if any(
                x == title
                for x in exclude_words
            ):
                continue

            link_node = (
                node
                if node.name == "a"
                else node.find("a")
            )

            if (
                link_node
                and link_node.get("href")
            ):

                url = urljoin(
                    AI_BOT_URL,
                    link_node.get("href")
                )

            else:

                url = AI_BOT_URL

            candidates.append(
                (title, url)
            )

    seen = set()

    important_words = [
        "发布",
        "推出",
        "上线",
        "开源",
        "免费",
        "更新",
        "新功能",
        "模型",
        "Agent",
        "智能体",
        "数据",
        "科研",
        "GitHub"
    ]

    for title, url in candidates:

        if title in seen:
            continue

        seen.add(title)

        priority = (
            "A"
            if any(
                word.lower()
                in title.lower()
                for word
                in important_words
            )
            else "B"
        )

        results.append(
            make_item(
                title=title,
                source="AI工具集",
                category="AI工具",
                url=url,
                summary="",
                priority=priority
            )
        )

    print(
        "AI工具集候选:",
        len(results)
    )

    # 防止第一次抓取过多
    return results[:30]


# =========================================================
# GitHub
# =========================================================

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


def fetch_github():

    print("Fetching GitHub...")

    results = []

    token = os.environ.get(
        "GITHUB_TOKEN"
    )

    headers = {
        "Accept":
            "application/vnd.github+json",

        "User-Agent":
            "icat-research-radar"
    }

    if token:

        headers[
            "Authorization"
        ] = f"Bearer {token}"

    since = (
        datetime.now(
            timezone.utc
        )
        - timedelta(days=14)
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

        print(
            "GitHub query:",
            topic
        )

        try:

            response = requests.get(
                "https://api.github.com/search/repositories",
                headers=headers,
                params={
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 8
                },
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

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

            stars = repo.get(
                "stargazers_count",
                0
            )

            # 太小的新项目暂时不展示
            if stars < 20:
                continue

            created_at = repo.get(
                "created_at"
            )

            priority = github_priority(
                stars,
                created_at
            )

            item = make_item(
                title=repo[
                    "full_name"
                ],

                source="GitHub",

                category="GitHub",

                url=repo[
                    "html_url"
                ],

                published_at=
                    created_at,

                summary=
                    repo.get(
                        "description"
                    ) or "",

                priority=
                    priority,

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
                        )
                }
            )

            results.append(
                item
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

            data = json.load(f)

        return data.get(
            "items",
            []
        )

    except Exception:

        return []


# =========================================================
# 合并和去重
# =========================================================

def merge_items(
    old_items,
    new_items
):

    merged = {}

    for item in old_items:

        if "id" in item:
            merged[
                item["id"]
            ] = item

    for item in new_items:

        item_id = item["id"]

        if item_id in merged:

            first_seen = merged[
                item_id
            ].get(
                "detected_at"
            )

            merged[
                item_id
            ].update(
                item
            )

            if first_seen:

                merged[
                    item_id
                ][
                    "detected_at"
                ] = first_seen

        else:

            merged[
                item_id
            ] = item

    items = list(
        merged.values()
    )

    items.sort(
        key=lambda x:
            x.get(
                "published_at",
                ""
            ),
        reverse=True
    )

    # 最多存1000条
    return items[:1000]


# =========================================================
# 保存
# =========================================================

def save_data(items):

    DATA_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output = {
        "updated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "count":
            len(items),

        "items":
            items
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
# 主程序
# =========================================================

def main():

    print(
        "===== Research Radar Start ====="
    )

    old_items = load_old_data()

    print(
        "Existing items:",
        len(old_items)
    )

    new_items = []

    nature_items = fetch_nature()

    ai_items = fetch_ai_bot()

    github_items = fetch_github()

    print(
        "Nature:",
        len(nature_items)
    )

    print(
        "AI工具集:",
        len(ai_items)
    )

    print(
        "GitHub:",
        len(github_items)
    )

    new_items.extend(
        nature_items
    )

    new_items.extend(
        ai_items
    )

    new_items.extend(
        github_items
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
        "===== Research Radar Done ====="
    )


if __name__ == "__main__":
    main()
