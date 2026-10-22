import {readFile,writeFile} from 'node:fs/promises';
import {URL} from 'node:url';
import {setTimeout as pause} from 'node:timers/promises';
const unresolved=JSON.parse(await readFile('/private/tmp/livelock-tpd-unresolved.json','utf8'));
const output='/private/tmp/livelock-tpd-resolved.json';
let saved={};try{saved=JSON.parse(await readFile(output,'utf8'));}catch{/* Fresh run. */}
const queue=[...new Set(unresolved.map(r=>r.destination))].filter(url=>{try{return new URL(url).hostname==='pdude.link'&&!saved[url];}catch{return false;}});
let index=0;let done=0;let stopped=false;
async function worker(){while(index<queue.length&&!stopped){const url=queue[index++];let target=url;const redirects=[];let status=0;try{for(let hop=0;hop<4;hop++){const response=await fetch(target,{method:'HEAD',redirect:'manual',credentials:'omit',referrerPolicy:'no-referrer',signal:AbortSignal.timeout(10000)});status=response.status;if(status===429){stopped=true;break;}const location=response.headers.get('location');if(!location)break;target=new URL(location,target).href;if(!['http:','https:'].includes(new URL(target).protocol))break;redirects.push(target);if(new URL(target).hostname!=='pdude.link')break;}saved[url]={status,redirects};}catch(error){saved[url]={status,redirects,error:error.name};}done++;if(done%100===0){await writeFile(output,JSON.stringify(saved));console.log(JSON.stringify({resolved:done,total:queue.length,rateLimited:stopped}));}await pause(150);}}
await Promise.all(Array.from({length:4},worker));await writeFile(output,JSON.stringify(saved));console.log(JSON.stringify({finished:!stopped,processed:done,total:queue.length,rateLimited:stopped}));
