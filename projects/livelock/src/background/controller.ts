import {builtinBlockedUrl,blocklistInfo} from '../core/blocklist';
import {defaults,parseConfig,allowed,allowRule,denyRules,validateObservation,platformUrl,canonicalRoom,blockedUrl,username,domain,type Config,type Grant,type Observation,type UiState} from '../core/policy';
import type {LiveStatusProvider} from '../providers/interface';
export class Controller {
  config:Config={...defaults}; revision=0; grant:Grant|null=null; observation:Observation|null=null; state:UiState='unconfigured'; manualLock=false; lastCheckedAt:number|null=null; error='';
  private epoch=0; private queue:Promise<unknown>=Promise.resolve(); private lastAttempt=0;
  constructor(private provider:LiveStatusProvider,public simulator:boolean,public providerConnected=false){}
  serial<T>(fn:()=>Promise<T>):Promise<T>{const p=this.queue.then(fn);this.queue=p.catch(()=>{});return p;}
  snapshot(){return {config:this.config,configRevision:this.revision,grant:this.grant,lastObservation:this.observation,state:this.state,manualLock:this.manualLock,lastCheckedAt:this.lastCheckedAt,lastError:this.error,simulator:this.simulator,providerConnected:this.providerConnected,blocklist:blocklistInfo,canOpen:allowed(this.config,this.grant,this.revision,Date.now())};}
  async persist(){await chrome.storage.local.set({...this.snapshot()});}
  async revoke(){await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds:[1]});this.grant=null;}
  async boot(){await this.serial(async()=>{
    await chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
    const data=await chrome.storage.local.get(['config','configRevision','manualLock']);this.config=parseConfig(data.config);this.revision=typeof data.configRevision==='number'&&Number.isSafeInteger(data.configRevision)?data.configRevision:0;this.manualLock=data.manualLock===true;
    await this.revoke(); await this.syncDeny();this.state=this.config.username?'locked_unknown':'unconfigured';await this.persist();await this.guardTabs();
    await chrome.alarms.create('poll',{periodInMinutes:1});await chrome.alarms.create('lease',{periodInMinutes:0.5});
  });}
  async syncDeny(){
    if(this.config.enabled) await chrome.declarativeNetRequest.updateEnabledRulesets({enableRulesetIds:['baseline']});
    const old=await chrome.declarativeNetRequest.getDynamicRules();await chrome.declarativeNetRequest.updateDynamicRules({removeRuleIds:old.map(r=>r.id),addRules:this.config.enabled?denyRules(this.config.blockedDomains):[]});
    if(!this.config.enabled) await chrome.declarativeNetRequest.updateEnabledRulesets({disableRulesetIds:['baseline']});
  }
  async guardTabs(){
    if(!this.config.enabled)return;
    const good=allowed(this.config,this.grant,this.revision,Date.now());
    for(const tab of await chrome.tabs.query({})){
      const url=tab.pendingUrl||tab.url||'';
      if(tab.id && ((platformUrl(url)||builtinBlockedUrl(url)||blockedUrl(url,this.config.blockedDomains))&&!(good&&canonicalRoom(url,this.config.username!)))){
        await chrome.tabs.update(tab.id,{url:chrome.runtime.getURL('blocked.html')}).catch(()=>{});
      }
    }
  }
  async reconcile(){return this.serial(async()=>{
    if(this.grant&&!allowed(this.config,this.grant,this.revision,Date.now())){++this.epoch;await this.revoke();this.state='locked_unknown';await this.persist();}
    await this.guardTabs();return this.snapshot();
  });}
  async save(input:{username?:string;blockedDomains?:string[];enabled?:boolean;confirmOff?:boolean}){
    ++this.epoch;
    return this.serial(async()=>{
      const next={...this.config};
      if(input.username!==undefined){if(typeof input.username!=='string')throw Error('Invalid handle');next.username=input.username.trim()?username(input.username):null;}
      if(input.blockedDomains!==undefined){if(!Array.isArray(input.blockedDomains)||input.blockedDomains.length>100)throw Error('Maximum 100 custom domains.');next.blockedDomains=[...new Set(input.blockedDomains.map(domain))];}
      if(input.enabled!==undefined){if(typeof input.enabled!=='boolean')throw Error('Invalid protection setting');if(!input.enabled&&!input.confirmOff)throw Error('Confirm protection OFF in Settings.');next.enabled=input.enabled;}
      await this.revoke();this.config=next;this.revision++;this.observation=null;this.state=next.username?'locked_unknown':'unconfigured';this.manualLock=false;this.error='';await this.persist();await this.syncDeny();await this.guardTabs();return this.snapshot();
    });
  }
  async lock(){++this.epoch;return this.serial(async()=>{await this.revoke();this.manualLock=true;this.state=this.config.username?'locked_unknown':'unconfigured';await this.persist();await this.guardTabs();return this.snapshot();});}
  async poll(manual=false){
    // Repeated UI clicks during the cooldown must not invalidate an in-flight check.
    if(Date.now()-this.lastAttempt<5000)return this.snapshot();
    const token=++this.epoch;
    const request=await this.serial(async()=>{
      if(!this.config.enabled||!this.config.username||(!manual&&this.manualLock)||Date.now()-this.lastAttempt<5000)return null;
      this.lastAttempt=Date.now();if(manual)this.manualLock=false;
      this.state='checking';await this.persist();return {name:this.config.username,revision:this.revision};
    });
    if(!request)return this.snapshot();
    let response:unknown;try{response=await this.provider.getStatus(request.name);}catch{response=null;}
    return this.serial(async()=>{
      if(token!==this.epoch||request.revision!==this.revision)return this.snapshot();
      const now=Date.now();const o=validateObservation(response,request.name,now,this.simulator);
      // Revoke before considering the next grant. Never keep a previous LIVE on failure.
      await this.revoke();this.observation=o;this.lastCheckedAt=now;this.error=o?'':'Live verification unavailable or invalid.';
      this.state=o?.state==='offline'?'locked_offline':'locked_unknown';
      if(o?.state==='live'&&this.config.enabled&&!this.manualLock){
        const rule=allowRule(request.name);const supported=await chrome.declarativeNetRequest.isRegexSupported({regex:rule.condition.regexFilter!,isCaseSensitive:true});
        if(supported.isSupported&&token===this.epoch){await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds:[1],addRules:[rule]});this.grant={username:request.name,grantedAtMs:now,observationAtMs:Date.parse(o.observedAt),expiresAtMs:Math.min(Date.parse(o.validUntil),now+90000),configRevision:this.revision};this.state='unlocked_live';if(token!==this.epoch){await this.revoke();this.state='locked_unknown';}}
      }
      await this.persist();await this.guardTabs();return this.snapshot();
    });
  }
}
