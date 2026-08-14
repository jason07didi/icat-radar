let allItems = [];


function escapeHTML(value) {

    if (!value) return "";

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");

}


function formatDate(value) {

    if (!value) return "";

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
            year: "numeric",
            month: "2-digit",
            day: "2-digit"
        }
    );

}


function renderItems(items) {

    const container =
        document.getElementById(
            "news-list"
        );

    container.innerHTML = "";


    if (!items.length) {

        container.innerHTML =
            `<div class="empty">
                暂无符合条件的资讯
            </div>`;

        return;
    }


    items.forEach(item => {

        const card =
            document.createElement(
                "article"
            );

        card.className =
            `news-card card-${item.priority}`;


        const stars =
            item.meta &&
            item.meta.stars
                ? `⭐ ${escapeHTML(
                    item.meta.stars
                )}`
                : "";


        const language =
            item.meta &&
            item.meta.language
                ? escapeHTML(
                    item.meta.language
                )
                : "";


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


        card.innerHTML = `

            <div class="card-header">

                <span
                    class="priority
                    priority-${escapeHTML(
                        item.priority
                    )}"
                >
                    ${escapeHTML(
                        item.priority
                    )}
                </span>

                <span class="category">
                    ${escapeHTML(
                        item.category
                    )}
                </span>

            </div>


            <h3>

                <a
                    href="${escapeHTML(
                        item.url
                    )}"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    ${escapeHTML(
                        item.title
                    )}
                </a>

            </h3>


            ${summary}


            <div class="meta">

                <span>
                    ${escapeHTML(
                        item.source
                    )}
                </span>

                <span>
                    ${formatDate(
                        item.published_at
                    )}
                </span>

                ${
                    stars
                        ? `<span>${stars}</span>`
                        : ""
                }

                ${
                    language
                        ? `<span>${language}</span>`
                        : ""
                }

            </div>

        `;


        container.appendChild(
            card
        );

    });

}


async function loadNews() {

    try {

        const response =
            await fetch(
                `data/news.json?t=${Date.now()}`
            );


        if (!response.ok) {

            throw new Error(
                "无法读取 news.json"
            );

        }


        const data =
            await response.json();


        allItems =
            data.items || [];


        document.getElementById(
            "update-time"
        ).textContent =
            data.updated_at
                ? `最近更新：${
                    new Date(
                        data.updated_at
                    ).toLocaleString(
                        "zh-CN"
                    )
                }`
                : "等待首次自动更新";


        document.getElementById(
            "today-summary"
        ).textContent =
            `目前共收录 ${
                allItems.length
            } 条最新动态，重点监控 AI 工具、GitHub、Scientific Data 与 Nature Cities。`;


        renderItems(
            allItems
        );

    }

    catch (error) {

        console.error(
            error
        );

        document.getElementById(
            "news-list"
        ).innerHTML =
            `<div class="empty">
                数据加载失败，请稍后刷新。
            </div>`;

    }

}


document.querySelectorAll(
    ".filter"
).forEach(button => {

    button.addEventListener(
        "click",
        () => {

            document.querySelectorAll(
                ".filter"
            ).forEach(
                item =>
                    item.classList.remove(
                        "active"
                    )
            );


            button.classList.add(
                "active"
            );


            const category =
                button.dataset.category;


            if (
                category === "all"
            ) {

                renderItems(
                    allItems
                );

            }

            else {

                renderItems(
                    allItems.filter(
                        item =>
                            item.category
                            === category
                    )
                );

            }

        }
    );

});


loadNews();
