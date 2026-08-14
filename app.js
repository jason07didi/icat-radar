let allItems = [];

let currentCategory = "all";


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


/* =========================================
   安全URL
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
   创建卡片
========================================= */

function createCard(item) {

    const priority =
        getPriority(
            item.priority
        );


    const card =
        document.createElement(
            "article"
        );


    card.className =
        `news-card card-${priority}`;


    const title =
        item.display_title
        ||
        item.title
        ||
        "未命名资讯";


    /* -------------------------
       突破标签
    -------------------------- */

    const breakthroughBadge =
        item.is_breakthrough
        ? `
            <span class="breakthrough">
                🔥 突破
            </span>
          `
        : "";


    /* -------------------------
       摘要
    -------------------------- */

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


    /* -------------------------
       GitHub Stars
    -------------------------- */

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


    /* -------------------------
       程序语言
    -------------------------- */

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

        <div class="card-header">

            <span
                class="priority
                priority-${priority}"
            >
                ${priority}
            </span>


            <span class="category">
                ${escapeHTML(
                    item.category
                    || "其他"
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

    `;


    return card;
}


/* =========================================
   渲染
========================================= */

function renderItems(items) {

    const container =
        document.getElementById(
            "news-list"
        );


    const resultCount =
        document.getElementById(
            "result-count"
        );


    if (!container) {
        return;
    }


    container.innerHTML = "";


    if (resultCount) {

        resultCount.textContent =
            `共 ${items.length} 条`;
    }


    if (!items.length) {

        container.innerHTML = `

            <div class="empty">

                <strong>
                    暂无符合条件的资讯
                </strong>

                <p>
                    当前栏目尚未抓取到符合筛选条件的最新内容。
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
   分类数量
========================================= */

function getCounts() {

    const counts = {

        all:
            allItems.length,

        "AI变现":
            0,

        "提效工具":
            0,

        "多源数据":
            0,

        "前沿研究":
            0
    };


    allItems.forEach(item => {

        if (
            Object.prototype
                .hasOwnProperty.call(
                    counts,
                    item.category
                )
        ) {

            counts[
                item.category
            ] += 1;
        }

    });


    return counts;
}


/* =========================================
   更新按钮数量
========================================= */

function updateFilterCounts() {

    const counts =
        getCounts();


    document
        .querySelectorAll(
            ".filter"
        )
        .forEach(button => {

            const category =
                button.dataset.category;


            if (
                !button.dataset.label
            ) {

                button.dataset.label =
                    button.textContent.trim();
            }


            const label =
                button.dataset.label;


            const count =
                counts[category]
                || 0;


            button.innerHTML = `

                <span>
                    ${escapeHTML(
                        label
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

function updateSummary(
    data
) {

    const element =
        document.getElementById(
            "today-summary"
        );


    if (!element) {
        return;
    }


    const counts =
        getCounts();


    const breakthroughCount =
        data.breakthrough_count
        || allItems.filter(
            item =>
                item.is_breakthrough
        ).length;


    element.textContent =

        `目前收录 ${allItems.length} 条最新动态，`

        + `其中突破性资讯 ${breakthroughCount} 条；`

        + `AI变现 ${counts["AI变现"]} 条，`

        + `提效工具 ${counts["提效工具"]} 条，`

        + `多源数据 ${counts["多源数据"]} 条，`

        + `前沿研究 ${counts["前沿研究"]} 条。`;
}


/* =========================================
   筛选
========================================= */

function applyFilter(category) {

    currentCategory =
        category;


    document
        .querySelectorAll(
            ".filter"
        )
        .forEach(button => {

            button.classList.toggle(
                "active",
                button.dataset.category
                === category
            );

        });


    if (
        category === "all"
    ) {

        renderItems(
            allItems
        );

        return;
    }


    const filtered =
        allItems.filter(
            item =>
                item.category
                === category
        );


    renderItems(
        filtered
    );
}


/* =========================================
   读取JSON
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


        /* -------------------------
           更新时间
        -------------------------- */

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


        /* -------------------------
           数量
        -------------------------- */

        updateFilterCounts();


        /* -------------------------
           今日提示
        -------------------------- */

        updateSummary(
            data
        );


        /* -------------------------
           默认全部
        -------------------------- */

        applyFilter(
            currentCategory
        );

    }


    catch (error) {

        console.error(
            "加载资讯失败：",
            error
        );


        const container =
            document.getElementById(
                "news-list"
            );


        if (container) {

            container.innerHTML = `

                <div class="empty error-box">

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
}


/* =========================================
   按钮事件
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
                    button.dataset.category
                );

            }
        );

    });


/* =========================================
   启动
========================================= */

loadNews();
