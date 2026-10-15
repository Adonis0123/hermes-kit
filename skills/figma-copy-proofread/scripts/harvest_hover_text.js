// Paste as browser_console `expression`. Returns hover-only copy (tooltips,
// title attributes) without real mouse hovers: static attributes are read
// directly; JS tooltips (Base UI / Radix / floating-ui) are opened by
// pointer-entering each marked trigger in turn.
// Probes at most 12 triggers per call (~11s); if `more` is true, run again
// with START raised by 12.
(async () => {
  const START = 0;
  const BATCH = 12;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const visible = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  // Scope to the open dialog when there is one; player caption menus are dialogs too, skip them.
  const ROOT = [...document.querySelectorAll('[role=dialog]')]
    .filter((d) => visible(d) && d.innerText.trim() && !/Caption|Beginning of dialog/.test(d.innerText))
    .sort((a, b) => b.innerText.length - a.innerText.length)[0] || document.body;
  const label = (el) => (el.innerText || el.getAttribute('aria-label') || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 40);
  const out = [];
  const seen = new Set();
  const add = (trigger, text, via) => {
    text = (text || '').trim().replace(/\s+/g, ' ');
    if (!text || seen.has(trigger + '|' + text)) return;
    seen.add(trigger + '|' + text);
    out.push({ trigger, text, via });
  };
  for (const el of ROOT.querySelectorAll('[title],[data-tooltip],[data-tip],[data-title]')) {
    if (!visible(el)) continue;
    const tip = el.getAttribute('title') || el.dataset.tooltip || el.dataset.tip || el.dataset.title || '';
    if (tip.trim() !== (el.innerText || '').trim()) add(label(el), tip, 'attr');
  }
  // Libraries mark their triggers; only fall back to icon-only controls when none are marked.
  const marked = [...ROOT.querySelectorAll('[data-base-ui-tooltip-trigger],[aria-describedby],[data-radix-tooltip-trigger]')];
  const pool = marked.length ? marked
    : [...ROOT.querySelectorAll('button,[role=button],[role=switch]')].filter((e) => !(e.innerText || '').trim());
  const all = [...new Set(pool)].filter(visible);
  const triggers = all.slice(START, START + BATCH);
  // Popups mount with zero size while animating in, so don't filter them by visibility.
  const tooltipTexts = () => new Set([...document.querySelectorAll(
    '[role=tooltip],[data-slot=tooltip-popup],.ant-tooltip-inner,[data-radix-popper-content-wrapper]')]
    .map((t) => t.innerText.trim()).filter(Boolean));
  const opts = { bubbles: true, pointerType: 'mouse' };
  for (const el of triggers) {
    const before = tooltipTexts();
    // floating-ui needs over + move, not just enter.
    for (const t of ['pointerenter', 'pointerover', 'pointermove']) el.dispatchEvent(new PointerEvent(t, opts));
    for (const t of ['mouseenter', 'mouseover', 'mousemove']) el.dispatchEvent(new MouseEvent(t, opts));
    await sleep(700);
    for (const t of tooltipTexts()) if (!before.has(t)) add(label(el), t, 'hover');
    for (const t of ['pointerleave', 'pointerout']) el.dispatchEvent(new PointerEvent(t, opts));
    for (const t of ['mouseleave', 'mouseout']) el.dispatchEvent(new MouseEvent(t, opts));
    await sleep(200);
  }
  return { probed: triggers.length, total: all.length, more: START + BATCH < all.length, found: out };
})()
