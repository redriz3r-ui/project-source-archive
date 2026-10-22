import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const path=process.argv[2];if(!path)throw Error('Pass the downloaded Block List Project porn-nl.txt snapshot.');
const raw=await readFile(path,'utf8');
const protectedDomains=['4chan.org','4channel.org','reddit.com','redd.it','twitter.com','x.com','tumblr.com','imgur.com','discord.com','discord.gg','wikipedia.org','youtube.com','google.com','bing.com','archive.org','pinterest.com','facebook.com','instagram.com','tiktok.com','deviantart.com','patreon.com','co.uk','org.uk','com.au','co.jp','com.br'];
const protectedSet=new Set(protectedDomains);
const safe=d=>d.length<=253&&/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(d);
const candidates=new Set(['chaturbate.com','pornhub.com','xvideos.com','xnxx.com','redtube.com','erome.com']);
let excluded=0;
for(const line of raw.split(/\r?\n/)){
 const value=line.trim().toLowerCase();if(!value||value.startsWith('#'))continue;
 const labels=value.split('.');let protect=false;
 for(let i=0;i<labels.length-1;i++)if(protectedSet.has(labels.slice(i).join('.'))){protect=true;break;}
 if(!safe(value)||protect){excluded++;continue;}candidates.add(value);
}
if(candidates.size<1000||candidates.size>2_000_000)throw Error('Unexpected list size; review input.');
// Parent domains already cover all subdomains in Chrome. Remove redundant descendants.
const ordered=[...candidates].sort((a,b)=>a.split('.').length-b.split('.').length||(a<b?-1:a>b?1:0));
const retained=new Set();
for(const value of ordered){const labels=value.split('.');let covered=false;for(let i=1;i<labels.length-1;i++)if(retained.has(labels.slice(i).join('.'))){covered=true;break;}if(!covered)retained.add(value);}
const domains=[...retained].sort();
const metadata={name:'Block List Project porn snapshot + LiveLock required domains',source:'https://blocklistproject.github.io/Lists/alt-version/porn-nl.txt',retrievedAt:new Date().toISOString(),sourceSha256:createHash('sha256').update(raw).digest('hex'),sourceEntries:raw.split(/\r?\n/).filter(x=>x.trim()&&!x.startsWith('#')).length,domainCount:domains.length,excludedOrInvalid:excluded,redundantSubdomains:candidates.size-domains.length,protectedMixedSites:protectedDomains,sourceHeader:raw.split(/\r?\n/).filter(x=>x.startsWith('#')).slice(0,20)};
await writeFile('src/rules/adult-domains.json',JSON.stringify(domains)+'\n');await writeFile('src/rules/blocklist-metadata.json',JSON.stringify(metadata,null,2)+'\n');console.log(JSON.stringify({domainCount:domains.length,excluded,redundantSubdomains:metadata.redundantSubdomains}));
