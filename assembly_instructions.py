"""
Stribeck Optics — Raspberry Pi Oscillator Assembly Instructions.

Step-by-step build guide for the high-frequency PWM prototype.
Run with:  python -m assembly_instructions

N. Joven, 2026.  CC0.
"""

ASSEMBLY = """
================================================================================
 STRIBECK OSCILLATOR — ASSEMBLY INSTRUCTIONS
 Raspberry Pi High-Frequency PWM Headlight Prototype
================================================================================

 SAFETY
────────────────────────────────────────────────────────────────────────────────
 - 12V supply can source enough current to cause burns.  Disconnect power
   before wiring changes.
 - LED headlight bulbs produce intense light.  Never look directly at the
   LED during operation.  Aim at a white diffuser board or wall.
 - The 3–5 Hz stress-test mode can trigger photosensitive responses.
   Run only in controlled conditions with informed participants.
 - This is bench equipment.  Do NOT mount on a vehicle for road use.


 BILL OF MATERIALS
────────────────────────────────────────────────────────────────────────────────
 Qty  Item                                     Est. Cost
 ───  ─────────────────────────────────────────  ─────────
  1   Raspberry Pi 4 Model B (2 GB+)            $45.00
  1   Raspberry Pi Camera Module v2 (8 MP)      $25.00
  1   5V 3A USB-C power supply (for Pi)          $8.00
  1   MicroSD card (16 GB+, with Raspberry       $8.00
      Pi OS pre-installed)
  1   IRLZ44N logic-level N-MOSFET               $1.50
  1   12V 5A DC power supply                    $12.00
  1   12V LED headlight bulb (H11 or similar)   $15.00
  2   10 kΩ resistor (1/4 W)                     $0.10
  1   100 Ω resistor (1/4 W)                     $0.10
  1   1N4007 flyback diode (or similar)           $0.10
  1   Full-size breadboard                        $5.00
  1   Jumper wire kit (M-M and M-F)               $3.00
  1   White acrylic diffuser sheet (A4 size)      $5.00
                                           ──────────────
                                     TOTAL   ~$128
 ───────────────────────────────────────────────────────────

 Optional (for analog frequency dial):
  1   10 kΩ potentiometer                        $2.00
  1   MCP3008 SPI ADC                            $3.50


 STEP 1 — PREPARE THE RASPBERRY PI
────────────────────────────────────────────────────────────────────────────────
 1.1  Flash Raspberry Pi OS (Bookworm, 64-bit) onto the MicroSD card.
      Use Raspberry Pi Imager:  https://www.raspberrypi.com/software/

 1.2  Boot the Pi, connect to Wi-Fi, and open a terminal.

 1.3  Install dependencies:

        sudo apt update
        sudo apt install -y pigpio python3-pigpio python3-numpy python3-opencv
        sudo systemctl enable pigpiod
        sudo systemctl start pigpiod

 1.4  Clone the repo:

        git clone https://github.com/nickjoven/stribeck-optics.git
        cd stribeck-optics

 1.5  Verify pigpio is running:

        pigs t      # should print the current tick (microseconds)


 STEP 2 — WIRE THE MOSFET DRIVER CIRCUIT
────────────────────────────────────────────────────────────────────────────────

 Schematic (active-low LED, N-channel MOSFET):

        +12V SUPPLY
            │
            │
        ┌───┴───┐
        │  LED  │   (12V headlight bulb, H11)
        │ bulb  │
        └───┬───┘
            │
            │  DRAIN
        ┌───┴───┐
        │IRLZ44N│   (logic-level N-MOSFET)
        │       │
        └───┬───┘
            │  SOURCE
            │
           GND  ◄── shared ground (Pi GND + 12V supply GND)


        GPIO 18 (Pi pin 12, physical)
            │
           [100 Ω]   ◄── gate series resistor (limits inrush)
            │
            ├────────── GATE (IRLZ44N)
            │
           [10 kΩ]   ◄── pull-down to GND (keeps MOSFET OFF at boot)
            │
           GND


        +12V SUPPLY
            │
            │   ┌──|◄──┐   1N4007 flyback diode
            │   │       │   (cathode toward +12V)
            │   └───────┘
            │       │
        ┌───┴───┐  │
        │  LED  ├──┘
        └───┬───┘
            │
          DRAIN


 2.1  Place the IRLZ44N on the breadboard.
      Pin 1 = Gate,  Pin 2 = Drain,  Pin 3 = Source.
      (Flat side facing you, pins down: G-D-S left to right.)

 2.2  Connect SOURCE (pin 3) to the breadboard GND rail.

 2.3  Connect a 10 kΩ pull-down resistor from GATE (pin 1) to GND rail.

 2.4  Connect a 100 Ω resistor from GATE (pin 1) to a free row.
      Run a jumper wire from that row to Raspberry Pi GPIO 18
      (physical pin 12).

 2.5  Connect the LED bulb's NEGATIVE lead to DRAIN (pin 2).

 2.6  Connect the LED bulb's POSITIVE lead to the +12V supply's
      positive terminal.

 2.7  Place the 1N4007 flyback diode across the LED leads:
        - Cathode (striped end) → +12V side
        - Anode → DRAIN side
      This protects the MOSFET from inductive voltage spikes.

 2.8  Connect the 12V supply's GND to the breadboard GND rail.

 2.9  Connect the Pi's GND (physical pin 6) to the breadboard GND rail.

      ┌─────────────────────────────────────────────────────┐
      │  CRITICAL: The Pi GND and 12V supply GND must be   │
      │  connected together.  Without a common ground, the │
      │  MOSFET gate signal has no reference.               │
      └─────────────────────────────────────────────────────┘


 STEP 3 — CONNECT THE CAMERA
────────────────────────────────────────────────────────────────────────────────
 3.1  Power off the Pi.

 3.2  Lift the camera port latch (between HDMI and audio jack).

 3.3  Insert the camera ribbon cable with the blue side facing the
      Ethernet port.  Press the latch down to lock.

 3.4  Boot the Pi.  Verify the camera:

        rpicam-still -o test.jpg
        # Should capture a JPEG without errors.


 STEP 4 — BENCH SETUP
────────────────────────────────────────────────────────────────────────────────

      ┌────────┐         2 meters          ┌──────────┐
      │ Camera │ ◄──────────────────────── │   LED    │
      │ (Pi)   │                           │  bulb    │
      └────────┘                           └────┬─────┘
                                                │
                        ┌───────────┐           │
                        │  white    │ ◄─────────┘  aimed at diffuser
                        │ diffuser  │
                        │  board    │
                        └───────────┘

 4.1  Mount the LED bulb on a stable surface (clamp or stand).

 4.2  Place the white diffuser sheet 30–50 cm in front of the LED.
      The camera will photograph the diffuser, not the bare LED.

 4.3  Position the Pi + camera 2 m from the diffuser, aimed straight
      at the illuminated spot.

 4.4  Darken the room as much as possible.  Ambient light adds noise.


 STEP 5 — SMOKE TEST (NO LED YET)
────────────────────────────────────────────────────────────────────────────────
 5.1  With the 12V supply OFF, power on the Pi.

 5.2  Run the oscillator in simulation mode to verify the code:

        cd ~/stribeck-optics
        python oscillator.py --simulate --carrier-hz 5000 --duty 70

      You should see "Carrier: 5000 Hz, base duty: 70.0%"
      and "Steady carrier — press Ctrl-C to stop."  Ctrl-C to exit.

 5.3  Run the temporal analysis to verify numpy works:

        python oscillator.py --analyze

      You should see a table of Fourier harmonics.


 STEP 6 — FIRST LIGHT (CARRIER ONLY)
────────────────────────────────────────────────────────────────────────────────
 6.1  Double-check all wiring.  Confirm:
        - Gate pull-down resistor in place (LED should be OFF)
        - Flyback diode correct polarity
        - Common GND between Pi and 12V supply

 6.2  Turn on the 12V supply.  The LED should remain OFF (gate pulled low).

 6.3  Run the oscillator for real:

        python oscillator.py --carrier-hz 5000 --duty 70

      The LED should turn on at ~70% brightness with no visible flicker.
      (5 kHz is well above flicker-fusion.)

 6.4  Try different duty cycles:

        python oscillator.py --carrier-hz 5000 --duty 30
        python oscillator.py --carrier-hz 5000 --duty 90

      Brightness should change smoothly.  Ctrl-C between runs.


 STEP 7 — CONTROL MEASUREMENT (STEADY LED)
────────────────────────────────────────────────────────────────────────────────
 7.1  In terminal 1, start the carrier at the test duty cycle:

        python oscillator.py --carrier-hz 5000 --duty 70

 7.2  In terminal 2, capture the control bloom data:

        python measure_bloom.py capture --label control --duration 30

      This writes results/bloom_control.csv with ~30 s of bloom radius
      measurements.

 7.3  Ctrl-C the oscillator in terminal 1.


 STEP 8 — MODULATED MEASUREMENT (STRESS TEST)
────────────────────────────────────────────────────────────────────────────────
 8.1  In terminal 1, start with the 4 Hz stress-test envelope:

        python oscillator.py --carrier-hz 5000 --duty 70 \\
            --envelope-hz 4 --envelope-depth 0.5

      The LED will pulse slowly (4 Hz) with the kHz carrier underneath.

      ┌─────────────────────────────────────────────────────┐
      │  WARNING: 4 Hz pulsing light.  Do not stare at the │
      │  LED.  Keep your eyes on the camera/terminal.       │
      └─────────────────────────────────────────────────────┘

 8.2  In terminal 2, capture the modulated bloom data:

        python measure_bloom.py capture --label modulated --duration 30

 8.3  Ctrl-C the oscillator.


 STEP 9 — COMPARE RESULTS
────────────────────────────────────────────────────────────────────────────────
 9.1  Run the comparison:

        python measure_bloom.py compare results/

      Expected output (example):

        === Bloom Radius Comparison ===

          Metric                      Control     Modulated     Reduction
          ─────────                   ───────     ─────────     ─────────
          bloom (px)                  42.3±2.1     35.8±1.8       -15.4%
          peak ()                    241.0±3.2    238.5±4.1        -1.0%
          snr ()                      18.7±1.0     19.2±0.9        +2.7%

      A NEGATIVE bloom reduction means smaller starbursts — this is
      the patent claim.

 9.2  Run the theoretical prediction for comparison:

        python temporal_bridge.py --stress-test

      The model predicts ~15% bloom reduction.  If your camera data
      is in the same ballpark, the theory is validated.


 STEP 10 — FREQUENCY SWEEP (OPTIONAL)
────────────────────────────────────────────────────────────────────────────────
 To find the exact carrier frequency that minimizes bloom for your
 specific LED, sweep from 1 kHz to 10 kHz:

    for freq in 1000 2000 3000 5000 7000 10000; do
        echo "=== Testing $freq Hz ==="
        python oscillator.py --carrier-hz $freq --duty 70 &
        PID=$!
        sleep 2  # let it stabilize
        python measure_bloom.py capture --label "sweep_${freq}hz" --duration 10
        kill $PID
    done

 Then compare CSVs to find the sweet spot.


 STEP 11 — LP INTEGRATION (ADVANCED)
────────────────────────────────────────────────────────────────────────────────
 Once you have the empirical bloom reduction factor, feed it back into
 the spatial-frequency LP solver:

    python -c "
    from temporal_bridge import temporal_attenuation
    T = temporal_attenuation(5000, 70)
    print(f'T(5kHz, 70%) = {T:.4f}')
    print(f'Glare threshold raised by {1/T:.2f}x')
    print(f'Re-run simulate.py with modified constraints for updated S*(f)')
    "

 The temporal attenuation factor T relaxes the glare constraints in
 the LP, allowing more spatial-frequency power allocation — which
 translates to better road visibility without increasing glare.


 TROUBLESHOOTING
────────────────────────────────────────────────────────────────────────────────
 Problem                          Fix
 ───────────────────────────────   ──────────────────────────────────────
 "Cannot connect to pigpio"       sudo pigpiod
 LED stays OFF                    Check gate wiring; measure with
                                  multimeter: GPIO 18 should swing
                                  0–3.3V when running
 LED stays ON (won't turn off)    Gate pull-down resistor missing or
                                  disconnected
 Visible flicker                  Carrier freq too low; increase to
                                  ≥2000 Hz
 Camera sees white-out            Reduce --duty or add ND filter to
                                  camera lens
 measure_bloom.py no frames       Check camera connection; run
                                  rpicam-still -o test.jpg
 Permission denied on GPIO        Run with sudo, or add user to gpio
                                  group: sudo usermod -aG gpio $USER


 WHAT SUCCESS LOOKS LIKE
────────────────────────────────────────────────────────────────────────────────
 You have a working prototype when:

   ✓  Carrier runs at 5 kHz with no visible flicker
   ✓  Camera measures bloom radius for both control and modulated
   ✓  Modulated bloom radius is 10–30% smaller than control
   ✓  The reduction holds even during the 3–5 Hz stress-test envelope
   ✓  temporal_bridge.py prediction matches camera data within ±5%

 This data set — theoretical prediction confirmed by physical
 measurement at the worst-case frequency — is the core of the
 patent filing.

================================================================================
"""

if __name__ == "__main__":
    print(ASSEMBLY)
