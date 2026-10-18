'use strict';
const fs = require('node:fs');
(async () => {
  const sharp = require(process.argv[2]);
  const job = JSON.parse(fs.readFileSync(0, 'utf8'));
  if (!Number.isInteger(job.quality) || job.quality < 1 || job.quality > 100) throw Error('Invalid quality');
  const meta = await sharp(job.input, {animated: true}).metadata();
  if ((meta.pages || 1) > 1) {
    process.stdout.write(JSON.stringify({skipped:'animated-source-requires-separate-review'})); return;
  }
  if (meta.orientation && meta.orientation !== 1) {
    process.stdout.write(JSON.stringify({skipped:'oriented-source-requires-separate-review'})); return;
  }
  if (!['png','jpeg'].includes(meta.format)) throw Error('Expected actual PNG or JPEG');
  const bytes = await sharp(job.input).keepIccProfile().webp({
    quality:job.quality, lossless:!!job.lossless, effort:4, alphaQuality:100
  }).toBuffer();
  const output = await sharp(bytes).metadata();
  fs.writeFileSync(job.output, bytes, {flag:'wx'});
  process.stdout.write(JSON.stringify({sharpVersion:sharp.versions.sharp,
    sourceWidth:meta.width,sourceHeight:meta.height,width:output.width,height:output.height,
    sourceHasAlpha:!!meta.hasAlpha,hasAlpha:!!output.hasAlpha,bytes:bytes.length}));
})().catch(error => { process.stderr.write(String(error)+'\n'); process.exitCode=1; });
