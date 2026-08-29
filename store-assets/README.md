# Store assets

Generated icon and graphics for the App Store / Google Play listings. Source
is a hand-authored SVG (dark background, ascending bars + magnifying glass),
rendered to PNG.

| File | Size | Use |
|---|---|---|
| `icon/app-icon-1024.png` | 1024×1024, opaque | App Store Connect marketing icon; also the base for Xcode's single-size app icon (Xcode generates the rest). |
| `icon/play-store-icon-512.png` | 512×512, RGBA | Google Play Console "App icon" (Store listing). |
| `icon/android-adaptive-foreground-432.png` | 432×432, transparent | Android adaptive icon foreground layer — content scaled to ~68% to sit inside the safe zone. |
| `icon/android-adaptive-background-432.png` | 432×432, opaque | Android adaptive icon background layer (solid gradient, no logo). |
| `feature-graphic/play-store-feature-graphic-1024x500.png` | 1024×500 | Google Play Store listing "Feature graphic" (required). |
| `listing.md` | — | Draft app name, subtitle/short description, full description, keywords, category, and IAP listing metadata for both consoles. |

## Regenerating / editing the icon

The SVG source lives inline in this repo's history as
`icon/source-icon.svg.html` (a standalone HTML file wrapping the `<svg>` —
open it directly in any browser to preview/edit). To tweak and re-render:

1. Edit the `<svg>` markup in `icon/source-icon.svg.html` (colors match the
   app's theme: `#0e141b`→`#1a2836` background gradient, `#2ea043`→`#40d763`
   green bars, `#4da3ff` accent blue).
2. Render to PNG at whatever size you need with a headless browser
   screenshot of the `<svg>` element (Playwright, Puppeteer, or just open it
   in a browser and use dev tools' "Capture node screenshot").

## Still needed before submission (can't be generated without a device)

- Real device/simulator screenshots of the built app (see `listing.md`
  "Screenshots needed").
- If you want App Store's full icon set pre-Xcode-16 single-icon flow, or
  Android's legacy (non-adaptive) launcher icon set (mdpi through xxxhdpi),
  generate them from `icon/app-icon-1024.png` via Xcode/Android Studio's
  asset catalog tooling — both platforms' current tooling can derive the
  full set from one source image.
