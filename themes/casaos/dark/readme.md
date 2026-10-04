# Theme for CasaOS

Made by [jw-notes](https://github.com/jw-notes).

An unofficial CasaOS theme with grey/glass surfaces, a teal accent , dark/light mode, and a collapsible top bar on the left.

## Included files

| File | Purpose |
| --- | --- |
| `casaos-dark.css` | Dashboard and panel styles |
| `casaos-dark.js` | Theme controls, saved preferences and dynamic panel detection |
| `README.md` | Installation, updates and removal |

Both theme files are required. The script adds the body classes that activate the styles.

## Features and behaviour

- Dark mode by default, with a light-mode toggle.
- Top bar collapses to a hamburger; when open, it shows a close icon and the theme toggle.
- Styling for settings, dropdowns, App Store, Files, Terminal and Logs.
- Page and terminal titles use “HomeServer”. CasaOS/IceWhale promotional bars are hidden.
- Theme and navigation preferences are stored in each browser's local storage.
- Detected terminal login fields are reset once per input element; port is set to 22. Browser autofill may fill fields again afterwards.

## Compatibility

This theme targets the component classes in the supplied CasaOS build. Some JavaScript panel detection uses English labels, so use English for the most consistent results. A modern browser with CSS `:has()` support is needed. Other CasaOS versions may need selector adjustments.

The guide below uses the standard native CasaOS web directory, `/var/lib/casaos/www`. This path is supported by the [official CasaOS UI build configuration](https://github.com/IceWhaleTech/CasaOS-UI/blob/main/package.json). Check your own server before copying anything. Docker-based or custom installations may have a different web root.

## Install on an existing CasaOS server

### 1. Extract and transfer the files

Extract the ZIP. In it, open `homelab/themes/casaos/dark/`.

Transfer `casaos-dark.css` and `casaos-dark.js` to a folder on the server, for example `~/casaos-theme/`, using SCP, SFTP or your usual file transfer tool. Run the following commands through SSH or a local server terminal. Keep that session open until the dashboard has loaded correctly.

```bash
cd ~/casaos-theme
ls -l casaos-dark.css casaos-dark.js
ls -l /var/lib/casaos/www/index.html
```

If `index.html` is missing, stop and locate the active CasaOS web directory. Adapt all paths below to that location.

### 2. Back up the current web interface

Run these commands in the same terminal session. The backup is stored outside the publicly served web directory.

```bash
CASAOS_THEME_BACKUP="$HOME/casaos-theme-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 "$CASAOS_THEME_BACKUP"
sudo cp -a /var/lib/casaos/www "$CASAOS_THEME_BACKUP/www"
printf 'Backup saved at: %s\n' "$CASAOS_THEME_BACKUP"
```

Save the printed backup path. Make sure the copy succeeded before proceeding. This backs up the web interface, including existing custom files.

### 3. Copy the theme assets

Install the assets under dedicated names so existing `custom.css` or `custom.js` files are preserved.

```bash
sudo install -d /var/lib/casaos/www/css /var/lib/casaos/www/js
sudo install -m 0644 casaos-dark.css /var/lib/casaos/www/css/casaos-dark.css
sudo install -m 0644 casaos-dark.js /var/lib/casaos/www/js/casaos-dark.js
```

If you already load the previous HomeServer theme through `custom.css`, `custom.js`, a browser extension or another loader, disable those old theme references before enabling this pair. Preserve unrelated customisations. Loading both versions can create duplicate controls or competing styles.

### 4. Add the loading tags

Open the existing HTML file; keep its original content and CasaOS scripts.

```bash
sudo nano /var/lib/casaos/www/index.html
```

Add this stylesheet tag immediately before `</head>`, after the existing stylesheet tags:

```html
<!-- HomeServer theme by jw-notes -->
<link rel="stylesheet" href="./css/casaos-dark.css?v=32">
```

Add this script tag immediately before `</body>`, after the existing CasaOS scripts:

```html
<script defer src="./js/casaos-dark.js?v=32"></script>
```

Add each tag only once. If these exact theme tags already exist, update them instead. Save with Ctrl+O, Enter, then exit with Ctrl+X. The script waits for the DOM and observes panels that appear later.

### 5. Reload and check

Open the normal CasaOS dashboard and press **Ctrl+Shift+R**. On a Mac, use **Cmd+Shift+R**. A server reboot is usually unnecessary for static asset changes.

Confirm that the top-left controls appear, then test dark/light mode, settings, Files, App Store, Terminal and Logs. Open the top bar to reveal the theme toggle.

If nothing changes, open browser developer tools and check the Network tab: `casaos-dark.css` and `casaos-dark.js` should load successfully, rather than return a 404 or HTML page. Check the Console for script errors. Also check whether an older copy of the theme is still loading or whether your installation uses a different web root.

## Update the theme

Back up first, then replace the two dedicated theme files with a matched pair from the next release. If the version changes, update both `?v=32` values in `index.html` and hard-refresh the browser.

CasaOS updates may replace `index.html` or the assets. Check the theme after an update and reapply the files/tags to the new HTML if needed. Do not restore an entire old web directory over a newer CasaOS version merely to re-enable the theme.

## Remove the theme

Remove the two theme loading tags and the optional attribution comment from `index.html`. Then delete only the dedicated assets:

```bash
sudo rm /var/lib/casaos/www/css/casaos-dark.css
sudo rm /var/lib/casaos/www/js/casaos-dark.js
```

Hard-refresh the dashboard. Reloading clears DOM changes made by the script. If you disabled an older theme while installing, restore its loading method only if you want to use it again.

To reset saved preferences, run this in the browser console on your CasaOS page, then reload:

```javascript
localStorage.removeItem("homeserver-theme");
localStorage.removeItem("homeserver-nav-collapsed");
location.reload();
```

## Restore after a failed installation

If this installation broke the dashboard and CasaOS has not been updated since the backup, restore the backed-up HTML from your saved backup path:

```bash
CASAOS_THEME_BACKUP="$HOME/casaos-theme-backup-REPLACE-WITH-YOUR-TIMESTAMP"
sudo cp -a "$CASAOS_THEME_BACKUP/www/index.html" /var/lib/casaos/www/index.html
```

Replace the placeholder with the actual backup folder. Hard-refresh. Your earlier custom files were not overwritten by these installation steps. Remove the dedicated theme assets if no longer needed.

## Publish to GitHub

Extract the ZIP and upload the contents of its `homelab/` folder into your `jw-notes/homelab` repository. The theme will live at `themes/casaos/dark/`; do not add an extra `homelab/` folder inside the repository.

If your repository already has a root README, merge the theme link into it. Keep its existing LICENSE; this ZIP does not select or add a licence.

## Credits

Theme made by [jw-notes](https://github.com/jw-notes). CasaOS and its original interface are developed by [IceWhale](https://github.com/IceWhaleTech/CasaOS-UI). This community theme is not affiliated with or endorsed by CasaOS or IceWhale.
