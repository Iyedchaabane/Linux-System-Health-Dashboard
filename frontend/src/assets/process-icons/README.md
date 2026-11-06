# Process icons: withheld brand assets

No brand SVGs are currently bundled. All process names use the existing Lucide
`AppWindow` fallback, inheriting the table's semantic `text` color. No brand
recoloring, new token, backing surface or row-height change is introduced.

## Evidence reviewed for T4.8

Simple Icons develop resolved to commit
`e451c581fccb01b56f47e1a77292bdd1fd95b1a4` during review. Its
`data/simple-icons.json` and `DISCLAIMER.md` were retrieved from develop, not
independently verified at that commit. The project is CC0, **not MIT**; its
disclaimer explicitly says this does not make every individual icon CC0 and
does not establish trademark permission. No blanket license or legal clearance
is claimed here.

| Withheld asset | Evidence / unresolved issue |
| --- | --- |
| Brave (`brave.svg`) | `https://brave.com/brave-branding-assets` retrieved; exact local geometry revision and redistribution evidence not established. |
| Docker (`docker.svg`) | `https://www.docker.com/company/newsroom/media-resources` retrieved; exact local geometry revision and redistribution evidence not established. |
| Firefox (`firefox.svg`) | `https://mozilla.design/firefox/logos-usage/` returned HTTP 403; local mark was Firefox, not the separate Firefox Browser product. No replacement verified. |
| GNOME Terminal (`gnometerminal.svg`) | Source at `https://gitlab.gnome.org/GNOME/gnome-terminal/-/raw/9c32e039bfb7902c136dc7aed3308e027325776c/data/icons/hicolor_apps_scalable_org.gnome.Terminal.svg` retrieved. Copyright 2018 Tobias Bernard, Lapo Calamandrei, Sam Hewitt; header GPL-3.0-or-later, metadata CC-BY-SA-4.0. Relationship to local simplified geometry and applicable obligations unresolved; local neutral recolor also failed light contrast. |
| OpenJDK (`openjdk.svg`) | Reported Simple Icons source `https://hg.openjdk.java.net/duke/duke/file/ca00f100dafc/vector/Agent.svg` at revision `ca00f100dafc` returned HTTP 403. Reported BSD-3-Clause metadata alone did not establish the exact copyright notice/source relationship. Original black plus a light backing was therefore not introduced. |
| Python (`python.svg`) | `https://www.python.org/community/logos/` retrieved; local geometry differs from an earlier cached asset. No explanation or exact pinned geometry/permission verification established, so neither was retained. |
| Spotify (`spotify.svg`) | `https://developer.spotify.com/documentation/design` retrieved; exact geometry revision and redistribution evidence not established; existing green failed light contrast. |

No third-party SVGs remain, so no asset license texts/notices are redistributed.
Before restoring any asset, verify its exact pinned origin, applicable license
and required notices, trademark guidelines, and contrast in both themes. Restore
only exact common aliases and anchored numeric Python executable versions; never
infer a brand from arbitrary paths, URLs, helper names, `java9`, `brave-browse`,
or broad Python space-prefixes. These currently all resolve neutrally.

## Integration contract

`resolveProcessIcon(name)`, `fallbackProcessIcon`, `ProcessIcon`, and
`ProcessIconResolution` remain exported with their existing API. Image failures
are remembered per resolved source for each mounted component: another source
gets a chance, while a previously failed source is not retried. No effect reset
or retry loop is used. ProcessTable display strings and truncation are unchanged.
