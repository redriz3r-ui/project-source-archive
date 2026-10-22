import {build} from 'esbuild';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
const name=process.argv[2];
if(!name){console.error('Usage: npm run check:live -- <your-selected-handle>');process.exit(1);}
const {campaign}=JSON.parse(await readFile('config/affiliate.local.json','utf8'));
const bundled=await build({entryPoints:['src/providers/affiliate-provider.ts'],bundle:true,write:false,format:'esm',platform:'node',target:'node22'});
const {AffiliateProvider}=await import('data:text/javascript;base64,'+Buffer.from(bundled.outputFiles[0].text).toString('base64'));
let state={};let requests=0;
const provider=new AffiliateProvider(campaign,{store:{get:async()=>state,set:async value=>{state=value;}},fetch:(...args)=>{requests++;return fetch(...args);}});
const observation=await provider.getStatus(name);
const report={checkedAt:new Date().toISOString(),provider:'official-chaturbate-users-online-v2',requests,observation,streamsFetched:0,cookiesUsed:false};
await mkdir('artifacts',{recursive:true});await writeFile('artifacts/live-verification.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({state:observation.state,reason:observation.reason||null,requests,source:observation.source,report:'artifacts/live-verification.json'}));
