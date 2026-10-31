import { post } from './api';
import { isDesktop } from './desktop';

/** Saves a file the page made. The desktop window's web view ignores browser downloads, so there the API writes it into ~/Downloads;
 *  in a browser (and on the phone) it is an ordinary download. Returns where it went, for the toast. */
export async function saveFile(filename: string, blob: Blob): Promise<string> {
  if (isDesktop) {
    const bytes = new Uint8Array(await blob.arrayBuffer()); let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    const r = await post<{ path: string }>('/downloads', { filename, base64: btoa(bin) });
    return r.path;
  }
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  return `your downloads (${filename})`;
}
