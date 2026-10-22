import './style.css';
import type {Controller} from '../background/controller';
type Snapshot=ReturnType<Controller['snapshot']>;
const $=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T|null;
let snapshot:Snapshot;
async function send(type:string,extra:Record<string,unknown>={}){
  const response=await chrome.runtime.sendMessage({type,...extra});if(!response?.ok)throw Error(response?.error||'Background unavailable; access stays locked.');return response.value as Snapshot;
}
function render(s:Snapshot){
  snapshot=s;$('mode')!.hidden=!s.simulator;$('protection')!.textContent=s.config.enabled?'Protection ON':'Protection OFF — LiveLock is not blocking';
  $('provider')!.textContent=s.simulator?'Simulated verification · development only':s.providerConnected?'Connected to Chaturbate’s official online-room API. Only confirmed public rooms can open.':'Live verification unavailable — blocking still works. Authorized provider not configured.';
  if($('status')){
    $('handle')!.textContent=s.config.username?`@${s.config.username} · Chaturbate`:'No broadcaster selected';
    const labels={unconfigured:'UNCONFIGURED',checking:'CHECKING',locked_offline:'OFFLINE',locked_unknown:'UNKNOWN',unlocked_live:s.canOpen?'LIVE':'UNKNOWN'};
    $('status')!.textContent=(s.config.enabled?labels[s.state]:'UNPROTECTED')+(s.simulator&&s.canOpen?' · SIMULATED':'');if(s.providerConnected&&s.lastObservation?.reason){$('provider')!.textContent+=' '+({ 'not-listed':'Not listed in the online feed; staying locked.', 'not-public':'Room is not public; staying locked.', 'rate-limited':'Waiting before the next API request.', 'scan-limit':'Could not verify within the scan limit; staying locked.', 'timeout':'API request timed out; staying locked.', 'stale':'API response is too old; staying locked.', 'unavailable':'API unavailable; staying locked.', 'access-denied':'API access denied; staying locked.', 'invalid-response':'Invalid API response; staying locked.' }[s.lastObservation.reason]||'Status not confirmed; staying locked.');}
    $('status')!.className='pill'+(s.canOpen?' live':'');
    $('checked')!.textContent=s.lastCheckedAt?`Last check: ${new Date(s.lastCheckedAt).toLocaleTimeString()}`:'No status check yet';
    $<HTMLButtonElement>('open')!.disabled=!s.canOpen;$('manual')!.hidden=!s.manualLock;
  }
  if($('simulator'))$('simulator')!.hidden=!s.simulator;
  if($('blocklist-info'))$('blocklist-info')!.textContent=`Built-in blocking: ${s.blocklist.domainCount.toLocaleString()} domain entries, including ${s.blocklist.directoryDomainCount.toLocaleString()} domains collected from ThePornDude’s directory. Listed domains and their subdomains are blocked in full, including mixed-use sites. Category-list snapshot: ${new Date(s.blocklist.retrievedAt).toLocaleDateString()}.`;
  if($('version'))$('version')!.textContent=`Version ${chrome.runtime.getManifest().version} · ${s.simulator?'Fixture provider (dev)':s.providerConnected?'Official Chaturbate API':'Provider unconfigured'}`;
}
function action(id:string,fn:()=>Promise<unknown>){$(id)?.addEventListener('click',()=>void perform(fn));}
async function perform(fn:()=>Promise<unknown>){$('error')!.textContent='';try{await fn();render(await send('snapshot'));}catch(error){$('error')!.textContent=error instanceof Error?error.message:'Action failed.';}}
action('settings',()=>chrome.runtime.openOptionsPage());action('open',()=>send('open'));action('lock',()=>send('lock'));action('check',()=>send('check'));
action('disable',async()=>{if(!$<HTMLInputElement>('confirm-off')!.checked)throw Error('Check the warning confirmation before disabling protection.');await send('save',{input:{enabled:false,confirmOff:true}});});
action('enable',()=>send('save',{input:{enabled:true}}));
action('apply-fixture',()=>send('fixture',{state:$<HTMLSelectElement>('fixture')!.value}));
$('config-form')?.addEventListener('submit',event=>{event.preventDefault();void perform(async()=>{await send('save',{input:{username:$<HTMLInputElement>('username')!.value,blockedDomains:$<HTMLTextAreaElement>('domains')!.value.split('\n').map(x=>x.trim()).filter(Boolean)}});$('notice')!.textContent='Saved. Room access locked until a fresh check.';});});
void perform(async()=>{
  render(await send('snapshot'));
  if($('username')){$<HTMLInputElement>('username')!.value=snapshot.config.username||'';$<HTMLTextAreaElement>('domains')!.value=snapshot.config.blockedDomains.join('\n');}
});
setInterval(()=>void perform(async()=>render(await send('snapshot'))),2000);
