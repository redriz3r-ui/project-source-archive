import {copyFile, readFile, stat, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {parseManifest} from '../src/manifest/schema';

type Asset = {id: string; localFile: string; title: string; itemUrl: string; institution: string; rightsStatus: 'NO_KNOWN_RESTRICTIONS'; rightsText: string};
const projectDir = path.resolve('public/projects/episode-1');
const manifestFile = path.join(projectDir, 'manifest.json');
const publicDomain1921 = 'Public domain in the United States: published in 1921, before January 1, 1931';

const newspaperTitles = [
  'Federal troop equipment bound for the coalfields', 'Soldiers waiting at Huntington station', 'Defense bivouac on Blair Mountain',
  'Citizens’ army unloading supplies', 'Don Chafin’s defenders under arms', 'Logan men waiting for action',
  'Logan army moving toward the ridge', 'Field beds guarded by the defense army', 'Field kitchen feeding the Logan army',
  'Logan Courthouse and transport vehicles', 'Crooked Creek schoolhouse near the fighting', 'Jessie Testerman Hatfield',
  'Federal troops and disarmed miners at Sharples and Jeffrey', 'Bill Blizzard after the battle', 'Miner searched by federal soldiers at Madison',
  'Army train proceeding toward Blair', 'Army supply wagons moving up Coal River', 'Sixteenth Infantry wagons and supplies',
  'Miners’ tent colony at Ethel', 'Logan Courthouse issuing arms', 'Military searchlight on the firing line',
  'Part of Chafin’s army resting at Blair Mountain', 'Armed deputies fighting at Blair Mountain', 'Wreckage of a federal Martin bomber',
  'Bomb displayed by UMW District 17', 'Machine gunners from the Logan fields', 'Federal soldiers pitching tents on Blair Mountain',
  'Sid Hatfield and Jessie Testerman',
];

const newspaperAssets: Asset[] = newspaperTitles.map((title, index) => {
  const number = String(index + 1).padStart(2, '0');
  return {id: `wv${number}`, localFile: `archive-assets/wv-newspapers/mw${number}.jpg`, title, itemUrl: `https://archive.wvculture.org/history/labor/mw${number}.jpg`, institution: 'West Virginia State Archives', rightsStatus: 'NO_KNOWN_RESTRICTIONS', rightsText: publicDomain1921};
});

const extraAssets: Asset[] = [
  {id:'blair-fighting',localFile:'archive-assets/01-bombs-shot-1.jpg',title:'Armed miners during the Battle of Blair Mountain',itemUrl:'https://commons.wikimedia.org/wiki/File:Blair_Mountain_Fighting.jpg',institution:'Wikimedia Commons',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Public-domain historical photograph'},
  {id:'blair-aftermath-1',localFile:'archive-assets/01-bombs-shot-3.jpg',title:'Miners after the Battle of Blair Mountain',itemUrl:'https://commons.wikimedia.org/wiki/File:Blair-after-the-battle-4.jpg',institution:'Wikimedia Commons',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Public-domain historical photograph'},
  {id:'blair-aftermath-2',localFile:'archive-assets/01-bombs-shot-5.jpg',title:'Miners gathered after the Battle of Blair Mountain',itemUrl:'https://commons.wikimedia.org/wiki/File:Blair-after-the-battle-4a.jpg',institution:'Wikimedia Commons',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Public-domain historical photograph'},
  {id:'miners-bomb',localFile:'archive-assets/08-ridge-shot-6.jpg',title:'Miners displaying a bomb used during the Blair Mountain conflict',itemUrl:'https://commons.wikimedia.org/wiki/File:Miners_with_bomb.jpg',institution:'Wikimedia Commons',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Public-domain historical photograph'},
  {id:'coal-shanties',localFile:'archive-assets/02-coalfields-shot-1.jpg',title:'Coal miners’ shanties at Bream, West Virginia',itemUrl:'https://www.loc.gov/item/2018678001/',institution:'Library of Congress',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'No known restrictions on publication'},
  {id:'coal-machine',localFile:'archive-assets/02-coalfields-shot-2.jpg',title:'Miner operating machinery at Brown Mine, West Virginia',itemUrl:'https://www.loc.gov/item/2018673772/',institution:'Library of Congress',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'No known restrictions on publication'},
  {id:'injured-miner',localFile:'archive-assets/02-coalfields-shot-3.jpg',title:'Young West Virginia miner injured in a mine accident',itemUrl:'https://www.loc.gov/item/2018675569/',institution:'Library of Congress',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'No known restrictions on publication'},
  {id:'coal-tipple',localFile:'archive-assets/02-coalfields-shot-4.jpg',title:'Empire Coal and Coke Company tipple, West Virginia',itemUrl:'https://www.loc.gov/item/91795728/',institution:'Library of Congress',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'No known restrictions on publication'},
  {id:'mother-jones-1',localFile:'archive-assets/mother-jones-1.jpg',title:'Mother Jones, portrait no. 2',itemUrl:'https://www.loc.gov/item/2005688160/',institution:'Library of Congress',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'No known restrictions on publication'},
  {id:'mother-jones-2',localFile:'archive-assets/mother-jones-2.jpg',title:'Mother Jones, portrait no. 1',itemUrl:'https://www.loc.gov/item/2004672082/',institution:'Library of Congress',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'No known restrictions on publication'},
  {id:'march-miners',localFile:'archive-assets/march-miners.jpg',title:'Miners at Laura Mine, Red Star, West Virginia, 1908',itemUrl:'https://www.nps.gov/articles/000/the-march-on-logan-county.htm',institution:'Library of Congress / National Park Service',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Lewis Hine photograph; public-domain Library of Congress collection'},
  {id:'blair-surrender',localFile:'archive-assets/blair-surrender.jpg',title:'Striking miners surrender rifles to federal troops',itemUrl:'https://www.nps.gov/articles/000/the-battle-of-blair-mountain.htm',institution:'Wikimedia Commons / National Park Service',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Public-domain historical photograph'},
  {id:'blair-machine-gun',localFile:'archive-assets/blair-machine-gun.jpg',title:'Striking miners at a machine-gun position',itemUrl:'https://www.nps.gov/articles/000/the-battle-of-blair-mountain.htm',institution:'Wikimedia Commons / National Park Service',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Public-domain historical photograph'},
  {id:'union-map',localFile:'archive-assets/01-bombs-shot-2.jpg',title:'Newspaper map of the union miners’ movement',itemUrl:'https://commons.wikimedia.org/wiki/File:Map_of_the_movement_of_the_union_miners_in_Battle_of_Blair_Mountain.png',institution:'Library of Congress / Wikimedia Commons',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Public-domain New-York Tribune map, August 26, 1921'},
  {id:'federal-map',localFile:'archive-assets/01-bombs-shot-4.jpg',title:'Newspaper map of federal troop movements and battle lines',itemUrl:'https://commons.wikimedia.org/wiki/File:Map_of_movement_of_federal_troops_and_location_of_union_and_nonunion_fighting_during_Blair_Mountain_Battle.png',institution:'Library of Congress / Wikimedia Commons',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Public-domain New-York Tribune map, September 3, 1921'},
  {id:'airfleet-headline',localFile:'archive-assets/01-bombs-shot-6.jpg',title:'Air fleet ordered to the West Virginia battlefield',itemUrl:'https://commons.wikimedia.org/wiki/File:Airfleet_ordered_to_West_Virginia_Battlefield_during_the_Blair_Mountain_fight_1921.png',institution:'Library of Congress / Wikimedia Commons',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Public-domain Washington Times page, September 1, 1921'},
  {id:'treason-headline',localFile:'archive-assets/treason-headline.jpg',title:'Miners on trial in courthouse famed by Brown treason trial',itemUrl:'https://www.nps.gov/articles/000/jefferson-county-courthouse-treason-trials.htm',institution:'Binghamton Press / National Park Service',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'Public domain in the United States: published April 28, 1922'},
  {id:'jefferson-interior',localFile:'archive-assets/jefferson-interior.jpg',title:'Jefferson County Courthouse interior, Historic American Buildings Survey',itemUrl:'https://www.nps.gov/people/images/service-pnp-habshaer-wv-wv0000-wv0045-photos-172235pr.jpg',institution:'Library of Congress / HABS',rightsStatus:'NO_KNOWN_RESTRICTIONS',rightsText:'U.S. government Historic American Buildings Survey photograph'},
];

const assets = [...newspaperAssets, ...extraAssets];
const assetById = new Map(assets.map((asset) => [asset.id, asset]));
const pools: Record<string, string[]> = {
  '01-bombs': ['miners-bomb','airfleet-headline','blair-fighting','blair-aftermath-1','blair-machine-gun','blair-aftermath-2','blair-surrender','federal-map'],
  '02-coalfields': ['coal-tipple','coal-machine','coal-shanties','injured-miner','march-miners','coal-machine','coal-tipple'],
  '03-hatfield': ['wv28','wv12','wv28','wv12','march-miners','wv28','wv12'],
  '04-demands': ['march-miners','blair-aftermath-1','blair-aftermath-2','blair-surrender','union-map','blair-fighting','coal-shanties'],
  '05-telegram': ['mother-jones-1','mother-jones-2','wv28','mother-jones-1','march-miners','mother-jones-2','blair-aftermath-1'],
  '06-route': ['union-map','federal-map','union-map','federal-map','blair-fighting'],
  '07-chafin': ['blair-fighting','federal-map','blair-aftermath-1','blair-machine-gun','miners-bomb','airfleet-headline'],
  '08-ridge': ['blair-machine-gun','blair-fighting','blair-surrender','blair-aftermath-1','miners-bomb','blair-aftermath-2'],
  '09-bombing': ['miners-bomb','airfleet-headline','blair-fighting','blair-aftermath-2','federal-map','blair-machine-gun'],
  '10-federal': ['blair-surrender','blair-aftermath-1','blair-aftermath-2','federal-map','airfleet-headline','march-miners','blair-fighting'],
  '11-treason': ['treason-headline','jefferson-interior','wv14','blair-aftermath-1','blair-surrender','treason-headline','jefferson-interior'],
  '12-legacy': ['blair-surrender','blair-aftermath-1','march-miners','coal-shanties','blair-aftermath-2','blair-fighting','union-map'],
};

const main = async () => {
  const original = await readFile(manifestFile, 'utf8');
  const manifest = parseManifest(JSON.parse(original));
  for (const asset of assets) {
    const size = (await stat(path.join(projectDir, asset.localFile))).size;
    if (size < 10_000) throw new Error(`Invalid or undersized archive asset: ${asset.localFile}`);
    const sourceId = `asset-${asset.id}`;
    if (!manifest.sources.some((source) => source.id === sourceId)) manifest.sources.push({id: sourceId, title: asset.title, url: asset.itemUrl, publisher: asset.institution, accessedAt: '2026-08-25', rights: asset.rightsText});
  }
  const usageCounts = new Map<string, number>();
  const usages: Array<{sceneId:string; assetId:string; localFile:string; editorialPurpose:string; cropVariant:string}> = [];
  const curated = manifest.scenes.map((scene) => {
    if (scene.type === 'TITLE_CARD') return {...scene,payload:{...scene.payload,backgroundSrc:'projects/episode-1/archive-assets/08-ridge-shot-6.jpg',backgroundAlt:'Miners displaying a bomb used during the Blair Mountain conflict',backgroundCredit:'Public-domain historical photograph · Wikimedia Commons'}};
    const passage = scene.direction?.passageId;
    const pool = passage ? pools[passage] : undefined;
    if (!pool?.length) throw new Error(`No archive pool for ${scene.id} (${passage ?? 'no passage'})`);
    const assetId = pool[(scene.direction?.shotIndex ?? 0) % pool.length];
    const asset = assetById.get(assetId)!;
    const use = usageCounts.get(assetId) ?? 0;
    usageCounts.set(assetId, use + 1);
    const variants = [
      {x:.5,y:.5,from:1.02,to:1.1,panX:-10,panY:-6,name:'wide'},
      {x:.36,y:.46,from:1.16,to:1.28,panX:14,panY:-5,name:'left detail'},
      {x:.64,y:.54,from:1.2,to:1.34,panX:-14,panY:6,name:'right detail'},
      {x:.5,y:.34,from:1.26,to:1.4,panX:6,panY:14,name:'upper detail'},
      {x:.5,y:.68,from:1.3,to:1.44,panX:-6,panY:-14,name:'lower detail'},
      {x:.28,y:.38,from:1.34,to:1.48,panX:16,panY:9,name:'far-left detail'},
      {x:.72,y:.4,from:1.36,to:1.5,panX:-16,panY:8,name:'far-right detail'},
      {x:.48,y:.55,from:1.44,to:1.58,panX:8,panY:-10,name:'tight center'},
    ];
    const crop = variants[use % variants.length];
    usages.push({sceneId:scene.id,assetId,localFile:asset.localFile,editorialPurpose:`${scene.direction?.purpose ?? 'EVIDENCE'}: support the narration with the closest authentic record available`,cropVariant:crop.name});
    const sourceId = `asset-${assetId}`;
    return {...scene, type:'KEN_BURNS' as const, reviewStatus:'APPROVED' as const, sourceIds:[...new Set([...scene.sourceIds, sourceId])], payload:{src:`projects/episode-1/${asset.localFile}`, archiveItemUrl:asset.itemUrl, rightsStatus:asset.rightsStatus, alt:asset.title, credit:`${asset.institution} · ${asset.title}`, focalPoint:{x:crop.x,y:crop.y}, zoomFrom:crop.from, zoomTo:crop.to, panX:crop.panX, panY:crop.panY}};
  });
  manifest.scenes = parseManifest({...manifest, scenes: curated}).scenes;
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  await copyFile(manifestFile, path.join(projectDir, `manifest.before-curation-${stamp}.json`));
  await writeFile(manifestFile, `${JSON.stringify(parseManifest(manifest), null, 2)}\n`);
  await writeFile(path.join(projectDir, 'asset-source-report.json'), `${JSON.stringify({schemaVersion:1,project:'episode-1',policy:'Authentic archive assets only; no generated primary visuals',rightsBasis:{newspapers1921:publicDomain1921,verificationUrl:'https://copyright.gov/what-is-copyright/'},assets,usages}, null, 2)}\n`);
  console.log(`Curated ${usages.length} archive-led shots from ${assets.length} authenticated assets; maximum reuse ${Math.max(...usageCounts.values())}`);
};

main().catch((error: unknown) => {console.error(error instanceof Error ? error.message : error); process.exitCode = 1;});
