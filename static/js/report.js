/**
 * REPORT.JS - Event handlers extracted from report.html
 * Binds onclick handlers to elements using addEventListener
 */

// Initialize all event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    
    // ===== Action Pills (Top Bar) =====
    const shareLinkBtn = document.getElementById('share-link-btn');
    if (shareLinkBtn) {
        shareLinkBtn.addEventListener('click', copyShareLink);
    }

    const pdfBtn = document.querySelector('.pill-pdf');
    if (pdfBtn) {
        pdfBtn.addEventListener('click', downloadPDF);
    }

    const retestBtn = document.querySelector('.pill-schedule');
    if (retestBtn) {
        retestBtn.addEventListener('click', function() {
            window.location.href = '/';
        });
    }

    // ===== Executive Metrics Cards =====
    const metricCards = document.querySelectorAll('.exec-metric-card');
    metricCards.forEach(card => {
        if (card.dataset.scroll === 'all' || card.classList.contains('metric-all')) {
            card.addEventListener('click', function() { scrollToResults('all'); });
        } else if (card.dataset.scroll === 'failed' || card.classList.contains('metric-failed')) {
            card.addEventListener('click', function() { scrollToResults('failed'); });
        } else if (card.dataset.scroll === 'passed' || card.classList.contains('metric-passed')) {
            card.addEventListener('click', function() { scrollToResults('passed'); });
        }
    });

    // ===== Performance Tabs =====
    const mobileTabBtn = document.getElementById('tab-mobile');
    if (mobileTabBtn) {
        mobileTabBtn.addEventListener('click', function() { switchPerfTab('mobile'); });
    }

    const desktopTabBtn = document.getElementById('tab-desktop');
    if (desktopTabBtn) {
        desktopTabBtn.addEventListener('click', function() { switchPerfTab('desktop'); });
    }

    // ===== Filter Form =====
    const filterForm = document.querySelector('form[data-filter-form]');
    if (filterForm) {
        filterForm.addEventListener('submit', function(e) {
            e.preventDefault();
            return false;
        });
    }

    // ===== Status Filter Buttons =====
    const statusFilterBtns = document.querySelectorAll('.filter-btn');
    statusFilterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const filterValue = this.dataset.filter || 'all';
            filterResults(filterValue, this);
        });
    });

    // ===== Module Filter Buttons =====
    const moduleFilterBtns = document.querySelectorAll('.module-btn');
    moduleFilterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const moduleValue = this.dataset.module || 'all';
            filterModule(moduleValue, this);
        });
    });

    // ===== Result Rows (Clickable Detail Toggle) =====
    const resultRows = document.querySelectorAll('.result-row');
    resultRows.forEach(row => {
        row.addEventListener('click', function() {
            toggleResultDetail(this);
        });
    });

    // ===== Show All Results Toggle =====
    const showAllToggleBtn = document.getElementById('show-all-toggle-btn');
    if (showAllToggleBtn) {
        showAllToggleBtn.addEventListener('click', function() {
            toggleShowAllResults(this);
        });
    }

    // ===== Custom AI Query Button =====
    const customAIBtn = document.getElementById('custom-ai-btn');
    if (customAIBtn) {
        customAIBtn.addEventListener('click', runCustomAIQuery);
    }

    // ===== AI Results Toggle =====
    const aiToggleBtn = document.getElementById('ai-toggle-btn');
    if (aiToggleBtn) {
        aiToggleBtn.addEventListener('click', toggleAIResults);
    }

    // ===== TOC Navigation Links =====
    const tocLinks = document.querySelectorAll('.toc-link');
    tocLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const section = this.dataset.section;
            const target = document.getElementById(section);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
                updateActiveTocLink(section);
            }
        });
    });

});

// ===== Event Handler Functions =====
// These functions are likely defined elsewhere in base.html or external scripts.
// We only bind them here via addEventListener.

function copyShareLink() {
    // Function implementation should exist in the page
    if (typeof window.copyShareLink === 'function') {
        window.copyShareLink();
    }
}

function downloadPDF() {
    // Function implementation should exist in the page
    if (typeof window.downloadPDF === 'function') {
        window.downloadPDF();
    }
}

function switchPerfTab(tabName) {
    // Function implementation should exist in the page
    if (typeof window.switchPerfTab === 'function') {
        window.switchPerfTab(tabName);
    }
}

function scrollToResults(status) {
    // Function implementation should exist in the page
    if (typeof window.scrollToResults === 'function') {
        window.scrollToResults(status);
    }
}

function filterResults(filter, element) {
    // Function implementation should exist in the page
    if (typeof window.filterResults === 'function') {
        window.filterResults(filter, element);
    }
}

function filterModule(module, element) {
    // Function implementation should exist in the page
    if (typeof window.filterModule === 'function') {
        window.filterModule(module, element);
    }
}

function toggleResultDetail(element) {
    // Function implementation should exist in the page
    if (typeof window.toggleResultDetail === 'function') {
        window.toggleResultDetail(element);
    }
}

function toggleShowAllResults(element) {
    // Function implementation should exist in the page
    if (typeof window.toggleShowAllResults === 'function') {
        window.toggleShowAllResults(element);
    }
}

function openResultById(index) {
    // Function implementation should exist in the page
    if (typeof window.openResultById === 'function') {
        window.openResultById(index);
    }
}

function runCustomAIQuery() {
    // Function implementation should exist in the page
    if (typeof window.runCustomAIQuery === 'function') {
        window.runCustomAIQuery();
    }
}

function toggleAIResults() {
    // Function implementation should exist in the page
    if (typeof window.toggleAIResults === 'function') {
        window.toggleAIResults();
    }
}

function updateActiveTocLink(section) {
    // Remove active class from all TOC links
    document.querySelectorAll('.toc-link').forEach(link => {
        link.classList.remove('active');
    });
    // Add active class to the current link
    const activeLink = document.querySelector(`.toc-link[data-section="${section}"]`);
    if (activeLink) {
        activeLink.classList.add('active');
    }
}
