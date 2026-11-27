/* Pure SillyTavern PNG Character Card V2/V3 `chara` chunk parser (browser & Node compatible). */

const PNG_SIG = [137, 80, 78, 71, 13, 10, 26, 10];

function decodeBase64Utf8(b64) {
  const clean = String(b64 || "").replace(/\s+/g, "");
  const bin = atob(clean);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder("utf-8").decode(bytes);
}

export function parsePngCharaChunk(buffer) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  if (bytes.length < 24) throw new Error("PNG 文件过小或格式无效");
  for (let i = 0; i < PNG_SIG.length; i++) {
    if (bytes[i] !== PNG_SIG[i]) throw new Error("文件不是有效的 PNG 图片");
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const latin1 = new TextDecoder("latin1");
  let offset = 8;
  let fallbackV3 = "";
  while (offset + 12 <= bytes.length) {
    const length = view.getUint32(offset, false);
    const type = latin1.decode(bytes.subarray(offset + 4, offset + 8));
    const dataStart = offset + 8;
    const dataEnd = dataStart + length;
    if (dataEnd + 4 > bytes.length) break;
    if (type === "tEXt" || type === "iTXt") {
      const chunk = bytes.subarray(dataStart, dataEnd);
      const nulIdx = chunk.indexOf(0);
      if (nulIdx > 0) {
        const keyword = latin1.decode(chunk.subarray(0, nulIdx)).trim().toLowerCase();
        if (keyword === "chara" || keyword === "ccv3") {
          let payloadBytes = null;
          if (type === "tEXt") {
            payloadBytes = chunk.subarray(nulIdx + 1);
          } else {
            const compFlag = chunk[nulIdx + 1] || 0;
            if (compFlag === 0) {
              const langEnd = chunk.indexOf(0, nulIdx + 3);
              const transEnd = langEnd >= 0 ? chunk.indexOf(0, langEnd + 1) : -1;
              if (transEnd >= 0) payloadBytes = chunk.subarray(transEnd + 1);
            }
          }
          if (payloadBytes && payloadBytes.length) {
            const rawText = latin1.decode(payloadBytes).trim();
            let jsonStr = rawText;
            if (!rawText.startsWith("{")) {
              jsonStr = decodeBase64Utf8(rawText);
            }
            JSON.parse(jsonStr);
            if (keyword === "chara") return jsonStr;
            fallbackV3 = jsonStr;
          }
        }
      }
    }
    if (type === "IEND") break;
    offset = dataEnd + 4;
  }
  if (fallbackV3) return fallbackV3;
  throw new Error("未在 PNG 中找到 SillyTavern 角色卡元数据（chara 块）");
}
