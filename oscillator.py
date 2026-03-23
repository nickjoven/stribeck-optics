"""
Stribeck Optics — Raspberry Pi High-Frequency PWM Oscillator Driver.

Drives a 12V LED headlight via hardware PWM on GPIO 18 through a MOSFET gate.
Supports two modes:

  1. Carrier-only:  Steady kHz PWM at configurable duty cycle.
  2. Stress test:   Low-frequency envelope (3–5 Hz) modulated onto the kHz carrier,
                    reproducing the worst-case flicker scenario for patent comparison.

The carrier frequency (2–10 kHz) is above flicker-fusion; the envelope is the
"danger zone" signal that the temporal shaping is designed to suppress.

Hardware wiring:
    GPIO 18 ──► gate of IRLZ44N (logic-level N-MOSFET)
    MOSFET drain ──► LED cathode
    LED anode ──► +12 V supply
    MOSFET source ──► GND (shared with Pi GND)

Safety:
    - Bench use only.  Do not mount on a vehicle for road testing.
    - Keep LED pointed at a diffuser or wall, never at eyes.
    - 3–5 Hz stress-test mode can trigger photosensitive responses;
      run only in controlled conditions with informed participants.

N. Joven, 2026.  CC0.
"""

from __future__ import annotations

import argparse
import math
import signal
import sys
import time

# ---------------------------------------------------------------------------
# Hardware PWM via pigpio (must be installed: sudo apt install pigpio)
# Falls back to software simulation for desktop development / CI.
# ---------------------------------------------------------------------------

try:
    import pigpio

    _HAS_PIGPIO = True
except ImportError:
    _HAS_PIGPIO = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PWM_PIN = 18  # BCM numbering — hardware PWM0
CARRIER_HZ_DEFAULT = 5_000  # 5 kHz carrier
DUTY_PCT_DEFAULT = 70  # percent ON during carrier high
ENVELOPE_HZ_DEFAULT = 4.0  # stress-test envelope
ENVELOPE_DEPTH_DEFAULT = 0.5  # 0 = no modulation, 1 = full on/off
SAMPLE_RATE_HZ = 200  # envelope update rate (software loop)

# pigpio uses 0–1_000_000 for duty cycle (microsecond resolution at 1 MHz)
PIGPIO_DUTY_RANGE = 1_000_000


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Simulated GPIO for development without a Pi
# ---------------------------------------------------------------------------


class _SimulatedPi:
    """Drop-in stub so the script can run on any machine for testing logic."""

    def __init__(self) -> None:
        self._freq = 0
        self._duty = 0

    def hardware_PWM(self, pin: int, freq: int, duty: int) -> None:  # noqa: N802
        self._freq = freq
        self._duty = duty

    def stop(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Core driver
# ---------------------------------------------------------------------------


class OscillatorDriver:
    """High-frequency PWM driver with optional low-frequency envelope."""

    def __init__(
        self,
        carrier_hz: float = CARRIER_HZ_DEFAULT,
        duty_pct: float = DUTY_PCT_DEFAULT,
        envelope_hz: float = 0.0,
        envelope_depth: float = ENVELOPE_DEPTH_DEFAULT,
        pin: int = PWM_PIN,
        simulate: bool = False,
    ) -> None:
        self.carrier_hz = carrier_hz
        self.base_duty_pct = _clamp(duty_pct, 0, 100)
        self.envelope_hz = envelope_hz
        self.envelope_depth = _clamp(envelope_depth, 0, 1)
        self.pin = pin
        self._running = False

        if simulate or not _HAS_PIGPIO:
            if not simulate and not _HAS_PIGPIO:
                print(
                    "WARNING: pigpio not available — running in simulation mode.",
                    file=sys.stderr,
                )
            self.pi = _SimulatedPi()
            self._simulated = True
        else:
            self.pi = pigpio.pi()
            if not self.pi.connected:
                raise RuntimeError(
                    "Cannot connect to pigpio daemon. Run: sudo pigpiod"
                )
            self._simulated = False

    # -- low-level PWM --

    def _set_duty(self, duty_pct: float) -> None:
        """Set instantaneous duty cycle (0–100 %) at the current carrier freq."""
        duty_micro = int(_clamp(duty_pct / 100.0, 0, 1) * PIGPIO_DUTY_RANGE)
        self.pi.hardware_PWM(self.pin, int(self.carrier_hz), duty_micro)

    # -- public API --

    def start(self) -> None:
        """Start the carrier (and optional envelope modulation loop)."""
        self._running = True
        print(
            f"Carrier: {self.carrier_hz:.0f} Hz, base duty: {self.base_duty_pct:.1f}%"
        )
        if self.envelope_hz > 0:
            print(
                f"Envelope: {self.envelope_hz:.1f} Hz, depth: {self.envelope_depth:.0%}"
            )
            self._run_envelope_loop()
        else:
            self._set_duty(self.base_duty_pct)
            print("Steady carrier — press Ctrl-C to stop.")
            try:
                while self._running:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                pass
            finally:
                self.stop()

    def _run_envelope_loop(self) -> None:
        """Software loop that amplitude-modulates the carrier duty cycle."""
        dt = 1.0 / SAMPLE_RATE_HZ
        t0 = time.monotonic()
        print("Envelope modulation running — press Ctrl-C to stop.")
        try:
            while self._running:
                t = time.monotonic() - t0
                # Sinusoidal envelope: modulates duty between
                #   base * (1 - depth) … base
                envelope = 0.5 * (1 + math.sin(2 * math.pi * self.envelope_hz * t))
                modulated_duty = self.base_duty_pct * (
                    1 - self.envelope_depth + self.envelope_depth * envelope
                )
                self._set_duty(modulated_duty)
                if self._simulated:
                    # Print a simple ASCII bar every ~0.25 s
                    if int(t * 4) != int((t - dt) * 4):
                        bar = "#" * int(modulated_duty / 2)
                        print(f"  t={t:6.2f}s  duty={modulated_duty:5.1f}%  |{bar}")
                time.sleep(dt)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        self._running = False
        self._set_duty(0)
        self.pi.stop()
        print("Oscillator stopped.")

    def request_stop(self) -> None:
        """Signal-safe stop request."""
        self._running = False


# ---------------------------------------------------------------------------
# Temporal modulation transfer analysis
# ---------------------------------------------------------------------------


def temporal_mtf(carrier_hz: float, duty_pct: float, harmonics: int = 20):
    """
    Compute the Fourier coefficients of a PWM waveform.

    Returns arrays (freqs_hz, amplitudes) for the first *harmonics* components.
    A well-chosen duty cycle concentrates energy in the DC + low harmonics,
    pushing the "flicker energy" above the critical flicker-fusion frequency
    (~60–80 Hz) where the eye integrates it as steady luminance.
    """
    import numpy as np

    duty = duty_pct / 100.0
    ns = np.arange(1, harmonics + 1)
    # Fourier coefficients of a rectangular pulse train
    amplitudes = np.abs(np.sinc(ns * duty)) * 2 * duty
    freqs = ns * carrier_hz
    # Prepend DC component
    freqs = np.concatenate([[0], freqs])
    amplitudes = np.concatenate([[duty], amplitudes])
    return freqs, amplitudes


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stribeck Optics — Raspberry Pi PWM oscillator driver."
    )
    parser.add_argument(
        "--carrier-hz",
        type=float,
        default=CARRIER_HZ_DEFAULT,
        help="Carrier PWM frequency in Hz (default: %(default)s).",
    )
    parser.add_argument(
        "--duty",
        type=float,
        default=DUTY_PCT_DEFAULT,
        help="Base duty cycle %% (default: %(default)s).",
    )
    parser.add_argument(
        "--envelope-hz",
        type=float,
        default=0.0,
        help="Low-frequency envelope for stress test (0 = off, default: %(default)s).",
    )
    parser.add_argument(
        "--envelope-depth",
        type=float,
        default=ENVELOPE_DEPTH_DEFAULT,
        help="Envelope modulation depth 0–1 (default: %(default)s).",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run without real hardware (desktop development).",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Print temporal MTF analysis instead of driving hardware.",
    )
    args = parser.parse_args()

    if args.analyze:
        freqs, amps = temporal_mtf(args.carrier_hz, args.duty)
        print(f"Temporal MTF for {args.carrier_hz:.0f} Hz carrier, {args.duty:.0f}% duty:\n")
        print(f"  {'Harmonic':>10}  {'Freq (Hz)':>10}  {'Amplitude':>10}")
        print(f"  {'--------':>10}  {'---------':>10}  {'---------':>10}")
        for i, (f, a) in enumerate(zip(freqs, amps)):
            label = "DC" if i == 0 else str(i)
            print(f"  {label:>10}  {f:>10.0f}  {a:>10.4f}")
        return

    driver = OscillatorDriver(
        carrier_hz=args.carrier_hz,
        duty_pct=args.duty,
        envelope_hz=args.envelope_hz,
        envelope_depth=args.envelope_depth,
        simulate=args.simulate,
    )
    signal.signal(signal.SIGINT, lambda *_: driver.request_stop())
    signal.signal(signal.SIGTERM, lambda *_: driver.request_stop())
    driver.start()


if __name__ == "__main__":
    main()
