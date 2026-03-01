/* STOKS — Table Sorting, Filtering & Search */
(function() {
    'use strict';

    // Table sorting
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const table = th.closest('table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const col = th.dataset.sort;
            const type = th.dataset.type || 'string';
            const currentDir = th.classList.contains('sort-asc') ? 'desc' : 'asc';

            // Clear all sort indicators
            table.querySelectorAll('th').forEach(t => t.classList.remove('sort-asc', 'sort-desc'));
            th.classList.add('sort-' + currentDir);

            rows.sort((a, b) => {
                let aVal = a.querySelector(`td[data-col="${col}"]`)?.dataset.value || '';
                let bVal = b.querySelector(`td[data-col="${col}"]`)?.dataset.value || '';

                if (type === 'number') {
                    aVal = parseFloat(aVal) || 0;
                    bVal = parseFloat(bVal) || 0;
                } else {
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }

                if (aVal < bVal) return currentDir === 'asc' ? -1 : 1;
                if (aVal > bVal) return currentDir === 'asc' ? 1 : -1;
                return 0;
            });

            rows.forEach(row => tbody.appendChild(row));
        });
    });

    // Search
    const searchBox = document.getElementById('search-box');
    if (searchBox) {
        searchBox.addEventListener('input', filterTable);
    }

    // Sector filter
    const sectorFilter = document.getElementById('sector-filter');
    if (sectorFilter) {
        sectorFilter.addEventListener('change', filterTable);
    }

    // Signal filter
    const signalFilter = document.getElementById('signal-filter');
    if (signalFilter) {
        signalFilter.addEventListener('change', filterTable);
    }

    function filterTable() {
        const search = (searchBox?.value || '').toLowerCase();
        const sector = sectorFilter?.value || '';
        const signal = signalFilter?.value || '';

        document.querySelectorAll('#candidates-table tbody tr').forEach(row => {
            const ticker = row.dataset.ticker?.toLowerCase() || '';
            const name = row.dataset.name?.toLowerCase() || '';
            const rowSector = row.dataset.sector || '';
            const rowSignal = row.dataset.signal || '';

            const matchSearch = !search || ticker.includes(search) || name.includes(search);
            const matchSector = !sector || rowSector === sector;
            const matchSignal = !signal || rowSignal === signal;

            row.style.display = (matchSearch && matchSector && matchSignal) ? '' : 'none';
        });
    }

    // Tab switching for rejected/errors
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            document.getElementById(target)?.classList.add('active');
        });
    });
})();

/* Glossary Help Popup */
(function() {
    'use strict';
    const overlay = document.getElementById('glossary-overlay');
    if (!overlay) return;
    const modal = overlay.querySelector('.glossary-modal');
    const titleEl = modal?.querySelector('.gm-title');
    const explEl = modal?.querySelector('.gm-expl');
    const grahamEl = modal?.querySelector('.gm-graham-text');
    const closeBtn = modal?.querySelector('.gm-close');

    document.addEventListener('click', e => {
        const icon = e.target.closest('.help-icon');
        if (!icon) return;
        e.stopPropagation();
        const t = icon.dataset.glossTitle || '';
        const ex = icon.dataset.glossExpl || '';
        const gr = icon.dataset.glossGraham || '';
        if (titleEl) titleEl.textContent = t;
        if (explEl) explEl.textContent = ex;
        if (grahamEl) grahamEl.textContent = gr;
        overlay.classList.add('active');
    });

    if (closeBtn) closeBtn.addEventListener('click', () => overlay.classList.remove('active'));
    overlay.addEventListener('click', e => {
        if (e.target === overlay) overlay.classList.remove('active');
    });
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') overlay.classList.remove('active');
    });
})();
