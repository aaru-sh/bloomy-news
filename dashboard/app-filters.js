/* Bloomy News — Filters Page App */
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

    let allArticles = [];
    let filteredArticles = [];
    let bookmarkedIds = [];
    let panelCurrentArticle = null;
    let selectedCategories = [];
    let selectedSources = [];
    let selectedDatePreset = 'all';
    let selectedCalendarDate = null;
    let calendarMonth, calendarYear;
    let searchTimeout = null;

    const searchEl = document.getElementById('search-input');
    const articleGrid = document.getElementById('article-grid');
    const emptyState = document.getElementById('empty-state');
    const resultsCountEl = document.getElementById('results-count');
    const activeFiltersEl = document.getElementById('active-filters');
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
                buildFilterMenus();
                applyUrlParams();
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
                filterArticles();
            })
            .catch(() => {
                bookmarkedIds = [];
                filterArticles();
            });
    }

    function isBookmarked(id) {
        return bookmarkedIds.indexOf(id) !== -1;
    }

    function findArticleById(id) {
        for (let i = 0; i < allArticles.length; i++) {
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

    function cssEscape(s) {
        if (window.CSS && CSS.escape) return CSS.escape(s);
        return String(s).replace(/[^a-zA-Z0-9_-]/g, (c) => `\\${c}`);
    }

    /* ── URL Params ── */
    function applyUrlParams() {
        const params = new URLSearchParams(window.location.search);
        const cat = params.get('category');
        if (cat) {
            selectedCategories = [cat];
        }
    }

    /* ── Filter Menus ── */
    function buildFilterMenus() {
        const categories = {};
        const sources = {};
        for (let i = 0; i < allArticles.length; i++) {
            if (allArticles[i].category) categories[allArticles[i].category] = true;
            if (allArticles[i].source) sources[allArticles[i].source] = true;
        }

        const catMenu = document.getElementById('filter-category-menu');
        const catKeys = Object.keys(categories).sort();
        let catHtml = '';
        for (let c = 0; c < catKeys.length; c++) {
            const checked = selectedCategories.indexOf(catKeys[c]) !== -1 ? 'checked' : '';
            catHtml += `<label class="filter-menu-item" data-cat="${escapeHtml(catKeys[c])}">
                <input type="checkbox" ${checked}> ${escapeHtml(catKeys[c])}
            </label>`;
        }
        if (catMenu) catMenu.innerHTML = catHtml;

        if (catMenu) {
            const catItems = catMenu.querySelectorAll('.filter-menu-item');
            for (let ci = 0; ci < catItems.length; ci++) {
                catItems[ci].addEventListener('change', handleCategoryChange);
            }
        }

        const srcMenu = document.getElementById('filter-source-menu');
        const srcKeys = Object.keys(sources).sort();
        let srcHtml = '';
        for (let s = 0; s < srcKeys.length; s++) {
            srcHtml += `<div class="filter-menu-item" data-source="${escapeHtml(srcKeys[s])}">${escapeHtml(srcKeys[s])}</div>`;
        }
        if (srcMenu) srcMenu.innerHTML = srcHtml;

        if (srcMenu) {
            const srcItems = srcMenu.querySelectorAll('.filter-menu-item');
            for (let si = 0; si < srcItems.length; si++) {
                srcItems[si].addEventListener('click', handleSourceClick);
            }
        }

        const dateItems = document.querySelectorAll('#filter-date-menu .filter-menu-item');
        for (let di = 0; di < dateItems.length; di++) {
            dateItems[di].addEventListener('click', handleDatePresetClick);
        }
    }

    /* ── Filter Dropdown Toggles ── */
    function setupDropdownToggle(btnId, menuId) {
        const btn = document.getElementById(btnId);
        const menu = document.getElementById(menuId);
        if (btn && menu) {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const isOpen = menu.classList.contains('open');
                closeAllMenus();
                if (!isOpen) menu.classList.add('open');
            });
        }
    }

    function closeAllMenus() {
        const menus = document.querySelectorAll('.filter-menu');
        for (let i = 0; i < menus.length; i++) menus[i].classList.remove('open');
    }

    document.addEventListener('click', closeAllMenus);

    setupDropdownToggle('filter-category-btn', 'filter-category-menu');
    setupDropdownToggle('filter-source-btn', 'filter-source-menu');
    setupDropdownToggle('filter-date-btn', 'filter-date-menu');

    /* ── Filter Handlers ── */
    function handleCategoryChange() {
        const catMenu = document.getElementById('filter-category-menu');
        if (!catMenu) return;
        const items = catMenu.querySelectorAll('.filter-menu-item');
        selectedCategories = [];
        for (let i = 0; i < items.length; i++) {
            if (items[i].querySelector('input').checked) {
                selectedCategories.push(items[i].getAttribute('data-cat'));
            }
        }
        filterArticles();
    }

    function handleSourceClick(e) {
        const item = e.currentTarget;
        const src = item.getAttribute('data-source');
        const idx = selectedSources.indexOf(src);
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
        const btn = document.getElementById('filter-source-btn');
        if (btn) {
            if (selectedSources.length > 0) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        }
    }

    function handleDatePresetClick(e) {
        const item = e.currentTarget;
        const dateVal = item.getAttribute('data-date');
        selectedDatePreset = dateVal;
        selectedCalendarDate = null;

        const items = document.querySelectorAll('#filter-date-menu .filter-menu-item');
        for (let i = 0; i < items.length; i++) items[i].classList.remove('selected');
        item.classList.add('selected');

        const btn = document.getElementById('filter-date-btn');
        if (btn) {
            if (dateVal !== 'all') {
                btn.classList.add('active');
                btn.childNodes[0].textContent = `Date: ${item.textContent.trim()} `;
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
        const now = new Date();
        calendarMonth = now.getMonth();
        calendarYear = now.getFullYear();
        renderCalendar();
    }

    function renderCalendar() {
        const months = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'];
        const calTitle = document.getElementById('cal-title');
        if (calTitle) calTitle.textContent = `${months[calendarMonth]} ${calendarYear}`;

        const grid = document.getElementById('calendar-grid');
        if (!grid) return;
        const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        let html = '';
        for (let d = 0; d < dayNames.length; d++) {
            html += `<div class="calendar-day-header">${dayNames[d]}</div>`;
        }

        const firstDay = new Date(calendarYear, calendarMonth, 1);
        const startDay = (firstDay.getDay() + 6) % 7;
        const daysInMonth = new Date(calendarYear, calendarMonth + 1, 0).getDate();
        const daysInPrev = new Date(calendarYear, calendarMonth, 0).getDate();

        const today = new Date();
        const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

        const articleDates = {};
        for (let i = 0; i < allArticles.length; i++) {
            const dObj = new Date(allArticles[i].published);
            if (isNaN(dObj.getTime())) continue;
            const key = `${dObj.getFullYear()}-${String(dObj.getMonth() + 1).padStart(2, '0')}-${String(dObj.getDate()).padStart(2, '0')}`;
            if (!articleDates[key]) articleDates[key] = {};
            const cat = allArticles[i].category;
            if (cat) articleDates[key][cat] = true;
        }

        for (let p = 0; p < startDay; p++) {
            const prevDay = daysInPrev - startDay + p + 1;
            html += `<div class="calendar-day other-month">${prevDay}</div>`;
        }

        for (let day = 1; day <= daysInMonth; day++) {
            const dateKey = `${calendarYear}-${String(calendarMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const isToday = dateKey === todayStr;
            const isSelected = selectedCalendarDate === dateKey;
            let classes = 'calendar-day';
            if (isToday) classes += ' today';
            if (isSelected) classes += ' selected';

            let dots = '';
            if (articleDates[dateKey]) {
                dots = '<div class="dot-row">';
                const cats = Object.keys(articleDates[dateKey]);
                for (let ci = 0; ci < cats.length; ci++) {
                    dots += `<span class="cat-dot" style="background:${catColor[cats[ci]] || '#888'}"></span>`;
                }
                dots += '</div>';
            }

            html += `<div class="${classes}" data-date="${dateKey}">${day}${dots}</div>`;
        }

        const totalCells = startDay + daysInMonth;
        const remaining = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
        for (let r = 0; r < remaining; r++) {
            html += `<div class="calendar-day other-month">${r + 1}</div>`;
        }

        grid.innerHTML = html;

        const dayEls = grid.querySelectorAll('.calendar-day:not(.other-month)');
        for (let de = 0; de < dayEls.length; de++) {
            dayEls[de].addEventListener('click', handleCalendarDayClick);
        }
    }

    function handleCalendarDayClick(e) {
        const el = e.currentTarget;
        const date = el.getAttribute('data-date');
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

    const calPrev = document.getElementById('cal-prev');
    if (calPrev) {
        calPrev.addEventListener('click', () => {
            calendarMonth--;
            if (calendarMonth < 0) { calendarMonth = 11; calendarYear--; }
            renderCalendar();
        });
    }

    const calNext = document.getElementById('cal-next');
    if (calNext) {
        calNext.addEventListener('click', () => {
            calendarMonth++;
            if (calendarMonth > 11) { calendarMonth = 0; calendarYear++; }
            renderCalendar();
        });
    }

    const calToday = document.getElementById('cal-today');
    if (calToday) {
        calToday.addEventListener('click', () => {
            const now = new Date();
            calendarMonth = now.getMonth();
            calendarYear = now.getFullYear();
            selectedDatePreset = 'today';
            selectedCalendarDate = null;
            renderCalendar();
            filterArticles();
        });
    }

    const calWeek = document.getElementById('cal-week');
    if (calWeek) {
        calWeek.addEventListener('click', () => {
            selectedDatePreset = '7d';
            selectedCalendarDate = null;
            renderCalendar();
            filterArticles();
        });
    }

    /* ── Search ── */
    if (searchEl) {
        searchEl.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(filterArticles, 300);
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === '/' && document.activeElement !== searchEl) {
            e.preventDefault();
            if (searchEl) searchEl.focus();
        }
        if (e.key === 'Escape') closePanel();
    });

    /* ── Filter Logic ── */
    function filterArticles() {
        const query = (searchEl ? searchEl.value : '').toLowerCase();
        const now = new Date();

        filteredArticles = allArticles.filter((a) => {
            if (selectedCategories.length > 0 && selectedCategories.indexOf(a.category) === -1) return false;
            if (selectedSources.length > 0 && selectedSources.indexOf(a.source) === -1) return false;

            if (selectedCalendarDate) {
                const d = new Date(a.published);
                if (isNaN(d.getTime())) return false;
                const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
                if (key !== selectedCalendarDate) return false;
            } else if (selectedDatePreset !== 'all') {
                const d2 = new Date(a.published);
                if (isNaN(d2.getTime())) return false;
                let cutoff = new Date(0);
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
                const hay = ((a.title || '') + ' ' + (a.summary || '') + ' ' + (a.source || '') + ' ' + (a.tags || []).join(' ')).toLowerCase();
                if (hay.indexOf(query) === -1) return false;
            }

            return true;
        });

        filteredArticles.sort((a, b) => new Date(b.published || 0) - new Date(a.published || 0));

        renderActiveFilters();
        renderArticles();
    }

    /* ── Active Filters ── */
    function renderActiveFilters() {
        let html = '';
        for (let c = 0; c < selectedCategories.length; c++) {
            html += `<span class="filter-chip">${escapeHtml(selectedCategories[c])}
                <button class="filter-chip-remove" data-type="category" data-value="${escapeHtml(selectedCategories[c])}">&times;</button></span>`;
        }
        for (let s = 0; s < selectedSources.length; s++) {
            html += `<span class="filter-chip">${escapeHtml(selectedSources[s])}
                <button class="filter-chip-remove" data-type="source" data-value="${escapeHtml(selectedSources[s])}">&times;</button></span>`;
        }
        if (selectedCalendarDate) {
            html += `<span class="filter-chip">${escapeHtml(selectedCalendarDate)}
                <button class="filter-chip-remove" data-type="date">&times;</button></span>`;
        } else if (selectedDatePreset !== 'all') {
            const label = selectedDatePreset === 'today' ? 'Today' : selectedDatePreset === '7d' ? '7 Days' : selectedDatePreset === '30d' ? '30 Days' : '';
            if (label) {
                html += `<span class="filter-chip">${label}
                    <button class="filter-chip-remove" data-type="date-preset">&times;</button></span>`;
            }
        }
        if (html) {
            html += '<button class="clear-all-btn" id="clear-all-filters">Clear All</button>';
        }
        if (activeFiltersEl) activeFiltersEl.innerHTML = html;

        if (activeFiltersEl) {
            const removeBtns = activeFiltersEl.querySelectorAll('.filter-chip-remove');
            for (let r = 0; r < removeBtns.length; r++) {
                removeBtns[r].addEventListener('click', handleRemoveFilter);
            }
        }

        const clearBtn = document.getElementById('clear-all-filters');
        if (clearBtn) {
            clearBtn.addEventListener('click', clearAllFilters);
        }
    }

    function handleRemoveFilter(e) {
        const btn = e.currentTarget;
        const type = btn.getAttribute('data-type');
        const value = btn.getAttribute('data-value');
        if (type === 'category') {
            selectedCategories = selectedCategories.filter((c) => c !== value);
            const catMenu = document.getElementById('filter-category-menu');
            if (catMenu) {
                const catItems = catMenu.querySelectorAll('.filter-menu-item');
                for (let i = 0; i < catItems.length; i++) {
                    if (catItems[i].getAttribute('data-cat') === value) {
                        catItems[i].querySelector('input').checked = false;
                    }
                }
            }
        } else if (type === 'source') {
            selectedSources = selectedSources.filter((s) => s !== value);
            const srcMenu = document.getElementById('filter-source-menu');
            if (srcMenu) {
                const srcItems = srcMenu.querySelectorAll('.filter-menu-item');
                for (let j = 0; j < srcItems.length; j++) {
                    if (srcItems[j].getAttribute('data-source') === value) {
                        srcItems[j].classList.remove('selected');
                    }
                }
            }
            updateSourceBtnState();
        } else if (type === 'date' || type === 'date-preset') {
            selectedCalendarDate = null;
            selectedDatePreset = 'all';
            const dateItems = document.querySelectorAll('#filter-date-menu .filter-menu-item');
            for (let k = 0; k < dateItems.length; k++) dateItems[k].classList.remove('selected');
            const dateBtn = document.getElementById('filter-date-btn');
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

        const catMenu = document.getElementById('filter-category-menu');
        if (catMenu) {
            const catItems = catMenu.querySelectorAll('.filter-menu-item input');
            for (let i = 0; i < catItems.length; i++) catItems[i].checked = false;
        }

        const srcMenu = document.getElementById('filter-source-menu');
        if (srcMenu) {
            const srcItems = srcMenu.querySelectorAll('.filter-menu-item');
            for (let j = 0; j < srcItems.length; j++) srcItems[j].classList.remove('selected');
        }
        updateSourceBtnState();

        const dateItems = document.querySelectorAll('#filter-date-menu .filter-menu-item');
        for (let k = 0; k < dateItems.length; k++) dateItems[k].classList.remove('selected');
        const dateBtn = document.getElementById('filter-date-btn');
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

        const limit = Math.min(filteredArticles.length, 300);
        let html = '';
        for (let i = 0; i < limit; i++) {
            const a = filteredArticles[i];
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

    function closePanel() {
        panelCurrentArticle = null;
        const sidePanel = document.getElementById('side-panel');
        if (sidePanel) sidePanel.classList.remove('open');
        const panelOverlay = document.getElementById('panel-overlay');
        if (panelOverlay) panelOverlay.classList.remove('open');
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

    if (panelStarBtn) {
        panelStarBtn.addEventListener('click', handlePanelStarClick);
    }

    const panelClose = document.getElementById('panel-close');
    if (panelClose) panelClose.addEventListener('click', closePanel);
    const panelOverlay = document.getElementById('panel-overlay');
    if (panelOverlay) panelOverlay.addEventListener('click', closePanel);

    /* ── Init ── */
    initTheme();
    initCalendar();
    loadData();
})();
