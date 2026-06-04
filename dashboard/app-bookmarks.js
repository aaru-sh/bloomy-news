/* Bloomy News — Bookmarks Page App */
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

    let bookmarkedIds = [];
    let allArticles = [];
    let panelCurrentArticle = null;
    const bookmarksList = document.getElementById('bookmarks-list');
    const emptyState = document.getElementById('empty-state');
    const bookmarksCountEl = document.getElementById('bookmarks-count');
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
    function loadBookmarks() {
        if (loadingEl) loadingEl.style.display = 'flex';
        if (errorEl) errorEl.style.display = 'none';
        fetch('/api/bookmarks')
            .then((resp) => {
                if (!resp.ok) throw new Error('Failed to fetch bookmarks');
                return resp.json();
            })
            .then((data) => {
                bookmarkedIds = data.bookmarks || [];
                loadArticles();
            })
            .catch(() => {
                bookmarkedIds = [];
                loadArticles();
            });
    }

    function loadArticles() {
        fetch('/api/articles')
            .then((resp) => {
                if (!resp.ok) throw new Error('Failed to fetch articles');
                return resp.json();
            })
            .then((data) => {
                if (loadingEl) loadingEl.style.display = 'none';
                allArticles = data.articles || [];
                renderBookmarks();
            })
            .catch(() => {
                if (loadingEl) loadingEl.style.display = 'none';
                allArticles = [];
                renderBookmarks();
                if (errorEl) {
                    errorEl.style.display = 'flex';
                    const retryBtn = errorEl.querySelector('.retry-btn');
                    if (retryBtn) retryBtn.addEventListener('click', loadBookmarks);
                }
            });
    }

    /* ── Render ── */
    function renderBookmarks() {
        const bookmarked = allArticles.filter((a) => bookmarkedIds.indexOf(a.id) !== -1);

        bookmarked.sort((a, b) => new Date(b.published || 0) - new Date(a.published || 0));

        if (bookmarksCountEl) {
            const n = bookmarked.length;
            bookmarksCountEl.textContent = `${n} article${n !== 1 ? 's' : ''} saved`;
        }

        if (bookmarked.length === 0) {
            if (bookmarksList) bookmarksList.innerHTML = '';
            if (emptyState) emptyState.style.display = 'flex';
            return;
        }
        if (emptyState) emptyState.style.display = 'none';

        let html = '';
        for (let i = 0; i < bookmarked.length; i++) {
            const a = bookmarked[i];
            const color = catColor[a.category] || '#888';
            html += `<div class="bookmark-card" data-id="${escapeHtml(a.id || '')}">
                <div class="bookmark-card-content">
                    <div class="bookmark-card-source">${escapeHtml(a.source || '')}</div>
                    <div class="bookmark-card-title">${escapeHtml(a.title || 'Untitled')}</div>
                    <div class="bookmark-card-summary">${escapeHtml(a.summary || '')}</div>
                    <div class="bookmark-card-meta">
                        <span class="article-card-cat" style="--cat-color:${color}"><span class="cat-dot"></span>${escapeHtml(a.category || '')}</span>
                        <span>${formatDateShort(a.published)}</span>
                    </div>
                </div>
                <button class="bookmark-star-btn" data-id="${escapeHtml(a.id || '')}" title="Remove bookmark">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                </button>
            </div>`;
        }
        if (bookmarksList) bookmarksList.innerHTML = html;

        if (bookmarksList) {
            const cards = bookmarksList.querySelectorAll('.bookmark-card');
            for (let j = 0; j < cards.length; j++) {
                cards[j].addEventListener('click', handleCardClick);
            }

            const starBtns = bookmarksList.querySelectorAll('.bookmark-star-btn');
            for (let k = 0; k < starBtns.length; k++) {
                starBtns[k].addEventListener('click', handleStarClick);
            }
        }
    }

    function handleCardClick(e) {
        if (e.target.closest('.bookmark-star-btn')) return;
        const card = e.currentTarget;
        const id = card.getAttribute('data-id');
        for (let i = 0; i < allArticles.length; i++) {
            if (allArticles[i].id === id) {
                openPanel(allArticles[i]);
                return;
            }
        }
    }

    function handleStarClick(e) {
        e.stopPropagation();
        const btn = e.currentTarget;
        const id = btn.getAttribute('data-id');

        let article = null;
        for (let i = 0; i < allArticles.length; i++) {
            if (allArticles[i].id === id) {
                article = allArticles[i];
                break;
            }
        }
        if (!article) return;

        toggleBookmark(article);
    }

    /* ── Bookmark Toggle ── */
    function toggleBookmark(article) {
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
            renderBookmarks();
        })
        .catch(() => {
            const idx = bookmarkedIds.indexOf(article.id);
            if (idx === -1) {
                bookmarkedIds.push(article.id);
            } else {
                bookmarkedIds.splice(idx, 1);
            }
            renderBookmarks();
        });
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

        updatePanelStar(panelStarBtn, true);

        const sidePanel = document.getElementById('side-panel');
        if (sidePanel) sidePanel.classList.add('open');
        const panelOverlay = document.getElementById('panel-overlay');
        if (panelOverlay) panelOverlay.classList.add('open');
    }

    function closePanel() {
        panelCurrentArticle = null;
        const sidePanel = document.getElementById('side-panel');
        if (sidePanel) sidePanel.classList.remove('open');
        const panelOverlay = document.getElementById('panel-overlay');
        if (panelOverlay) panelOverlay.classList.remove('open');
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

    function handlePanelStarClick() {
        if (!panelCurrentArticle) return;
        const article = panelCurrentArticle;
        toggleBookmark(article, () => {
            closePanel();
        });
    }

    if (panelStarBtn) {
        panelStarBtn.addEventListener('click', handlePanelStarClick);
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
    loadBookmarks();
})();
