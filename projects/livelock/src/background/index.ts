import {Controller} from './controller';
import {UnconfiguredProvider} from '../providers/interface';
import {AffiliateProvider} from '../providers/affiliate-provider';
import {FixtureProvider} from '../providers/fixture-provider.dev';
import {allowed,canonicalRoom} from '../core/policy';
const controller=new Controller(__SIMULATOR__?new FixtureProvider():__AFFILIATE_CAMPAIGN__?new AffiliateProvider(__AFFILIATE_CAMPAIGN__):new UnconfiguredProvider(),__SIMULATOR__,Boolean(__AFFILIATE_CAMPAIGN__)&&!__SIMULATOR__);
const ready=controller.boot();
function run(job:()=>Promise<unknown>){void ready.then(job).catch(async()=>{await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds:[1]}).catch(()=>{});});}
// Register synchronously before any await; MV3 can dispatch events during startup.
chrome.runtime.onInstalled.addListener(()=>run(()=>controller.reconcile()));
chrome.runtime.onStartup.addListener(()=>run(()=>controller.reconcile()));
chrome.alarms.onAlarm.addListener(alarm=>run(async()=>{await controller.reconcile();if(alarm.name==='poll')await controller.poll();}));
chrome.tabs.onActivated.addListener(()=>run(()=>controller.reconcile()));
chrome.tabs.onUpdated.addListener((_id,change)=>{if(change.url||change.status==='loading')run(()=>controller.reconcile());});
chrome.windows.onFocusChanged.addListener(()=>run(()=>controller.reconcile()));
chrome.webNavigation.onCommitted.addListener(d=>{if(d.frameId===0)run(()=>controller.reconcile());});
chrome.webNavigation.onHistoryStateUpdated.addListener(d=>{if(d.frameId===0)run(()=>controller.reconcile());});
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  void ready.then(async()=>{
    if(message?.type==='guard'){
      await controller.reconcile();const s=controller.snapshot();
      const access=!s.config.enabled || (s.canOpen&&canonicalRoom(sender.url||'',s.config.username!));
      return {allowed:access,enabled:s.config.enabled,expiresAtMs:s.grant?.expiresAtMs??0};
    }
    if(message?.type==='blocked-status'){
      if(sender.id!==chrome.runtime.id||sender.url!==chrome.runtime.getURL('blocked.html')||sender.frameId!==0) return {username:null,enabled:true,canOpen:false,manualLock:false,state:'unconfigured',simulator:false};
      const status=await controller.reconcile();
      return {username:status.config.username,enabled:status.config.enabled,canOpen:status.canOpen,manualLock:status.manualLock,state:status.state,simulator:status.simulator};
    }
    const trusted=sender.id===chrome.runtime.id&&[chrome.runtime.getURL('popup.html'),chrome.runtime.getURL('options.html')].includes(sender.url||'');
    if(!trusted)throw Error('Untrusted control request.');
    switch(message?.type){
      case 'snapshot':return controller.reconcile();
      case 'save':return controller.save(message.input||{});
      case 'lock':return controller.lock();
      case 'check':return controller.poll(true);
      case 'fixture':
        if(!__SIMULATOR__||!['live','offline','unknown'].includes(message.state))throw Error('Simulator unavailable.');
        await controller.lock();await chrome.storage.local.set({fixtureState:message.state});return controller.snapshot();
      case 'open':return controller.serial(async()=>{
        if(!allowed(controller.config,controller.grant,controller.revision,Date.now()))throw Error('Room is locked.');
        await chrome.tabs.create({url:`https://chaturbate.com/${controller.config.username}/`});return controller.snapshot();
      });
      default:throw Error('Unknown action.');
    }
  }).then(value=>reply({ok:true,value})).catch(async error=>{
    await chrome.declarativeNetRequest.updateSessionRules({removeRuleIds:[1]}).catch(()=>{});
    controller.grant=null;reply({ok:false,error:error instanceof Error?error.message:'Operation failed; access locked.'});
  });return true;
});
