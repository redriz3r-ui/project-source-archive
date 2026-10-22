import {describe,it,expect,vi,beforeEach,afterEach} from 'vitest';
import {username,domain,canonicalRoom,roomRegex,validateObservation,allowed,defaults,parseConfig} from '../src/core/policy';
import {GatewayProvider} from '../src/providers/gateway-provider';
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});
const now=Date.parse('2026-10-22T17:00:00Z');
const observation=(patch:Record<string,unknown>={})=>({platform:'chaturbate',username:'sample_handle',state:'live',source:'authorized-affiliate',observedAt:new Date(now).toISOString(),validUntil:new Date(now+90000).toISOString(),...patch});
describe('input and URL boundary',()=>{
  it.each(['Sample_Handle',' https://www.chaturbate.com/Sample_Handle/ '])('normalizes %s',input=>expect(username(input)).toBe('sample_handle'));
  it.each(['https://chaturbate.com.evil.test/sample_handle/','https://evilchaturbate.com/sample_handle/','https://chaturbate.com@evil.test/sample_handle/','https://chaturbate.com/sample_handle/other/','https://chaturbate.com/sample_handle/?x=1','https://chaturbate.com/sample_handle/#hash','http://chaturbate.com/sample_handle/','https://chaturbate.com:444/sample_handle/','https://chaturbate.com/%73ample_handle/','ab','a.*','discover','éabc','a/b'])('rejects %s',input=>expect(()=>username(input)).toThrow());
  it.each(['*.example.com','https://example.com','a..com','xn--abc.com','localhost','127.0.0.1','evil.com/a','-bad.com'])('rejects domain %s',input=>expect(()=>domain(input)).toThrow());
  it('domains and corrupted config fail safely',()=>{expect(domain(' EXAMPLE.COM ')).toBe('example.com');expect(parseConfig({enabled:false})).toEqual(defaults);});
  it('exact rule has main URL boundaries',()=>{
    const re=new RegExp(roomRegex('sample_handle'));
    for(const u of ['https://chaturbate.com/sample_handle/','https://www.chaturbate.com/sample_handle/?x=y'])expect(re.test(u)).toBe(true);
    for(const u of ['https://chaturbate.com/','https://chaturbate.com/sample_handle2/','https://m.chaturbate.com/sample_handle/','https://chaturbate.com/sample_handle/x','http://chaturbate.com/sample_handle/'])expect(re.test(u)).toBe(false);
    expect(canonicalRoom('https://chaturbate.com/sample_handle/?x=1#ok','sample_handle')).toBe(true);
    expect(canonicalRoom('https://chaturbate.com/other/','sample_handle')).toBe(false);
  });
});
describe('provider trust',()=>{
  it('accepts fresh exact authorized LIVE',()=>expect(validateObservation(observation(),'sample_handle',now,false)?.state).toBe('live'));
  it.each([{username:'other'},{platform:'other'},{source:'fixture'},{state:'LIVE'},{observedAt:new Date(now-91000).toISOString()},{observedAt:new Date(now+6000).toISOString()},{validUntil:new Date(now).toISOString()},{validUntil:new Date(now+91000).toISOString()},{observedAt:'nope'},{validUntil:42}])('rejects invalid observation %j',patch=>expect(validateObservation(observation(patch),'sample_handle',now,false)).toBeNull());
  it('fixture source requires simulator flag',()=>{expect(validateObservation(observation({source:'fixture'}),'sample_handle',now,true)).not.toBeNull();expect(validateObservation(observation(),'sample_handle',now,true)).toBeNull();});
  it('expiry, revision and disabled configuration lock',()=>{const c={...defaults,username:'sample_handle'};const g={username:'sample_handle',configRevision:2,grantedAtMs:now,observationAtMs:now,expiresAtMs:now+90000};expect(allowed(c,g,2,now)).toBe(true);expect(allowed(c,g,3,now)).toBe(false);expect(allowed(c,g,2,now+90000)).toBe(false);expect(allowed({...c,enabled:false},g,2,now)).toBe(false);});
});
describe('future gateway defensive client',()=>{
  beforeEach(()=>{vi.useFakeTimers();vi.setSystemTime(now);});
  it.each([429,500])('fails closed for HTTP %i',async status=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}',{status})));expect((await new GatewayProvider('https://gateway.example').getStatus('sample_handle')).state).toBe('unknown');});
  it.each(['bad-json','wrong-user','throw','stale','malformed'])('fails closed for %s',async kind=>{
    vi.stubGlobal('fetch',vi.fn(async()=>{if(kind==='throw')throw Error('timeout');return new Response(kind==='bad-json'?'not json':JSON.stringify(kind==='malformed'?{}:observation(kind==='wrong-user'?{username:'other'}:{validUntil:new Date(now-1).toISOString()})));}));expect((await new GatewayProvider('https://gateway.example',10).getStatus('sample_handle')).state).toBe('unknown');
  });
  it('aborts an actual pending fetch via its timeout signal',async()=>{vi.useRealTimers();vi.stubGlobal('fetch',vi.fn((_url:URL,options:RequestInit)=>new Promise((_resolve,reject)=>{options.signal!.addEventListener('abort',()=>reject(options.signal!.reason));})));expect((await new GatewayProvider('https://gateway.example',10).getStatus('sample_handle')).state).toBe('unknown');});
  it('requests only the pinned HTTPS origin, omitting credentials',async()=>{const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify(observation())));vi.stubGlobal('fetch',fetch);expect((await new GatewayProvider('https://gateway.example').getStatus('sample_handle')).state).toBe('live');expect(fetch.mock.calls[0][1].credentials).toBe('omit');expect(()=>new GatewayProvider('http://gateway.example')).toThrow();});
});
