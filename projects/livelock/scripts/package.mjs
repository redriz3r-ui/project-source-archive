import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
await mkdir('artifacts',{recursive:true});
const version=JSON.parse(await readFile('package.json','utf8')).version;
const connected=JSON.parse(await readFile('dist/provider.json','utf8')).type==='official-affiliate';
for(const [dir,name] of [['dist',`livelock-${version}-${connected?'connected':'unconfigured'}`],['dist-dev',`livelock-${version}-simulator`]]){
  const path=`artifacts/${name}.zip`;execFileSync('/usr/bin/zip',['-qr','-FS',path,dir]);
  const hash=createHash('sha256').update(await readFile(path)).digest('hex');await writeFile(`${path}.sha256`,`${hash}  ${name}.zip\n`);
}
