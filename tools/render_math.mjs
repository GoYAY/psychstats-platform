// Build-time formula layout. No math JavaScript is required in the browser.
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const katex = require('../site/assets/vendor/katex/katex.min.js');
let input = '';
for await (const chunk of process.stdin) input += chunk;
const formulas = JSON.parse(input);
const result = {};
for (const [slug, latex] of Object.entries(formulas)) {
  try {
    result[slug] = katex.renderToString(latex, {
      displayMode: true, output: 'htmlAndMathml', throwOnError: true,
      trust: context => context.command === '\\htmlClass', strict: 'ignore', maxExpand: 1000, maxSize: 10,
    });
  } catch (error) {
    process.stderr.write(`${slug}: ${error.message}\n`);
    process.exit(1);
  }
}
process.stdout.write(JSON.stringify(result));
