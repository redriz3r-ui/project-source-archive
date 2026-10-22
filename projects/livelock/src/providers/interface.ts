import type {Observation} from '../core/policy';
export interface LiveStatusProvider {getStatus(username: string): Promise<unknown>}
export function unknown(name:string,reason='unavailable'):Observation {const now=Date.now();return {platform:'chaturbate',username:name,state:'unknown',observedAt:new Date(now).toISOString(),validUntil:new Date(now+90000).toISOString(),source:'authorized-affiliate',reason};}
export class UnconfiguredProvider implements LiveStatusProvider {async getStatus(name:string){return unknown(name);}}
