/** 16-bit mono WAV bytes from samples in -1..1. Every phone browser can make these, and Whisper reads them directly. */
export function encodeWav(samples: Float32Array, rate = 16000): Blob {
  const buf = new ArrayBuffer(44 + samples.length * 2); const v = new DataView(buf);
  const str = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); str(8, 'WAVE'); str(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); str(36, 'data'); v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) { const x = Math.max(-1, Math.min(1, samples[i])); v.setInt16(44 + i * 2, x < 0 ? x * 0x8000 : x * 0x7fff, true); }
  return new Blob([buf], { type: 'audio/wav' });
}

/** Down-sample one block to 16 kHz (averaging the samples that fall in each output step); `carry` keeps the fraction left over for the next block. */
export function toRate16k(input: Float32Array, inRate: number, carry: { pos: number } = { pos: 0 }): Float32Array {
  if (inRate === 16000) return input;
  const ratio = inRate / 16000; const out: number[] = []; let pos = carry.pos;
  while (pos + ratio <= input.length) {
    const a = Math.floor(pos), b = Math.max(a + 1, Math.floor(pos + ratio)); let s = 0; for (let i = a; i < b && i < input.length; i++) s += input[i];
    out.push(s / (b - a)); pos += ratio;
  }
  carry.pos = pos - input.length;
  return Float32Array.from(out);
}
