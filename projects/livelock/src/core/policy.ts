export type LiveState = 'live' | 'offline' | 'unknown';
export interface Config { schemaVersion: 1; enabled: boolean; platform: 'chaturbate'; username: string | null; blockedDomains: string[]; strictRoomOnly: true; notifyWhenLive: false; providerBaseUrl: null }
export interface Observation { platform: 'chaturbate'; username: string; state: LiveState; observedAt: string; validUntil: string; source: 'fixture' | 'authorized-affiliate'; reason?: string }
export interface Grant { username: string; expiresAtMs: number; observationAtMs: number; grantedAtMs: number; configRevision: number }
export type UiState = 'unconfigured' | 'checking' | 'locked_offline' | 'locked_unknown' | 'unlocked_live';
export const defaults: Config = {schemaVersion:1,enabled:true,platform:'chaturbate',username:null,blockedDomains:[],strictRoomOnly:true,notifyWhenLive:false,providerBaseUrl:null};
const reserved = new Set(['auth','accounts','affiliates','statsapi','discover','tags','followed-cams','private','female-cams','male-cams','couple-cams','trans-cams','terms','privacy','support']);
export function username(input: string): string {
  let name = input.trim().toLowerCase();
  if (name.includes('://')) {
    const u = new URL(name);
    if(u.protocol !== 'https:' || !['chaturbate.com','www.chaturbate.com'].includes(u.hostname) || u.port || u.username || u.password || u.search || u.hash || !/^\/[a-z0-9_]+\/?$/.test(u.pathname)) throw Error('Use a plain handle or exact HTTPS room URL without query or fragment.');
    name = u.pathname.replace(/^\/|\/$/g,'');
  }
  // Conservative local policy, not a claim about the platform's full naming rules.
  if (!/^[a-z0-9_]{3,30}$/.test(name) || reserved.has(name)) throw Error('Use 3–30 ASCII letters, digits or underscores; site routes are not handles.');
  return name;
}
export function domain(input: string): string {
  const d = input.trim().toLowerCase();
  if(d.length>253 || !/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(d) || d.includes('xn--')) throw Error('Enter a DNS domain, without URL, wildcard, port or path. IDN domains are not supported.');
  return d;
}
export function parseConfig(value: unknown): Config {
  if(!value || typeof value!=='object') return {...defaults};
  const c = value as Partial<Config>;
  try {
    if(c.schemaVersion!==1 || typeof c.enabled!=='boolean' || !Array.isArray(c.blockedDomains) || c.blockedDomains.length>100) return {...defaults};
    return {...defaults,enabled:c.enabled,username:c.username ? username(c.username):null,blockedDomains:[...new Set(c.blockedDomains.map(domain))]};
  } catch {return {...defaults};}
}
export function roomRegex(name: string): string { return '^https://(www\\.)?chaturbate\\.com/'+username(name)+'/(\\?[^#]*)?$'; }
export function canonicalRoom(url: string, name: string): boolean {
  try {const u = new URL(url); return u.protocol==='https:' && ['chaturbate.com','www.chaturbate.com'].includes(u.hostname) && !u.port && !u.username && !u.password && u.pathname===`/${name}/`; } catch {return false;}
}
export function platformUrl(url: string): boolean {try {const h = new URL(url).hostname;return h==='chaturbate.com'||h.endsWith('.chaturbate.com');} catch{return false;}}
export function blockedUrl(url: string, domains: string[]): boolean {try{const h = new URL(url).hostname;return domains.some(d=>h===d||h.endsWith('.'+d));}catch{return false;}}
export function validateObservation(value: unknown, name: string, now: number, simulator: boolean): Observation | null {
  if(!value || typeof value!=='object') return null;
  const o = value as Observation;
  if(o.platform!=='chaturbate' || o.username!==name || !['live','offline','unknown'].includes(o.state) || o.source!==(simulator?'fixture':'authorized-affiliate')) return null;
  if(typeof o.observedAt!=='string'||typeof o.validUntil!=='string') return null;
  const at = Date.parse(o.observedAt), end = Date.parse(o.validUntil);
  if(!Number.isFinite(at)||!Number.isFinite(end)||at>now+5000||at<now-90000||end<=now||end<=at||end-at>90000) return null;
  return o;
}
export function allowed(config: Config, grant: Grant | null, revision: number, now: number): boolean {
  return config.enabled && !!config.username && !!grant && grant.username===config.username && grant.configRevision===revision && grant.expiresAtMs>now && grant.grantedAtMs<=now+5000 && now-grant.observationAtMs<=90000;
}
export function allowRule(name: string): chrome.declarativeNetRequest.Rule {return {id:1,priority:200,action:{type:chrome.declarativeNetRequest.RuleActionType.ALLOW},condition:{regexFilter:roomRegex(name),isUrlFilterCaseSensitive:true,resourceTypes:[chrome.declarativeNetRequest.ResourceType.MAIN_FRAME]}};}
export function denyRules(domains: string[]): chrome.declarativeNetRequest.Rule[] {return domains.map((d,i)=>({id:1000+i,priority:100,action:{type:chrome.declarativeNetRequest.RuleActionType.BLOCK},condition:{requestDomains:[domain(d)],resourceTypes:[chrome.declarativeNetRequest.ResourceType.MAIN_FRAME,chrome.declarativeNetRequest.ResourceType.SUB_FRAME]}}));}
