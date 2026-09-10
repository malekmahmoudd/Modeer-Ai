/* Run against tools.qa_server (mock, throwaway DB) and a frontend proxying to it.
   PLAYWRIGHT_MODULE may point to an existing Playwright install. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.env.QA_URL || 'http://localhost:3001';
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const checks = [];
  const check = name => { checks.push(name); console.log('PASS', name); };
  const send = async text => {
    await page.locator('textarea').fill(text);
    await page.getByRole('button', {name:'Send message', exact:true}).click();
  };
  const settled = async () => {
    await page.getByRole('button', {name:'Send message', exact:true}).waitFor();
  };
  try {
    await page.goto(base + '/');
    await page.waitForURL(base + '/login');
    await page.waitForLoadState('networkidle');
    await page.getByLabel('Access key').fill('q'.repeat(40));
    await page.getByRole('button', {name:'Meet your team'}).click();
    await page.waitForURL(base + '/');
    check('browser login and session');
    // The QA database may already contain an earlier diagnostic conversation.
    const onboarding = page.getByRole('link', {name:'Start with Modeer'});
    if (await onboarding.isVisible()) await onboarding.click();
    else await page.goto(base + '/agents/modeer?onboarding=1');
    await send('I live in Cairo. I am studying computer science. My native language is Arabic.');
    await page.getByText('offline preview response', {exact:false}).first().waitFor();
    await settled();
    const me = await page.request.get(base + '/api/users/me');
    assert.equal((await me.json()).onboarded, true);
    check('onboarding completed through chat');
    await page.goto(base + '/memory');
    await page.getByText('Cairo', {exact:true}).waitFor();
    await page.getByText('computer science', {exact:true}).waitFor();
    check('chat facts visible in Memory');
    await page.goto(base + '/agents/study');
    await send('Help me plan my studies.');
    await page.getByText('Using what the team already knows about you:', {exact:false}).waitFor();
    await settled();
    assert.match(await page.locator('body').innerText(), /Cairo/);
    check('specialist follow-up receives saved context');
    await page.getByRole('button', {name:/Conversation history/}).click();
    await page.getByRole('dialog', {name:'Conversations'}).waitFor();
    await page.getByRole('button', {name:'Close conversations'}).click();
    check('history drawer opens and closes');
    for (const width of [1440, 768, 390]) {
      await page.setViewportSize({width, height:844});
      for (const path of ['/', '/team', '/memory', '/goals', '/agents/study']) {
        await page.goto(base + path);
        await page.waitForLoadState('networkidle');
        await page.locator('main').waitFor();
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${path} overflow at ${width}`);
      }
      check(`no horizontal overflow at ${width}px`);
    }
    await page.locator('textarea').waitFor();
    await context.setOffline(true);
    await send('Reconnect test');
    await page.getByText(/Failed to fetch|NetworkError|Load failed/).waitFor();
    await context.setOffline(false);
    await send('Please help me study.');
    await page.getByText('offline preview response', {exact:false}).first().waitFor();
    await settled();
    check('mobile offline failure and successful retry');
    const pattern = '**/api/agents/study/chat/stream';
    await page.route(pattern, route => route.fulfill({status:429, contentType:'application/json', body:JSON.stringify({detail:'You are sending messages too quickly. Please wait a minute and try again.'})}));
    await send('Limit test');
    await page.getByText('You are sending messages too quickly. Please wait a minute and try again.', {exact:true}).waitFor();
    await page.unroute(pattern);
    check('rate-limit explanation displayed');
    await page.route(pattern, route => route.fulfill({status:200,contentType:'text/event-stream',body:'data: {"type":"delta","text":"partial"}\n\n'}));
    await send('Interrupted stream test');
    await page.getByText('The connection ended before the reply finished. Please try again.', {exact:true}).waitFor();
    await page.unroute(pattern);
    check('incomplete stream surfaces an error');
    let intercepted;
    const pending = new Promise(resolve => intercepted = resolve);
    await page.route(pattern, async route => { intercepted(); await new Promise(r => setTimeout(r,1500)); await route.abort().catch(()=>{}); });
    await send('Navigation interruption');
    await pending;
    await page.getByRole('link', {name:'Memory', exact:true}).click();
    await page.getByText('A little more you.', {exact:true}).waitFor();
    await page.unroute(pattern);
    await page.goto(base + '/agents/study');
    await send('One more study suggestion.');
    await page.getByText('offline preview response', {exact:false}).first().waitFor();
    await settled();
    check('navigate away during pending reply, return and send again');
    assert.deepEqual(errors, []);
    check('no uncaught browser errors');
    fs.writeFileSync(process.env.QA_REPORT || 'browser-qa-results.json', JSON.stringify({provider:'mock', checks, errors},null,2));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
