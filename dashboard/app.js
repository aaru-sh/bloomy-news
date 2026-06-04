/* Bloomsberg News — Landing Page App */
(function () {
    'use strict';

    function escapeHtml(s) {
        var d = document.createElement('div');
        d.textContent = s || '';
        return d.innerHTML;
    }

    function safeUrl(url) {
        if (!url) return '#';
        var lower = url.toLowerCase().trim();
        if (lower.startsWith('http://') || lower.startsWith('https://')) {
            return url;
        }
        return '#';
    }

    function formatDateShort(iso) {
        if (!iso) return '';
        var date;
        if (typeof iso === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(iso)) {
            var parts = iso.split('-');
            date = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
        } else {
            date = new Date(iso);
        }
        if (isNaN(date.getTime())) return '';
        var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return months[date.getMonth()] + ' ' + date.getDate() + ', ' + date.getFullYear();
    }

    var catColor = {
        'LLM': '#8b5cf6',
        'Neural-Nets': '#06b6d4',
        'ML-Research': '#3b82f6',
        'AI-Applications': '#10b981',
        'Finance': '#f59e0b',
        'Cybersecurity': '#ef4444'
    };

    var catIcons = {
        'LLM': '🧠',
        'Neural-Nets': '🔬',
        'ML-Research': '📊',
        'AI-Applications': '🤖',
        'Finance': '💰',
        'Cybersecurity': '🔒'
    };

    var catLabels = {
        'LLM': 'LLM',
        'Neural-Nets': 'Neural Nets',
        'ML-Research': 'ML Research',
        'AI-Applications': 'AI Apps',
        'Finance': 'Finance',
        'Cybersecurity': 'Cyber'
    };

    var allArticles = [];
    var stats = {};
    var bookmarkedIds = [];
    var panelCurrentArticle = null;

    var categoryGrid = document.getElementById('category-grid');
    var articleGrid = document.getElementById('article-grid');
    var emptyState = document.getElementById('empty-state');
    var themeToggle = document.getElementById('theme-toggle');
    var loadingEl = document.getElementById('loading');
    var errorEl = document.getElementById('error-state');
    var panelStarBtn = document.getElementById('panel-star-btn');

    /* ── Theme ── */
    function safeStorageGet(key, fallback) {
        try { return localStorage.getItem(key) || fallback; } catch (e) { return fallback; }
    }
    function safeStorageSet(key, value) {
        try { localStorage.setItem(key, value); } catch (e) { /* private mode / quota */ }
    }
    function initTheme() {
        var saved = safeStorageGet('bloomsberg-theme', 'dark');
        document.documentElement.setAttribute('data-theme', saved);
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', function () {
            var current = document.documentElement.getAttribute('data-theme');
            var next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            safeStorageSet('bloomsberg-theme', next);
            themeToggle.setAttribute('aria-pressed', String(next === 'dark'));
        });
    }

    /* ── Data ── */
    function loadData() {
        if (loadingEl) loadingEl.style.display = 'flex';
        if (errorEl) errorEl.style.display = 'none';
        fetch('data/dashboard_data.json')
            .then(function (resp) {
                if (!resp.ok) throw new Error('Network response was not ok');
                return resp.json();
            })
            .then(function (data) {
                if (loadingEl) loadingEl.style.display = 'none';
                allArticles = data.articles || [];
                stats = data.stats || {};
                var updateTimeEl = document.getElementById('update-time');
                if (updateTimeEl) updateTimeEl.textContent = data.generated || '--';
                loadBookmarks();
            })
            .catch(function () {
                if (loadingEl) loadingEl.style.display = 'none';
                if (articleGrid) articleGrid.innerHTML = '';
                if (emptyState) emptyState.style.display = 'none';
                if (errorEl) {
                    errorEl.style.display = 'flex';
                    var retryBtn = errorEl.querySelector('.retry-btn');
                    if (retryBtn) retryBtn.addEventListener('click', loadData);
                }
            });
    }

    function loadBookmarks() {
        fetch('/api/bookmarks')
            .then(function (resp) { return resp.ok ? resp.json() : { bookmarks: [] }; })
            .then(function (data) {
                bookmarkedIds = data.bookmarks || [];
                renderCategoryGrid();
                renderArticles();
            })
            .catch(function () {
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
        .then(function (resp) {
            if (!resp.ok) throw new Error('Failed to toggle bookmark');
            return resp.json();
        })
        .then(function (data) {
            bookmarkedIds = data.bookmarks || [];
            if (onDone) onDone(true);
        })
        .catch(function () {
            var idx = bookmarkedIds.indexOf(article.id);
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
            var svg = btn.querySelector('svg');
            if (svg) svg.setAttribute('fill', 'currentColor');
        } else {
            btn.classList.remove('is-starred');
            btn.setAttribute('aria-pressed', 'false');
            btn.setAttribute('aria-label', 'Bookmark this article');
            btn.setAttribute('title', 'Bookmark this article');
            var svg = btn.querySelector('svg');
            if (svg) svg.setAttribute('fill', 'none');
        }
    }

    function updatePanelStar(btn, bookmarked) {
        if (!btn) return;
        if (bookmarked) {
            btn.classList.add('is-starred');
            btn.setAttribute('aria-pressed', 'true');
            btn.setAttribute('title', 'Remove bookmark');
            var svg = btn.querySelector('svg');
            if (svg) svg.setAttribute('fill', 'currentColor');
        } else {
            btn.classList.remove('is-starred');
            btn.setAttribute('aria-pressed', 'false');
            btn.setAttribute('title', 'Bookmark article');
            var svg = btn.querySelector('svg');
            if (svg) svg.setAttribute('fill', 'none');
        }
    }

    /* ── Category Grid ── */
    function renderCategoryGrid() {
        var cats = stats.categories || {};
        var categories = ['LLM', 'Neural-Nets', 'ML-Research', 'AI-Applications', 'Finance', 'Cybersecurity'];
        var sources = {};
        for (var i = 0; i < allArticles.length; i++) {
            if (allArticles[i].source) sources[allArticles[i].source] = true;
        }
        var sourceCountEl = document.getElementById('source-count');
        if (sourceCountEl) sourceCountEl.textContent = Object.keys(sources).length;

        var html = '';
        for (var j = 0; j < categories.length; j++) {
            var cat = categories[j];
            var count = cats[cat] || 0;
            html += '<div class="category-card" data-category="' + escapeHtml(cat) + '" style="--cat-color:' + (catColor[cat] || '#888') + '">' +
                '<span class="cat-icon">' + (catIcons[cat] || '📰') + '</span>' +
                '<div class="cat-name">' + escapeHtml(catLabels[cat] || cat) + '</div>' +
                '<div class="cat-count">' + count + '</div>' +
            '</div>';
        }
        if (categoryGrid) categoryGrid.innerHTML = html;

        if (categoryGrid) {
            var cards = categoryGrid.querySelectorAll('.category-card');
            for (var k = 0; k < cards.length; k++) {
                cards[k].addEventListener('click', function () {
                    var cat = this.getAttribute('data-category');
                    window.location.href = 'filters.html?category=' + encodeURIComponent(cat);
                });
            }
        }
    }

    /* ── Articles ── */
    function renderArticles() {
        var sorted = allArticles.slice().sort(function (a, b) {
            return new Date(b.published || 0) - new Date(a.published || 0);
        });

        var limit = Math.min(sorted.length, 12);
        if (limit === 0) {
            if (articleGrid) articleGrid.innerHTML = '';
            if (emptyState) emptyState.style.display = 'flex';
            return;
        }
        if (emptyState) emptyState.style.display = 'none';

        var html = '';
        for (var i = 0; i < limit; i++) {
            var a = sorted[i];
            var color = catColor[a.category] || '#888';
            var starred = isBookmarked(a.id);
            var starClass = 'article-card-star' + (starred ? ' is-starred' : '');
            var starFill = starred ? 'currentColor' : 'none';
            var starAriaPressed = starred ? 'true' : 'false';
            var starLabel = starred ? 'Remove bookmark' : 'Bookmark this article';
            var starTitle = starred ? 'Remove bookmark' : 'Bookmark this article';
            html += '<div class="article-card" data-id="' + escapeHtml(a.id || '') + '" style="--cat-color:' + color + '">' +
                '<button class="' + starClass + '" data-id="' + escapeHtml(a.id || '') + '" title="' + starTitle + '" aria-label="' + starLabel + '" aria-pressed="' + starAriaPressed + '">' +
                    '<svg width="16" height="16" viewBox="0 0 24 24" fill="' + starFill + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>' +
                '</button>' +
                '<div class="article-card-source">' + escapeHtml(a.source || '') + '</div>' +
                '<div class="article-card-title">' + escapeHtml(a.title || 'Untitled') + '</div>' +
                '<div class="article-card-summary">' + escapeHtml(a.summary || '') + '</div>' +
                '<div class="article-card-meta">' +
                    '<span class="article-card-cat"><span class="cat-dot"></span>' + escapeHtml(a.category || '') + '</span>' +
                    '<span class="article-card-date">' + formatDateShort(a.published) + '</span>' +
                '</div>' +
            '</div>';
        }
        if (articleGrid) articleGrid.innerHTML = html;

        if (articleGrid) {
            var cards = articleGrid.querySelectorAll('.article-card');
            for (var j = 0; j < cards.length; j++) {
                cards[j].addEventListener('click', handleCardClick);
            }

            var starBtns = articleGrid.querySelectorAll('.article-card-star');
            for (var k = 0; k < starBtns.length; k++) {
                starBtns[k].addEventListener('click', handleStarClick);
            }
        }
    }

    function handleStarClick(e) {
        e.stopPropagation();
        var btn = e.currentTarget;
        var id = btn.getAttribute('data-id');
        var article = findArticleById(id);
        if (!article) return;

        var wasStarred = isBookmarked(id);
        updateCardStar(btn, !wasStarred);

        toggleBookmark(article, function (success) {
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
        for (var i = 0; i < allArticles.length; i++) {
            if (allArticles[i].id === id) return allArticles[i];
        }
        return null;
    }

    function handleCardClick(e) {
        var card = e.currentTarget;
        var id = card.getAttribute('data-id');
        for (var i = 0; i < allArticles.length; i++) {
            if (allArticles[i].id === id) {
                openPanel(allArticles[i]);
                return;
            }
        }
    }

    /* ── Side Panel ── */
    function openPanel(a) {
        panelCurrentArticle = a;

        var catEl = document.getElementById('panel-category');
        if (catEl) {
            catEl.textContent = (a.category || '').toUpperCase();
            catEl.setAttribute('data-cat', a.category || '');
        }

        var panelTitle = document.getElementById('panel-title');
        if (panelTitle) panelTitle.textContent = a.title || 'Untitled';
        var panelSource = document.getElementById('panel-source');
        if (panelSource) panelSource.textContent = a.source || '';
        var panelDate = document.getElementById('panel-date');
        if (panelDate) panelDate.textContent = formatDateShort(a.published);

        var tagsEl = document.getElementById('panel-tags');
        var tags = a.tags || [];
        if (tagsEl) {
            if (tags.length > 0) {
                tagsEl.innerHTML = tags.map(function (t) {
                    return '<span class="panel-tag">' + escapeHtml(t) + '</span>';
                }).join('');
                tagsEl.style.display = 'flex';
            } else {
                tagsEl.innerHTML = '';
                tagsEl.style.display = 'none';
            }
        }

        var panelSummary = document.getElementById('panel-summary');
        if (panelSummary) panelSummary.textContent = a.summary || 'No summary available.';
        var panelLink = document.getElementById('panel-link');
        if (panelLink) panelLink.href = safeUrl(a.url);

        updatePanelStar(panelStarBtn, isBookmarked(a.id));

        var sidePanel = document.getElementById('side-panel');
        if (sidePanel) sidePanel.classList.add('open');
        var panelOverlay = document.getElementById('panel-overlay');
        if (panelOverlay) panelOverlay.classList.add('open');
    }

    function handlePanelStarClick() {
        if (!panelCurrentArticle) return;
        var article = panelCurrentArticle;
        var wasStarred = isBookmarked(article.id);
        updatePanelStar(panelStarBtn, !wasStarred);

        toggleBookmark(article, function (success) {
            if (success) {
                updatePanelStar(panelStarBtn, isBookmarked(article.id));
                var cardBtn = articleGrid.querySelector('.article-card-star[data-id="' + cssEscape(article.id) + '"]');
                if (cardBtn) updateCardStar(cardBtn, isBookmarked(article.id));
            } else {
                updatePanelStar(panelStarBtn, wasStarred);
            }
        });
    }

    function cssEscape(s) {
        if (window.CSS && CSS.escape) return CSS.escape(s);
        return String(s).replace(/[^a-zA-Z0-9_-]/g, function (c) {
            return '\\' + c;
        });
    }

    if (panelStarBtn) {
        panelStarBtn.addEventListener('click', handlePanelStarClick);
    }

    function closePanel() {
        var sidePanel = document.getElementById('side-panel');
        if (sidePanel) sidePanel.classList.remove('open');
        var panelOverlay = document.getElementById('panel-overlay');
        if (panelOverlay) panelOverlay.classList.remove('open');
    }

    var panelClose = document.getElementById('panel-close');
    if (panelClose) panelClose.addEventListener('click', closePanel);
    var panelOverlay = document.getElementById('panel-overlay');
    if (panelOverlay) panelOverlay.addEventListener('click', closePanel);

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closePanel();
    });

    /* ── Init ── */
    initTheme();
    loadData();
})();
