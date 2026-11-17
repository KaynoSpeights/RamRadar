document.addEventListener('DOMContentLoaded', () => {
    const menuButton = document.querySelector('.menu-toggle');
    const navigation = document.querySelector('#primary-nav');

    if (menuButton && navigation) {
        const closeMenu = () => {
            menuButton.setAttribute('aria-expanded', 'false');
            menuButton.setAttribute('aria-label', 'Open navigation menu');
            navigation.classList.remove('is-open');
            document.body.classList.remove('menu-open');
        };
        menuButton.addEventListener('click', () => {
            const isOpen = menuButton.getAttribute('aria-expanded') === 'true';
            menuButton.setAttribute('aria-expanded', String(!isOpen));
            menuButton.setAttribute('aria-label', isOpen ? 'Open navigation menu' : 'Close navigation menu');
            navigation.classList.toggle('is-open', !isOpen);
            document.body.classList.toggle('menu-open', !isOpen);
        });
        navigation.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') closeMenu();
        });
    }

    const revealItems = document.querySelectorAll('.reveal');
    if ('IntersectionObserver' in window && revealItems.length) {
        document.documentElement.classList.add('motion-ready');
        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });
        revealItems.forEach((item, index) => {
            item.style.transitionDelay = `${Math.min(index % 4, 3) * 70}ms`;
            observer.observe(item);
        });
    }

    // Filter the cards rendered by Flask; search remains useful without a database query.
    const form = document.querySelector('#activity-search');
    const input = document.querySelector('#search-query');
    const grid = document.querySelector('.activity-grid');
    if (!form || !input || !grid) return;

    const buttons = [...document.querySelectorAll('.category[data-category]')];
    const summary = document.querySelector('.filter-summary');
    const count = document.querySelector('#results-count');
    const empty = document.querySelector('#no-results');
    const clearButton = document.querySelector('#clear-filters');
    let category = 'all';
    const normalize = value => value.trim().replace(/\s+/g, ' ').toLocaleLowerCase();

    function filterActivities() {
        const terms = normalize(input.value).split(' ').filter(Boolean);
        const cards = [...grid.querySelectorAll('.activity-card')];
        let matches = 0;
        cards.forEach(card => {
            const text = normalize(card.textContent);
            const visible = (category === 'all' || card.dataset.category === category)
                && terms.every(term => text.includes(term));
            card.hidden = !visible;
            if (visible) matches++;
        });
        buttons.forEach(button => {
            const selected = button.dataset.category === category;
            button.classList.toggle('active', selected);
            button.setAttribute('aria-pressed', String(selected));
        });
        if (count) count.textContent = `${matches} of ${cards.length} ${cards.length === 1 ? 'activity' : 'activities'} shown`;
        if (empty) empty.hidden = matches !== 0;
        if (summary) summary.hidden = false;
    }

    form.addEventListener('submit', event => {
        event.preventDefault();
        filterActivities();
    });
    input.addEventListener('input', filterActivities);
    buttons.forEach(button => button.addEventListener('click', () => {
        category = button.dataset.category;
        filterActivities();
    }));
    if (clearButton) {
        clearButton.addEventListener('click', () => {
            input.value = '';
            category = 'all';
            filterActivities();
            input.focus();
        });
    }
    // Reapply the current selection when database-backed or newly created cards appear.
    new MutationObserver(filterActivities).observe(grid, { childList: true, subtree: true, characterData: true });
    filterActivities();
});
