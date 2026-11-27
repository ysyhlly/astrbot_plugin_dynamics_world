import test from 'node:test';
import assert from 'node:assert/strict';
import {parsePngCharaChunk} from '../pages/world/png-chara.js';

function makePngChunk(type, dataBytes) {
  const len = dataBytes.length;
  const out = new Uint8Array(12 + len);
  const view = new DataView(out.buffer);
  view.setUint32(0, len, false);
  for (let i = 0; i < 4; i++) out[4 + i] = type.charCodeAt(i);
  out.set(dataBytes, 8);
  // CRC placeholder (parser doesn't enforce CRC for offline browser uploads)
  view.setUint32(8 + len, 0, false);
  return out;
}

function buildMinimalPng(extraChunks = []) {
  const sig = new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = makePngChunk('IHDR', new Uint8Array(13));
  const iend = makePngChunk('IEND', new Uint8Array(0));
  const parts = [sig, ihdr, ...extraChunks, iend];
  const total = parts.reduce((acc, p) => acc + p.length, 0);
  const buf = new Uint8Array(total);
  let off = 0;
  for (const p of parts) {
    buf.set(p, off);
    off += p.length;
  }
  return buf;
}

test('parsePngCharaChunk extracts SillyTavern V2 UTF-8 JSON from tEXt chara chunk', () => {
  const card = {
    spec: 'chara_card_v2',
    spec_version: '2.0',
    data: {name: '夏目安安', description: '喜欢宅在小屋里写字与品茶的角色卡。'},
  };
  const b64 = Buffer.from(JSON.stringify(card), 'utf-8').toString('base64');
  const payload = Buffer.concat([Buffer.from('chara\0', 'latin1'), Buffer.from(b64, 'latin1')]);
  const png = buildMinimalPng([makePngChunk('tEXt', new Uint8Array(payload))]);
  const extracted = parsePngCharaChunk(png);
  const parsed = JSON.parse(extracted);
  assert.equal(parsed.data.name, '夏目安安');
  assert.match(parsed.data.description, /小屋/);
});

test('parsePngCharaChunk supports uncompressed iTXt chara chunk', () => {
  const card = {spec: 'chara_card_v2', data: {name: '林间旅人'}};
  const b64 = Buffer.from(JSON.stringify(card), 'utf-8').toString('base64');
  // keyword\0 compFlag(0) compMethod(0) lang\0 trans\0 text
  const payload = Buffer.concat([
    Buffer.from('chara\0\0\0\0\0', 'latin1'),
    Buffer.from(b64, 'latin1'),
  ]);
  const png = buildMinimalPng([makePngChunk('iTXt', new Uint8Array(payload))]);
  const parsed = JSON.parse(parsePngCharaChunk(png));
  assert.equal(parsed.data.name, '林间旅人');
});

test('parsePngCharaChunk rejects non-PNG and PNG without chara metadata', () => {
  assert.throws(() => parsePngCharaChunk(new Uint8Array([1, 2, 3, 4])), /PNG/);
  const emptyPng = buildMinimalPng([]);
  assert.throws(() => parsePngCharaChunk(emptyPng), /chara/);
});
