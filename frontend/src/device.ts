/** True when SmartWard is open on a phone (or any device) through the private https address, not in the laptop's own window. */
export const onPhone = typeof location !== 'undefined' && location.protocol === 'https:' && !/^(localhost|127\.)/.test(location.hostname);

/** Menus show as a centred dialog rather than a dropdown here: on a phone, or a window too narrow for a dropdown to fit beside its button. */
export const useSheet = () => onPhone || (typeof window !== 'undefined' && window.innerWidth < 640);
