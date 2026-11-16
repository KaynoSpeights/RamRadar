# Activity search and category filtering

Contribution: Malik Terry — homepage activity discovery.

## Behavior
- Search titles, descriptions, categories, and locations as the user types or submits with Enter/Search.
- Ignore capitalization and extra whitespace. Every entered word must occur somewhere on the card.
- Combine the search with one selected category. All Activities removes the category restriction while keeping the search.
- Show a result count and a no-matches message.
- Clear filters resets both controls and returns focus to search.
- Keep every activity visible if JavaScript is disabled.

## Integration for teammates
The filters operate on the activity cards rendered by Flask; they do not store data or query the database. Keep `.activity-grid` around the list and `.activity-card` on each card. Give each card a `data-category` matching a category button exactly (for example, `Study Sessions`). In a Jinja loop use `data-category="{{ activity.category }}"` with normal escaping enabled. New cards inserted into the grid are automatically filtered. This filters only cards loaded on the page; server-side pagination would need backend search support.

## User stories
- As a student, I want to search activities by keyword so I can find relevant meetups.
- As a student, I want to combine a category with my search so I can narrow the results.
- As a student, I want to clear filters so I can see all activities again.

## Demo
1. Open the homepage: three sample activities appear.
2. Search `BASKETBALL`: the basketball meetup remains.
3. Select Study Sessions while that search remains: no matches appear.
4. Clear filters: all three return.
5. Select Study Sessions and search `library`: only the study session appears.

## Scope
This contribution covers search/filter interaction and related styling, accessibility, tests, and integration notes. Activity creation, database storage, Docker, deployment, and the full team report/slides remain team work.

## Validation completed
`node tests/search-filters-dom.cjs` passed all DOM interaction checks, including search normalization, combined filters, empty results, reset/focus, dynamic cards, result counts, and selected states. `node --check static/js/script.js` and `git diff --check` passed. The Playwright browser checks are included in `tests/search-filters.cjs` but could not run in the build environment because Chromium process creation was blocked. Live Flask rendering and desktop/mobile visual checks still need to be done.

## Add this work to GitHub
1. On the repository page, open the `main` branch selector.
2. Enter `malik/search-and-filters` and choose Create branch from main.
3. Extract the supplied ZIP. Upload the `static`, `templates`, `docs`, and `tests` folders using Add file > Upload files on that branch. Preserve the folder structure; do not upload the ZIP itself.
4. Commit with: `Add activity search and category filtering`.
5. Open a pull request into main and let the group review and combine the changes.
6. Before merging, run the project locally and test the demo above on desktop and mobile. Check for newer changes on main before replacing shared files.

Suggested presentation explanation: “I worked on activity discovery. I connected the search bar and category buttons so students can narrow down the activity list. Search ignores capitalization and extra spaces, works together with the selected category, and searches the information already rendered on each activity card. I added result counts, an empty-results message, and a clear-filters button. I also tested the interaction logic and documented the card structure for database integration.”
  
