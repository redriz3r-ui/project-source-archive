import type {LiveState, Observation} from '../core/policy';
import type {LiveStatusProvider} from './interface';
export class FixtureProvider implements LiveStatusProvider {
  async getStatus(name:string):Promise<Observation> {
    const {fixtureState} = await chrome.storage.local.get('fixtureState');
    const state:LiveState = fixtureState==='live'||fixtureState==='offline'?fixtureState:'unknown';
    const now=Date.now();return {platform:'chaturbate',username:name,state,observedAt:new Date(now).toISOString(),validUntil:new Date(now+90000).toISOString(),source:'fixture'};
  }
}
