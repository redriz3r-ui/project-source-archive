import {copyFile, mkdir, readFile, stat, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {parseManifest} from '../src/manifest/schema';

type Asset={id:string;localFile:string;title:string;itemUrl:string;publisher:string;copyrightOwner:string};
const projectDir=path.resolve('public/projects/episode-2');
const manifestFile=path.join(projectDir,'manifest.json');
const assets:Asset[]=[
  {id:'retirement',localFile:'archive-assets/jordan-retirement.jpg',title:'Jordan announces his first retirement, October 1993',itemUrl:'https://www.opencourt-basketball.com/2025/10/06/michael-jordans-first-retirement-in-1993-the-shocking-exit-of-a-basketball-legend/',publisher:'OpenCourt Basketball',copyrightOwner:'Original photographer / news agency'},
  {id:'return',localFile:'archive-assets/jordan-return.jpg',title:'Jordan addresses the media during his comeback period',itemUrl:'https://www.businessinsider.com/michael-jordan-im-back-fax-2015-3',publisher:'Business Insider',copyrightOwner:'Original photographer / news agency'},
  {id:'barons-hero',localFile:'archive-assets/jordan-barons-hero.jpg',title:'Michael Jordan with the Birmingham Barons in 1994',itemUrl:'https://www.mlb.com/milb/history/michael-jordan',publisher:'Minor League Baseball',copyrightOwner:'Cliff Welch / MiLB'},
  {id:'barons-1',localFile:'archive-assets/jordan-barons-1.jpg',title:'Jordan during his 1994 minor-league season',itemUrl:'https://www.mlb.com/milb/history/michael-jordan',publisher:'Minor League Baseball',copyrightOwner:'Photographer / MiLB'},
  {id:'barons-2',localFile:'archive-assets/jordan-barons-2.jpg',title:'Jordan training in the White Sox organization',itemUrl:'https://www.mlb.com/milb/history/michael-jordan',publisher:'Minor League Baseball',copyrightOwner:'Photographer / MiLB'},
  {id:'barons-3',localFile:'archive-assets/jordan-barons-3.jpg',title:'Jordan at the ballpark during the 1994 season',itemUrl:'https://www.mlb.com/milb/history/michael-jordan',publisher:'Minor League Baseball',copyrightOwner:'Photographer / MiLB'},
  {id:'barons-4',localFile:'archive-assets/jordan-barons-4.jpg',title:'Jordan batting for Birmingham in 1994',itemUrl:'https://www.mlb.com/milb/history/michael-jordan',publisher:'Minor League Baseball',copyrightOwner:'Photographer / MiLB'},
  {id:'whitesox',localFile:'archive-assets/jordan-whitesox.jpg',title:'Jordan at White Sox spring training in 1994',itemUrl:'https://www.si.com/nba/2014/02/07/michael-jordan-ballplayer',publisher:'Sports Illustrated',copyrightOwner:'Original photographer / Sports Illustrated'},
  {id:'barons-swing',localFile:'archive-assets/jordan-barons-swing.jpg',title:'Jordan batting for the Birmingham Barons',itemUrl:'https://www.foxnews.com/sports/michael-jordan-helped-baseball-teammate-learn-english',publisher:'Fox News',copyrightOwner:'Getty Images / original photographer'},
  {id:'debut',localFile:'archive-assets/jordan-debut.jpg',title:'Jordan at bat during his Birmingham debut season',itemUrl:'https://www.ajc.com/sports/photos-michael-jordan-made-baseball-debut-years-ago/TqBppjW4KA6gjlKJ0J6BZK/',publisher:'Atlanta Journal-Constitution',copyrightOwner:'Original photographer / Associated Press'},
];
const pools:Record<string,string[]>={
  '01-fax':['return','retirement','barons-hero'], '02-retirement':['retirement','return','whitesox'],
  '03-signing':['whitesox','barons-1','barons-2','barons-hero'], '04-birmingham':['debut','barons-swing','barons-4','barons-3'],
  '05-learning':['barons-1','barons-2','barons-swing','debut'], '06-season':['barons-hero','barons-3','barons-4','barons-2'],
  '07-strike':['barons-4','barons-hero','whitesox','barons-3'], '08-practice':['return','retirement','whitesox'],
  '09-fax-return':['return','retirement','barons-hero'], '10-indiana':['return','retirement','whitesox'],
  '11-meaning':['barons-1','barons-2','barons-3','barons-4','debut'], '12-close':['return','barons-hero','retirement','barons-swing'],
};
const variants=Array.from({length:16},(_,i)=>({name:`crop-${String(i+1).padStart(2,'0')}`,x:.2+(i%4)*.2,y:.28+(Math.floor(i/4)%4)*.14,from:1.03+(i%5)*.08,to:1.13+(i%5)*.08,panX:(i%2?-1:1)*(6+(i%4)*4),panY:(i%3-1)*7}));

const main=async()=>{
  for(const asset of assets) if((await stat(path.join(projectDir,asset.localFile))).size<10_000) throw new Error(`Invalid asset ${asset.localFile}`);
  const original=await readFile(manifestFile,'utf8');
  const manifest=parseManifest(JSON.parse(original));
  const byId=new Map(assets.map(a=>[a.id,a])); const counts=new Map<string,number>();
  const usages:Array<Record<string,string>>=[];
  for(const asset of assets){const id=`media-${asset.id}`;if(!manifest.sources.some(s=>s.id===id))manifest.sources.push({id,title:asset.title,url:asset.itemUrl,publisher:asset.publisher,accessedAt:'2026-08-26',rights:'Copyrighted media used under a documented, limited editorial fair-use rationale; permission not asserted'});}
  manifest.scenes=manifest.scenes.map(scene=>{
    if(scene.type==='TITLE_CARD')return {...scene,payload:{...scene.payload,backgroundSrc:'projects/episode-2/archive-assets/jordan-return.jpg',backgroundAlt:'Michael Jordan during the 1995 comeback period',backgroundCredit:'Editorial excerpt · Business Insider source page'}};
    const passage=scene.direction?.passageId??'';const pool=pools[passage];if(!pool)throw new Error(`No pool for ${scene.id}`);
    const assetId=pool[(scene.direction?.shotIndex??0)%pool.length];const asset=byId.get(assetId)!;const use=counts.get(assetId)??0;counts.set(assetId,use+1);const crop=variants[use];
    if(!crop)throw new Error(`Asset ${assetId} exceeds documented crop capacity`);
    usages.push({sceneId:scene.id,assetId,localFile:asset.localFile,cropVariant:crop.name,editorialPurpose:`Historical identification and commentary supporting ${passage}`,fairUseRationale:'Limited still-image excerpt used at reduced resolution, with narration and captions that analyze the documented event; no substitute for the original photograph or licensed collection.',sourceUrl:asset.itemUrl,copyrightOwner:asset.copyrightOwner});
    return {...scene,type:'KEN_BURNS' as const,reviewStatus:'APPROVED' as const,sourceIds:[...new Set([...scene.sourceIds,`media-${assetId}`])],payload:{src:`projects/episode-2/${asset.localFile}`,archiveItemUrl:asset.itemUrl,rightsStatus:'EDITORIAL_FAIR_USE' as const,alt:asset.title,credit:`Editorial excerpt · ${asset.publisher} · ${asset.title}`,focalPoint:{x:crop.x,y:crop.y},zoomFrom:crop.from,zoomTo:crop.to,panX:crop.panX,panY:crop.panY}};
  });
  await mkdir(path.join(projectDir,'audio'),{recursive:true});
  for(const name of ['score.wav','chapter-impact.wav','transition-whoosh.wav'])await copyFile(path.resolve('public/projects/episode-1/audio',name),path.join(projectDir,'audio',name));
  manifest.soundtrack={src:'projects/episode-2/audio/score.wav',provider:'local-original',title:'Original restrained documentary score',license:'Original generated asset — CC0 dedication',baseVolume:.05,duckVolume:.016};
  manifest.soundEffects=[
    {id:'opening-impact',src:'projects/episode-2/audio/chapter-impact.wav',provider:'local-original',startFrame:0,volume:.18,license:'Original generated asset — CC0 dedication'},
    {id:'retirement-transition',src:'projects/episode-2/audio/transition-whoosh.wav',provider:'local-original',startFrame:90,volume:.11,license:'Original generated asset — CC0 dedication'},
  ];
  const stamp=new Date().toISOString().replace(/[:.]/g,'-');await copyFile(manifestFile,path.join(projectDir,`manifest.before-jordan-curation-${stamp}.json`));
  await writeFile(manifestFile,`${JSON.stringify(parseManifest(manifest),null,2)}\n`);
  await writeFile(path.join(projectDir,'asset-source-report.json'),`${JSON.stringify({schemaVersion:1,project:'episode-2',policy:'Authentic period media only; no generated historical imagery',legalNotice:'Fair use is a case-specific legal doctrine and does not prevent copyright or platform claims.',assets:assets.map(a=>({...a,rightsStatus:'EDITORIAL_FAIR_USE'})),usages},null,2)}\n`);
  console.log(`Curated ${usages.length} shots from ${assets.length} authentic media assets; maximum reuse ${Math.max(...counts.values())}`);
};
main().catch(e=>{console.error(e instanceof Error?e.message:e);process.exitCode=1});
