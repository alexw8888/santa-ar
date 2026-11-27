import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { lstatSync, renameSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const docs = fileURLToPath(new URL('./docs/', import.meta.url));
const release = fileURLToPath(new URL('./santa-release.zip', import.meta.url));
const temporaryZip = fileURLToPath(new URL(`./.santa-release-${randomUUID()}.zip`, import.meta.url));

const pages = [
  'Santa_Chaiiwala.html',
  'Santa_Aisle24.html',
  'Santa_Bouquet_Cafe.html',
  'Santa_Landmark.html',
  'Santa_Mello.html',
  'Santa_Yunqueen.html',
];
const models = ['santa01', 'santa02', 'santa03', 'santa04', 'santa05', 'santa06'];
const files = [
  ...pages,
  'model-viewer.min.js',
  'model-viewer-LICENSE',
  ...models.flatMap((model) => [
    `${model}.glb`,
    `${model}-android.glb`,
    `${model}.usdz`,
    `${model}-poster.webp`,
  ]),
];

try {
  for (const file of files) {
    if (!lstatSync(new URL(`./docs/${file}`, import.meta.url), { throwIfNoEntry: false })?.isFile()) {
      throw new Error(`Expected a file at docs/${file}`);
    }
  }

  const options = { cwd: docs, stdio: 'inherit' };
  if (process.platform === 'win32') {
    execFileSync('tar.exe', ['-a', '-c', '-f', temporaryZip, '--', ...files], options);
  } else {
    // Info-ZIP's -MM makes a missing or unreadable input a fatal error.
    execFileSync('zip', ['-q', '-MM', temporaryZip, ...files], options);
  }

  renameSync(temporaryZip, release);
  console.log(`Created ${release} with ${files.length} files.`);
} catch (error) {
  console.error(`Release creation failed. ${error.message}`);
  process.exitCode = 1;
} finally {
  rmSync(temporaryZip, { force: true });
}
