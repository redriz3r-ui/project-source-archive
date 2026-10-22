import {parseConfig} from '../core/policy';
interface BlockedStatus {
  username: string | null;
  enabled: boolean;
  canOpen: boolean;
  manualLock: boolean;
  state: string;
  simulator: boolean;
}
const element = (id: string) => document.getElementById(id)!;
let displayed: BlockedStatus | null = null;
function render(status: BlockedStatus) {
  displayed = status;
  element('protection').textContent = `LIVELOCK${status.simulator ? ' · DEVELOPMENT SIMULATOR' : ''}`;
  let heading: string;
  let detail: string;
  const handle = status.username ? `@${status.username}` : '';
  if (!status.enabled) {
    heading = 'LiveLock is off.';
    detail = 'Blocking is paused. Turn it back on in Settings when you’re ready.';
  } else if (!handle) {
    heading = 'No broadcaster selected.';
    detail = 'All NSFW is locked.\nChoose a broadcaster in LiveLock.';
  } else if (status.manualLock) {
    heading = `${handle} is locked.`;
    detail = 'All NSFW is locked.\nPlease check again in LiveLock.';
  } else if (status.canOpen) {
    heading = status.simulator ? `${handle} is live (simulated).` : `${handle} is live ✨`;
    detail = 'Their room is available.\nAll other NSFW is locked.';
  } else if (status.state === 'checking') {
    heading = `Checking on ${handle}…`;
    detail = 'All NSFW is locked.\nChecking now…';
  } else if (status.state === 'locked_offline') {
    heading = `${handle} is offline${status.simulator ? ' (simulated)' : ''}.`;
    detail = 'All NSFW is locked.\nPlease check again.';
  } else if (status.state === 'unavailable') {
    heading = `${handle}’s live status is unavailable.`;
    detail = 'All NSFW is locked.\nPlease check again.';
  } else {
    heading = `${handle} isn’t confirmed live.`;
    detail = 'All NSFW is locked.\nPlease check again.';
  }
  element('heading').textContent = heading;
  element('selection').textContent = detail;
}
let pending = false;
async function localSelection(): Promise<BlockedStatus | null> {
  try {
    // A top-level extension page can read its own local preference even while an older
    // worker is running or restarting. Never infer LIVE or an allowance from storage.
    const data = await chrome.storage.local.get(['config', 'manualLock']);
    const config = parseConfig(data.config);
    return {username:config.username,enabled:config.enabled,manualLock:data.manualLock===true,canOpen:false,state:'unavailable',simulator:chrome.runtime.getManifest().name.includes('DEVELOPMENT SIMULATOR')};
  } catch { return null; }
}
async function refresh() {
  if (pending) return;
  pending = true;
  let local: BlockedStatus | null = null;
  try {
    local = await localSelection();
    if (local && (!displayed || displayed.username !== local.username || displayed.enabled !== local.enabled || displayed.manualLock !== local.manualLock)) render(local);
    const response = await chrome.runtime.sendMessage({type:'blocked-status'});
    if (response?.ok && response.value && (response.value.username || !local?.username)) render(response.value);
    else if (local) render(local);
  } catch {
    // Preserve the selected-name reminder. A failed status request must never invent LIVE.
    if (local) render(local);
    else element('selection').textContent = 'Status is unavailable right now. Check LiveLock in your toolbar.';
  } finally { pending = false; }
}
// This page is web-accessible for relocking. Never reveal a selection in an embedded frame.
if (window.top === window.self) {
  void refresh();
  chrome.storage.onChanged.addListener((_changes, area) => { if (area === 'local') void refresh(); });
  addEventListener('focus', () => void refresh());
  setInterval(() => void refresh(), 5000);
} else {
  element('selection').textContent = 'Please check again.';
}
