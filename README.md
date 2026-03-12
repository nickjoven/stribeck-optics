# stribeck-optics

Atmospheric scattering as a stick-slip transfer function: designing headlight emission profiles optimized for the joint PSF of scattering media and aberrated eyes.

## Status

Stub. The conceptual framing exists (see [intersections/joven_stick_slip_dark_matter.md](../intersections/joven_stick_slip_dark_matter.md), §9); the experimental optics work has not been done.

## Core idea

Point-source headlights through fog/rain are the "fast bow" — the atmosphere period-doubles the signal into halos and streaks. The intervention is not at the lens (corrective glasses) or the source intensity (brighter headlights), but at the medium interaction: shape the emitted spatial frequency content to match the atmospheric transfer function so mode conversion doesn't occur.

## Adjacent work

- CMU smart headlights (Narasimhan, 2012-2014) — per-raindrop DLP avoidance
- Sandia circular polarization in fog (van der Laan, 2015-2023)
- Quintana Benito (2022, Heliyon) — structured illumination, 500% contrast gain
- UC Berkeley vision-correcting displays (Huang, SIGGRAPH 2014)
- Black et al. (2019, OPO) — astigmatism impairs night driving (correction-side only)

## Gap

Nobody treats the headlight beam as a signal with spatial frequency content optimized against the scattering transfer function of the atmospheric medium, jointly with the PSF distribution of the driving population's visual aberrations.

## Formal problem statement

See [PROBLEM.md](PROBLEM.md) — Lagrangian relaxation over joint atmospheric and aberration constraints, framed as spatial frequency-division multiple access (SF-DMA). Includes tractable discretization (60-variable LP) and measurement requirements.
