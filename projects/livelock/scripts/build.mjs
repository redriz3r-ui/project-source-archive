import {build as viteBuild} from 'vite';
import {build} from 'esbuild';
import {mkdir,writeFile,copyFile,readFile} from 'node:fs/promises';
const simulator=process.argv.includes('--simulator');process.env.LIVELOCK_SIMULATOR=simulator?'1':'0';
let campaign='';
if(!simulator&&!process.argv.includes('--unconfigured')){
  try {campaign=JSON.parse(await readFile('config/affiliate.local.json','utf8')).campaign;} catch(error){if(error.code!=='ENOENT')throw error;}
  if(typeof campaign!=='string'||(campaign&&!/^[A-Za-z0-9_-]{1,64}$/.test(campaign)))throw Error('Invalid public affiliate campaign configuration.');
}
const out=process.argv.includes('--unconfigured')?'dist-unconfigured':simulator?'dist-dev':'dist';
process.env.LIVELOCK_OUT_DIR=out;
await viteBuild();
await build({entryPoints:['src/background/index.ts'],outfile:`${out}/background.js`,bundle:true,format:'esm',target:'chrome120',minify:true,define:{__SIMULATOR__:String(simulator),__AFFILIATE_CAMPAIGN__:JSON.stringify(campaign)}});
await build({entryPoints:['src/content/room-guard.ts'],outfile:`${out}/room-guard.js`,bundle:true,format:'iife',target:'chrome120',minify:true});
await mkdir(`${out}/icons`,{recursive:true});
for(const size of [16,32,48,128])await copyFile(`public/icons/icon${size}.png`,`${out}/icons/icon${size}.png`);
const domains=[...new Set([...JSON.parse(await readFile('src/rules/adult-domains.json','utf8')),...JSON.parse(await readFile('src/rules/directory-domains.json','utf8'))])].sort();
const paths=JSON.parse(await readFile('src/rules/blocked-paths.json','utf8'));
const rules=[];
for(let offset=0;offset<domains.length;offset+=100)rules.push({id:rules.length+1,priority:100,action:{type:'block'},condition:{requestDomains:domains.slice(offset,offset+100),resourceTypes:['main_frame','sub_frame']}});
for(const path of paths)rules.push({id:rules.length+1,priority:100,action:{type:'block'},condition:{regexFilter:path.regex,isUrlFilterCaseSensitive:false,resourceTypes:['main_frame','sub_frame']}});
if(rules.length>30000)throw Error('Baseline exceeds guaranteed Chrome static rule budget.');
await writeFile(`${out}/baseline.json`,JSON.stringify(rules));
await mkdir(`${out}/third-party`,{recursive:true});
await copyFile('third-party/blocklistproject-UNLICENSE.txt',`${out}/third-party/blocklistproject-UNLICENSE.txt`);
await copyFile('src/rules/blocklist-metadata.json',`${out}/blocklist-metadata.json`);
await copyFile('src/rules/directory-metadata.json',`${out}/directory-metadata.json`);
const manifest={manifest_version:3,name:simulator?'LiveLock — DEVELOPMENT SIMULATOR':'LiveLock',version:JSON.parse(await readFile('package.json','utf8')).version,minimum_chrome_version:'120',description:simulator?'Development simulation only. Real navigation blocking; synthetic live status.':campaign?'Selective site blocker with official Chaturbate public-room status verification.':'Selective site blocker. Live verification unconfigured; defaults locked.',permissions:['declarativeNetRequest','storage','alarms','webNavigation','tabs'],host_permissions:['https://chaturbate.com/*','https://*.chaturbate.com/*'],background:{service_worker:'background.js',type:'module'},action:{default_popup:'popup.html',default_title:'LiveLock'},options_page:'options.html',icons:Object.fromEntries([16,32,48,128].map(s=>[s,`icons/icon${s}.png`])),content_security_policy:{extension_pages:"script-src 'self'; object-src 'none'; base-uri 'none';"},declarative_net_request:{rule_resources:[{id:'baseline',enabled:true,path:'baseline.json'}]},content_scripts:[{matches:['https://chaturbate.com/*','https://*.chaturbate.com/*'],js:['room-guard.js'],run_at:'document_start',all_frames:true}],web_accessible_resources:[{resources:['blocked.html'],matches:['https://chaturbate.com/*','https://*.chaturbate.com/*']}]};
await writeFile(`${out}/provider.json`,JSON.stringify({type:simulator?'fixture':campaign?'official-affiliate':'unconfigured'}));
await writeFile(`${out}/manifest.json`,JSON.stringify(manifest,null,2));
const bg=await readFile(`${out}/background.js`,'utf8');
if(!simulator&&(bg.includes('fixtureState')||bg.includes('source:"fixture"')))throw Error('Fixture leaked into production');
console.log(`Built ${out}/ (${simulator?'SIMULATOR':campaign?'official Chaturbate API':'unconfigured production'}).`);
