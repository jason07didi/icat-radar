let allItems = [];

let currentFilter = {
    type: "all",
    value: "all"
};


/* =========================================
   HTML转义
========================================= */

function escapeHTML(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


/* =========================================
   日期
========================================= */

function formatDate(value) {

    if (!value) {
        return "";
    }

    const date = new Date(value);

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
            timeZone: "Asia/Shanghai",
            year: "numeric",
            month: "2-digit",
            day: "2-digit"
        }
    );
}


/* =========================================
   最近扫描时间
========================================= */

function formatUpdateTime(value) {

    if (!value) {
        return "等待首次自动更新";
    }

    const date = new Date(value);

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return "最近更新时间未知";
    }


    const text = date.toLocaleString(
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
                false,

            hourCycle:
                "h23"
        }
    );


    return (
        `最近更新：${text}`
        + `（北京时间）`
    );
}


/* =========================================
   URL
========================================= */

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


/* =========================================
   priority
========================================= */

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


/* =========================================
   图片占位样式
========================================= */

function getPlaceholderInfo(item) {

    if (
        item.source
        === "Scientific Data"
    ) {

        return {
            icon: "DATA",
            text: "Scientific Data",
            cls: "placeholder-data"
        };
    }


    if (
        item.source
        === "Nature Cities"
    ) {

        return {
            icon: "CITY",
            text: "Nature Cities",
            cls: "placeholder-city"
        };
    }


    if (
        item.category
        === "AI变现"
    ) {

        return {
            icon: "AI",
            text: "AI · BUSINESS",
            cls: "placeholder-ai"
        };
    }


    if (
        item.category
        === "前沿动态"
    ) {

        return {
            icon: "NEW",
            text: "SCIENCE · BREAKTHROUGH",
            cls: "placeholder-research"
        };
    }


    return {
        icon: "TOOL",
        text: "RESEARCH · TOOL",
        cls: "placeholder-tool"
    };
}


/* =========================================
   图片HTML
========================================= */

function buildImageHTML(item) {

    const placeholder =
        getPlaceholderInfo(item);


    if (
        item.image_url
    ) {

        return `

            <img
                class="card-image"
                src="${escapeHTML(
                    item.image_url
                )}"
                alt=""
                loading="lazy"
                referrerpolicy="no-referrer"
            >

            <div
                class="image-placeholder
                ${placeholder.cls}"
                hidden
            >

                <strong>
                    ${escapeHTML(
                        placeholder.icon
                    )}
                </strong>

                <span>
                    ${escapeHTML(
                        placeholder.text
                    )}
                </span>

            </div>
        `;
    }


    return `

        <div
            class="image-placeholder
            ${placeholder.cls}"
        >

            <strong>
                ${escapeHTML(
                    placeholder.icon
                )}
            </strong>

            <span>
                ${escapeHTML(
                    placeholder.text
                )}
            </span>

        </div>
    `;
}


/* =========================================
   卡片
========================================= */

function createCard(
    item,
    featured = false
) {

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


    const breakthroughBadge =
        item.is_breakthrough
        ? `
            <span class="breakthrough">
                🔥 突破
            </span>
          `
        : "";


    const badgeText =
        (
            item.source
            === "Scientific Data"
            ||
            item.source
            === "Nature Cities"
        )
        ? item.source
        : item.category;


    const summary =
        item.summary
        ? `
            <p class="summary">
                ${escapeHTML(
                    item.summary
                )}
            </p>
          `
        : "";


    const stars =
        item.meta &&
        item.meta.stars
        ? `
            <span>
                ⭐ ${escapeHTML(
                    item.meta.stars
                )}
            </span>
          `
        : "";


    const language =
        item.meta &&
        item.meta.language
        ? `
            <span>
                ${escapeHTML(
                    item.meta.language
                )}
            </span>
          `
        : "";


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

                ${buildImageHTML(
                    item
                )}

                ${
                    item.is_breakthrough
                    ? `
                        <span class="image-breakthrough">
                            🔥 突破
                        </span>
                      `
                    : ""
                }

            </div>

        </a>


        <div class="card-body">


            <div class="card-header">

                <span
                    class="priority
                    priority-${priority}"
                >
                    ${priority}
                </span>


                <span class="category">

                    ${escapeHTML(
                        badgeText
                        || "资讯"
                    )}

                </span>


                ${breakthroughBadge}

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


            ${summary}


            <div class="meta">

                <span class="source">

                    ${escapeHTML(
                        item.source
                        || "未知来源"
                    )}

                </span>


                <span>

                    ${escapeHTML(
                        formatDate(
                            item.published_at
                        )
                    )}

                </span>


                ${stars}

                ${language}

            </div>


        </div>
    `;


    /* -------------------------
       图片加载失败自动切换占位图
    -------------------------- */

    const image =
        card.querySelector(
            ".card-image"
        );


    if (image) {

        image.addEventListener(
            "error",
            () => {

                image.hidden = true;

                const placeholder =
                    card.querySelector(
                        ".image-placeholder"
                    );


                if (placeholder) {

                    placeholder.hidden =
                        false;
                }

            }
        );
    }


    return card;
}


/* =========================================
   过滤
========================================= */

function filterItems(
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


    return allItems;
}


/* =========================================
   标题
========================================= */

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
        return "Scientific Data 最新文章";
    }


    if (
        value === "Nature Cities"
    ) {
        return "Nature Cities 最新文章";
    }


    return "最新资讯";
}


/* =========================================
   列表
========================================= */

function renderMainList() {

    const items =
        filterItems(
            currentFilter.type,
            currentFilter.value
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


    if (!items.length) {

        container.innerHTML = `

            <div class="empty full-grid">

                <strong>
                    暂无符合条件的资讯
                </strong>

                <p>
                    当前栏目尚未抓取到新的内容。
                </p>

            </div>
        `;

        return;
    }


    items.forEach(item => {

        container.appendChild(
            createCard(item)
        );

    });
}


/* =========================================
   最新突破
========================================= */

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


    /* 只在全部和前沿动态下显示 */

    const showFeatured = (

        currentFilter.type === "all"

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


    const breakthroughItems =
        allItems
        .filter(
            item =>
                item.is_breakthrough
        )
        .slice(
            0,
            6
        );


    if (
        !breakthroughItems.length
    ) {

        section.hidden = true;

        return;
    }


    section.hidden = false;

    container.innerHTML = "";


    if (count) {

        count.textContent =
            `精选 ${breakthroughItems.length} 条`;
    }


    breakthroughItems.forEach(
        item => {

            container.appendChild(
                createCard(
                    item,
                    true
                )
            );

        }
    );
}


/* =========================================
   数量统计
========================================= */

function countByFilter(
    type,
    value
) {

    return filterItems(
        type,
        value
    ).length;
}


/* =========================================
   按钮数字
========================================= */

function updateFilterCounts() {

    document
        .querySelectorAll(
            ".filter"
        )
        .forEach(button => {


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

        });
}


/* =========================================
   今日提示
========================================= */

function updateSummary() {

    const element =
        document.getElementById(
            "today-summary"
        );


    if (!element) {
        return;
    }


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
        ).length;


    element.textContent =

        `当前收录 ${allItems.length} 条最新动态，`

        + `其中突破性资讯 ${breakthroughCount} 条；`

        + `AI变现 ${aiCount} 条，`

        + `提效工具 ${toolCount} 条，`

        + `前沿动态 ${frontierCount} 条，`

        + `Scientific Data ${sdataCount} 篇，`

        + `Nature Cities ${citiesCount} 篇。`;
}


/* =========================================
   应用过滤
========================================= */

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
        .forEach(button => {

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

        });


    renderFeatured();

    renderMainList();
}


/* =========================================
   载入JSON
========================================= */

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
                "news.json格式错误"
            );
        }


        allItems =
            data.items;


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


        const container =
            document.getElementById(
                "news-list"
            );


        container.innerHTML = `

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
}


/* =========================================
   按钮
========================================= */

document
    .querySelectorAll(
        ".filter"
    )
    .forEach(button => {

        button.addEventListener(
            "click",
            () => {

                applyFilter(

                    button.dataset.filterType,

                    button.dataset.filterValue
                );

            }
        );

    });


loadNews();
