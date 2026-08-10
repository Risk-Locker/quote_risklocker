"use client";

type Listener = (pending: number) => void;

let pending = 0;
const listeners = new Set<Listener>();

export function beginRequest() {
  pending += 1;
  emit();
}

export function endRequest() {
  pending = Math.max(0, pending - 1);
  emit();
}

export function isBusy() {
  return pending > 0;
}

export function subscribe(listener: Listener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function emit() {
  listeners.forEach((listener) => listener(pending));
}
