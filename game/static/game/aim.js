// Aim minigames turn player input into a single normalized accuracy value
// (0.0 = worst possible shot, 1.0 = perfect) which the server maps onto a
// damage band. Holding the contract to that one number is what keeps new
// minigames drop-in: implement `run()`, register it for a vehicle type, and
// nothing on the server changes.

export const AUTO_ACCURACY = 0.5;

// Resolves immediately at mid-band. Used when no minigame is registered for a
// vehicle type, and as the accessibility / fast-forward path.
export const instantAim = {
  name: 'instant',
  async run() {
    return AUTO_ACCURACY;
  },
};

const registry = new Map();

export function registerAim(vehicleType, minigame) {
  registry.set(vehicleType, minigame);
}

export function aimFor(vehicleType) {
  return registry.get(vehicleType) || instantAim;
}

// Runs the minigame registered for a vehicle type and returns an accuracy in
// [0, 1]. A minigame that throws or yields something unusable falls back to
// auto-resolve rather than blocking the attack outright.
export async function runAim(vehicleType, context = {}) {
  try {
    const accuracy = await aimFor(vehicleType).run(context);
    if (typeof accuracy !== 'number' || !Number.isFinite(accuracy)) return AUTO_ACCURACY;
    return Math.min(Math.max(accuracy, 0), 1);
  } catch (err) {
    console.error('Aim minigame failed, auto-resolving:', err);
    return AUTO_ACCURACY;
  }
}
