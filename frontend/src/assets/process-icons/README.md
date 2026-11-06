# Process icons: provenance and licensing

**61 of 61 application logos bundled; 61/61 exact alias identities supported;
0 apps use the neutral Lucide AppWindow fallback. Every bundled asset has
pinned asset-specific or repository-level redistribution evidence. No legal
clearance is claimed; trademarks remain with their owners.**

## Classification legend

| Class | Count | Meaning |
| --- | --- | --- |
| Asset-specific evidence | 56 | A pinned asset with explicit per-file licence or permission metadata whose obligations this project can meet; the asset is bundled and its notice ships with the build. |
| Repository-level evidence | 5 | VSCodium, QEMU, OpenCode, Insomnia and pgAdmin: the repository-level licence at the pinned commit, with no separate per-file logo licence found (residual risk). |
| Total bundled | 61 | 56 asset-specific + 5 repository-level; the neutral icon is never used for a known app. |
| No bundled fallback for known apps | 0 | Every registry entry resolves to a local brand asset. The neutral Lucide icon is used only for process names that match no registry alias. |
| Trademark considerations | separate | Trademark rights are distinct from copyright licences and are never granted by CC BY, CC BY-SA, CC0, MIT, Apache-2.0, the GPL or a logo-usage permission. No app is claimed to be free of trademark restrictions. |

This supersedes T6.2's permissive-only policy: **CC BY-SA, MPL and GPL assets are
acceptable when their obligations are met** (attribution, share-alike, source
availability). Wikimedia Commons licence tags are file-specific licence metadata
recorded on each file page; they are not a legal clearance and do not address
trademark rights.

Repository-level evidence: for five bundled assets the evidence is the
repository-level licence at the pinned commit, not a separate per-file logo
licence — VSCodium (`VSCodium/vscodium`, MIT, residual repository-level risk
documented below), qemu (`qemu/qemu`, GPL-2.0), insomnia (`Kong/insomnia`,
Apache-2.0), opencode (`sst/opencode`, MIT) and pgadmin
(`pgadmin-org/pgadmin4`, PostgreSQL). These are residual risks, not legal
clearance.

## Provenance

### 1. Font Awesome Free 6.7.2

- Pin: `840c215f894f429b26b8c1402a65da835dc5a450`
- Source: `https://github.com/FortAwesome/Font-Awesome/tree/840c215f894f429b26b8c1402a65da835dc5a450/svgs/brands`
- Licence: Icons CC BY 4.0; copyright (c) 2024 Fonticons, Inc.
- Required attribution: `Font Awesome Free 6.7.2 by @fontawesome - https://fontawesome.com - License: https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT)`
- Bundled from: `firefox-browser`, `brave`, `chrome`, `edge`, `opera`, `docker`,
  `node-js`, `python`, `java`, `spotify`, `discord`, `slack`, `telegram`,
  `whatsapp`, `github` (as GitHub Desktop), `steam`, `signal-messenger`,
  `jenkins`.
- Modification: root `fill` brand colour added; geometry unchanged. The
  upstream attribution comment inside each SVG is preserved.
- Full licence text: `LICENSE-fontawesome.txt`.

### 2. Simple Icons

- Pin: `e451c581fccb01b56f47e1a77292bdd1fd95b1a4`
- Source: `https://github.com/simple-icons/simple-icons/tree/e451c581fccb01b56f47e1a77292bdd1fd95b1a4/icons`
- Simple Icons itself is CC0 1.0, but **per-icon licences apply**:
  - **Vivaldi** — CC BY 4.0. Source `https://vivaldi.com/press`; credit
    "Vivaldi Technologies"; the press page states images are CC BY 4.0 and
    logos are subject to trademark restrictions.
  - **Inkscape** — CC BY-SA 3.0. Source
    `https://inkscape.org/gallery/=inkscape-branding/inkscape-brand-assets/`.
  - **Apache NetBeans** — Apache-2.0. Source `https://apache.org/logos`;
    attribution The Apache Software Foundation.
  - **GIMP** — CC BY-SA 4.0. Source
    `https://gitlab.gnome.org/GNOME/gimp-data/-/blob/e62f1905dcef7ec831ea6c052bb035eb37eaa69e/images/logo/gimp-logo-unicolor.svg`.
- Modification: root `fill` brand colour added; geometry unchanged. The
  modified Inkscape and GIMP assets **remain under their CC BY-SA licences**
  (3.0 and 4.0 respectively), so share-alike obligations attach to those files.

### 3. Git

- Existing CC BY 3.0 asset, unchanged.
- Attribution: "Git Logo by Jason Long is licensed under the Creative Commons
  Attribution 3.0 Unported License."
- Source: `https://git-scm.com/images/logos/downloads/Git-Icon-Black.svg`
- Modification: none (byte-identical).

### 4. VSCodium

- Existing MIT asset. Modification: XML declaration and external-DTD DOCTYPE removed; geometry and gradient unchanged.
- Canonical `VSCodium/vscodium` commit
  `5e26c4a9c475ebf59052c2da916b80d471af739f`, path
  `icons/stable/codium_cnl.svg`.
- Copyright lines: 2018-present The VSCodium contributors; 2018-present Peter
  Squicciarini; 2015-present Microsoft Corporation.
- There is **no per-file licence notice** for the asset; redistribution rests
  on the repository-level MIT licence. That absence is a residual
  repository-level risk. Full notice in `LICENSE-vscodium.txt`.

### 5. Wikimedia Commons: public-domain-tagged logos

File-specific Commons licence metadata, not legal clearance. "Commons revid" is
the permanent file revision identifier; `Special:Redirect/file` URLs resolve the
pinned revision. All are unmodified unless noted.

| Asset | Source file (pinned revid) | Licence tag | Attribution | Modification |
| --- | --- | --- | --- | --- |
| `chromium.svg` | `File:Chromium_Logo.svg`, revid 1207739646 | PD-textlogo | The Chromium Authors / Google | unmodified |
| `vscode.svg` | `File:Visual_Studio_Code_1.35_icon.svg`, revid 1082378456 | PD-shape | Microsoft | unmodified |
| `mysql.svg` | `File:MySQL_textlogo.svg`, revid 1016341408 | PD-textlogo | Oracle Corporation | unmodified (wordmark) |
| `redis.svg` | `File:Redis_logo.svg`, revid 1274416148 | PD-textlogo | Redis Ltd | unmodified (wordmark) |
| `postman.png` | `File:Postman_(software).png`, revid 1088854200 | PD-textlogo | Postman, Inc. | 659x200 downscaled to 256x78 |
| `intellij.png` | `File:IntelliJ_IDEA_Icon.svg`, revid 1104075656 | PD-textlogo | JetBrains | 960 px raster render downscaled to 256 px |
| `teams.svg` | `File:Microsoft_Office_Teams_(2025–present).svg`, revid 1259002657 | PD-textlogo | Microsoft | unmodified |
| `pycharm.svg` | `File:PyCharm_Icon.svg`, revid 725398577 | PD-textlogo | JetBrains | unmodified |
| `webstorm.png` | `File:WebStorm_Icon.svg`, revid 1008636300 | PD-textlogo | JetBrains | 960 px raster render downscaled to 256 px |
| `android-studio.png` | `File:Android_Studio_Logo_(2023).svg`, revid 1220366636 | PD-textlogo | Google | 960 px raster render downscaled to 256 px |
| `virtualbox.svg` | `File:VirtualBox_2024_Logo.svg`, revid 1103776088 | PD-textlogo | Oracle VirtualBox | unmodified |
| `kubernetes.svg` | `File:Kubernetes_logo_without_workmark.svg`, revid 1291255072 | PD-logo | Google, Inc. | unmodified |
| `chatgpt.svg` | `File:ChatGPT-Logo.svg`, revid 1253678087 | PD-simple | OpenAI | unmodified |

Trademark note: Chromium, Visual Studio Code, MySQL, Redis, Postman, IntelliJ
IDEA, Microsoft Teams, PyCharm, WebStorm, Android Studio, VirtualBox,
Kubernetes, ChatGPT and their logos are trademarks of their respective owners.
Public-domain copyright status does not grant trademark rights or imply
endorsement.

### 6. CC0 1.0

| Asset | Source file (pinned revid) | Attribution | Modification |
| --- | --- | --- | --- |
| `zoom.png` | `File:Zoom_meeting_app_icon.png`, revid 1259296218 | Ghostw7856 (uploader) | 512 px downscaled to 256 px |
| `kdenlive.png` | `File:Kdenlive-logo.svg`, revid 1016443346 | Kdenlive | 960 px raster render downscaled to 256x192 |

Licence: Creative Commons CC0 1.0 Universal,
`https://creativecommons.org/publicdomain/zero/1.0/`. CC0 waives copyright and
related rights; it does not grant trademark rights.

Trademark note: Zoom and Kdenlive and their logos are trademarks of their
respective owners; no endorsement is implied.

### 7. CC BY 2.5

| Asset | Source file (pinned revid) | Attribution | Modification |
| --- | --- | --- | --- |
| `krita.png` | `File:Krita_Application_Logo.svg`, revid 1215238824 | KOffice Team | 960 px raster render downscaled to 188x256 |

Licence: Creative Commons Attribution 2.5,
`https://creativecommons.org/licenses/by/2.5/`. Obligations: credit the author,
link the licence and indicate changes. No trademark rights are granted. Krita
and the Krita logo are trademarks of the Krita Foundation; no endorsement is
implied.

### 8. CC BY-SA 3.0

| Asset | Source file (pinned revid) | Attribution | Modification |
| --- | --- | --- | --- |
| `mongodb.svg` | `File:Antu_mongodb.svg`, revid 1274486419 | Fabián Alexis (Antu icon set); community/third-party artwork, not an official project logo | unmodified |
| `eclipse.png` | `File:Eclipse-SVG.svg`, revid 978508658 | User:Eduemoni (Commons); community/third-party artwork, not an official project logo | 960 px raster render downscaled to 256 px |

Licence: Creative Commons Attribution-ShareAlike 3.0 Unported,
`https://creativecommons.org/licenses/by-sa/3.0/`. Obligations: credit, link the
licence, indicate changes and share adaptations under the same licence. No
trademark rights are granted. MongoDB and Eclipse are trademarks of their
respective owners; no endorsement is implied.

### 9. MPL-2.0

| Asset | Source file (pinned revid) | Attribution | Modification |
| --- | --- | --- | --- |
| `libreoffice.png` | `File:LibreOffice_7.5_Main_Icon.svg`, revid 1091663302 | Galdam Jitsu (Geeko) | 960 px raster render downscaled to 256 px |
| `thunderbird.png` | `File:Mozilla_Thunderbird_logo.png`, revid 762405301 | Mozilla Foundation | 512 px downscaled to 256 px |

Licence: Mozilla Public License 2.0, `https://mozilla.org/MPL/2.0/`. Obligations:
source availability for covered files and retention of notices. No trademark
rights are granted. LibreOffice and Thunderbird and their logos are trademarks
of their respective owners; no endorsement is implied.

### 10. GPL-2.0 / GPL (as tagged on the file page)

| Asset | Source (pinned revision) | Licence as tagged | Attribution | Modification |
| --- | --- | --- | --- | --- |
| `gnome-terminal.png` | `File:GNOME_Terminal_icon_2019.svg`, revid 1264922384 | GPL-3.0 (dual GPLv3/GFDL-1.3) | Jakub Steiner (jimmac) | 960 px raster render downscaled to 256 px |
| `nautilus.png` | `File:Nautilus_icon.svg`, revid 1117282381 | GPL-2.0 only | Ulisse Perusin | 960 px raster render downscaled to 256 px |
| `evince.png` | `File:Evince_logo_2011.svg`, revid 1218952497 | GPL | Jakub Steiner | 960 px raster render downscaled to 256 px |
| `vlc.svg` | `File:VLC_Icon.svg`, revid 1252262404 | GPL | Richard C. G. Øiestad | unmodified |
| `obs.svg` | `File:OBS_Studio_Logo.svg`, revid 1173968490 | GPL-2.0 (also tagged PD-logo) | Hugh "Jim" Bailey | unmodified |
| `audacity.png` | `File:Audacity_Logo_Plain.svg`, revid 1068775185 | GPL | Audacity | 960 px raster render downscaled to 256x240 |
| `filezilla.svg` | `File:FileZilla_logo.svg`, revid 1252670970 | GPL | eeme158 team / FileZilla | unmodified |
| `mongodb-compass.png` | `File:Biglinux-Icons_%E2%80%93_mongodb-compass.svg`, revid 1208009554 | GPL-3.0 | BigLinux contributors (BigLinux icon set; community/third-party artwork, not an official project logo) | 960 px raster render downscaled to 256 px |
| `qemu.svg` | `qemu/qemu` commit `f71afb409a87c4ecd0f9d63a5963eb645dfab780`, path `ui/icons/qemu.svg` | GPL-2.0 | QEMU contributors (repository-level GPL-2.0 at the pinned commit; no separate per-file logo licence found) | unmodified |
| `zed.png` | `File:Zed_Editor_Logo.png`, revid 1253681587 | GPL | Zed Industries | 960 px raster render downscaled to 256 px |

Obligations: provide the licence text, keep copyright notices, and make the
corresponding source available. No trademark rights are granted. GNOME,
Nautilus, Evince, VLC, OBS Studio, Audacity, FileZilla, MongoDB Compass, QEMU,
Zed and their logos are trademarks of their respective owners; no endorsement is
implied.

### 11. Apache-2.0 (additional assets)

| Asset | Source (pinned revision) | Attribution | Modification |
| --- | --- | --- | --- |
| `insomnia.svg` | `Kong/insomnia` commit `54e46851ff4a4ca8a357e351ef8bed713ceda42a`, path `packages/insomnia/src/ui/images/insomnia-logo.svg` | Kong Inc. / Insomnia contributors (repository-level Apache-2.0 at the pinned commit; no separate per-file logo licence found) | unmodified |
| `dbeaver.svg` | `File:DBeaver_logo.svg`, revid 1016334304 | Serge Rider / DBeaver developers | unmodified |

Licence: Apache License 2.0, `https://www.apache.org/licenses/LICENSE-2.0`. The
full text is reproduced in `THIRD_PARTY_NOTICES.txt` (section 4). Obligations:
retain notices and state changes. No trademark rights are granted. Insomnia and
DBeaver and their logos are trademarks of their respective owners; no
endorsement is implied.

### 12. PostgreSQL / BSD

| Asset | Source (pinned revision) | Licence | Attribution | Modification |
| --- | --- | --- | --- | --- |
| `postgresql.svg` | `File:Postgresql_elephant.svg`, revid 1260167757 | PostgreSQL/BSD | Daniel Lundin; PostgreSQL Global Development Group | unmodified |
| `pgadmin.png` | `pgadmin-org/pgadmin4` commit `d9647f93f022681b43ef6039290c800da45fa5d7`, path `web/pgadmin/static/img/logo-128.png` | PostgreSQL licence | pgAdmin Development Team (repository-level PostgreSQL licence at the pinned commit; no separate per-file logo licence found) | unmodified 128x128 PNG |

Licence: The PostgreSQL Licence (BSD-style),
`https://www.postgresql.org/about/licence/`. No trademark rights are granted.
PostgreSQL, the PostgreSQL elephant and pgAdmin are trademarks of their
respective owners; no endorsement is implied.

### 13. MIT (additional assets)

| Asset | Source (pinned revision) | Attribution | Modification |
| --- | --- | --- | --- |
| `ollama.svg` | `File:Ollama-logo.svg`, revid 1222804376 | ParthSareen / Ollama | unmodified |
| `opencode.svg` | `sst/opencode` commit `72da577c0bb01115e3603ed7655637e9f560d816`, path `packages/console/app/src/asset/brand/opencode-logo-light-square.svg` | OpenCode contributors (repository-level MIT at the pinned commit; no separate per-file logo licence found) | unmodified |

Licence: MIT. The full text is reproduced in `THIRD_PARTY_NOTICES.txt`
(section 7). Copyright lines retained under MIT, in addition to the attribution
above: `ollama.svg` — "Copyright (c) 2023 Ollama"; `opencode.svg` —
"Copyright (c) 2025 opencode" (from the `sst/opencode` LICENSE at commit
`72da577c0bb01115e3603ed7655637e9f560d816`). No other copyright holder is
asserted. Obligations: retain the copyright and permission notice. No
trademark rights are granted. Ollama and OpenCode and their logos are
trademarks of their respective owners; no endorsement is implied.

### 14. Blender logo (conditional permission)

- Source: `https://www.blender.org/about/logo/`; official logo kit
  `https://download.blender.org/branding/blender_logo_kit.zip`, kit SHA-256
  `61d79b4c71264709a3d8dad2628e77eb4179cda99bf63125bcc1e4dd7261e35d`.
- Asset: `blender.png`, from the official `blender_icon_512x512.png`, downscaled
  to 256 px.
- Status: **Blender is the property of the Blender Foundation.** The mark is
  taken from the official logo kit and used only as a secondary brand to
  identify and credit Blender as an application this dashboard can display. It
  is not used as a primary or product brand and must not imply endorsement,
  sponsorship or affiliation by the Blender Foundation.
- **The Blender logo is not licensed under the GPL or any Creative Commons
  licence**; use is governed by the Blender Foundation's conditional logo usage
  guidelines, which permit third-party use solely to identify or credit Blender.
- No legal clearance is claimed.

## Bundled assets and full status (61 apps)

All 61 registry entries are bundled; no known app falls back to the neutral
icon. `Commons` means a pinned Wikimedia Commons file revision; `revid` is the
permanent file revision id.

| # | App | Aliases | Asset | Source / licence | Dark treatment | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Firefox | `firefox`, `firefox-bin`, `firefox-esr` | `firefox.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 2 | Brave Browser | `brave`, `brave-browser` | `brave.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 3 | Google Chrome | `chrome`, `google-chrome`, `chrome-stable` | `chrome.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 4 | Chromium | `chromium`, `chromium-browser`, `chromium-browse` | `chromium.svg` | Commons revid 1207739646, PD-textlogo | none | Bundled |
| 5 | VS Code | `code`, `code-oss` | `vscode.svg` | Commons revid 1082378456, PD-shape | none | Bundled |
| 6 | VSCodium | `codium`, `vscodium` | `vscodium.svg` | VSCodium repo, MIT | none | Bundled |
| 7 | Python | `python`, `python3`, `python3.10`–`python3.14` | `python.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 8 | Java / OpenJDK | `java`, `javaw` | `java.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 9 | Node.js | `node`, `nodejs` | `node.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 10 | Docker | `docker`, `dockerd`, `docker-desktop` | `docker.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 11 | Spotify | `spotify` | `spotify.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 12 | Discord | `discord` | `discord.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 13 | Slack | `slack` | `slack.svg` | Font Awesome 6.7.2, CC BY 4.0 | `dark:brightness-200` | Bundled |
| 14 | Telegram Desktop | `telegram`, `telegram-desktop`, `telegram-deskto` | `telegram.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 15 | Zoom | `zoom`, `zoom.us` | `zoom.png` | Commons revid 1259296218, CC0 1.0 | none | Bundled |
| 16 | PostgreSQL | `postgres`, `postmaster` | `postgresql.svg` | Commons revid 1260167757, PostgreSQL/BSD | none | Bundled |
| 17 | MySQL | `mysqld` | `mysql.svg` | Commons revid 1016341408, PD-textlogo | none | Bundled |
| 18 | Redis | `redis-server` | `redis.svg` | Commons revid 1274416148, PD-textlogo | none | Bundled |
| 19 | MongoDB | `mongod` | `mongodb.svg` | Commons revid 1274486419, CC BY-SA 3.0 | none | Bundled |
| 20 | Git | `git` | `git.svg` | Git project, CC BY 3.0 | `dark:invert` | Bundled |
| 21 | GitHub Desktop | `github-desktop`, `githubdesktop` | `github-desktop.svg` | Font Awesome 6.7.2, CC BY 4.0 | `dark:invert` | Bundled |
| 22 | Postman | `postman` | `postman.png` | Commons revid 1088854200, PD-textlogo | none | Bundled |
| 23 | Insomnia | `insomnia` | `insomnia.svg` | Insomnia repo commit `54e4685`, Apache-2.0 | none | Bundled |
| 24 | GNOME Terminal | `gnome-terminal`, `gnome-terminal-server`, `gnome-terminal-` | `gnome-terminal.png` | Commons revid 1264922384, GPL-3.0 | none | Bundled |
| 25 | Nautilus | `nautilus` | `nautilus.png` | Commons revid 1117282381, GPL-2.0 only | none | Bundled |
| 26 | LibreOffice | `soffice`, `soffice.bin` | `libreoffice.png` | Commons revid 1091663302, MPL-2.0 | none | Bundled |
| 27 | Evince | `evince`, `evince-previewer`, `evince-previewe` | `evince.png` | Commons revid 1218952497, GPL | none | Bundled |
| 28 | VLC | `vlc` | `vlc.svg` | Commons revid 1252262404, GPL | none | Bundled |
| 29 | GIMP | `gimp`, `gimp-3.0` | `gimp.svg` | Simple Icons / GIMP, CC BY-SA 4.0 | none | Bundled |
| 30 | IntelliJ IDEA | `idea`, `idea.sh` | `intellij.png` | Commons revid 1104075656, PD-textlogo | none | Bundled |
| 31 | WhatsApp / Whatsie | `whatsapp`, `whatsapp-desktop`, `whatsapp-deskto`, `whatsapp-for-linux`, `whatsapp-for-li`, `whatsie` | `whatsapp.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 32 | Microsoft Edge | `microsoft-edge`, `microsoft-edge-stable`, `microsoft-edge-beta`, `microsoft-edge-dev`, `microsoft-edge-` | `edge.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 33 | Opera | `opera` | `opera.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 34 | Vivaldi | `vivaldi` | `vivaldi.svg` | Simple Icons / Vivaldi, CC BY 4.0 | none | Bundled |
| 35 | Thunderbird | `thunderbird`, `thunderbird-bin` | `thunderbird.png` | Commons revid 762405301, MPL-2.0 | none | Bundled |
| 36 | Microsoft Teams | `teams`, `teams-for-linux` | `teams.svg` | Commons revid 1259002657, PD-textlogo | none | Bundled |
| 37 | Signal Desktop | `signal-desktop` | `signal.svg` | Font Awesome 6.7.2, CC BY 4.0 | `dark:brightness-125` | Bundled |
| 38 | OBS Studio | `obs` | `obs.svg` | Commons revid 1173968490, GPL-2.0 / PD-logo | none | Bundled |
| 39 | Steam | `steam`, `steamwebhelper` | `steam.svg` | Font Awesome 6.7.2, CC BY 4.0 | `dark:invert` | Bundled |
| 40 | Blender | `blender` | `blender.png` | Blender logo kit, conditional permission | none | Bundled |
| 41 | Inkscape | `inkscape` | `inkscape.svg` | Simple Icons / Inkscape, CC BY-SA 3.0 | `dark:invert` | Bundled |
| 42 | Krita | `krita` | `krita.png` | Commons revid 1215238824, CC BY 2.5 | none | Bundled |
| 43 | Audacity | `audacity` | `audacity.png` | Commons revid 1068775185, GPL | none | Bundled |
| 44 | Kdenlive | `kdenlive` | `kdenlive.png` | Commons revid 1016443346, CC0 1.0 | none | Bundled |
| 45 | FileZilla | `filezilla` | `filezilla.svg` | Commons revid 1252670970, GPL | none | Bundled |
| 46 | DBeaver | `dbeaver` | `dbeaver.svg` | Commons revid 1016334304, Apache-2.0 | none | Bundled |
| 47 | pgAdmin | `pgadmin`, `pgadmin4` | `pgadmin.png` | pgAdmin repo commit `d9647f9`, PostgreSQL | none | Bundled |
| 48 | MongoDB Compass | `mongodb-compass` | `mongodb-compass.png` | Commons revid 1208009554, GPL-3.0 | none | Bundled |
| 49 | PyCharm | `pycharm`, `pycharm.sh`, `pycharm-community`, `pycharm-communi`, `pycharm-professional`, `pycharm-profess` | `pycharm.svg` | Commons revid 725398577, PD-textlogo | none | Bundled |
| 50 | WebStorm | `webstorm`, `webstorm.sh` | `webstorm.png` | Commons revid 1008636300, PD-textlogo | none | Bundled |
| 51 | Eclipse IDE | `eclipse` | `eclipse.png` | Commons revid 978508658, CC BY-SA 3.0 | none | Bundled |
| 52 | Apache NetBeans | `netbeans` | `netbeans.svg` | Simple Icons / Apache, Apache-2.0 | none | Bundled |
| 53 | Android Studio | `android-studio`, `studio.sh` | `android-studio.png` | Commons revid 1220366636, PD-textlogo | none | Bundled |
| 54 | VirtualBox | `virtualbox`, `virtualboxvm`, `vboxheadless`, `vboxsvc` | `virtualbox.svg` | Commons revid 1103776088, PD-textlogo | none | Bundled |
| 55 | QEMU | `qemu-system-x86_64`, `qemu-system-x86`, `qemu-system-i386`, `qemu-system-i38`, `qemu-system-aarch64`, `qemu-system-aar`, `qemu-kvm` | `qemu.svg` | QEMU repo commit `f71afb4`, GPL-2.0 | `dark:invert` | Bundled |
| 56 | Jenkins | `jenkins` | `jenkins.svg` | Font Awesome 6.7.2, CC BY 4.0 | none | Bundled |
| 57 | Kubernetes / kubectl | `kubectl`, `kubelet`, `kube-apiserver`, `kube-proxy`, `kube-scheduler`, `kube-controller-manager`, `kube-controller` | `kubernetes.svg` | Commons revid 1291255072, PD-logo | none | Bundled |
| 58 | Ollama | `ollama`, `ollama_llama_server`, `ollama_llama_se` | `ollama.svg` | Commons revid 1222804376, MIT | `dark:invert` | Bundled |
| 59 | OpenCode | `opencode` | `opencode.svg` | OpenCode repo commit `72da577`, MIT | `dark:invert` | Bundled |
| 60 | ChatGPT Desktop | `chatgpt`, `chatgpt-desktop` | `chatgpt.svg` | Commons revid 1253678087, PD-simple | `dark:invert` | Bundled |
| 61 | Zed Editor | `zed` | `zed.png` | Commons revid 1253681587, GPL | none | Bundled |

Dark treatment: `dark:invert` applies to git, github-desktop, steam, inkscape,
qemu, ollama, opencode and chatgpt; `dark:brightness-200` to slack;
`dark:brightness-125` to signal; the other 51 assets have no dark filter.

These entries record the reviewed file-specific evidence only; they are not a
legal opinion about any third party's rights.

## Integration contract

`processApps` holds all 61 definitions; `resolveProcessApp(name)` trims and
lowercases the name and performs an exact `Map` lookup (no prefix, substring or
regex). `resolveProcessIcon(name)` returns a `brand` resolution for the **61
applications with `src`**, `key` and optional `darkClassName`, otherwise
`{ kind: "fallback", icon: AppWindow }` for a name that matches no alias. Brand
images render at 16×16 with `alt=""`, `aria-hidden="true"`, `object-contain` and
the per-mark `darkClassName`; failures are remembered per source (`failedSrc`),
replaced by the neutral icon, and retried only when the resolved source changes.
No timer, request, polling loop or WebSocket change is involved.

Linux `psutil.Process.name()` returns the 15-character `comm`, so the registry
includes the documented truncation aliases (`telegram-deskto`,
`whatsapp-deskto`, `whatsapp-for-li`, `gnome-terminal-`, `chromium-browse`,
`microsoft-edge-`, `pycharm-communi`, `pycharm-profess`, `evince-previewe`,
`qemu-system-x86`, `qemu-system-i38`, `qemu-system-aar`, `ollama_llama_se`,
`kube-controller`). Exact aliases are never guessed from a prefix.

## Bundle and performance

- 61 assets total **850,091 bytes (830.2 KiB)** source: 24 existing assets
  36,558 B (35.7 KiB), 37 new assets 813,533 B (794.5 KiB).
- Every import uses `?no-inline`, so Vite inlines nothing and emits each icon as
  a separate content-hashed URL under `dist/assets/`: **61 emitted icon files,
  850,091 bytes total**. Only icons that become visible are fetched at runtime;
  there is no remote image request.
- Measured production build: **JS 712,450 B (gzip 207.53 kB)**, **CSS
  15,803 B (gzip 3.99 kB)**.
- Baseline before T6.5: JS 749,028 B, CSS 15,803 B. Delta: **JS -36,578 B**,
  **CSS 0 B** — the icons moved out of the JS bundle into separate asset URLs.
- No timers, polling, WebSocket behaviour or request paths changed.

## Asset safety scan

Intake scan of the 37 new files: the 19 new SVGs contain no `<script>`, no `on*`
event-handler attributes, no external `href`/`xlink:href` resource references,
no `<foreignObject>`, no XML entities and no `data:` URIs; the 18 new PNGs carry
no active content. Remaining URLs in those SVGs are W3C namespace declarations,
DOCTYPEs, metadata (`dc:source`) or comments and are not loaded at runtime. The
24 existing SVGs were already clean and contain only W3C namespace declarations.
No third-party resource is loaded at runtime.

## Shipped notices

`frontend/public/THIRD_PARTY_NOTICES.txt` covers every bundled group: Font
Awesome, Vivaldi, Inkscape, Apache NetBeans, GIMP, Git, VSCodium, the
Commons-tagged public-domain logos, CC0, CC BY 2.5, CC BY-SA 3.0, MPL-2.0,
GPL-2.0/GPL, Apache-2.0 (Insomnia, DBeaver), PostgreSQL/BSD, MIT (Ollama,
OpenCode) and the Blender conditional logo permission, plus the global trademark
notice and the unknown-name fallback note. Vite copies `public/` into the build,
so the file ships at `frontend/dist/THIRD_PARTY_NOTICES.txt`; the build
verification compares its SHA-256 with the source copy.

## Policy

Only assets with explicit redistribution evidence and a pinned source may be
bundled. Each addition records source, licence, copyright, attribution and
modification, ships the required notice, keeps trademark rights separate and
passes the safety scan. CC BY-SA, MPL and GPL are acceptable when their
obligations are met. Commons tags are file-specific licence metadata, not legal
clearance, and brand or trademark pages alone are not sufficient. No legal
clearance is claimed.
