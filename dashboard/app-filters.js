/* Bloomy News — Filters Page App */
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

    var allArticles = [];
    var filteredArticles = [];
    var bookmarkedIds = [];
    var panelCurrentArticle = null;
    var selectedCategories = [];
    var selectedSources = [];
    var selectedDatePreset = 'all';
    var selectedCalendarDate = null;
    var calendarMonth, calendarYear;
    var searchTimeout = null;

    var searchEl = document.getElementById('search-input');
    var articleGrid = document.getElementById('article-grid');
    var emptyState = document.getElementById('empty-state');
    var resultsCountEl = document.getElementById('results-count');
    var activeFiltersEl = document.getElementById('active-filters');
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
        var saved = safeStorageGet('Bloomy-theme', 'dark');
        document.documentElement.setAttribute('data-theme', saved);
    }
    if (themeToggle) {
        themeToggle.addEventListener('click', function () {
            var current = document.documentElement.getAttribute('data-theme');
            var next = current === 'dark' ? 'light' : 'dark';
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
            .then(function (resp) {
                if (!resp.ok) throw new Error('Network response was not ok');
                return resp.json();
            })
            .then(function (data) {
                if (loadingEl) loadingEl.style.display = 'none';
                allArticles = data.articles || [];
                buildFilterMenus();
                applyUrlParams();
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
                filterArticles();
            })
            .catch(function () {
                bookmarkedIds = [];
                filterArticles();
            });
    }

    function isBookmarked(id) {
        return bookmarkedIds.indexOf(id) !== -1;
    }

    function findArticleById(id) {
        for (var i = 0; i < allArticles.length; i++) {
            if (allArticles[i].id === id) return allArticles[i];
        }
        return null;
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

    function cssEscape(s) {
        if (window.CSS && CSS.escape) return CSS.escape(s);
        return String(s).replace(/[^a-zA-Z0-9_-]/g, function (c) {
            return '\\' + c;
        });
    }

    /* ── URL Params ── */
    function applyUrlParams() {
        var params = new URLSearchParams(window.location.search);
        var cat = params.get('category');
        if (cat) {
            selectedCategories = [cat];
        }
    }

    /* ── Filter Menus ── */
    function buildFilterMenus() {
        var categories = {};
        var sources = {};
        for (var i = 0; i < allArticles.length; i++) {
            if (allArticles[i].category) categories[allArticles[i].category] = true;
            if (allArticles[i].source) sources[allArticles[i].source] = true;
        }

        var catMenu = document.getElementById('filter-category-menu');
        var catKeys = Object.keys(categories).sort();
        var catHtml = '';
        for (var c = 0; c < catKeys.length; c++) {
            var checked = selectedCategories.indexOf(catKeys[c]) !== -1 ? 'checked' : '';
            catHtml += '<label class="filter-menu-item" data-cat="' + escapeHtml(catKeys[c]) + '">' +
                '<input type="checkbox" ' + checked + '> ' + escapeHtml(catKeys[c]) +
            '</label>';
        }
        if (catMenu) catMenu.innerHTML = catHtml;

        if (catMenu) {
            var catItems = catMenu.querySelectorAll('.filter-menu-item');
            for (var ci = 0; ci < catItems.length; ci++) {
                catItems[ci].addEventListener('change', handleCategoryChange);
            }
        }

        var srcMenu = document.getElementById('filter-source-menu');
        var srcKeys = Object.keys(sources).sort();
        var srcHtml = '';
        for (var s = 0; s < srcKeys.length; s++) {
            srcHtml += '<div class="filter-menu-item" data-source="' + escapeHtml(srcKeys[s]) + '">' + escapeHtml(srcKeys[s]) + '</div>';
        }
        if (srcMenu) srcMenu.innerHTML = srcHtml;

        if (srcMenu) {
            var srcItems = srcMenu.querySelectorAll('.filter-menu-item');
            for (var si = 0; si < srcItems.length; si++) {
                srcItems[si].addEventListener('click', handleSourceClick);
            }
        }

        var dateItems = document.querySelectorAll('#filter-date-menu .filter-menu-item');
        for (var di = 0; di < dateItems.length; di++) {
            dateItems[di].addEventListener('click', handleDatePresetClick);
        }
    }

    /* ── Filter Dropdown Toggles ── */
    function setupDropdownToggle(btnId, menuId) {
        var btn = document.getElementById(btnId);
        var menu = document.getElementById(menuId);
        if (btn && menu) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var isOpen = menu.classList.contains('open');
                closeAllMenus();
                if (!isOpen) menu.classList.add('open');
            });
        }
    }

    function closeAllMenus() {
        var menus = document.querySelectorAll('.filter-menu');
        for (var i = 0; i < menus.length; i++) menus[i].classList.remove('open');
    }

    document.addEventListener('click', closeAllMenus);

    setupDropdownToggle('filter-category-btn', 'filter-category-menu');
    setupDropdownToggle('filter-source-btn', 'filter-source-menu');
    setupDropdownToggle('filter-date-btn', 'filter-date-menu');

    /* ── Filter Handlers ── */
    function handleCategoryChange() {
        var catMenu = document.getElementById('filter-category-menu');
        if (!catMenu) return;
        var items = catMenu.querySelectorAll('.filter-menu-item');
        selectedCategories = [];
        for (var i = 0; i < items.length; i++) {
            if (items[i].querySelector('input').checked) {
                selectedCategories.push(items[i].getAttribute('data-cat'));
            }
        }
        filterArticles();
    }

    function handleSourceClick(e) {
        var item = e.currentTarget;
        var src = item.getAttribute('data-source');
        var idx = selectedSources.indexOf(src);
        if (idx === -1) {
            selectedSources.push(src);
            item.classList.add('selected');
        } else {
            selectedSources.splice(idx, 1);
            item.classList.remove('selected');
        }
        updateSourceBtnState();
        filterArticles();
    }

    function updateSourceBtnState() {
        var btn = document.getElementById('filter-source-btn');
        if (btn) {
            if (selectedSources.length > 0) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        }
    }

    function handleDatePresetClick(e) {
        var item = e.currentTarget;
        var dateVal = item.getAttribute('data-date');
        selectedDatePreset = dateVal;
        selectedCalendarDate = null;

        var items = document.querySelectorAll('#filter-date-menu .filter-menu-item');
        for (var i = 0; i < items.length; i++) items[i].classList.remove('selected');
        item.classList.add('selected');

        var btn = document.getElementById('filter-date-btn');
        if (btn) {
            if (dateVal !== 'all') {
                btn.classList.add('active');
                btn.childNodes[0].textContent = 'Date: ' + item.textContent.trim() + ' ';
            } else {
                btn.classList.remove('active');
                btn.childNodes[0].textContent = 'Date ';
            }
        }

        renderCalendar();
        filterArticles();
    }

    /* ── Calendar ── */
    function initCalendar() {
        var now = new Date();
        calendarMonth = now.getMonth();
        calendarYear = now.getFullYear();
        renderCalendar();
    }

    function renderCalendar() {
        var months = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'];
        var calTitle = document.getElementById('cal-title');
        if (calTitle) calTitle.textContent = months[calendarMonth] + ' ' + calendarYear;

        var grid = document.getElementById('calendar-grid');
        if (!grid) return;
        var dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        var html = '';
        for (var d = 0; d < dayNames.length; d++) {
            html += '<div class="calendar-day-header">' + dayNames[d] + '</div>';
        }

        var firstDay = new Date(calendarYear, calendarMonth, 1);
        var startDay = (firstDay.getDay() + 6) % 7;
        var daysInMonth = new Date(calendarYear, calendarMonth + 1, 0).getDate();
        var daysInPrev = new Date(calendarYear, calendarMonth, 0).getDate();

        var today = new Date();
        var todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');

        var articleDates = {};
        for (var i = 0; i < allArticles.length; i++) {
            var dObj = new Date(allArticles[i].published);
            if (isNaN(dObj.getTime())) continue;
            var key = dObj.getFullYear() + '-' + String(dObj.getMonth() + 1).padStart(2, '0') + '-' + String(dObj.getDate()).padStart(2, '0');
            if (!articleDates[key]) articleDates[key] = {};
            var cat = allArticles[i].category;
            if (cat) articleDates[key][cat] = true;
        }

        for (var p = 0; p < startDay; p++) {
            var prevDay = daysInPrev - startDay + p + 1;
            html += '<div class="calendar-day other-month">' + prevDay + '</div>';
        }

        for (var day = 1; day <= daysInMonth; day++) {
            var dateKey = calendarYear + '-' + String(calendarMonth + 1).padStart(2, '0') + '-' + String(day).padStart(2, '0');
            var isToday = dateKey === todayStr;
            var isSelected = selectedCalendarDate === dateKey;
            var classes = 'calendar-day';
            if (isToday) classes += ' today';
            if (isSelected) classes += ' selected';

            var dots = '';
            if (articleDates[dateKey]) {
                dots = '<div class="dot-row">';
                var cats = Object.keys(articleDates[dateKey]);
                for (var ci = 0; ci < cats.length; ci++) {
                    dots += '<span class="cat-dot" style="background:' + (catColor[cats[ci]] || '#888') + '"></span>';
                }
                dots += '</div>';
            }

            html += '<div class="' + classes + '" data-date="' + dateKey + '">' + day + dots + '</div>';
        }

        var totalCells = startDay + daysInMonth;
        var remaining = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
        for (var r = 0; r < remaining; r++) {
            html += '<div class="calendar-day other-month">' + (r + 1) + '</div>';
        }

        grid.innerHTML = html;

        var dayEls = grid.querySelectorAll('.calendar-day:not(.other-month)');
        for (var de = 0; de < dayEls.length; de++) {
            dayEls[de].addEventListener('click', handleCalendarDayClick);
        }
    }

    function handleCalendarDayClick(e) {
        var el = e.currentTarget;
        var date = el.getAttribute('data-date');
        if (selectedCalendarDate === date) {
            selectedCalendarDate = null;
            selectedDatePreset = 'all';
        } else {
            selectedCalendarDate = date;
            selectedDatePreset = 'custom';
        }
        renderCalendar();
        filterArticles();
    }

    var calPrev = document.getElementById('cal-prev');
    if (calPrev) {
        calPrev.addEventListener('click', function () {
            calendarMonth--;
            if (calendarMonth < 0) { calendarMonth = 11; calendarYear--; }
            renderCalendar();
        });
    }

    var calNext = document.getElementById('cal-next');
    if (calNext) {
        calNext.addEventListener('click', function () {
            calendarMonth++;
            if (calendarMonth > 11) { calendarMonth = 0; calendarYear++; }
            renderCalendar();
        });
    }

    var calToday = document.getElementById('cal-today');
    if (calToday) {
        calToday.addEventListener('click', function () {
            var now = new Date();
            calendarMonth = now.getMonth();
            calendarYear = now.getFullYear();
            selectedDatePreset = 'today';
            selectedCalendarDate = null;
            renderCalendar();
            filterArticles();
        });
    }

    var calWeek = document.getElementById('cal-week');
    if (calWeek) {
        calWeek.addEventListener('click', function () {
            selectedDatePreset = '7d';
            selectedCalendarDate = null;
            renderCalendar();
            filterArticles();
        });
    }

    /* ── Search ── */
    if (searchEl) {
        searchEl.addEventListener('input', function () {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(filterArticles, 300);
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === '/' && document.activeElement !== searchEl) {
            e.preventDefault();
            if (searchEl) searchEl.focus();
        }
        if (e.key === 'Escape') closePanel();
    });

    /* ── Filter Logic ── */
    function filterArticles() {
        var query = (searchEl ? searchEl.value : '').toLowerCase();
        var now = new Date();

        filteredArticles = allArticles.filter(function (a) {
            if (selectedCategories.length > 0 && selectedCategories.indexOf(a.category) === -1) return false;
            if (selectedSources.length > 0 && selectedSources.indexOf(a.source) === -1) return false;

            if (selectedCalendarDate) {
                var d = new Date(a.published);
                if (isNaN(d.getTime())) return false;
                var key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
                if (key !== selectedCalendarDate) return false;
            } else if (selectedDatePreset !== 'all') {
                var d2 = new Date(a.published);
                if (isNaN(d2.getTime())) return false;
                var cutoff = new Date(0);
                if (selectedDatePreset === 'today') {
                    cutoff = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                } else if (selectedDatePreset === '7d') {
                    cutoff = new Date(now - 7 * 86400000);
                } else if (selectedDatePreset === '30d') {
                    cutoff = new Date(now - 30 * 86400000);
                }
                if (d2 < cutoff) return false;
            }

            if (query) {
                var hay = ((a.title || '') + ' ' + (a.summary || '') + ' ' + (a.source || '') + ' ' + (a.tags || []).join(' ')).toLowerCase();
                if (hay.indexOf(query) === -1) return false;
            }

            return true;
        });

        filteredArticles.sort(function (a, b) {
            return new Date(b.published || 0) - new Date(a.published || 0);
        });

        renderActiveFilters();
        renderArticles();
    }

    /* ── Active Filters ── */
    function renderActiveFilters() {
        var html = '';
        for (var c = 0; c < selectedCategories.length; c++) {
            html += '<span class="filter-chip">' + escapeHtml(selectedCategories[c]) +
                '<button class="filter-chip-remove" data-type="category" data-value="' + escapeHtml(selectedCategories[c]) + '">&times;</button></span>';
        }
        for (var s = 0; s < selectedSources.length; s++) {
            html += '<span class="filter-chip">' + escapeHtml(selectedSources[s]) +
                '<button class="filter-chip-remove" data-type="source" data-value="' + escapeHtml(selectedSources[s]) + '">&times;</button></span>';
        }
        if (selectedCalendarDate) {
            html += '<span class="filter-chip">' + escapeHtml(selectedCalendarDate) +
                '<button class="filter-chip-remove" data-type="date">&times;</button></span>';
        } else if (selectedDatePreset !== 'all') {
            var label = selectedDatePreset === 'today' ? 'Today' : selectedDatePreset === '7d' ? '7 Days' : selectedDatePreset === '30d' ? '30 Days' : '';
            if (label) {
                html += '<span class="filter-chip">' + label +
                    '<button class="filter-chip-remove" data-type="date-preset">&times;</button></span>';
            }
        }
        if (html) {
            html += '<button class="clear-all-btn" id="clear-all-filters">Clear All</button>';
        }
        if (activeFiltersEl) activeFiltersEl.innerHTML = html;

        if (activeFiltersEl) {
            var removeBtns = activeFiltersEl.querySelectorAll('.filter-chip-remove');
            for (var r = 0; r < removeBtns.length; r++) {
                removeBtns[r].addEventListener('click', handleRemoveFilter);
            }
        }

        var clearBtn = document.getElementById('clear-all-filters');
        if (clearBtn) {
            clearBtn.addEventListener('click', clearAllFilters);
        }
    }

    function handleRemoveFilter(e) {
        var btn = e.currentTarget;
        var type = btn.getAttribute('data-type');
        var value = btn.getAttribute('data-value');
        if (type === 'category') {
            selectedCategories = selectedCategories.filter(function (c) { return c !== value; });
            var catMenu = document.getElementById('filter-category-menu');
            if (catMenu) {
                var catItems = catMenu.querySelectorAll('.filter-menu-item');
                for (var i = 0; i < catItems.length; i++) {
                    if (catItems[i].getAttribute('data-cat') === value) {
                        catItems[i].querySelector('input').checked = false;
                    }
                }
            }
        } else if (type === 'source') {
            selectedSources = selectedSources.filter(function (s) { return s !== value; });
            var srcMenu = document.getElementById('filter-source-menu');
            if (srcMenu) {
                var srcItems = srcMenu.querySelectorAll('.filter-menu-item');
                for (var j = 0; j < srcItems.length; j++) {
                    if (srcItems[j].getAttribute('data-source') === value) {
                        srcItems[j].classList.remove('selected');
                    }
                }
            }
            updateSourceBtnState();
        } else if (type === 'date' || type === 'date-preset') {
            selectedCalendarDate = null;
            selectedDatePreset = 'all';
            var dateItems = document.querySelectorAll('#filter-date-menu .filter-menu-item');
            for (var k = 0; k < dateItems.length; k++) dateItems[k].classList.remove('selected');
            var dateBtn = document.getElementById('filter-date-btn');
            if (dateBtn) {
                dateBtn.classList.remove('active');
                dateBtn.childNodes[0].textContent = 'Date ';
            }
            renderCalendar();
        }
        filterArticles();
    }

    function clearAllFilters() {
        selectedCategories = [];
        selectedSources = [];
        selectedDatePreset = 'all';
        selectedCalendarDate = null;
        if (searchEl) searchEl.value = '';

        var catMenu = document.getElementById('filter-category-menu');
        if (catMenu) {
            var catItems = catMenu.querySelectorAll('.filter-menu-item input');
            for (var i = 0; i < catItems.length; i++) catItems[i].checked = false;
        }

        var srcMenu = document.getElementById('filter-source-menu');
        if (srcMenu) {
            var srcItems = srcMenu.querySelectorAll('.filter-menu-item');
            for (var j = 0; j < srcItems.length; j++) srcItems[j].classList.remove('selected');
        }
        updateSourceBtnState();

        var dateItems = document.querySelectorAll('#filter-date-menu .filter-menu-item');
        for (var k = 0; k < dateItems.length; k++) dateItems[k].classList.remove('selected');
        var dateBtn = document.getElementById('filter-date-btn');
        if (dateBtn) {
            dateBtn.classList.remove('active');
            dateBtn.childNodes[0].textContent = 'Date ';
        }

        renderCalendar();
        filterArticles();
    }

    /* ── Render Articles ── */
    function renderArticles() {
        if (resultsCountEl) resultsCountEl.textContent = filteredArticles.length;

        if (filteredArticles.length === 0) {
            if (articleGrid) articleGrid.innerHTML = '';
            if (emptyState) emptyState.style.display = 'flex';
            return;
        }
        if (emptyState) emptyState.style.display = 'none';

        var limit = Math.min(filteredArticles.length, 300);
        var html = '';
        for (var i = 0; i < limit; i++) {
            var a = filteredArticles[i];
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

    function closePanel() {
        panelCurrentArticle = null;
        var sidePanel = document.getElementById('side-panel');
        if (sidePanel) sidePanel.classList.remove('open');
        var panelOverlay = document.getElementById('panel-overlay');
        if (panelOverlay) panelOverlay.classList.remove('open');
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

    if (panelStarBtn) {
        panelStarBtn.addEventListener('click', handlePanelStarClick);
    }

    var panelClose = document.getElementById('panel-close');
    if (panelClose) panelClose.addEventListener('click', closePanel);
    var panelOverlay = document.getElementById('panel-overlay');
    if (panelOverlay) panelOverlay.addEventListener('click', closePanel);

    /* ── Init ── */
    initTheme();
    initCalendar();
    loadData();
})();
