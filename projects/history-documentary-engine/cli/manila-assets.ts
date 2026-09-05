import {createHash} from 'node:crypto';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';

type Meta=Record<string,{value?:string}>;
type Page={title:string;imageinfo?:Array<{url:string;thumburl?:string;descriptionurl:string;extmetadata?:Meta}>};
const root=path.resolve('public/projects/bombing-of-manila-wwii');
const assetDir=path.join(root,'04-assets/media');
const clean=(value='')=>value.replace(/<[^>]+>/g,'').replace(/&amp;/g,'&').replace(/&#0?39;/g,"'").trim();
const safe=(value:string)=>value.replace(/^File:/,'').replace(/[^a-zA-Z0-9._-]+/g,'-').replace(/-+/g,'-');
const archival=/^(?:File:)?(?:80-G-|Approach to Manila|Bombing campaign|Damage to the Manila Post Office|Fire Damage to the Manila Post Office|Injured POWs|Japanese troops wounded|L5-B air evacuation|Manila capture|Manila Walled City|Manila00[123]|ManilaBilibid|ManilaEscape|ManilaIntramuros|National Assembly building ruins\.jpg|Sixth Army advances|The Capture of Manila)/i;
const federalProvenance=/^(?:File:)?(?:80-G-|Bombing campaign.*NARA|Manila00[123]|ManilaBilibid|ManilaEscape|ManilaIntramuros|Manila Walled City|Damage to the Manila Post Office|Fire Damage to the Manila Post Office)/i;
const roles=(title:string)=>/map|approach|advances/i.test(title)?['LOCATION','EVIDENCE']:/POW|evacuation|escape|prisoner|wounded/i.test(title)?['CHARACTER','EVIDENCE']:/Post Office|Assembly|Walled City|Intramuros|Manila00/i.test(title)?['LOCATION','EVIDENCE']:['ACTION','EVIDENCE'];
const allMoments=Array.from({length:12},(_,i)=>`mc-${String(i+1).padStart(2,'0')}`);
const fetchImage=(url:string)=>fetch(url,{headers:{'User-Agent':'HistoryDocumentaryEngine/0.1 (documentary research; resumable batches)'}});

const main=async()=>{
  await mkdir(assetDir,{recursive:true});
  const params=new URLSearchParams({action:'query',format:'json',origin:'*',generator:'categorymembers',gcmtitle:'Category:Battle of Manila (1945)',gcmtype:'file',gcmlimit:'50',prop:'imageinfo',iiprop:'url|extmetadata',iiurlwidth:'1600'});
  const response=await fetch(`https://commons.wikimedia.org/w/api.php?${params}`,{headers:{'User-Agent':'HistoryDocumentaryEngine/0.1'}});if(!response.ok)throw new Error(`Commons ${response.status}`);
  const data=await response.json() as {query?:{pages?:Record<string,Page>}};
  const pages=Object.values(data.query?.pages??{}).filter(page=>archival.test(page.title)&&/\.(?:jpe?g|png)$/i.test(page.title)).sort((a,b)=>a.title.localeCompare(b.title));
  console.log(`DISCOVERED: ${pages.length} curated category records`);
  const assets=[];const review=[];const hashes=new Set<string>();let newDownloads=0;
  for(const [index,page] of pages.entries()){
    const info=page.imageinfo?.[0];if(!info)continue;const meta=info.extmetadata??{};
    const license=clean(meta.LicenseShortName?.value);const usage=clean(meta.UsageTerms?.value);const permission=clean(meta.Permission?.value);const copyrighted=clean(meta.Copyrighted?.value);const source=clean(meta.Credit?.value||meta.Source?.value);const rightsBlob=[license,usage,permission,copyrighted,source].join(' ');
    const explicitPublicDomain=/public domain|PD-US|PD US|USGov|not copyrighted/i.test(rightsBlob)||copyrighted.toLowerCase()==='false';
    const verifiedFederal=federalProvenance.test(page.title)&&/U\.S\.|United States|Army|Navy|NARA|federal government/i.test(rightsBlob);
    const publicDomain=explicitPublicDomain||verifiedFederal;const cc=/^CC BY/i.test(license);
    if(!publicDomain&&!cc){review.push({title:page.title,itemUrl:info.descriptionurl,license,permission,source});continue;}
    const filename=`${String(index+1).padStart(2,'0')}-${safe(page.title)}`;const localFile=path.join(assetDir,filename);let bytes:Buffer;
    try{bytes=await readFile(localFile);}catch{if(newDownloads>=3){review.push({title:page.title,itemUrl:info.descriptionurl,license,permission:'Deferred to next resumable batch',source});continue;}const image=await fetchImage(info.url);if(!image.ok){review.push({title:page.title,itemUrl:info.descriptionurl,license,permission:`Download HTTP ${image.status}`,source});continue;}bytes=Buffer.from(await image.arrayBuffer());if(bytes.length>25_000_000)continue;await writeFile(localFile,bytes);newDownloads++;}
    const hash=createHash('sha256').update(bytes).digest('hex');if(hashes.has(hash))continue;hashes.add(hash);
    assets.push({schemaVersion:1,id:`manila-${String(assets.length+1).padStart(2,'0')}`,src:`projects/bombing-of-manila-wwii/04-assets/media/${filename}`,itemUrl:info.descriptionurl,imageUrl:info.url,title:page.title.replace(/^File:/,''),date:clean(meta.DateTimeOriginal?.value||meta.DateTime?.value||'1945'),credit:clean(meta.Credit?.value||meta.Artist?.value||'Wikimedia Commons / U.S. military archive'),rightsStatus:publicDomain?'NO_KNOWN_RESTRICTIONS':'LICENSED',rightsText:[license,usage,permission,verifiedFederal?'Verified U.S. federal military provenance':''].filter(Boolean).join(' — '),depicts:[page.title.replace(/^File:/,'')],roles:roles(page.title),storyMoments:allMoments,treatments:['FULL_FRAME','DETAIL','SIDE_BY_SIDE','STAT_OVERLAY'],maxFullFrameUses:1,maxTotalUses:3,contentHash:hash});
  }
  await writeFile(path.join(root,'04-assets/asset-inventory.json'),`${JSON.stringify({schemaVersion:1,provider:'Wikimedia Commons',category:'Battle of Manila (1945)',generatedAt:'2026-08-26T00:00:00.000Z',assets},null,2)}\n`);
  await writeFile(path.join(root,'04-assets/rights-ledger.json'),`${JSON.stringify({schemaVersion:1,assets:assets.map(({id,itemUrl,credit,rightsStatus,rightsText,contentHash})=>({id,itemUrl,credit,rightsStatus,rightsText,contentHash})),review},null,2)}\n`);
  console.log(`${assets.length>=18?'PASS':'IN_PROGRESS'}: ${assets.length} distinct rights-cleared authentic assets; ${newDownloads} acquired this batch; ${review.length} deferred/review`);
};
main().catch(error=>{console.error(error instanceof Error?error.message:error);process.exitCode=1;});
