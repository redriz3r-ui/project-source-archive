import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest';
import {AffiliateProvider,type AffiliateStore} from '../src/providers/affiliate-provider';
const selected='sample_handle';
let saved:Awaited<ReturnType<AffiliateStore['get']>>;
const store:AffiliateStore={get:async()=>saved,set:async value=>{saved=value;}};
const payload=(rows:unknown[],count=rows.length)=>({count,results:rows});
const entry=(name=selected,current_show='public')=>({username:name,current_show});
function response(body:unknown,headers:Record<string,string>={},status=200){return new Response(typeof body==='string'?body:JSON.stringify(body),{status,headers:{'content-type':'application/json',date:new Date().toUTCString(),...headers}});}
function provider(fetcher:typeof fetch){return new AffiliateProvider('example_campaign',{store,fetch:fetcher,pause:async()=>{}});}
beforeEach(()=>{vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-22T18:00:00Z'));saved={};});
afterEach(()=>vi.useRealTimers());
describe('official affiliate v2 adapter',()=>{
  it('confirms exact public room through documented direct request',async()=>{
    const fetcher=vi.fn().mockResolvedValue(response(payload([entry()])));const result=await provider(fetcher).getStatus(selected);
    expect(result.state).toBe('live');expect(result.source).toBe('authorized-affiliate');expect(Date.parse(result.validUntil)-Date.parse(result.observedAt)).toBe(90000);
    const [url,options]=fetcher.mock.calls[0];expect(url.origin).toBe('https://chaturbate.com');expect(url.pathname).toBe('/api/public/affiliates/onlinerooms/');expect(Object.fromEntries(url.searchParams)).toEqual({wm:'example_campaign',client_ip:'request_ip',format:'json',limit:'500',offset:'0'});expect(options.credentials).toBe('omit');expect(options.redirect).toBe('error');expect(url.searchParams.has('username')).toBe(false);
  });
  it('enumerates documented pages and matches only exact lowercase identity',async()=>{const fetcher=vi.fn().mockResolvedValueOnce(response(payload([entry('other_handle')],501))).mockResolvedValueOnce(response(payload([entry()],501)));const result=await provider(fetcher).getStatus(selected);expect(result.state).toBe('live');expect(fetcher.mock.calls[1][0].searchParams.get('offset')).toBe('500');expect(saved.hintOffset).toBe(500);});
  it('omission is UNKNOWN even with an empty or complete roster',async()=>{for(const rows of [[],[entry('other_handle')]]){saved={};expect((await provider(vi.fn().mockResolvedValue(response(payload(rows)))).getStatus(selected)).reason).toBe('not-listed');}});
  it.each(['private','group','away','unrecognized'])('does not grant for %s',async show=>expect((await provider(vi.fn().mockResolvedValue(response(payload([entry(selected,show)])))).getStatus(selected)).state).toBe('unknown'));
  it.each([null,{}, {count:-1,results:[]},{count:0,results:[entry()]},{count:1,results:[{username:selected}]},{count:1,results:'bad'},'bad json'])('fails closed for malformed %j',async body=>expect((await provider(vi.fn().mockResolvedValue(response(body))).getStatus(selected)).state).toBe('unknown'));
  it.each([401,403,429,500])('fails closed for HTTP %i',async code=>expect((await provider(vi.fn().mockResolvedValue(response({}, {},code))).getStatus(selected)).state).toBe('unknown'));
  it.each<Record<string,string>>([{date:'invalid'},{date:'Thu, 22 Oct 2026 17:58:00 GMT'},{date:'Thu, 22 Oct 2026 18:01:00 GMT'},{age:'60'},{age:'bad'},{'content-type':'text/html'}])('rejects stale/non-JSON transport %j',async headers=>expect((await provider(vi.fn().mockResolvedValue(response(payload([entry()]),headers))).getStatus(selected)).state).toBe('unknown'));
  it('caches within the original lease and reserves scan budget across worker recreation',async()=>{const fetcher=vi.fn().mockImplementation(async()=>response(payload([entry()])));const first=await provider(fetcher).getStatus(selected);vi.advanceTimersByTime(30000);const second=await provider(fetcher).getStatus(selected);expect(second).toEqual(first);expect(fetcher).toHaveBeenCalledTimes(1);expect((await provider(fetcher).getStatus('other_handle')).state).toBe('unknown');expect(fetcher).toHaveBeenCalledTimes(1);vi.advanceTimersByTime(61000);await provider(fetcher).getStatus(selected);expect(fetcher).toHaveBeenCalledTimes(2);});
  it('failed refresh never falls back to old LIVE',async()=>{const fetcher=vi.fn().mockResolvedValueOnce(response(payload([entry()]))).mockRejectedValue(Error('network'));const p=provider(fetcher);expect((await p.getStatus(selected)).state).toBe('live');vi.advanceTimersByTime(61000);expect((await p.getStatus(selected)).state).toBe('unknown');expect(saved.cached).toBeUndefined();});
  it('honors Retry-After and does not retry during backoff',async()=>{const fetcher=vi.fn().mockResolvedValue(response({}, {'retry-after':'600'},429));await provider(fetcher).getStatus(selected);vi.advanceTimersByTime(60000);expect((await provider(fetcher).getStatus(selected)).reason).toBe('rate-limited');expect(fetcher).toHaveBeenCalledTimes(1);});
  it('caps roster scanning and never grants on a partial miss',async()=>{const fetcher=vi.fn().mockImplementation(async()=>response(payload([],50000)));expect((await provider(fetcher).getStatus(selected)).reason).toBe('scan-limit');expect(fetcher).toHaveBeenCalledTimes(40);});
  it('timeouts fail closed',async()=>{vi.useRealTimers();const fetcher=vi.fn((_url:URL|RequestInfo,options?:RequestInit)=>new Promise<Response>((_resolve,reject)=>options!.signal!.addEventListener('abort',()=>reject(Error('timeout')))));const p=new AffiliateProvider('example_campaign',{store,fetch:fetcher,timeoutMs:10,pause:async()=>{}});expect((await p.getStatus(selected)).state).toBe('unknown');});
  it('rejects malformed campaign and username before a request',async()=>{expect(()=>new AffiliateProvider('a&evil=1')).toThrow();const fetcher=vi.fn();await expect(provider(fetcher).getStatus('a/b')).rejects.toThrow();expect(fetcher).not.toHaveBeenCalled();});
});
