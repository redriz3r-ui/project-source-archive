# Removal and local data

There is **no released macOS app bundle yet**. An internal ad-hoc-signed app
exists for packaging tests only. These instructions are not proof of a
notarized installer or automated uninstaller.

For the current source build, stop the application and Intiface Central first.
Move the SelfPleasure project directory to Trash in Finder if you no longer
need the code. Before doing so, review any private `config.local.*` files,
the `.models/` directory, and `evaluation-data/` inside that directory; do
not discard them if you want to retain your calibration or numeric test data.
Empty Trash only when you have deliberately chosen permanent removal.

For the internal `.app` and a future direct-distribution app, use **Quit app**
on the dashboard or Hand session page, move `SelfPleasure.app` from Applications
to Trash, then optionally remove
`~/Library/Application Support/SelfPleasure/` in Finder. That folder contains
calibration, rules, and any opt-in saved numeric evaluation data. Inspect it
before deleting; removal cannot be undone after Trash is emptied. This flow
still needs a clean-machine usability test before publication.
This will not uninstall Intiface Central, remove its pairings, or erase device
firmware. macOS backups and browser history may retain separate copies.
