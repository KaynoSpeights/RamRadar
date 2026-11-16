// Filter the cards currently rendered by Flask. No activity data is copied here.
document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('#activity-search');
    const input = document.querySelector('#search-query');
    const grid = document.querySelector('.activity-grid');
    if (!form || !input || !grid) return;

    const buttons = [...document.querySelectorAll('.category[data-category]')];
    const summary = document.querySelector('.filter-summary');
    const count = document.querySelector('#results-count');
    const empty = document.querySelector('#no-results');
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
        count.textContent = `${matches} of ${cards.length} ${cards.length === 1 ? 'activity' : 'activities'} shown`;
        empty.hidden = matches !== 0;
        summary.hidden = false;
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
    document.querySelector('#clear-filters').addEventListener('click', () => {
        input.value = '';
        category = 'all';
        filterActivities();
        input.focus();
    });
    // Reapply the current selection when database-backed or newly created cards appear.
    new MutationObserver(filterActivities).observe(grid, { childList: true, subtree: true, characterData: true });
    filterActivities();
});
