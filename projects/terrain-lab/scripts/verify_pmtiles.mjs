import assert from 'node:assert/strict';
import { parseArchiveUrl, StrictRangeSource } from '../src/sandbox/pmtiles.ts';

assert.equal(parseArchiveUrl('pmtiles://https://example.org/tiles.pmtiles'), 'https://example.org/tiles.pmtiles');
assert.throws(() => parseArchiveUrl('http://example.org/tiles.pmtiles'), /HTTPS/);
assert.throws(() => parseArchiveUrl('https://user:secret@example.org/tiles.pmtiles'), /username or password/);
assert.throws(() => parseArchiveUrl('not a url'), /valid absolute/);

const originalFetch = globalThis.fetch;
try {
  let requestedRange = '';
  globalThis.fetch = async (_url, options) => {
    requestedRange = options.headers.Range;
    return new Response(new Uint8Array([80, 77, 1, 2]), {
      status: 206,
      headers: { 'Content-Range': 'bytes 0-3/100', 'Content-Length': '4', ETag: 'test-v1' },
    });
  };
  const source = new StrictRangeSource('https://example.org/small.pmtiles');
  const result = await source.getBytes(0, 4);
  assert.equal(requestedRange, 'bytes=0-3');
  assert.equal(result.data.byteLength, 4);
  assert.equal(result.etag, 'test-v1');

  globalThis.fetch = async () => new Response(new Uint8Array([80, 77, 1, 2]), {
    status: 206, headers: { 'Content-Length': '4' },
  });
  assert.equal((await source.getBytes(0, 4)).data.byteLength, 4,
    'A valid 206 is accepted when CORS does not expose Content-Range');

  let bodyCanceled = false;
  globalThis.fetch = async () => ({
    status: 200,
    body: { cancel: async () => { bodyCanceled = true; } },
  });
  await assert.rejects(source.getBytes(0, 16_384), /whole archive/);
  assert.equal(bodyCanceled, true, 'A 200 response is canceled before reading its body');

  globalThis.fetch = async () => new Response(new Uint8Array([1, 2, 3, 4]), {
    status: 206, headers: { 'Content-Range': 'bytes 5-8/100' },
  });
  await assert.rejects(source.getBytes(0, 4), /incorrect Content-Range/);

  globalThis.fetch = async () => { throw new TypeError('network failure'); };
  await assert.rejects(source.getBytes(0, 4), /CORS, network access/);
  console.log('PMTiles checks passed: URL validation, byte ranges, unexposed Content-Range, whole-file refusal, bad range, and CORS/network message.');
} finally { globalThis.fetch = originalFetch; }
