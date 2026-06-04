/* Bloomy News — Landing Page App */
(function () {
    'use strict';

    function escapeHtml(s) {
        const d = document.createElement('div');
        d.textContent = s || '';
        return d.innerHTML;
    }

    function safeUrl(url) {
        if (!url) return '#';
        const lower = url.toLowerCase().trim();
        if (lower.startsWith('http://') || lower.startsWith('https://')) {
            return url;
        }
        return '#';
    }

    function formatDateShort(iso) {
        if (!iso) return '';
        let date;
        if (typeof iso === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(iso)) {
            const parts = iso.split('-');
            date = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
        } else {
            date = new Date(iso);
        }
        if (isNaN(date.getTime())) return '';
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
    }

    const catColor = {
        'LLM': '#8b5cf6',
        'Neural-Nets': '#06b6d4',
        'ML-Research': '#3b82f6',
        'AI-Applications': '#10b981',
        'Finance': '#f59e0b',
        'Cybersecurity': '#ef4444'
    };

    const catIcons = {
        'LLM': '🧠',
        'Neural-Nets': '🔬',
        'ML-Research': '📊',
        'AI-Applications': '🤖',
        'Finance': '💰',
        'Cybersecurity': '🔒'
    };

    const catLabels = {
        'LLM': 'LLM',
        'Neural-Nets': 'Neural Nets',
        'ML-Research': 'ML Research',
        'AI-Applications': 'AI Apps',
        'Finance': 'Finance',
        'Cybersecurity': 'Cyber'
    };

    let allArticles = [];
    let stats = {};
    let bookmarkedIds = [];
    let panelCurrentArticle = null;

    const categoryGrid = document.getElementById('category-grid');
    const articleGrid = document.getElementById('article-grid');
    const emptyState = document.getElementById('empty-state');
    const themeToggle = document.getElementById('theme-toggle');
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error-state');
    const panelStarBtn = document.getElementById('panel-star-btn');

    /* ── Theme ── */
    function safeStorageGet(key, fallback) {
        try { return localStorage.getItem(key) || fallback; } catch (e) { return fallback; }
    }
    function safeStorageSet(key, value) {
        try { localStorage.setItem(key, value); } catch (e) { /* private mode / quota */ }
    }
    function initTheme() {
        const saved = safeStorageGet('Bloomy-theme', 'dark');
        document.documentElement.setAttribute('data-theme', saved);
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            safeStorageSet('Bloomy-theme', next);
            themeToggle.setAttribute('aria-pressed', String(next === 'dark'));
        });
    }

    /* ── Data ── */
    function loadData() {
        if (loadingEl) loadingEl.style.display = 'flex';
        if (errorEl) errorEl.style.display = 'none';
        fetch('data/dashboard_data.json')
            .then((resp) => {
                if (!resp.ok) throw new Error('Network response was not ok');
                return resp.json();
            })
            .then((data) => {
                if (loadingEl) loadingEl.style.display = 'none';
                allArticles = data.articles || [];
                stats = data.stats || {};
                const updateTimeEl = document.getElementById('update-time');
                if (updateTimeEl) updateTimeEl.textContent = data.generated || '--';
                loadBookmarks();
            })
            .catch(() => {
                if (loadingEl) loadingEl.style.display = 'none';
                if (articleGrid) articleGrid.innerHTML = '';
                if (emptyState) emptyState.style.display = 'none';
                if (errorEl) {
                    errorEl.style.display = 'flex';
                    const retryBtn = errorEl.querySelector('.retry-btn');
                    if (retryBtn) retryBtn.addEventListener('click', loadData);
                }
            });
    }

    function loadBookmarks() {
        fetch('/api/bookmarks')
            .then((resp) => resp.ok ? resp.json() : { bookmarks: [] })
            .then((data) => {
                bookmarkedIds = data.bookmarks || [];
                renderCategoryGrid();
                renderArticles();
            })
            .catch(() => {
                bookmarkedIds = [];
                renderCategoryGrid();
                renderArticles();
            });
    }

    function isBookmarked(id) {
        return bookmarkedIds.indexOf(id) !== -1;
    }

    function toggleBookmark(article, onDone) {
        fetch('/api/bookmarks/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: article.id })
        })
        .then((resp) => {
            if (!resp.ok) throw new Error('Failed to toggle bookmark');
            return resp.json();
        })
        .then((data) => {
            bookmarkedIds = data.bookmarks || [];
            if (onDone) onDone(true);
        })
        .catch(() => {
            const idx = bookmarkedIds.indexOf(article.id);
            if (idx === -1) bookmarkedIds.push(article.id);
            else bookmarkedIds.splice(idx, 1);
            if (onDone) onDone(false);
        });
    }

    function updateCardStar(btn, bookmarked) {
        if (bookmarked) {
            btn.classList.add('is-starred');
            btn.setAttribute('aria-pressed', 'true');
            btn.setAttribute('aria-label', 'Remove bookmark');
            btn.setAttribute('title', 'Remove bookmark');
            const svg = btn.querySelector('svg');
            if (svg) svg.setAttribute('fill', 'currentColor');
        } else {
            btn.classList.remove('is-starred');
            btn.setAttribute('aria-pressed', 'false');
            btn.setAttribute('aria-label', 'Bookmark this article');
            btn.setAttribute('title', 'Bookmark this article');
            const svg = btn.querySelector('svg');
            if (svg) svg.setAttribute('fill', 'none');
        }
    }

    function updatePanelStar(btn, bookmarked) {
        if (!btn) return;
        if (bookmarked) {
            btn.classList.add('is-starred');
            btn.setAttribute('aria-pressed', 'true');
            btn.setAttribute('title', 'Remove bookmark');
            const svg = btn.querySelector('svg');
            if (svg) svg.setAttribute('fill', 'currentColor');
        } else {
            btn.classList.remove('is-starred');
            btn.setAttribute('aria-pressed', 'false');
            btn.setAttribute('title', 'Bookmark article');
            const svg = btn.querySelector('svg');
            if (svg) svg.setAttribute('fill', 'none');
        }
    }

    /* ── Category Grid ── */
    function renderCategoryGrid() {
        const cats = stats.categories || {};
        const categories = ['LLM', 'Neural-Nets', 'ML-Research', 'AI-Applications', 'Finance', 'Cybersecurity'];
        const sources = {};
        for (let i = 0; i < allArticles.length; i++) {
            if (allArticles[i].source) sources[allArticles[i].source] = true;
        }
        const sourceCountEl = document.getElementById('source-count');
        if (sourceCountEl) sourceCountEl.textContent = Object.keys(sources).length;

        let html = '';
        for (let j = 0; j < categories.length; j++) {
            const cat = categories[j];
            const count = cats[cat] || 0;
            html += `<div class="category-card" data-category="${escapeHtml(cat)}" style="--cat-color:${catColor[cat] || '#888'}">
                <span class="cat-icon">${catIcons[cat] || '📰'}</span>
                <div class="cat-name">${escapeHtml(catLabels[cat] || cat)}</div>
                <div class="cat-count">${count}</div>
            </div>`;
        }
        if (categoryGrid) categoryGrid.innerHTML = html;

        if (categoryGrid) {
            const cards = categoryGrid.querySelectorAll('.category-card');
            for (let k = 0; k < cards.length; k++) {
                cards[k].addEventListener('click', function () {
                    const cat = this.getAttribute('data-category');
                    window.location.href = `filters.html?category=${encodeURIComponent(cat)}`;
                });
            }
        }
    }

    /* ── Articles ── */
    function renderArticles() {
        const sorted = allArticles.slice().sort((a, b) => {
            return new Date(b.published || 0) - new Date(a.published || 0);
        });

        const limit = Math.min(sorted.length, 12);
        if (limit === 0) {
            if (articleGrid) articleGrid.innerHTML = '';
            if (emptyState) emptyState.style.display = 'flex';
            return;
        }
        if (emptyState) emptyState.style.display = 'none';

        let html = '';
        for (let i = 0; i < limit; i++) {
            const a = sorted[i];
            const color = catColor[a.category] || '#888';
            const starred = isBookmarked(a.id);
            const starClass = 'article-card-star' + (starred ? ' is-starred' : '');
            const starFill = starred ? 'currentColor' : 'none';
            const starAriaPressed = starred ? 'true' : 'false';
            const starLabel = starred ? 'Remove bookmark' : 'Bookmark this article';
            const starTitle = starred ? 'Remove bookmark' : 'Bookmark this article';
            html += `<div class="article-card" data-id="${escapeHtml(a.id || '')}" style="--cat-color:${color}">
                <button class="${starClass}" data-id="${escapeHtml(a.id || '')}" title="${starTitle}" aria-label="${starLabel}" aria-pressed="${starAriaPressed}">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="${starFill}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                </button>
                <div class="article-card-source">${escapeHtml(a.source || '')}</div>
                <div class="article-card-title">${escapeHtml(a.title || 'Untitled')}</div>
                <div class="article-card-summary">${escapeHtml(a.summary || '')}</div>
                <div class="article-card-meta">
                    <span class="article-card-cat"><span class="cat-dot"></span>${escapeHtml(a.category || '')}</span>
                    <span class="article-card-date">${formatDateShort(a.published)}</span>
                </div>
            </div>`;
        }
        if (articleGrid) articleGrid.innerHTML = html;

        if (articleGrid) {
            const cards = articleGrid.querySelectorAll('.article-card');
            for (let j = 0; j < cards.length; j++) {
                cards[j].addEventListener('click', handleCardClick);
            }

            const starBtns = articleGrid.querySelectorAll('.article-card-star');
            for (let k = 0; k < starBtns.length; k++) {
                starBtns[k].addEventListener('click', handleStarClick);
            }
        }
    }

    function handleStarClick(e) {
        e.stopPropagation();
        const btn = e.currentTarget;
        const id = btn.getAttribute('data-id');
        const article = findArticleById(id);
        if (!article) return;

        const wasStarred = isBookmarked(id);
        updateCardStar(btn, !wasStarred);

        toggleBookmark(article, (success) => {
            if (success) {
                updateCardStar(btn, isBookmarked(id));
                if (panelCurrentArticle && panelCurrentArticle.id === id) {
                    updatePanelStar(panelStarBtn, isBookmarked(id));
                }
            } else {
                updateCardStar(btn, wasStarred);
            }
        });
    }

    function findArticleById(id) {
        for (let i = 0; i < allArticles.length; i++) {
            if (allArticles[i].id === id) return allArticles[i];
        }
        return null;
    }

    function handleCardClick(e) {
        const card = e.currentTarget;
        const id = card.getAttribute('data-id');
        for (let i = 0; i < allArticles.length; i++) {
            if (allArticles[i].id === id) {
                openPanel(allArticles[i]);
                return;
            }
        }
    }

    /* ── Side Panel ── */
    function openPanel(a) {
        panelCurrentArticle = a;

        const catEl = document.getElementById('panel-category');
        if (catEl) {
            catEl.textContent = (a.category || '').toUpperCase();
            catEl.setAttribute('data-cat', a.category || '');
        }

        const panelTitle = document.getElementById('panel-title');
        if (panelTitle) panelTitle.textContent = a.title || 'Untitled';
        const panelSource = document.getElementById('panel-source');
        if (panelSource) panelSource.textContent = a.source || '';
        const panelDate = document.getElementById('panel-date');
        if (panelDate) panelDate.textContent = formatDateShort(a.published);

        const tagsEl = document.getElementById('panel-tags');
        const tags = a.tags || [];
        if (tagsEl) {
            if (tags.length > 0) {
                tagsEl.innerHTML = tags.map((t) => `<span class="panel-tag">${escapeHtml(t)}</span>`).join('');
                tagsEl.style.display = 'flex';
            } else {
                tagsEl.innerHTML = '';
                tagsEl.style.display = 'none';
            }
        }

        const panelSummary = document.getElementById('panel-summary');
        if (panelSummary) panelSummary.textContent = a.summary || 'No summary available.';
        const panelLink = document.getElementById('panel-link');
        if (panelLink) panelLink.href = safeUrl(a.url);

        updatePanelStar(panelStarBtn, isBookmarked(a.id));

        const sidePanel = document.getElementById('side-panel');
        if (sidePanel) sidePanel.classList.add('open');
        const panelOverlay = document.getElementById('panel-overlay');
        if (panelOverlay) panelOverlay.classList.add('open');
    }

    function handlePanelStarClick() {
        if (!panelCurrentArticle) return;
        const article = panelCurrentArticle;
        const wasStarred = isBookmarked(article.id);
        updatePanelStar(panelStarBtn, !wasStarred);

        toggleBookmark(article, (success) => {
            if (success) {
                updatePanelStar(panelStarBtn, isBookmarked(article.id));
                const cardBtn = articleGrid.querySelector(`.article-card-star[data-id="${cssEscape(article.id)}"]`);
                if (cardBtn) updateCardStar(cardBtn, isBookmarked(article.id));
            } else {
                updatePanelStar(panelStarBtn, wasStarred);
            }
        });
    }

    function cssEscape(s) {
        if (window.CSS && CSS.escape) return CSS.escape(s);
        return String(s).replace(/[^a-zA-Z0-9_-]/g, (c) => `\\${c}`);
    }

    if (panelStarBtn) {
        panelStarBtn.addEventListener('click', handlePanelStarClick);
    }

    function closePanel() {
        const sidePanel = document.getElementById('side-panel');
        if (sidePanel) sidePanel.classList.remove('open');
        const panelOverlay = document.getElementById('panel-overlay');
        if (panelOverlay) panelOverlay.classList.remove('open');
    }

    const panelClose = document.getElementById('panel-close');
    if (panelClose) panelClose.addEventListener('click', closePanel);
    const panelOverlay = document.getElementById('panel-overlay');
    if (panelOverlay) panelOverlay.addEventListener('click', closePanel);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closePanel();
    });

    /* ── Init ── */
    initTheme();
    loadData();
})();
