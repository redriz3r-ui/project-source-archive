# Install the connected extension

1. Chrome → `chrome://extensions` → Developer mode → Load unpacked → choose `dist/`.
2. If already installed from this folder, click Reload. Disable/remove any older LiveLock or simulator instance so it does not block the chosen room independently.
3. Pin the extension. Open Settings & setup, read the adult/scope notices, enter your selected handle/room URL and Save and lock.
4. Open the toolbar popup and Check again. Connected means the official API client is configured. LIVE means the selected exact room was listed public. UNKNOWN means not confirmed (not necessarily offline), and access stays locked.
5. Checks use a minimum 60-second API scan interval. A repeated check may reuse the same still-fresh observation without extending it, or report waiting. No room opens automatically.
6. Lock now revokes access and pauses automatic unlocking until Check again. To turn all protection OFF, acknowledge the Settings warning and press Turn protection OFF. ON restores denial first.

The connected ZIP is `artifacts/livelock-0.4.5-connected.zip`; extract it and choose its `dist/` folder. The simulator is separately labeled and must not be mistaken for real status.

The actual selected-handle metadata check did not find the selected broadcaster in the online feed. That is a real locked/UNKNOWN result, not a fake OFFLINE. Real-network browser verification tests only the API/grant path and does not open streams. Real-room rendering with age/login/private transitions remains a separate manual item.

Outstanding manual checks: headed end-user Chrome restart/update; forced worker suspension; actual OS sleep/delayed alarms; incognito disabled/enabled; multiple-window focus; competing blockers; keyboard-only/screen-reader use; permitted real-room rendering. Automated isolated Chromium restart, expiry, SPA, exact DNR rules and OFF/ON checks are separately reported in test-matrix.md.

Version 0.3.0 expands default blocking to 764,348 domain entries plus 4chan /gif. After reloading, erome.com and boards.4chan.org/gif/ should be blocked while protection is ON. Other boards such as /g/ remain accessible. Reloading preserves your selected broadcaster and preferences. List coverage is broad but not exhaustive; mixed-content pages and newly created domains can be missed.

Version 0.4.0 adds ThePornDude’s collected directory domains, including the directory/referral host itself. Its strict policy blocks entire listed mixed-use domains, such as Reddit, YouTube, Instagram and all 4chan boards. This supersedes v0.3.0’s other-board allowance above. Reload the same dist/ folder to get version 0.4.0; your selected broadcaster and preferences persist. The exact verified-live room remains allowed. Future directory changes require an updated build.

Version 0.4.1 personalizes the local restricted page using the selected handle and current access state. Reload LiveLock and refresh an existing restricted-page tab. No handle is stored in the page URL or hardcoded; changing your selection updates the page automatically. A restricted page embedded by a site stays generic.

Version 0.4.2 makes the reminder playful (“Nice try. You picked @handle.”) and preserves the local selected name if the background worker cannot answer. In that case it says live status is reconnecting; it does not claim a verified live room. Reload LiveLock, then refresh the blocked tab.

Version 0.4.3 simplifies the restricted page to a personalized status and one brief sentence. No footer or settings link. Offline is shown only when confirmed; unknown remains “Waiting for @handle.” Reload the extension and refresh the blocked tab.

Version 0.4.5 uses the requested three-line status format: broadcaster status, “All NSFW is locked”, please check again. It does not claim the entire internet is blocked or infer OFFLINE from an unconfirmed feed absence. Reload the extension, then refresh the blocked page.
