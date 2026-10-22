import type {LiveStatusProvider} from './interface';
import {unknown} from './interface';
import {validateObservation} from '../core/policy';
/** Future internal gateway contract, NOT a Chaturbate API adapter. Not enabled in builds. */
export class GatewayProvider implements LiveStatusProvider {
  constructor(private readonly pinnedOrigin:string, private readonly timeoutMs=5000){const u=new URL(pinnedOrigin);if(u.protocol!=='https:'||u.origin!==pinnedOrigin) throw Error('Pin an HTTPS origin at build time.');}
  async getStatus(name:string){
    try {
      const url=new URL('/v1/status',this.pinnedOrigin);url.searchParams.set('platform','chaturbate');url.searchParams.set('username',name);
      const response=await fetch(url,{signal:AbortSignal.timeout(this.timeoutMs),credentials:'omit',cache:'no-store',redirect:'error',referrerPolicy:'no-referrer'});
      if(!response.ok) return unknown(name,response.status===429?'rate-limited':'unavailable');
      return validateObservation(await response.json(),name,Date.now(),false)??unknown(name,'invalid-response');
    }catch{return unknown(name);}
  }
}
