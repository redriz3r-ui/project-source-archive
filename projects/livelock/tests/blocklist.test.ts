import {describe,it,expect} from 'vitest';
import directoryDomains from '../src/rules/directory-domains.json';
import {builtinBlockedUrl,blocklistInfo} from '../src/core/blocklist';
describe('bundled category and board blocking',()=>{
  it('covers every extracted directory domain and its subdomains',()=>{const missed=directoryDomains.filter(d=>!builtinBlockedUrl(`https://${d}/`)||!builtinBlockedUrl(`https://www.${d}/`));expect(missed).toEqual([]);});
  it('contains a substantial bundled category snapshot',()=>expect(blocklistInfo.domainCount).toBeGreaterThan(100000));
  it.each(['https://erome.com/','https://www.erome.com/a/example','http://erome.com/','https://pornhub.com/','https://xvideos.com/','https://xnxx.com/','https://redtube.com/','https://chaturbate.com/','https://boards.4chan.org/gif/','https://4chan.org/gif','https://boards.4chan.org/gif/thread/123','https://boards.4channel.org/gif/?x=1','https://boards.4chan.org/%67if/','https://boards.4chan.org/GIF/','https://boards.4chan.org/g/','https://boards.4chan.org/gifx/','https://4chan.org/','https://4chan.org/faq','https://reddit.com/','https://theporndude.com/','https://pdude.link/anything','https://onlyfans.com/'])('blocks %s',url=>expect(builtinBlockedUrl(url)).toBe(true));
  it.each(['https://4chan.org.example.org/gif/','https://erome.com.example.org/','https://example.org/?url=erome.com','https://wikipedia.org/','chrome-extension://test/blocked.html'])('does not blanket-block %s',url=>expect(builtinBlockedUrl(url)).toBe(false));
});
