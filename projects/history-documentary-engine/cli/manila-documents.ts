import {createHash} from 'node:crypto';
import {mkdir,readFile,stat,writeFile} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve('public/projects/bombing-of-manila-wwii/04-assets/documents');
const docs=[
  {id:'doc-luzon',name:'us-army-luzon.pdf',url:'https://history.army.mil/Portals/143/Images/Publications/Publication%20By%20Title%20Images/C%20Img/campaigns-wwii/pdf/21.pdf',credit:'U.S. Army Center of Military History'},
  {id:'doc-triumph',name:'triumph-in-the-philippines.pdf',url:'https://history.army.mil/portals/143/Images/Publications/catalog/5-10.pdf',credit:'U.S. Army Center of Military History'},
  {id:'doc-yamashita',name:'yamashita-trial.pdf',url:'https://tile.loc.gov/storage-services/service/ll/llmlp/Yamashita-trial_Vol_21-34_PT-23Nov1945/Yamashita-trial_Vol_21-34_PT-23Nov1945.pdf',credit:'Library of Congress'},
];
const main=async()=>{await mkdir(root,{recursive:true});const records=[];for(const doc of docs){const file=path.join(root,doc.name);let bytes:Buffer;try{if((await stat(file)).size<1000)throw new Error();bytes=await readFile(file);}catch{const response=await fetch(doc.url,{headers:{'User-Agent':'HistoryDocumentaryEngine/0.1'}});if(!response.ok)throw new Error(`${doc.id}: HTTP ${response.status}`);bytes=Buffer.from(await response.arrayBuffer());await writeFile(file,bytes);}records.push({...doc,localPath:`projects/bombing-of-manila-wwii/04-assets/documents/${doc.name}`,contentHash:createHash('sha256').update(bytes).digest('hex'),rightsStatus:'NO_KNOWN_RESTRICTIONS',use:'SOURCE_DOCUMENT'});}await writeFile(path.join(root,'document-ledger.json'),`${JSON.stringify({schemaVersion:1,documents:records},null,2)}\n`);console.log(`PASS: ${records.length} source documents cached`);};
main().catch(error=>{console.error(error instanceof Error?error.message:error);process.exitCode=1;});
