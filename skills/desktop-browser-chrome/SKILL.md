---
name: desktop-browser-chrome
description: Use when opening URLs in the user's real Chrome.
version: 1.0.0
license: MIT
author: Adonis0123
platforms: [macos]
metadata:
  hermes:
    tags: [computer-use, chrome, desktop, navigation]
    category: desktop
    related_skills: [computer-use]
---

# Desktop browser chrome (Chrome via computer_use)

Load **`computer-use`** first for the full capture / escalate ladder.
This skill only adds **browser chrome** navigation validated on the owner's
macOS Chrome (cua-driver background + foreground).

## When to use

- User asks to open a site in **their** Chrome (not headless)
- Task needs logged-in profile / extensions / existing tabs
- Omnibox / tabs / window chrome — **not** page DOM (for page content
  prefer `cua_browser_*` when binding is exact, or headless `browser_*`)

## Success criteria (hard)

**Do not claim navigation success from address-bar text alone.**

| Signal | Enough? |
|--------|---------|
| Omnibox value = target URL | no |
| `type` → `effect: confirmed` | no |
| Window title / web-area label matches site | yes |
| Address bar + main content both match | yes (best) |

Example: after `https://example.com`, wait until title looks like
`Example Domain …` (not still the previous page, e.g. `… Jenkins`).

## Preferred open-URL sequence (macOS)

1. `list_apps` / `focus_app(app="Google Chrome", raise_window=false)`.
2. `capture(mode="som", app="Google Chrome")`.
3. If a tab title already is the target site → click that tab; done.
4. Else navigate with **foreground** chrome focus (one coherent sequence):

```
key(keys="cmd+l", delivery_mode="foreground")
type(text="https://example.com", delivery_mode="foreground")
key(keys="return", delivery_mode="foreground", capture_after=true)
```

5. Re-check title / web area. If still on old page → one more foreground
   `cmd+l` → type → `return`, or ask user to press Enter once.

## Background-first still applies — then escalate

Default `computer_use` is background. For Chrome omnibox:

| Attempt | Typical result | Next |
|---------|----------------|------|
| Click address field + type + background `return` | URL written; page may not change; Enter often `unverifiable` | Escalate submit to foreground |
| Foreground `cmd+l` + type + `return` | Page actually navigates | Verify title |

Do **not** re-type a URL that already confirmed in the omnibox; only
re-submit (or re-run the full foreground jump).

## Pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| Omnibox shows URL, content still old site | Background Enter / AXPress did not submit navigation | Foreground `cmd+l` → type → `return` |
| Click address field feels flaky | Omnibox UX / focus | Prefer `cmd+l` over clicking the text field |
| Huge SOM trees on Jenkins-like pages | Dense AX | Scope `app="Google Chrome"`; ignore page body until chrome is done |
| User said "continue yourself" | Expect agent to escalate, not stop at half-state | Keep going until title/content verify or one clear blocker |

## Related

- Full tool vocabulary + escalate ladder: skill `computer-use`
- Session notes: `references/chrome-omnibox-navigation.md`
