let context;

// Unlock audio during the Download button's user gesture so the completion
// chime can play later, including while the user is looking at another window.
export function prepareCompletionSound() {
  try {
    if (!context || context.state === "closed") context = new AudioContext();
    return context
      .resume()
      .then(() => true)
      .catch(() => false);
  } catch {
    return Promise.resolve(false);
  }
}

export async function playCompletionSound() {
  if (!(await prepareCompletionSound())) return false;
  const start = context.currentTime + 0.02;
  [659.25, 880].forEach((frequency, index) => {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    const at = start + index * 0.18;
    oscillator.type = "sine";
    oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0, at);
    gain.gain.linearRampToValueAtTime(0.16, at + 0.025);
    gain.gain.exponentialRampToValueAtTime(0.001, at + 0.38);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.onended = () => {
      oscillator.disconnect();
      gain.disconnect();
    };
    oscillator.start(at);
    oscillator.stop(at + 0.4);
  });
  return true;
}
