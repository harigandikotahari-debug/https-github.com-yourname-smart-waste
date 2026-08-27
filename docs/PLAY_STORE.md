# Publishing SwachhAI to Google Play

This is the honest, step-by-step path from the live web app to a real
Play Store listing, using a no-code web-to-Android packager (no local
Android Studio/SDK required). It's split clearly into what's already
prepared for you vs. the handful of steps only you can complete (they
require your own Google account, payment, and identity).

## Already prepared

- **Live app**: your deployed URL on Streamlit Cloud (see chat history
  for the exact link, or "Manage app" in your Streamlit Cloud dashboard)
- **App name**: SwachhAI
- **Icon assets**: `branding/play_store/play_store_icon_512.png` (512x512,
  required store icon), `branding/android_adaptive_icon/` (Android
  adaptive icon foreground/background layers), `branding/play_store/feature_graphic_1024x500.png`
  (Play Store listing banner)
- **Privacy policy**: published, publicly viewable page (get the URL
  from the artifact you were given — make sure it's set to shared/public
  from the page's share menu, since Play Console requires a *public*
  privacy policy URL)

## Step 1 — Package the app (PWABuilder, free, no install)

1. Go to **[pwabuilder.com](https://www.pwabuilder.com)**.
2. Enter your live Streamlit app URL and let it analyze the site.
3. PWABuilder will report your site isn't a full PWA (no manifest/service
   worker — expected, Streamlit doesn't generate one). That's fine — go
   to the **Android** package option anyway; it can still generate a
   plain WebView-wrapped Android package pointed at your URL without
   requiring full PWA compliance.
4. In the Android package options:
   - **Package ID**: reverse-domain style, e.g. `com.swachhai.app`
   - **App name**: `SwachhAI`
   - **Icon**: upload `branding/play_store/play_store_icon_512.png`
   - Leave "Trusted Web Activity" unchecked/use the WebView-wrapper
     option if offered — TWA needs Digital Asset Link verification at
     your domain root, which a `*.streamlit.app` subdomain doesn't
     support (see `docs/LIMITATIONS.md`-style honesty: this is a real
     constraint, not a PWABuilder bug).
5. Download the generated project/package (an `.aab` — Android App
   Bundle — is what Play Console wants; PWABuilder can build and sign
   one for you, or hand you a project to build yourself if you later
   install Android Studio).

## Step 2 — Google Play Console account (only you can do this)

1. Go to **[play.google.com/console](https://play.google.com/console)**.
2. Sign in with your Google account, pay the one-time **$25** registration
   fee, complete identity verification.
3. This step requires your own payment method and identity — I can't do
   it on your behalf.

## Step 3 — Create the app listing

1. Play Console → **Create app** → fill in name (`SwachhAI`), default
   language, app/game = App, free/paid = Free (or your choice).
2. **Store listing** fields — use the copy below.
3. Upload `branding/play_store/play_store_icon_512.png` as the app icon
   and `branding/play_store/feature_graphic_1024x500.png` as the feature
   graphic. You'll also need 2+ phone screenshots — take these from your
   live app (any page, at a phone-sized browser window, or from an
   emulator running the packaged app).
4. **Privacy policy URL**: paste your published privacy-policy artifact
   URL.
5. **Data safety form**: declare that the app collects photos (camera/
   gallery) for on-device-adjacent AI processing, and account info
   (username/email) for login — see `docs/PLAY_STORE.md#privacy-policy`
   above and the published policy for exact wording to match.
6. **Content rating questionnaire**: answer honestly — no violence, no
   user-generated content shared publicly, no ads, no data selling. This
   should land at "Everyone."
7. Upload the `.aab` from Step 1 under **Production → Create release**.
8. Submit for review. Google's review typically takes a few hours to a
   few days for a first submission.

## Store listing copy

**App name**: `SwachhAI`

**Short description** (max 80 characters):
```
AI waste sorting, smart bin monitoring & optimized collection routes
```

**Full description** (max 4000 characters):
```
SwachhAI is an AI-powered waste segregation and intelligent collection
system, built for Smart India Hackathon.

WHAT IT DOES
• Point your camera at an item — SwachhAI's AI detects and classifies
  it into the correct waste category (plastic, paper, cardboard, glass,
  metal, organic, or other) and tells you which bin it belongs in.
• Uncertain items are never guessed — low-confidence results are
  flagged "Unknown / Manual Verification Required" instead of a wrong
  automatic answer.
• Municipal operators get a live bin-monitoring dashboard: fill levels,
  AI-predicted overflow risk, and a priority score per bin.
• An optimized multi-vehicle collection route is generated automatically
  for bins that actually need a visit — not a fixed daily round.

WHO IT'S FOR
• Citizens: snap a photo, get an instant, explained segregation
  recommendation.
• Collection operators: see your assigned bins and today's optimized
  route.
• Municipal admins: monitor the whole system, manage bins and users,
  and review real model performance (precision/recall/F1, not just a
  marketing number).

HONESTY BY DESIGN
SwachhAI is upfront about what's real vs. simulated: the waste
classifier is a genuinely trained AI model evaluated on held-out test
data, while bin sensor history in this prototype build is clearly
labeled simulated demo data. Every screen tells you which is which.

A Smart India Hackathon prototype demonstrating how computer vision and
data science can make municipal waste collection cleaner, faster, and
less wasteful.
```

**Category**: Tools (or Lifestyle — either fits; Tools is the safer default)

**Content rating**: Everyone (no ads, no user-generated public content, no violence)

## Notes on the WebView-wrapper approach

- Since this isn't a verified TWA, Android may show a thin URL/address
  bar at the top the first time the app opens (standard for
  Custom-Tabs-based WebView wrappers without domain verification). This
  is a known, accepted trade-off — documented here rather than hidden.
- If you later want the seamless no-address-bar TWA experience, you'd
  need a custom domain you fully control (to serve
  `/.well-known/assetlinks.json` at the root) — see `docs/DEPLOYMENT.md`
  for hosting options that support custom domains (Render, Railway).
