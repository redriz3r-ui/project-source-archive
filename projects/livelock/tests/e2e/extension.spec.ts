import {test,expect,chromium,type BrowserContext,type Worker} from '@playwright/test';
import {resolve} from 'node:path';
import {mkdtemp,rm,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
let context:BrowserContext;let worker:Worker;let profile:string;let id:string;
async function start(dir:string,reuse=false){if(!reuse)profile=await mkdtemp(resolve(tmpdir(),'livelock-e2e-'));const path=resolve(dir);context=await chromium.launchPersistentContext(profile,{channel:'chromium',headless:true,args:[`--disable-extensions-except=${path}`,`--load-extension=${path}`]});worker=context.serviceWorkers()[0]||await context.waitForEvent('serviceworker');id=worker.url().split('/')[2];}
async function options(){const page=await context.newPage();page.on('console',m=>console.log('UI',m.text()));page.on('pageerror',e=>console.log('UI ERROR',e.message));await page.goto(`chrome-extension://${id}/options.html`);await expect(page.locator('#protection')).toContainText('Protection ON').catch(async e=>{console.log('BODY',await page.locator('body').innerText());console.log('STORAGE',await worker.evaluate(()=>chrome.storage.local.get(null)));throw e;});return page;}
test.afterEach(async()=>{await context?.close();if(profile)await rm(profile,{recursive:true,force:true});});
test('simulator: real MV3 install, rule matching, default block, settings, LIVE, relock and OFF',async()=>{
  await start('dist-dev');const page=await options();await expect(page.locator('#mode')).toBeVisible();
  const deny=await context.newPage();await expect(deny.goto('https://chaturbate.com/sample_handle/')).rejects.toThrow(/ERR_BLOCKED_BY_CLIENT/);
  await page.locator('#username').fill('https://www.chaturbate.com/Sample_Handle/');await page.locator('#domains').fill('example.com');await page.getByRole('button',{name:'Save and lock',exact:true}).click();await expect(page.locator('#notice')).toContainText('Saved');
  await page.selectOption('#fixture','live');await page.locator('#apply-fixture').click();await page.waitForTimeout(5100);await page.locator('#check').click();
  await expect.poll(()=>worker.evaluate(async()=>!!(await chrome.storage.local.get('grant')).grant)).toBe(true);
  const outcomes=await worker.evaluate(async()=>{
    const urls=['https://chaturbate.com/sample_handle/','https://www.chaturbate.com/sample_handle/?a=b','https://chaturbate.com/other_handle/','https://chaturbate.com/','https://chaturbate.com/sample_handle2/','https://m.chaturbate.com/sample_handle/','https://pornhub.com/','https://example.com/'];
    const result=[];for(const url of urls)result.push((await chrome.declarativeNetRequest.testMatchOutcome({url,type:chrome.declarativeNetRequest.ResourceType.MAIN_FRAME})).matchedRules);return result;
  });expect(outcomes[0][0].rulesetId).toBe('_session');expect(outcomes[1][0].rulesetId).toBe('_session');for(const r of outcomes.slice(2)){expect(r.length).toBeGreaterThan(0);expect(r.every(x=>x.rulesetId!=='_session')).toBe(true);}
  const frame=await worker.evaluate(()=>chrome.declarativeNetRequest.testMatchOutcome({url:'https://chaturbate.com/sample_handle/',type:chrome.declarativeNetRequest.ResourceType.SUB_FRAME}));expect(frame.matchedRules[0].rulesetId).toBe('baseline');
  // Synthetic document prevents any adult content request in automated tests.
  await context.route('https://chaturbate.com/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><title>Synthetic room</title><h1>Local synthetic room</h1>'}));
  const room=await context.newPage();await room.goto('https://chaturbate.com/sample_handle/');await expect(room.locator('h1')).toBeVisible();
  await room.evaluate(()=>history.pushState({},'', '/other_handle/'));await expect(room).toHaveURL(/blocked.html/);
  const popup=await context.newPage();await popup.goto(`chrome-extension://${id}/popup.html`);await expect(popup.locator('#status')).toContainText('SIMULATED');await popup.locator('#lock').click();await expect.poll(()=>worker.evaluate(()=>chrome.declarativeNetRequest.getSessionRules())).toEqual([]);
  await page.selectOption('#fixture','offline');await page.locator('#apply-fixture').click();await worker.evaluate(()=>{const actual=Date.now;Date.now=()=>actual()+6000;});await page.locator('#check').click();await expect.poll(()=>worker.evaluate(async()=>(await chrome.storage.local.get('state')).state)).toBe('locked_offline');expect(await worker.evaluate(()=>chrome.declarativeNetRequest.getSessionRules())).toEqual([]);
  await page.selectOption('#fixture','unknown');await page.locator('#apply-fixture').click();await worker.evaluate(()=>{const actual=Date.now;Date.now=()=>actual()+6000;});await page.locator('#check').click();await expect.poll(()=>worker.evaluate(async()=>(await chrome.storage.local.get('state')).state)).toBe('locked_unknown');
  await page.locator('#confirm-off').check();await page.locator('#disable').click();await expect(page.locator('#protection')).toContainText('Protection OFF');expect(await worker.evaluate(()=>chrome.declarativeNetRequest.getEnabledRulesets())).toEqual([]);expect(await worker.evaluate(()=>chrome.declarativeNetRequest.getDynamicRules())).toEqual([]);
  await page.locator('#enable').click();await expect(page.locator('#protection')).toHaveText('Protection ON');expect(await worker.evaluate(()=>chrome.declarativeNetRequest.getEnabledRulesets())).toEqual(['baseline']);
  await page.screenshot({path:'artifacts/settings-simulator.png',fullPage:true});
  // Real browser restart preserves OFF preference and does not resurrect any grant.
  await page.locator('#disable').click();await expect(page.locator('#protection')).toContainText('Protection OFF');await context.close();await start('dist-dev',true);const restarted=await context.newPage();await restarted.goto(`chrome-extension://${id}/options.html`);await expect(restarted.locator('#protection')).toContainText('Protection OFF');expect(await worker.evaluate(()=>chrome.declarativeNetRequest.getEnabledRulesets())).toEqual([]);expect(await worker.evaluate(()=>chrome.declarativeNetRequest.getSessionRules())).toEqual([]);
});
test('production: no simulator controls or fixture code; UNKNOWN cannot grant',async()=>{
  await start('dist-unconfigured');const page=await options();await expect(page.locator('#simulator')).toBeHidden();await expect(page.locator('#provider')).toContainText('unavailable');await page.locator('#username').fill('sample_handle');await page.getByRole('button',{name:'Save and lock',exact:true}).click();await expect(page.locator('#notice')).toContainText('Saved');
  await worker.evaluate(()=>chrome.storage.local.set({fixtureState:'live'}));
  const popup=await context.newPage();await popup.goto(`chrome-extension://${id}/popup.html`);await popup.locator('#check').click();await expect(popup.locator('#status')).toHaveText('UNKNOWN');await expect(popup.locator('#open')).toBeDisabled();expect(await worker.evaluate(()=>chrome.declarativeNetRequest.getSessionRules())).toEqual([]);
  expect(await readFile('dist-unconfigured/background.js','utf8')).not.toContain('fixtureState');await popup.screenshot({path:'artifacts/popup-production.png'});
});

test('simulator: lease expiry redirects all rooms and browser restart revokes a fresh grant',async()=>{
  await start('dist-dev');const page=await options();await page.locator('#username').fill('sample_handle');await page.getByRole('button',{name:'Save and lock',exact:true}).click();await expect(page.locator('#notice')).toContainText('Saved');
  await page.selectOption('#fixture','live');await page.locator('#apply-fixture').click();await page.locator('#check').click();await expect.poll(()=>worker.evaluate(async()=>!!(await chrome.storage.local.get('grant')).grant)).toBe(true);
  await context.route('https://chaturbate.com/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><h1>Synthetic room</h1>'}));
  const rooms=await Promise.all([context.newPage(),context.newPage()]);for(const room of rooms){await room.goto('https://chaturbate.com/sample_handle/');await expect(room.locator('h1')).toBeVisible();}
  await worker.evaluate(()=>{const actual=Date.now;Date.now=()=>actual()+91000;});
  const popup=await context.newPage();await popup.goto(`chrome-extension://${id}/popup.html`);await expect(popup.locator('#open')).toBeDisabled();await expect.poll(()=>worker.evaluate(()=>chrome.declarativeNetRequest.getSessionRules())).toEqual([]);for(const room of rooms)await expect(room).toHaveURL(/blocked.html/);
  // Reload the entire isolated browser, preserving stored config and fixture, then make a fresh grant.
  await context.close();await start('dist-dev',true);const settings=await options();await settings.locator('#check').click();await expect.poll(()=>worker.evaluate(async()=>!!(await chrome.storage.local.get('grant')).grant)).toBe(true);await context.close();await start('dist-dev',true);await options();expect(await worker.evaluate(()=>chrome.declarativeNetRequest.getSessionRules())).toEqual([]);expect((await worker.evaluate(()=>chrome.storage.local.get('grant'))).grant).toBeNull();
});

test('connected production: official response grants exact room, failed refresh relocks, fixtures ignored',async()=>{
  test.skip(JSON.parse(await readFile('dist/provider.json','utf8')).type!=='official-affiliate','No local affiliate campaign configured.');
  await start('dist');let mode='public';let calls=0;
  await context.route('https://chaturbate.com/api/public/affiliates/onlinerooms/**',route=>{calls++;const u=new URL(route.request().url());expect(u.searchParams.get('client_ip')).toBe('request_ip');return mode==='error'?route.fulfill({status:500,body:'{}'}):route.fulfill({contentType:'application/json',headers:{date:new Date().toUTCString()},body:JSON.stringify({count:1,results:[{username:'sample_handle',current_show:mode}]})});});
  const settings=await options();await expect(settings.locator('#provider')).toContainText('Connected');await expect(settings.locator('#simulator')).toBeHidden();await settings.locator('#username').fill('sample_handle');await settings.getByRole('button',{name:'Save and lock',exact:true}).click();await expect(settings.locator('#notice')).toContainText('Saved');
  const popup=await context.newPage();await popup.goto(`chrome-extension://${id}/popup.html`);await popup.locator('#check').click();await expect(popup.locator('#status')).toHaveText('LIVE');expect(calls).toBe(1);await expect(popup.locator('#open')).toBeEnabled();const rules=await worker.evaluate(()=>chrome.declarativeNetRequest.getSessionRules());expect(rules).toHaveLength(1);expect(rules[0].condition.regexFilter).toContain('/sample_handle/');
  const scoped=await worker.evaluate(async()=>{const result=[];for(const url of ['https://chaturbate.com/sample_handle/','https://theporndude.com/','https://onlyfans.com/','https://reddit.com/'])result.push((await chrome.declarativeNetRequest.testMatchOutcome({url,type:chrome.declarativeNetRequest.ResourceType.MAIN_FRAME})).matchedRules.map(rule=>rule.rulesetId));return result;});expect(scoped[0]).toEqual(['_session']);for(const result of scoped.slice(1))expect(result).toEqual(['baseline']);
  await popup.screenshot({path:'artifacts/popup-connected.png'});mode='error';await worker.evaluate(async()=>{await chrome.storage.session.remove('affiliateRequestState');const actual=Date.now;Date.now=()=>actual()+6000;});await popup.locator('#check').click();await expect(popup.locator('#status')).toHaveText('UNKNOWN');expect(await worker.evaluate(()=>chrome.declarativeNetRequest.getSessionRules())).toEqual([]);
  mode='private';await worker.evaluate(async()=>{await chrome.storage.session.remove('affiliateRequestState');await chrome.storage.local.set({fixtureState:'live'});const actual=Date.now;Date.now=()=>actual()+6000;});await popup.locator('#check').click();await expect(popup.locator('#status')).toHaveText('UNKNOWN');await expect(popup.locator('#open')).toBeDisabled();
});

test('LIVE NETWORK: real official API public-room observation installs a real session allowance',async()=>{
  test.skip(process.env.LIVELOCK_REAL_API!=='1','Explicit live metadata check only. Never fetches streams.');
  await start('dist');const settings=await options();
  const {campaign}=JSON.parse(await readFile('config/affiliate.local.json','utf8'));
  const publicHandle=await worker.evaluate(async campaign=>{const url=new URL('https://chaturbate.com/api/public/affiliates/onlinerooms/');for(const [key,value] of Object.entries({wm:campaign,client_ip:'request_ip',format:'json',limit:'500',offset:'0'}))url.searchParams.set(key,value);const response=await fetch(url,{credentials:'omit',redirect:'error',cache:'no-store'});if(!response.ok)throw Error('Official API unavailable');const data=await response.json();return data.results.find((room:{username:string;current_show:string})=>room.current_show==='public'&&/^[a-z0-9_]{3,30}$/.test(room.username))?.username;},campaign);
  expect(publicHandle).toBeTruthy();await settings.locator('#username').fill(publicHandle);await settings.getByRole('button',{name:'Save and lock',exact:true}).click();await expect(settings.locator('#notice')).toContainText('Saved');
  const popup=await context.newPage();await popup.goto(`chrome-extension://${id}/popup.html`);await popup.locator('#check').click();await expect(popup.locator('#status')).toHaveText('LIVE',{timeout:30000});await expect(popup.locator('#open')).toBeEnabled();
  const result=await worker.evaluate(async()=>{const stored=await chrome.storage.local.get(['grant','lastObservation']);const rules=await chrome.declarativeNetRequest.getSessionRules();const observation=stored.lastObservation as {source:string;state:string;username:string}|undefined;const grant=stored.grant as {username:string}|undefined;return {source:observation?.source,state:observation?.state,exactUsernameMatch:grant?.username===observation?.username,sessionRuleCount:rules.length};});expect(result).toEqual({source:'authorized-affiliate',state:'live',exactUsernameMatch:true,sessionRuleCount:1});await writeFile('artifacts/live-browser-verification.json',JSON.stringify({checkedAt:new Date().toISOString(),...result,syntheticApiResponse:false,streamsFetched:0,cookiesUsed:false},null,2));
});

test('expanded and directory blocking: native domain denial and OFF/ON',async()=>{
  await start('dist');const settings=await options();await expect(settings.locator('#blocklist-info')).toContainText('domain entries');
  const targets=['https://erome.com/','https://www.erome.com/a/example','http://erome.com/','https://boards.4chan.org/gif/','https://boards.4chan.org/gif/thread/123','https://4chan.org/gif','https://boards.4channel.org/gif/','https://boards.4chan.org/%67if/','https://boards.4chan.org/g/','https://boards.4chan.org/gifx/','https://theporndude.com/','https://reddit.com/','https://onlyfans.com/'];
  const matches=await worker.evaluate(async urls=>{const out=[];for(const url of urls)out.push((await chrome.declarativeNetRequest.testMatchOutcome({url,type:chrome.declarativeNetRequest.ResourceType.MAIN_FRAME})).matchedRules);return out;},targets);for(const match of matches){expect(match.length).toBeGreaterThan(0);expect(match.every(rule=>rule.rulesetId==='baseline')).toBe(true);}
  const safe=await worker.evaluate(async()=>{const out=[];for(const url of ['https://4chan.org.example.org/g/','https://erome.com.example.org/','https://wikipedia.org/'])out.push((await chrome.declarativeNetRequest.testMatchOutcome({url,type:chrome.declarativeNetRequest.ResourceType.MAIN_FRAME})).matchedRules);return out;});for(const match of safe)expect(match).toEqual([]);
  // Browser-native denial is verified without requesting adult content.
  for(const url of ['https://erome.com/','https://boards.4chan.org/gif/']){const blocked=await context.newPage();await expect(blocked.goto(url)).rejects.toThrow(/ERR_BLOCKED_BY_CLIENT/);await blocked.close();}
  await settings.locator('#confirm-off').check();await settings.locator('#disable').click();await expect(settings.locator('#protection')).toContainText('Protection OFF');const off=await worker.evaluate(()=>chrome.declarativeNetRequest.testMatchOutcome({url:'https://erome.com/',type:chrome.declarativeNetRequest.ResourceType.MAIN_FRAME}));expect(off.matchedRules).toEqual([]);await settings.locator('#enable').click();await expect(settings.locator('#protection')).toHaveText('Protection ON');const restored=await worker.evaluate(()=>chrome.declarativeNetRequest.testMatchOutcome({url:'https://boards.4chan.org/gif/',type:chrome.declarativeNetRequest.ResourceType.MAIN_FRAME}));expect(restored.matchedRules.length).toBeGreaterThan(0);
});

test('restricted page follows the selected handle and lock/OFF state without exposing it in an iframe',async()=>{
  await start('dist-dev');
  const settings=await options();
  await settings.locator('#username').fill('sample_handle');
  await settings.getByRole('button',{name:'Save and lock',exact:true}).click();
  await expect(settings.locator('#notice')).toContainText('Saved');
  const blocked=await context.newPage();
  await blocked.goto(`chrome-extension://${id}/blocked.html`);
  await expect(blocked.locator('#heading')).toHaveText('@sample_handle isn’t confirmed live.');
  await expect(blocked.locator('#selection')).toContainText('Please check again.');
  await blocked.screenshot({path:'artifacts/blocked-personalized.png'});
  await settings.locator('#username').fill('another_handle');
  await settings.getByRole('button',{name:'Save and lock',exact:true}).click();
  await expect(blocked.locator('#heading')).toHaveText('@another_handle isn’t confirmed live.');
  const popup=await context.newPage();await popup.goto(`chrome-extension://${id}/popup.html`);await popup.locator('#lock').click();
  await expect(blocked.locator('#heading')).toHaveText('@another_handle is locked.');
  await settings.locator('#confirm-off').check();await settings.locator('#disable').click();
  await expect(blocked.locator('#heading')).toHaveText('LiveLock is off.');
  await settings.locator('#enable').click();
  await context.route('https://chaturbate.com/privacy-frame-test',route=>route.fulfill({contentType:'text/html',body:`<iframe src="chrome-extension://${id}/blocked.html"></iframe>`}));
  // Protection OFF permits the synthetic host; personalized content must still stay out of its iframe.
  await settings.locator('#confirm-off').check();await settings.locator('#disable').click();await expect(settings.locator('#protection')).toContainText('Protection OFF');
  const host=await context.newPage();await host.goto('https://chaturbate.com/privacy-frame-test');
  const frame=host.frameLocator('iframe');
  await expect(frame.locator('#heading')).toHaveText('This website is blocked.');
  await expect(frame.locator('#selection')).not.toContainText('another_handle');
  await expect(frame.locator('a, button')).toHaveCount(0);
});

test('personalized reminder survives an older or unavailable worker without claiming LIVE',async()=>{
  await start('dist');const settings=await options();await settings.locator('#username').fill('sample_handle');await settings.getByRole('button',{name:'Save and lock',exact:true}).click();await expect(settings.locator('#notice')).toContainText('Saved');
  const blocked=await context.newPage();await blocked.addInitScript(()=>{Object.defineProperty(chrome.runtime,'sendMessage',{value:async()=>{throw Error('Legacy worker / temporarily unavailable');}});});
  await blocked.goto(`chrome-extension://${id}/blocked.html`);await expect(blocked.locator('#heading')).toHaveText('@sample_handle’s live status is unavailable.');await expect(blocked.locator('#selection')).toContainText('Please check again.');await expect(blocked.locator('#heading')).not.toContainText('is live');await blocked.screenshot({path:'artifacts/blocked-personalized-fallback.png'});
});
