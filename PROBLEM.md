# Formal Problem Statement

**Optimal Headlight Emission Spectra Under Joint Atmospheric Scattering and Population Aberration Constraints**

N. Joven, 2026. CC0.

---

## 1. Setup

A headlight emits a beam whose spatial frequency content is described by a power spectral density $S(f)$, where $f$ is spatial frequency in cycles per degree (cpd). This signal propagates through an atmospheric medium (rain, fog, clear air) and is received by a human visual system with optical aberrations.

The system has three transfer functions in cascade:

1. **Emission spectrum**: $S(f)$, the design variable
2. **Atmospheric scattering kernel**: $H_{\text{atm}}(f, w)$, where $w \in \mathcal{W}$ indexes weather state
3. **Ocular point spread function**: $H_{\text{eye}}(f, a)$, where $a \in \mathcal{A}$ indexes the observer's aberration profile

The received signal at the retina is:

$$R(f, w, a) = S(f) \cdot H_{\text{atm}}(f, w) \cdot H_{\text{eye}}(f, a)$$

The design problem: choose $S(f)$ to maximize perceptual information transfer across the driving population, subject to safety constraints.

---

## 2. The Stick-Slip Structure

Following Joven (2026, §10), the atmospheric medium is the scattering channel whose transfer function has a critical threshold. Below this threshold, the medium mode-converts the input into lower-frequency artifacts — halos, streaks, glare. This is the optical stick-slip transition:

| Stick-slip parameter | Optical analogue |
|---|---|
| Relative velocity | Spatial frequency $f$ relative to scattering scale |
| Critical velocity | Frequency at which $H_{\text{atm}}(f, w)$ drops below mode-conversion threshold |
| Subharmonic energy | Halo/streak artifacts (energy appearing at unintended frequencies) |
| Stribeck curve | $H_{\text{atm}}(f, w)$ as a function of $f$ for fixed $w$ |

The intervention is not at the receiver (corrective lenses) or the source intensity (brighter headlights), but at the emission spectrum: shape $S(f)$ so that the product $S(f) \cdot H_{\text{atm}}(f, w)$ does not cross the mode-conversion threshold at any frequency.

---

## 3. Optimization Problem

### 3.1 Objective

Maximize expected perceptual information transfer over the joint distribution of weather states and aberration profiles:

$$\max_{S(f)} \; \mathbb{E}_{w \sim P_{\mathcal{W}}, \; a \sim P_{\mathcal{A}}} \left[ \int_0^{f_{\max}} I\bigl(R(f, w, a)\bigr) \, df \right]$$

where $I(\cdot)$ is a perceptual information measure (e.g., contrast sensitivity-weighted signal power above detection threshold) and $P_{\mathcal{W}}$, $P_{\mathcal{A}}$ are the population distributions over weather and aberration states.

### 3.2 Constraints

**C1. Scattering threshold (stick-slip limit).** For each aberration profile $a$ and spatial frequency $f$, the received signal must not exceed the mode-conversion threshold of the eye:

$$H_{\text{eye}}(f, a) \cdot S(f) \leq T_{\text{scatter}}(f, a) \qquad \forall f, \; \forall a \in \mathcal{A}$$

This prevents the eye's aberrations from converting transmitted power into perceptual artifacts (halos, starbursts). The threshold $T_{\text{scatter}}(f, a)$ is the maximum input power at frequency $f$ that an eye with aberration profile $a$ can process without mode conversion.

**C2. Glare limit (oncoming driver safety).** For each weather state $w$ and spatial frequency $f$, the scattered signal must not exceed the disability glare threshold for oncoming drivers:

$$H_{\text{atm}}(f, w) \cdot S(f) \leq G(f, w) \qquad \forall f, \; \forall w \in \mathcal{W}$$

where $G(f, w)$ is the maximum scattered power at frequency $f$ in weather $w$ that does not produce disability glare (per CIE veiling luminance standards or equivalent).

**C3. Total power budget.**

$$\int_0^{f_{\max}} S(f) \, df \leq P_{\max}$$

**C4. Non-negativity.**

$$S(f) \geq 0 \qquad \forall f$$

### 3.3 Lagrangian Relaxation

Relax C1 and C2 into the objective with multipliers $\lambda_a(f)$ and $\mu_w(f)$:

$$\mathcal{L}(S, \lambda, \mu) = \mathbb{E}_{w,a}\left[\int I(R) \, df\right] - \int \sum_{a \in \mathcal{A}} \lambda_a(f) \bigl[H_{\text{eye}}(f,a) \cdot S(f) - T_{\text{scatter}}(f,a)\bigr] \, df - \int \sum_{w \in \mathcal{W}} \mu_w(f) \bigl[H_{\text{atm}}(f,w) \cdot S(f) - G(f,w)\bigr] \, df$$

The dual problem:

$$\min_{\lambda \geq 0, \; \mu \geq 0} \; \max_{S \geq 0} \; \mathcal{L}(S, \lambda, \mu) \quad \text{s.t. } \int S(f)\,df \leq P_{\max}$$

### 3.4 Shadow Price Interpretation

At the optimum:

- $\lambda_a^*(f)$ is the **shadow price of aberration $a$ at frequency $f$**: the marginal cost of tightening the scatter threshold for that aberration type at that frequency. High $\lambda_a^*$ means this aberration is the binding constraint — the beam design is limited by this subpopulation's visual system at this frequency.

- $\mu_w^*(f)$ is the **shadow price of weather $w$ at frequency $f$**: the marginal cost of tightening the glare limit for that weather condition. High $\mu_w^*$ means the atmosphere in this weather state is the binding constraint.

At each frequency, the designer faces a tradeoff surface: allocate power to overcome atmospheric attenuation (improving visibility) vs. withhold power to avoid triggering aberration-specific artifacts (preventing glare/halos). The multipliers tell you which constraint is more expensive to satisfy.

---

## 4. SF-DMA Interpretation

This is a **spatial frequency-division multiple access** problem:

- **Subcarriers**: spatial frequencies $f \in [0, f_{\max}]$
- **Users**: drivers indexed by aberration profile $a \in \mathcal{A}$
- **Channel**: atmosphere in state $w \in \mathcal{W}$, with transfer function $H_{\text{atm}}(f, w)$
- **Receiver filter**: eye with PSF $H_{\text{eye}}(f, a)$
- **Power allocation**: $S(f)$ across subcarriers

The optimal $S^*(f)$ is the water-filling solution over spatial frequencies, where the "water level" at each frequency is set by the tightest constraint (worst-case aberration or worst-case weather) active at that frequency.

The key difference from telecommunications OFDMA: the receiver population is heterogeneous and uncontrollable. You cannot assign users to subcarriers. Every driver receives every frequency. The optimization must satisfy all receivers simultaneously — it is a worst-case (minimax) or distributional (chance-constrained) problem over the aberration population, not an assignment problem.

---

## 5. What Must Be Measured

To instantiate this optimization, the following transfer functions must be characterized empirically:

### 5.1 Atmospheric Scattering Kernels $H_{\text{atm}}(f, w)$

| Weather state $w$ | Scattering mechanism | Key parameter |
|---|---|---|
| Clear | Negligible | — |
| Light rain | Mie scattering from drops (1–3 mm) | Drop size distribution, density |
| Heavy rain | Mie + multiple scattering | Optical depth |
| Fog | Mie scattering from droplets (1–15 µm) | Visibility distance, droplet size |
| Snow | Large-particle forward scatter | Crystal size, density |

These are measurable via modulation transfer function (MTF) measurement of a structured target through controlled scattering media (fog chamber, rain simulator).

### 5.2 Ocular PSFs $H_{\text{eye}}(f, a)$

Population data on wavefront aberrations exists from large-scale aberrometry studies:

- **Thibos et al. (2002)**: Zernike decomposition of 200 eyes, Indiana population
- **Porter et al. (2001)**: 109 eyes, Rochester population
- **Salmon & van de Pol (2006)**: meta-analysis, 2560 eyes

The dominant aberrations affecting night driving:

| Aberration $a$ | Zernike term | Effect on headlight perception |
|---|---|---|
| Defocus | $Z_2^0$ | Uniform blur, loss of acuity |
| Astigmatism | $Z_2^{\pm 2}$ | Directional streaks |
| Coma | $Z_3^{\pm 1}$ | Asymmetric flare |
| Spherical | $Z_4^0$ | Halos around point sources |
| Trefoil | $Z_3^{\pm 3}$ | Three-pointed starburst |

Each aberration has a characteristic modulation transfer function that attenuates and redistributes spatial frequencies. The mode-conversion threshold $T_{\text{scatter}}(f, a)$ is where the aberration's MTF causes the PSF sidelobes to exceed the Weber contrast detection threshold (~2% for scotopic/mesopic vision).

### 5.3 Perceptual Information Measure $I(\cdot)$

The contrast sensitivity function (CSF) provides a frequency-dependent weighting:

$$I(R(f, w, a)) = \begin{cases} \log\bigl(1 + \text{CSF}(f) \cdot R(f, w, a)\bigr) & \text{if } R(f, w, a) > R_{\text{threshold}}(f) \\ 0 & \text{otherwise} \end{cases}$$

where $\text{CSF}(f)$ peaks around 3–5 cpd for mesopic (night driving) vision and $R_{\text{threshold}}(f)$ is the detection threshold at frequency $f$.

---

## 6. Tractable Approximation

The full problem is infinite-dimensional (continuous $f$) over continuous distributions ($P_{\mathcal{W}}$, $P_{\mathcal{A}}$). A tractable first pass:

1. **Discretize frequencies**: $f_1, f_2, \ldots, f_N$ at $N$ spatial frequency bins spanning 0.5–30 cpd (the range relevant to headlight perception at driving distances)

2. **Finite weather states**: $|\mathcal{W}| = 5$ (clear, light rain, heavy rain, fog, snow)

3. **Representative aberration profiles**: cluster the Thibos/Porter population data into $K$ representative profiles via k-means on Zernike coefficients. Start with $K = 8$: (emmetropic, low myopic, high myopic, astigmatic-WTR, astigmatic-ATR, comatic, spherical-aberration-dominant, mixed-HOA)

4. **Solve the discretized LP/QP**: with $N$ frequency bins, $5$ weather states, and $8$ aberration profiles, the problem has $N$ design variables, $5N + 8N + 1 = 13N + 1$ constraints, and $13N$ dual variables. For $N = 60$ (0.5 cpd resolution), this is a 60-variable problem with 781 constraints — solvable with any standard LP/QP solver.

5. **Sensitivity analysis**: vary $K$ and $N$ to check stability of the optimal $S^*(f)$.

---

## 7. What Success Looks Like

The output is a **headlight emission spatial frequency profile** $S^*(f)$ — not a single number (lumens) or a simple angular cutoff (ECE beam pattern), but a frequency-domain specification:

- At each spatial frequency, how much power to emit
- Which frequencies to suppress (where atmospheric mode-conversion or aberration artifacts dominate)
- Which frequencies to boost (where perceptual information gain is highest per unit power)

This translates into a physical beam pattern via inverse Fourier transform: the far-field intensity distribution of a headlight whose spatial frequency content is $S^*(f)$.

A successful result would show:
1. The optimal $S^*$ is not flat (uniform illumination is suboptimal)
2. The binding constraints shift between weather-limited and aberration-limited across frequencies
3. The shadow prices identify specific frequency bands where the current ECE/SAE beam patterns are over- or under-allocating power
4. The solution is robust to reasonable variation in the population aberration distribution

---

## 8. Connection to Parent Work

This is the experimental instance of Joven (2026, §10):

> "Any system where a signal propagates through a scattering medium — and the medium's transfer function has a critical threshold below which it mode-converts the input into lower-frequency artifacts — is a candidate for the same analysis. Atmospheric optics is one such system."

The Lagrangian relaxation structure is inherited directly: the multipliers $\lambda_a^*(f)$ and $\mu_w^*(f)$ are the optical analogues of the dark matter dual variable — they represent the cost the emission spectrum pays to satisfy constraints it cannot meet with uniform illumination alone. The "dark matter halo" of a headlight is the glare halo produced when the atmospheric scattering constraint binds; the optimal $S^*$ is the beam that avoids producing it.
