import {username, type Observation} from '../core/policy';
import {unknown, type LiveStatusProvider} from './interface';

const ENDPOINT = 'https://chaturbate.com/api/public/affiliates/onlinerooms/';
const PAGE_SIZE = 500;
const MAX_PAGES = 40;
const MIN_SCAN_INTERVAL = 60_000;
const LEASE_MS = 90_000;
const TIMEOUT_MS = 25_000;

interface RequestState {
  nextScanAt?: number;
  hintOffset?: number;
  cached?: Observation;
}
export interface AffiliateStore {
  get(): Promise<RequestState>;
  set(state: RequestState): Promise<void>;
}
export interface AffiliateDependencies {
  store: AffiliateStore;
  fetch: typeof fetch;
  now: () => number;
  pause: (milliseconds: number) => Promise<void>;
  timeoutMs: number;
}
const sessionStore: AffiliateStore = {
  async get() {
    const value = (await chrome.storage.session.get('affiliateRequestState')).affiliateRequestState;
    return value && typeof value === 'object' ? value as RequestState : {};
  },
  async set(state) { await chrome.storage.session.set({affiliateRequestState: state}); }
};

function result(name: string, reason: string): Observation { return unknown(name, reason); }

/** Official Users Online v2. Public campaign slug, no cookies/passwords/API secrets.
 * No undocumented username filter: exact matching happens locally in bounded pages.
 * Missing/non-public rooms NEVER become OFFLINE or LIVE.
 */
export class AffiliateProvider implements LiveStatusProvider {
  readonly configured = true;
  private dependencies: AffiliateDependencies;

  constructor(private campaign: string, dependencies?: Partial<AffiliateDependencies>) {
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(campaign)) throw Error('Invalid public affiliate campaign slug.');
    this.dependencies = {
      store: sessionStore,
      fetch: (...args) => fetch(...args),
      now: () => Date.now(),
      pause: ms => new Promise(resolve => setTimeout(resolve, ms)),
      timeoutMs: TIMEOUT_MS,
      ...dependencies
    };
  }

  async getStatus(input: string): Promise<Observation> {
    const name = username(input);
    const {store, now, pause} = this.dependencies;
    let prior: RequestState;
    try { prior = await store.get(); } catch { return result(name, 'unavailable'); }
    if (typeof prior.nextScanAt === 'number' && prior.nextScanAt > now()) {
      // Reuse only a still-valid observation of the SAME selection, never extend it.
      const cached = prior.cached;
      if (cached?.username === name && cached.source === 'authorized-affiliate'
          && Date.parse(cached.validUntil) > now() && Date.parse(cached.observedAt) <= now() + 5000) return cached;
      return result(name, 'rate-limited');
    }

    const state: RequestState = {nextScanAt: now() + MIN_SCAN_INTERVAL, hintOffset: prior.hintOffset};
    // Reserve the budget BEFORE fetching; survives MV3 worker suspension.
    try { await store.set(state); } catch { return result(name, 'unavailable'); }
    const signal = AbortSignal.timeout(this.dependencies.timeoutMs);
    let pageCount = 1;
    let requests = 0;
    const visited = new Set<number>();
    const hint = Number.isSafeInteger(prior.hintOffset) && prior.hintOffset! >= 0
      && prior.hintOffset! < PAGE_SIZE * MAX_PAGES ? prior.hintOffset! : 0;
    // Probe the last positive page first. Ordering can change, so scan other pages on a miss.
    const offsets = hint ? [hint, 0] : [0];
    try {
      while (offsets.length && requests < MAX_PAGES) {
        if (signal.aborted) throw Error('timeout');
        const offset = offsets.shift()!;
        if (visited.has(offset)) continue;
        visited.add(offset);
        if (requests) await pause(150);
        const url = new URL(ENDPOINT);
        for (const [key, value] of Object.entries({wm: this.campaign, client_ip: 'request_ip', format: 'json', limit: String(PAGE_SIZE), offset: String(offset)})) url.searchParams.set(key, value);
        const response = await this.dependencies.fetch(url, {
          credentials: 'omit', redirect: 'error', cache: 'no-store', referrerPolicy: 'no-referrer', signal
        });
        requests++;
        if (!response.ok) {
          if (response.status === 429) {
            const retry = response.headers.get('retry-after');
            const seconds = retry && /^\d+$/.test(retry) ? Number(retry) * 1000 : Date.parse(retry || '') - now();
            state.nextScanAt = now() + Math.max(MIN_SCAN_INTERVAL, Math.min(Number.isFinite(seconds) ? seconds : 300_000, 3_600_000));
          }
          await store.set(state);
          return result(name, response.status === 429 ? 'rate-limited' : response.status === 401 || response.status === 403 ? 'access-denied' : 'unavailable');
        }
        if (!response.headers.get('content-type')?.includes('application/json')) return result(name, 'invalid-response');
        const at = Date.parse(response.headers.get('date') || '');
        const age = Number(response.headers.get('age') || '0');
        // This is HTTP response freshness, not a claim of a stream-event timestamp.
        if (!Number.isFinite(at) || at > now() + 5000 || now() - at >= LEASE_MS || !Number.isFinite(age) || age < 0 || age >= 60) return result(name, 'stale');
        const body: unknown = await response.json();
        if (!body || typeof body !== 'object') return result(name, 'invalid-response');
        const payload = body as {count?: unknown; results?: unknown};
        if (typeof payload.count !== 'number' || !Number.isSafeInteger(payload.count) || payload.count < 0 || !Array.isArray(payload.results) || payload.results.length > PAGE_SIZE || payload.count < payload.results.length) return result(name, 'invalid-response');
        pageCount = Math.min(MAX_PAGES, Math.ceil(payload.count / PAGE_SIZE));
        for (const entry of payload.results) {
          if (!entry || typeof entry !== 'object' || typeof entry.username !== 'string' || typeof entry.current_show !== 'string') return result(name, 'invalid-response');
          if (entry.username !== name) continue;
          if (entry.current_show !== 'public') return result(name, 'not-public');
          const expires = Math.min(at + LEASE_MS, now() + LEASE_MS);
          if (expires <= now()) return result(name, 'stale');
          const observation: Observation = {platform: 'chaturbate', username: name, state: 'live', source: 'authorized-affiliate', observedAt: new Date(at).toISOString(), validUntil: new Date(expires).toISOString()};
          state.hintOffset = offset;
          state.cached = observation;
          await store.set(state);
          return observation;
        }
        // Only request documented offsets. Roster movement/opt-out makes even a full miss UNKNOWN.
        for (let page = 0; page < pageCount; page++) {
          const candidate = page * PAGE_SIZE;
          if (!visited.has(candidate) && !offsets.includes(candidate)) offsets.push(candidate);
        }
      }
      return result(name, pageCount >= MAX_PAGES ? 'scan-limit' : 'not-listed');
    } catch {
      // Do not reuse a previous LIVE after any failed attempted refresh.
      return result(name, signal.aborted ? 'timeout' : 'unavailable');
    }
  }
}
