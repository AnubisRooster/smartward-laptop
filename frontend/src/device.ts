/** True when SmartWard is open on a phone (or any device) through the private https address, not in the laptop's own window. */
export const onPhone = typeof location !== 'undefined' && location.protocol === 'https:' && !/^(localhost|127\.)/.test(location.hostname);
