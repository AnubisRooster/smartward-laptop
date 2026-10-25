import QRCode from 'qrcode';

/** A scannable picture (PNG data address) of `text`: dark on white with a clear border, which phone cameras need even in dark mode. */
export const qrDataUrl = (text: string) => QRCode.toDataURL(text, { width: 176, margin: 2, errorCorrectionLevel: 'M', color: { dark: '#000000', light: '#ffffff' } });
