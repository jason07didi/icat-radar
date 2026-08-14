/* =========================================================
   ICAT Research Radar V8
   Frontend

   功能：
   1. 普通资讯
   2. 最新突破
   3. 热点
   4. AI变现
   5. 提效工具
   6. 前沿动态
   7. Scientific Data
   8. Nature Cities
========================================================= */


/* =========================================================
   全局数据
========================================================= */

let allItems = [];

let allHotspots = [];

let currentFilter = {
    type: "all",
    value: "all"
};


/* =========================================================
   HTML 转义
========================================================= */

function escapeHTML(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)

        .replaceAll(
            "&",
            "&amp;"
        )

        .replaceAll(
            "<",
            "&lt;"
        )

        .replaceAll(
            ">",
            "&gt;"
        )

        .replaceAll(
            '"',
            "&quot;"
        )

        .replaceAll(
            "'",
            "&#039;"
        );
}


/* =========================================================
   乱码判断
========================================================= */

function looksBrokenText(value) {

    if (!value) {
        return false;
    }

    const text =
        String(value);

    const badTokens = [

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

        "�"
    ];

    let score = 0;

    badTokens.forEach(
        token => {

            score +=
                text.split(
                    token
                ).length - 1;

        }
    );

    return score >= 2;
}


/* =========================================================
   日期格式
========================================================= */

function formatDate(value) {

    if (!value) {
        return "";
    }

    const date =
        new Date(value);


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return "";
    }


    return date.toLocaleDateString(

        "zh-CN",

        {

            timeZone:
                "Asia/Shanghai",

            year:
                "numeric",

            month:
                "2-digit",

            day:
                "2-digit"

        }

    );
}


/* =========================================================
   最近更新时间
========================================================= */

function formatUpdateTime(value) {

    if (!value) {

        return "等待首次自动更新";
    }


    const date =
        new Date(value);


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return "最近更新时间未知";
    }


    const text =
        date.toLocaleString(

            "zh-CN",

            {

                timeZone:
                    "Asia/Shanghai",

                year:
                    "numeric",

                month:
                    "2-digit",

                day:
                    "2-digit",

                hour:
                    "2-digit",

                minute:
                    "2-digit",

                hour12:
                    false

            }

        );


    return (
        `最近更新：${text}`
        + `（北京时间）`
    );
}


/* =========================================================
   URL 安全处理
========================================================= */

function safeURL(value) {

    if (!value) {

        return "#";
    }


    try {

        const url =
            new URL(value);


        if (
            url.protocol === "http:"
            ||
            url.protocol === "https:"
        ) {

            return value;
        }

    }

    catch (error) {

        console.warn(
            "Invalid URL:",
            value
        );
    }


    return "#";
}


/* =========================================================
   Priority
========================================================= */

function getPriority(value) {

    if (
        value === "A"
        ||
        value === "B"
        ||
        value === "C"
    ) {

        return value;
    }


    return "B";
}


/* =========================================================
   传播潜力等级
========================================================= */

function getScoreClass(score) {

    const value =
        Number(score) || 0;


    if (value >= 90) {

        return "score-excellent";
    }


    if (value >= 80) {

        return "score-high";
    }


    if (value >= 70) {

        return "score-medium";
    }


    return "score-normal";
}


/* =========================================================
   普通资讯标签
========================================================= */

function getNewsBadge(item) {

    if (
        item.source
        === "Scientific Data"
    ) {

        return "Scientific Data";
    }


    if (
        item.source
        === "Nature Cities"
    ) {

        return "Nature Cities";
    }


    return (
        item.category
        || "资讯"
    );
}


/* =========================================================
   普通资讯卡片
========================================================= */

function createNewsCard(
    item,
    featured = false
) {

    /* 没有图片不显示 */

    if (!item.image_url) {

        return null;
    }


    const priority =
        getPriority(
            item.priority
        );


    const card =
        document.createElement(
            "article"
        );


    card.className =

        featured

        ? `news-card featured-card card-${priority}`

        : `news-card card-${priority}`;


    const title =

        item.display_title

        ||

        item.title

        ||

        "未命名资讯";


    const badge =
        getNewsBadge(
            item
        );


    /* =====================================================
       摘要
    ===================================================== */

    let summaryHTML = "";


    if (
        item.summary

        &&

        !looksBrokenText(
            item.summary
        )
    ) {

        summaryHTML = `

            <p class="summary">

                ${escapeHTML(
                    item.summary
                )}

            </p>

        `;
    }


    /* =====================================================
       GitHub Stars
    ===================================================== */

    const starsHTML =

        (
            item.meta
            &&
            item.meta.stars
        )

        ? `

            <span class="meta-item">

                ⭐ ${escapeHTML(
                    item.meta.stars
                )}

            </span>

          `

        : "";


    /* =====================================================
       GitHub语言
    ===================================================== */

    const languageHTML =

        (
            item.meta
            &&
            item.meta.language
        )

        ? `

            <span class="meta-item">

                ${escapeHTML(
                    item.meta.language
                )}

            </span>

          `

        : "";


    /* =====================================================
       图片突破标签
    ===================================================== */

    const imageBreakthroughHTML =

        item.is_breakthrough

        ? `

            <span class="image-breakthrough">

                🔥 突破

            </span>

          `

        : "";


    /* =====================================================
       正文突破标签
    ===================================================== */

    const breakthroughHTML =

        item.is_breakthrough

        ? `

            <span class="breakthrough">

                🔥 突破

            </span>

          `

        : "";


    /* =====================================================
       卡片
    ===================================================== */

    card.innerHTML = `


        <a

            class="image-link"

            href="${escapeHTML(
                safeURL(
                    item.url
                )
            )}"

            target="_blank"

            rel="noopener noreferrer"

        >


            <div class="image-box">


                <img

                    class="card-image"

                    src="${escapeHTML(
                        item.image_url
                    )}"

                    alt="${escapeHTML(
                        title
                    )}"

                    loading="lazy"

                >


                ${imageBreakthroughHTML}


            </div>


        </a>



        <div class="card-body">


            <div class="card-header">


                <span
                    class="
                        priority
                        priority-${priority}
                    "
                >

                    ${priority}

                </span>


                <span class="category">

                    ${escapeHTML(
                        badge
                    )}

                </span>


                ${breakthroughHTML}


            </div>



            <h3>


                <a

                    href="${escapeHTML(
                        safeURL(
                            item.url
                        )
                    )}"

                    target="_blank"

                    rel="noopener noreferrer"

                >

                    ${escapeHTML(
                        title
                    )}

                </a>


            </h3>



            ${summaryHTML}



            <div class="meta">


                <span class="source">

                    ${escapeHTML(
                        item.source
                        || "未知来源"
                    )}

                </span>


                <span class="meta-item">

                    ${escapeHTML(
                        formatDate(
                            item.published_at
                        )
                    )}

                </span>


                ${starsHTML}


                ${languageHTML}


            </div>


        </div>

    `;


    /* =====================================================
       图片失效
       整个词条隐藏
    ===================================================== */

    const image =
        card.querySelector(
            ".card-image"
        );


    if (image) {

        image.addEventListener(

            "error",

            () => {

                card.remove();

            }

        );
    }


    return card;
}


/* =========================================================
   Nature关联论文
========================================================= */

function buildRelatedPapersHTML(
    papers
) {

    if (
        !Array.isArray(
            papers
        )
        ||
        !papers.length
    ) {

        return "";
    }


    const items = papers

        .slice(
            0,
            3
        )

        .map(
            paper => {


                const title =
                    paper.title
                    || "Nature相关研究";


                const journal =
                    paper.source
                    || "Nature Portfolio";


                const date =
                    formatDate(
                        paper.published_at
                    );


                const imageHTML =

                    paper.image_url

                    ? `

                        <img

                            class="related-paper-image"

                            src="${escapeHTML(
                                paper.image_url
                            )}"

                            alt=""

                            loading="lazy"

                        >

                      `

                    : "";


                return `

                    <a

                        class="related-paper"

                        href="${escapeHTML(
                            safeURL(
                                paper.url
                            )
                        )}"

                        target="_blank"

                        rel="noopener noreferrer"

                    >


                        ${imageHTML}


                        <div class="related-paper-content">


                            <div class="related-paper-source">

                                ${escapeHTML(
                                    journal
                                )}

                                ${
                                    date
                                    ? ` · ${escapeHTML(
                                        date
                                    )}`
                                    : ""
                                }

                            </div>


                            <div class="related-paper-title">

                                ${escapeHTML(
                                    title
                                )}

                            </div>


                        </div>


                    </a>

                `;

            }

        )

        .join("");


    return `

        <div class="hotspot-papers">


            <div class="hotspot-block-title">

                Nature 关联研究

            </div>


            <div class="related-paper-list">

                ${items}

            </div>


        </div>

    `;
}


/* =========================================================
   热点卡片
========================================================= */

function createHotspotCard(
    hotspot
) {

    if (!hotspot.image_url) {

        return null;
    }


    const card =
        document.createElement(
            "article"
        );


    card.className =
        "hotspot-card";


    const title =
        hotspot.title
        || "热点";


    const topic =
        hotspot.topic
        || "热点";


    const score =
        Number(
            hotspot.score
        ) || 0;


    const rank =
        Number(
            hotspot.rank
        ) || 0;


    const recommendedTitle =
        hotspot.recommended_title
        || "";


    const angle =
        hotspot.angle
        || "";


    const scoreClass =
        getScoreClass(
            score
        );


    /* =====================================================
       百度排名
    ===================================================== */

    const rankHTML =

        rank > 0

        ? `

            <span class="hotspot-rank">

                百度热榜 #${rank}

            </span>

          `

        : "";


    /* =====================================================
       热点摘要
    ===================================================== */

    let summaryHTML = "";


    if (
        hotspot.summary

        &&

        !looksBrokenText(
            hotspot.summary
        )
    ) {

        summaryHTML = `

            <p class="hotspot-summary">

                ${escapeHTML(
                    hotspot.summary
                )}

            </p>

        `;
    }


    /* =====================================================
       推荐标题
    ===================================================== */

    const recommendedHTML =

        recommendedTitle

        ? `

            <div class="hotspot-block">


                <div class="hotspot-block-title">

                    推荐标题

                </div>


                <div class="recommended-title">

                    ${escapeHTML(
                        recommendedTitle
                    )}

                </div>


            </div>

          `

        : "";


    /* =====================================================
       切入角度
    ===================================================== */

    const angleHTML =

        angle

        ? `

            <div class="hotspot-block">


                <div class="hotspot-block-title">

                    推荐切口

                </div>


                <p class="hotspot-angle">

                    ${escapeHTML(
                        angle
                    )}

                </p>


            </div>

          `

        : "";


    /* =====================================================
       相关Nature论文
    ===================================================== */

    const relatedHTML =
        buildRelatedPapersHTML(
            hotspot.related_papers
        );


    /* =====================================================
       卡片HTML
    ===================================================== */

    card.innerHTML = `


        <div class="hotspot-image-wrap">


            <a

                href="${escapeHTML(
                    safeURL(
                        hotspot.url
                    )
                )}"

                target="_blank"

                rel="noopener noreferrer"

            >


                <img

                    class="hotspot-image"

                    src="${escapeHTML(
                        hotspot.image_url
                    )}"

                    alt="${escapeHTML(
                        title
                    )}"

                    loading="lazy"

                >


            </a>


            <div
                class="
                    potential-score
                    ${scoreClass}
                "
            >

                <span class="score-label">

                    传播潜力

                </span>


                <strong>

                    ${score}

                </strong>


            </div>


        </div>



        <div class="hotspot-content">


            <div class="hotspot-tags">


                <span class="hotspot-main-tag">

                    🔥 热点

                </span>


                <span class="hotspot-topic">

                    ${escapeHTML(
                        topic
                    )}

                </span>


                ${rankHTML}


            </div>



            <h3 class="hotspot-title">


                <a

                    href="${escapeHTML(
                        safeURL(
                            hotspot.url
                        )
                    )}"

                    target="_blank"

                    rel="noopener noreferrer"

                >

                    ${escapeHTML(
                        title
                    )}

                </a>


            </h3>



            ${summaryHTML}



            ${recommendedHTML}



            ${angleHTML}



            ${relatedHTML}


        </div>

    `;


    /* =====================================================
       主图片加载失败
       整条热点删除
    ===================================================== */

    const image =
        card.querySelector(
            ".hotspot-image"
        );


    if (image) {

        image.addEventListener(

            "error",

            () => {

                card.remove();

            }

        );
    }


    /* =====================================================
       Nature关联小图片失效
       只隐藏小图
    ===================================================== */

    card
        .querySelectorAll(
            ".related-paper-image"
        )
        .forEach(
            image => {

                image.addEventListener(

                    "error",

                    () => {

                        image.remove();

                    }

                );

            }
        );


    return card;
}


/* =========================================================
   普通资讯过滤
========================================================= */

function filterNewsItems(
    type,
    value
) {

    if (
        type === "all"
    ) {

        return allItems;
    }


    if (
        type === "category"
    ) {

        return allItems.filter(

            item =>

                item.category
                === value

        );
    }


    if (
        type === "source"
    ) {

        return allItems.filter(

            item =>

                item.source
                === value

        );
    }


    return [];
}


/* =========================================================
   普通资讯列表标题
========================================================= */

function getListTitle(
    type,
    value
) {

    if (
        type === "all"
    ) {

        return "最新资讯";
    }


    if (
        value === "AI变现"
    ) {

        return "AI变现";
    }


    if (
        value === "提效工具"
    ) {

        return "提效工具";
    }


    if (
        value === "前沿动态"
    ) {

        return "前沿动态";
    }


    if (
        value === "Scientific Data"
    ) {

        return (
            "Scientific Data 最新文章"
        );
    }


    if (
        value === "Nature Cities"
    ) {

        return (
            "Nature Cities 最新文章"
        );
    }


    return "最新资讯";
}


/* =========================================================
   普通资讯渲染
========================================================= */

function renderMainList() {

    const section =
        document.getElementById(
            "news-section"
        );


    const container =
        document.getElementById(
            "news-list"
        );


    const resultCount =
        document.getElementById(
            "result-count"
        );


    const titleElement =
        document.getElementById(
            "list-title"
        );


    /* 热点模式不显示普通资讯 */

    if (
        currentFilter.type
        === "hotspot"
    ) {

        section.hidden = true;

        return;
    }


    section.hidden = false;


    const items =
        filterNewsItems(

            currentFilter.type,

            currentFilter.value

        );


    container.innerHTML = "";


    if (resultCount) {

        resultCount.textContent =
            `共 ${items.length} 条`;
    }


    if (titleElement) {

        titleElement.textContent =
            getListTitle(

                currentFilter.type,

                currentFilter.value

            );
    }


    let rendered = 0;


    items.forEach(
        item => {


            const card =
                createNewsCard(
                    item
                );


            if (card) {

                container.appendChild(
                    card
                );

                rendered += 1;
            }


        }
    );


    if (!rendered) {

        container.innerHTML = `

            <div class="empty full-grid">

                <strong>
                    暂无符合条件的资讯
                </strong>

                <p>
                    当前栏目尚未发现带有效图片的最新内容。
                </p>

            </div>

        `;
    }
}


/* =========================================================
   最新突破
========================================================= */

function renderFeatured() {

    const section =
        document.getElementById(
            "featured-section"
        );


    const container =
        document.getElementById(
            "featured-list"
        );


    const count =
        document.getElementById(
            "featured-count"
        );


    /* =====================================================
       只在：
       全部
       前沿动态
       显示
    ===================================================== */

    const showFeatured = (

        currentFilter.type
        === "all"

        ||

        (
            currentFilter.type
            === "category"

            &&

            currentFilter.value
            === "前沿动态"
        )

    );


    if (!showFeatured) {

        section.hidden = true;

        return;
    }


    const items =
        allItems

        .filter(

            item =>

                item.is_breakthrough

                &&

                item.image_url

        )

        .slice(
            0,
            6
        );


    if (!items.length) {

        section.hidden = true;

        return;
    }


    section.hidden = false;


    container.innerHTML = "";


    if (count) {

        count.textContent =
            `精选 ${items.length} 条`;
    }


    items.forEach(
        item => {


            const card =
                createNewsCard(
                    item,
                    true
                );


            if (card) {

                container.appendChild(
                    card
                );
            }


        }
    );
}


/* =========================================================
   热点渲染
========================================================= */

function renderHotspots() {

    const section =
        document.getElementById(
            "hotspot-section"
        );


    const container =
        document.getElementById(
            "hotspot-list"
        );


    const count =
        document.getElementById(
            "hotspot-count"
        );


    /* 不是热点模式 */

    if (
        currentFilter.type
        !== "hotspot"
    ) {

        section.hidden = true;

        return;
    }


    section.hidden = false;


    container.innerHTML = "";


    const hotspots =
        allHotspots.filter(

            hotspot =>
                hotspot.image_url

        );


    if (count) {

        count.textContent =
            `共 ${hotspots.length} 条`;
    }


    if (!hotspots.length) {

        container.innerHTML = `

            <div class="empty">

                <strong>
                    暂无热点
                </strong>

                <p>
                    当前热榜中暂未发现与近期 Nature 研究高度匹配的内容。
                </p>

            </div>

        `;

        return;
    }


    hotspots.forEach(
        hotspot => {


            const card =
                createHotspotCard(
                    hotspot
                );


            if (card) {

                container.appendChild(
                    card
                );
            }


        }
    );
}


/* =========================================================
   按筛选条件计数
========================================================= */

function countByFilter(
    type,
    value
) {

    if (
        type === "hotspot"
    ) {

        return allHotspots.filter(

            hotspot =>
                hotspot.image_url

        ).length;
    }


    return filterNewsItems(
        type,
        value
    )

    .filter(

        item =>
            item.image_url

    )

    .length;
}


/* =========================================================
   导航按钮数量
========================================================= */

function updateFilterCounts() {

    document
        .querySelectorAll(
            ".filter"
        )
        .forEach(
            button => {


                if (
                    !button.dataset.label
                ) {

                    button.dataset.label =
                        button.textContent.trim();
                }


                const type =
                    button.dataset.filterType;


                const value =
                    button.dataset.filterValue;


                const count =
                    countByFilter(
                        type,
                        value
                    );


                button.innerHTML = `


                    <span>

                        ${escapeHTML(
                            button.dataset.label
                        )}

                    </span>


                    <span class="filter-count">

                        ${count}

                    </span>


                `;


            }
        );
}


/* =========================================================
   今日提示
========================================================= */

function updateSummary() {

    const element =
        document.getElementById(
            "today-summary"
        );


    if (!element) {

        return;
    }


    const hotspotCount =
        allHotspots.filter(

            hotspot =>
                hotspot.image_url

        ).length;


    const aiCount =
        countByFilter(
            "category",
            "AI变现"
        );


    const toolCount =
        countByFilter(
            "category",
            "提效工具"
        );


    const frontierCount =
        countByFilter(
            "category",
            "前沿动态"
        );


    const sdataCount =
        countByFilter(
            "source",
            "Scientific Data"
        );


    const citiesCount =
        countByFilter(
            "source",
            "Nature Cities"
        );


    const breakthroughCount =
        allItems.filter(

            item =>

                item.is_breakthrough

                &&

                item.image_url

        ).length;


    element.textContent =

        `当前收录 ${allItems.length} 条带图资讯，`

        + `热点 ${hotspotCount} 条，`

        + `突破性资讯 ${breakthroughCount} 条；`

        + `AI变现 ${aiCount} 条，`

        + `提效工具 ${toolCount} 条，`

        + `前沿动态 ${frontierCount} 条，`

        + `Scientific Data ${sdataCount} 篇，`

        + `Nature Cities ${citiesCount} 篇。`;
}


/* =========================================================
   应用导航筛选
========================================================= */

function applyFilter(
    type,
    value
) {

    currentFilter = {
        type,
        value
    };


    document
        .querySelectorAll(
            ".filter"
        )
        .forEach(
            button => {


                const active = (

                    button.dataset.filterType
                    === type

                    &&

                    button.dataset.filterValue
                    === value

                );


                button.classList.toggle(

                    "active",

                    active

                );


            }
        );


    renderHotspots();

    renderFeatured();

    renderMainList();


    /* =====================================================
       点击分类后回到导航下面
    ===================================================== */

    const filters =
        document.querySelector(
            ".filters"
        );


    if (filters) {

        const y =

            filters
                .getBoundingClientRect()
                .top

            +

            window.scrollY

            -

            16;


        window.scrollTo({

            top:
                y,

            behavior:
                "smooth"

        });
    }
}


/* =========================================================
   读取 news.json
========================================================= */

async function loadNews() {

    try {

        const response =
            await fetch(

                `./data/news.json?t=${Date.now()}`,

                {

                    cache:
                        "no-store"

                }

            );


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );
        }


        const data =
            await response.json();


        if (
            !data
            ||
            !Array.isArray(
                data.items
            )
        ) {

            throw new Error(
                "news.json 数据格式错误"
            );
        }


        /* =================================================
           普通资讯
           没图不进入
        ================================================= */

        allItems =
            data.items.filter(

                item =>
                    Boolean(
                        item.image_url
                    )

            );


        /* =================================================
           热点
        ================================================= */

        allHotspots =
            Array.isArray(
                data.hotspots
            )

            ? data.hotspots.filter(

                hotspot =>
                    Boolean(
                        hotspot.image_url
                    )

            )

            : [];


        /* =================================================
           最近更新时间
        ================================================= */

        const updateElement =
            document.getElementById(
                "update-time"
            );


        if (updateElement) {

            updateElement.textContent =
                formatUpdateTime(
                    data.updated_at
                );
        }


        /* =================================================
           更新页面
        ================================================= */

        updateFilterCounts();

        updateSummary();


        applyFilter(
            "all",
            "all"
        );


    }

    catch (error) {

        console.error(
            "加载失败：",
            error
        );


        const newsContainer =
            document.getElementById(
                "news-list"
            );


        const hotspotContainer =
            document.getElementById(
                "hotspot-list"
            );


        if (newsContainer) {

            newsContainer.innerHTML = `

                <div class="empty full-grid">

                    <strong>
                        数据加载失败
                    </strong>

                    <p>
                        请稍后刷新页面。
                    </p>

                </div>

            `;
        }


        if (hotspotContainer) {

            hotspotContainer.innerHTML = `

                <div class="empty">

                    <strong>
                        热点加载失败
                    </strong>

                </div>

            `;
        }

    }
}


/* =========================================================
   导航按钮事件
========================================================= */

document
    .querySelectorAll(
        ".filter"
    )
    .forEach(
        button => {


            button.addEventListener(

                "click",

                () => {


                    applyFilter(

                        button.dataset.filterType,

                        button.dataset.filterValue

                    );


                }

            );


        }
    );


/* =========================================================
   启动
========================================================= */

loadNews();
