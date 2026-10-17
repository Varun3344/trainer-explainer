#!/usr/bin/env node
/**
 * Render the panel page to a transparent PNG per video frame.
 *
 *   node tools/render_panel.mjs projects/<name> [--workers 2] [--preview 1.5,6,12]
 *
 * Reads <project>/out/timeline.json, writes <project>/out/frames/f00000.png ...
 * --preview writes only out/preview_<t>.png for the given times (quick layout check).
 * Every frame is posed by seeking the page to its time, so frames are split across --workers tabs of one browser.
 * Browser: installed Google Chrome by default, else Playwright's Chromium; CHROME_PATH=/path/to/chrome overrides.
 */
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const project = args[0];
if (!project || project.startsWith('--')) {
  console.error('usage: node tools/render_panel.mjs projects/<name> [--workers 2] [--preview 1.5,6,12]');
  process.exit(1);
}
const outDir = path.resolve(project, 'out');
const tl = JSON.parse(fs.readFileSync(path.join(outDir, 'timeline.json'), 'utf8'));
const page = 'file://' + path.resolve(opt('--page', path.join(here, '..', 'panel', 'panel.html')));
const workers = Math.max(1, Number(opt('--workers', '2')));
const preview = opt('--preview');

async function launch() {
  if (process.env.CHROME_PATH) return chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH });
  try {
    return await chromium.launch({ headless: true, channel: 'chrome' });
  } catch {
    return chromium.launch({ headless: true });
  }
}

async function openTab(browser) {
  const tab = await browser.newPage({ viewport: { width: tl.width, height: tl.height }, deviceScaleFactor: 1 });
  await tab.goto(page);
  await tab.evaluate(() => document.fonts.ready);
  await tab.evaluate((t) => window.__init(t), tl);
  return tab;
}

async function shot(tab, t, file) {
  await tab.evaluate((t) => window.__seek(t), t);
  await tab.screenshot({ path: file, omitBackground: true, type: 'png' });
}

const browser = await launch();
try {
  if (preview) {
    const tab = await openTab(browser);
    for (const s of preview.split(',')) {
      const f = path.join(outDir, `preview_${Number(s).toFixed(2)}.png`);
      await shot(tab, Number(s), f);
      console.log('preview', f);
    }
  } else {
    const frames = path.join(outDir, 'frames');
    fs.rmSync(frames, { recursive: true, force: true });
    fs.mkdirSync(frames, { recursive: true });
    const total = Math.ceil(tl.duration * tl.fps);
    let next = 0, done = 0;
    const started = Date.now();
    const work = async () => {
      const tab = await openTab(browser);
      while (next < total) {
        const n = next++;
        await shot(tab, n / tl.fps, path.join(frames, `f${String(n).padStart(5, '0')}.png`));
        if (++done % 240 === 0 || done === total) {
          const secs = (Date.now() - started) / 1000;
          console.log(`${done}/${total} frames  ${(done / secs).toFixed(1)} fps`);
        }
      }
    };
    await Promise.all(Array.from({ length: workers }, work));
    console.log(`${total} frames -> ${frames}`);
  }
} finally {
  await browser.close();
}
