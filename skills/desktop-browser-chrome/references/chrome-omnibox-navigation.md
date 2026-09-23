# Chrome omnibox navigation — session notes

Validated 2026-08-08 on the owner's macOS with `computer_use` / cua-driver.

## Task

User: load computer-use skill, open Chrome, go to a website (example.com below).

## What failed (do not repeat as the main path)

1. Background click address bar → type `https://example.com` → background `return`.
2. Result: omnibox held the URL; window title stayed on Jenkins pipeline.
3. Foreground `return` alone after background type was still unverifiable until the full `cmd+l` + type + return sequence ran in foreground.

## What worked

```
key(keys="cmd+l", delivery_mode="foreground")
type(text="https://example.com", delivery_mode="foreground")
key(keys="return", delivery_mode="foreground", capture_after=true)
```

Post-condition: window title became  
`Example Domain - Google Chrome`.

## Agent product lesson

- "Address bar updated" ≠ "navigated".
- User saying "你应该能继续操作" means keep escalating; do not hand back a half-done omnibox state as the final answer when more rungs remain.
