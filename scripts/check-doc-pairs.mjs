#!/usr/bin/env node
// Fails when README.md or a docs/**/*.md page lacks its .zh-CN.md pair (or the reverse),
// or when either file is missing its language-switch first line.
// Exempt: AGENTS.md, CLAUDE.md, CONTEXT.md, LICENSE, llms.txt, docs/templates/**, skills/**, plugins/**.
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const EXEMPT_DIRS = ['docs/templates/', 'skills/', 'plugins/', 'node_modules/', '.git/'];
const ZH = '.zh-CN.md';

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(path.join(root, dir), { withFileTypes: true })) {
    const rel = dir ? `${dir}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      if (!EXEMPT_DIRS.some((d) => `${rel}/`.startsWith(d))) walk(rel, out);
    } else if (rel.endsWith('.md')) {
      out.push(rel);
    }
  }
  return out;
}

const candidates = ['README.md', ...(fs.existsSync(path.join(root, 'docs')) ? walk('docs') : [])]
  .filter((f) => fs.existsSync(path.join(root, f)));
const errors = [];

for (const file of candidates) {
  const isZh = file.endsWith(ZH);
  const pair = isZh ? file.slice(0, -ZH.length) + '.md' : file.slice(0, -3) + ZH;
  if (!fs.existsSync(path.join(root, pair))) {
    errors.push(`${file}: missing pair ${pair}`);
    continue;
  }
  const firstLine = fs.readFileSync(path.join(root, file), 'utf8').split('\n', 1)[0];
  const pairName = path.basename(pair);
  const expected = isZh ? `[English](${pairName}) | 简体中文` : `English | [简体中文](${pairName})`;
  if (firstLine.trim() !== expected) {
    errors.push(`${file}: first line should be "${expected}", got "${firstLine}"`);
  }
}

if (errors.length) {
  console.error(`check-doc-pairs: ${errors.length} problem(s)`);
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}
console.log(`check-doc-pairs: ${candidates.length} files OK`);
