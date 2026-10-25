/** "Start talking" on the chat list opens the new chat with audio chat already on. */
let want = false;
export const wantAudioChat = () => { want = true; };
export const takeAudioChat = () => { const w = want; want = false; return w; };
