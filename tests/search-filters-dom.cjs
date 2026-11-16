// Run: npm install --no-save --package-lock=false jsdom
// Then: node tests/search-filters-dom.cjs
const {JSDOM} = require('jsdom');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname,'..');
(async()=>{
 const dom = new JSDOM(fs.readFileSync(path.join(root,'templates/index.html'),'utf8'),{runScripts:'outside-only'});
 await new Promise(resolve=>dom.window.addEventListener('load',resolve));
 const w=dom.window, d=w.document;
 w.eval(fs.readFileSync(path.join(root,'static/js/script.js'),'utf8'));
 d.dispatchEvent(new w.Event('DOMContentLoaded'));
 const input=d.querySelector('#search-query');
 const search=value=>{input.value=value;input.dispatchEvent(new w.Event('input'));};
 const click=name=>[...d.querySelectorAll('button')].find(b=>b.textContent===name).click();
 const visible=()=>[...d.querySelectorAll('.activity-card')].filter(c=>!c.hidden).length;
 assert.equal(visible(),3);
 search('  BASKETBALL  '); assert.equal(visible(),1);
 const submit=new w.Event('submit',{cancelable:true});d.querySelector('form').dispatchEvent(submit);assert.equal(submit.defaultPrevented,true);
 click('Study Sessions');assert.equal(visible(),0);assert.equal(d.querySelector('#no-results').hidden,false);
 click('Clear filters');assert.equal(visible(),3);assert.equal(input.value,'');assert.equal(d.activeElement,input);
 click('Study Sessions');search('library study');assert.equal(visible(),1);
 assert.equal([...d.querySelectorAll('[aria-pressed="true"]')].length,1);
 click('All Activities');assert.equal(visible(),1);
 search('virtual');assert.equal(visible(),1);
 search('<script>alert(1)</script>');assert.equal(visible(),0);
 click('Clear filters');click('Career');assert.equal(visible(),0);
 const card=d.createElement('article');card.className='activity-card';card.dataset.category='Career';card.textContent='Resume workshop';d.querySelector('.activity-grid').append(card);
 await new Promise(resolve=>w.setTimeout(resolve,0));assert.equal(visible(),1);
 assert.equal(d.querySelector('#results-count').textContent,'1 of 4 activities shown');
 console.log('PASS: search, capitalization, whitespace, Enter/submit, combined categories, empty state, clear/focus, location, multiple words, literal input, dynamic cards, counts and selected state.');
 dom.window.close();
})().catch(e=>{console.error(e);process.exit(1);});
