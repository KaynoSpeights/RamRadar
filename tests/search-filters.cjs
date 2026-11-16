// Run: npm install --no-save --package-lock=false playwright && npx playwright install chromium
// Then: node tests/search-filters.cjs
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
(async () => {
 const browser = await chromium.launch({headless:true, ...(process.env.CHROMIUM_PATH ? {executablePath:process.env.CHROMIUM_PATH} : {})});
 const page = await browser.newPage();
 const errors = [];
 page.on('pageerror', error => errors.push(error.message));
 let html = fs.readFileSync(path.join(root,'templates/index.html'),'utf8')
  .replace(/<link[^>]+>/, '')
  .replace(/<script[^>]+><\/script>/, '');
 await page.setContent(html);
 await page.addStyleTag({content:fs.readFileSync(path.join(root,'static/css/style.css'),'utf8')});
 await page.addScriptTag({content:fs.readFileSync(path.join(root,'static/js/script.js'),'utf8')});
 await page.evaluate(() => document.dispatchEvent(new Event('DOMContentLoaded')));
 const visible = () => page.locator('.activity-card:visible').count();
 const input = page.locator('#search-query');
 const category = name => page.getByRole('button',{name,exact:true});
 assert.equal(await visible(),3);
 await input.fill('  BASKETBALL  '); assert.equal(await visible(),1);
 await input.press('Enter'); assert.equal(await visible(),1);
 await category('Study Sessions').click(); assert.equal(await visible(),0);
 assert.equal(await page.locator('#no-results').isVisible(),true);
 await category('Clear filters').click(); assert.equal(await visible(),3);
 assert.equal(await input.inputValue(),'');
 await category('Study Sessions').click(); await input.fill('library study');
 assert.equal(await visible(),1);
 assert.equal(await category('Study Sessions').getAttribute('aria-pressed'),'true');
 await category('All Activities').click(); assert.equal(await visible(),1);
 await input.fill('virtual'); assert.equal(await visible(),1);
 await input.fill('<script>alert(1)</script>'); assert.equal(await visible(),0);
 await category('Clear filters').click();
 await category('Career').click(); assert.equal(await visible(),0);
 await page.evaluate(() => {
  const card = document.createElement('article'); card.className='activity-card';
  card.dataset.category='Career'; card.textContent='Resume workshop';
  document.querySelector('.activity-grid').append(card);
 });
 await page.waitForFunction(() => document.querySelector('#results-count').textContent === '1 of 4 activities shown');
 assert.equal(await visible(),1);
 await page.locator('.activity-card').last().evaluate(el=>el.remove());
 await category('Clear filters').click();
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),true);
 await page.screenshot({path:'/tmp/ramradar-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1000});
 await page.screenshot({path:'/tmp/ramradar-desktop.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('PASS: initial results, search, Enter, combined filters, empty state, reset, category state, locations, literal input, new cards, mobile overflow, browser errors.');
 await browser.close();
})().catch(error=>{ console.error(error); process.exit(1); });
