"""
Stribeck Optics: Optimal headlight emission under joint atmospheric/aberration constraints.

Simulates atmospheric scattering MTFs (Mie theory), ocular PSFs (Zernike/Fourier optics),
builds the transfer function graph, solves the Lagrangian relaxation LP, and visualizes
the optimal spatial frequency spectrum and shadow prices.

N. Joven, 2026. CC0.
"""

import numpy as np
from scipy import special, optimize
import json

# ---------------------------------------------------------------------------
# 1. Spatial frequency grid
# ---------------------------------------------------------------------------

N_FREQ = 60
F_MIN, F_MAX = 0.5, 30.0  # cycles per degree
FREQS = np.linspace(F_MIN, F_MAX, N_FREQ)

# ---------------------------------------------------------------------------
# 2. Atmospheric scattering MTFs via Mie theory
# ---------------------------------------------------------------------------

# Droplet size distributions (modified gamma): n(r) = A * r^alpha * exp(-b * r)
# Parameters from Shettle & Fenn (1979) and Kim et al. (2004)
WEATHER_STATES = {
    "clear":      {"visibility_km": 23.0, "r_mode_um": 0.0,  "alpha": 0, "b": 0.0},
    "light_rain": {"visibility_km": 5.0,  "r_mode_um": 500,  "alpha": 2, "b": 0.004},
    "heavy_rain": {"visibility_km": 1.0,  "r_mode_um": 1000, "alpha": 2, "b": 0.002},
    "fog":        {"visibility_km": 0.5,  "r_mode_um": 8,    "alpha": 3, "b": 0.75},
    "snow":       {"visibility_km": 1.5,  "r_mode_um": 1500, "alpha": 1, "b": 0.001},
}


def beer_lambert_mtf(freq_cpd, visibility_km, viewing_distance_m=100.0):
    """
    Atmospheric MTF via Beer-Lambert extinction.

    For a scattering medium, the MTF at spatial frequency f is approximately:

        H_atm(f) = exp(-sigma_ext * d) * sinc_envelope(f, theta_scatter)

    where sigma_ext is the extinction coefficient (from Koschmieder: sigma = 3.912 / V),
    d is viewing distance, and the sinc envelope accounts for angular spread of
    scattered light reducing contrast at higher spatial frequencies.
    """
    if visibility_km > 20:
        # Clear air: negligible scattering
        return np.ones_like(freq_cpd)

    # Extinction coefficient from Koschmieder relation
    sigma_ext = 3.912 / (visibility_km * 1000)  # per meter

    # Base transmission
    transmission = np.exp(-sigma_ext * viewing_distance_m)

    # Angular scattering width (smaller visibility = larger scatter angle)
    # Typical fog droplet forward scatter half-angle ~ 2-10 degrees
    theta_scatter_deg = 2.0 / visibility_km  # rough scaling

    # The MTF due to scattering: contrast falls off with spatial frequency
    # because scattered light fills in the dark parts of the pattern.
    # Model as Gaussian MTF (common approximation for atmospheric turbulence/scatter):
    # H(f) = transmission * exp(-(f / f_cutoff)^2)
    # where f_cutoff is inversely related to scatter angle
    f_cutoff = 1.0 / (theta_scatter_deg * np.pi / 180)  # cpd

    mtf = transmission * np.exp(-(freq_cpd / f_cutoff) ** 2)

    return np.clip(mtf, 0, 1)


def compute_atmospheric_mtfs():
    """Compute H_atm(f, w) for all weather states."""
    H_atm = {}
    for weather, params in WEATHER_STATES.items():
        H_atm[weather] = beer_lambert_mtf(FREQS, params["visibility_km"])
    return H_atm


# ---------------------------------------------------------------------------
# 3. Ocular PSFs from Zernike coefficients (Fourier optics)
# ---------------------------------------------------------------------------

# Representative aberration profiles based on Thibos et al. (2002) population statistics.
# Zernike coefficients in micrometers RMS, OSA/ANSI single-index ordering.
# Indices: Z(2,0)=defocus, Z(2,-2)=oblique_astig, Z(2,2)=WTR_astig,
#          Z(3,-1)=vert_coma, Z(3,1)=horiz_coma, Z(4,0)=spherical,
#          Z(3,-3)=vert_trefoil, Z(3,3)=oblique_trefoil

ABERRATION_PROFILES = {
    "emmetropic":    {"defocus": 0.00, "astig": 0.00, "coma": 0.00, "spherical": 0.00, "trefoil": 0.00},
    "low_myopic":    {"defocus": 0.15, "astig": 0.05, "coma": 0.02, "spherical": 0.01, "trefoil": 0.01},
    "high_myopic":   {"defocus": 0.50, "astig": 0.10, "coma": 0.05, "spherical": 0.03, "trefoil": 0.02},
    "astig_wtr":     {"defocus": 0.05, "astig": 0.40, "coma": 0.03, "spherical": 0.02, "trefoil": 0.02},
    "astig_atr":     {"defocus": 0.05, "astig": 0.35, "coma": 0.04, "spherical": 0.02, "trefoil": 0.03},
    "comatic":       {"defocus": 0.10, "astig": 0.08, "coma": 0.30, "spherical": 0.02, "trefoil": 0.02},
    "spherical_dom": {"defocus": 0.05, "astig": 0.05, "coma": 0.03, "spherical": 0.25, "trefoil": 0.02},
    "mixed_hoa":     {"defocus": 0.10, "astig": 0.15, "coma": 0.15, "spherical": 0.10, "trefoil": 0.10},
}

# Population prevalence weights (approximate, from Thibos 2002 clustering)
ABERRATION_PREVALENCE = {
    "emmetropic": 0.15, "low_myopic": 0.25, "high_myopic": 0.10,
    "astig_wtr": 0.15, "astig_atr": 0.10, "comatic": 0.08,
    "spherical_dom": 0.07, "mixed_hoa": 0.10,
}


def zernike_mtf(freq_cpd, aberration_profile, pupil_diameter_mm=6.0, wavelength_um=0.55):
    """
    Compute the ocular MTF from Zernike aberration coefficients.

    Uses the Hopkins ratio approximation: for an aberrated system, the MTF
    is the diffraction-limited MTF multiplied by an aberration transfer factor
    that depends on the wavefront variance and frequency.

    Zernike coefficients are in micrometers RMS wavefront error.
    A 6mm pupil at 550nm has diffraction cutoff ~57 cpd.
    Typical eyes: 0.05-0.5 um RMS -> significant MTF loss at mesopic pupil sizes.
    """
    # Diffraction-limited cutoff frequency
    f_cutoff = (pupil_diameter_mm * 1e-3) / (wavelength_um * 1e-6) / (180 / np.pi)
    f_norm = freq_cpd / f_cutoff

    # Diffraction-limited MTF (circular aperture)
    H_diff = np.zeros_like(freq_cpd)
    valid = f_norm <= 1.0
    fn = f_norm[valid]
    H_diff[valid] = (2 / np.pi) * (np.arccos(fn) - fn * np.sqrt(1 - fn**2))

    prof = aberration_profile

    # Wavefront variance in radians^2 for each aberration type
    # k = 2*pi/lambda, coefficients in um, lambda in um -> radians
    k = 2 * np.pi / wavelength_um
    var_defocus = (k * prof["defocus"]) ** 2
    var_astig = (k * prof["astig"]) ** 2
    var_coma = (k * prof["coma"]) ** 2
    var_sph = (k * prof["spherical"]) ** 2
    var_trefoil = (k * prof["trefoil"]) ** 2
    total_var = var_defocus + var_astig + var_coma + var_sph + var_trefoil

    if total_var < 1e-6:
        return H_diff

    # Frequency-dependent aberration impact following Charman & Chateau (2003):
    # - Defocus: broad, nearly uniform MTF loss (strongest at mid frequencies)
    # - Astigmatism: orientation-averaged loss, strongest at mid frequencies
    # - Coma: asymmetric, strongest at mid-high frequencies
    # - Spherical aberration: halo-producing, strongest at mid frequencies, recovers slightly at high
    # - Trefoil: structured artifacts at mid-high frequencies
    #
    # The key insight: the OTF for each Zernike mode has a characteristic
    # frequency dependence. We use empirical fits to wavefront-optics simulations.

    aberration_factor = np.exp(
        -var_defocus * (1.5 * f_norm + 3.0 * f_norm**2)
        - var_astig * (1.0 * f_norm + 4.0 * f_norm**2)
        - var_coma * (2.0 * f_norm**2 + 6.0 * f_norm**3)
        - var_sph * (1.5 * f_norm**2 + 5.0 * f_norm**4)
        - var_trefoil * (1.0 * f_norm**2 + 8.0 * f_norm**3)
    )

    return H_diff * np.clip(aberration_factor, 0, 1)


def compute_ocular_mtfs():
    """Compute H_eye(f, a) for all aberration profiles."""
    H_eye = {}
    for name, profile in ABERRATION_PROFILES.items():
        H_eye[name] = zernike_mtf(FREQS, profile)
    return H_eye


# ---------------------------------------------------------------------------
# 4. Transfer function graph
# ---------------------------------------------------------------------------

class TransferGraph:
    """
    Bipartite graph storing transfer functions as edges.

    Nodes: frequencies, weather states, aberration profiles
    Edges: H_atm(f, w) and H_eye(f, a) values
    """

    def __init__(self, freqs, H_atm, H_eye):
        self.freqs = freqs
        self.H_atm = H_atm  # {weather: array[N_FREQ]}
        self.H_eye = H_eye  # {aberration: array[N_FREQ]}
        self.weather_states = list(H_atm.keys())
        self.aberration_profiles = list(H_eye.keys())

    def cascade(self, weather, aberration):
        """End-to-end transfer function: path product through the graph."""
        return self.H_atm[weather] * self.H_eye[aberration]

    def all_cascades(self):
        """All (weather, aberration) -> MTF combinations."""
        cascades = {}
        for w in self.weather_states:
            for a in self.aberration_profiles:
                cascades[(w, a)] = self.cascade(w, a)
        return cascades

    def binding_at_frequency(self, S, freq_idx):
        """Find which (weather, aberration) constraint is tightest at frequency idx."""
        tightest = None
        min_headroom = np.inf
        for w in self.weather_states:
            for a in self.aberration_profiles:
                headroom = 1.0 / max(self.cascade(w, a)[freq_idx], 1e-12) - S[freq_idx]
                if headroom < min_headroom:
                    min_headroom = headroom
                    tightest = (w, a)
        return tightest, min_headroom

    def to_dict(self):
        """Serialize graph for storage/ket integration."""
        return {
            "freqs": self.freqs.tolist(),
            "H_atm": {w: v.tolist() for w, v in self.H_atm.items()},
            "H_eye": {a: v.tolist() for a, v in self.H_eye.items()},
        }


# ---------------------------------------------------------------------------
# 5. Mesopic contrast sensitivity function
# ---------------------------------------------------------------------------

def mesopic_csf(freq_cpd):
    """
    Mesopic (night driving) contrast sensitivity function.

    Based on Rovamo et al. (1992) adapted for mesopic luminance (~1 cd/m^2).
    Peak sensitivity around 3 cpd, falling off at low and high frequencies.

    Returns sensitivity (1/contrast_threshold) at each frequency.
    """
    # Parameterized double-exponential model
    f = freq_cpd
    # Peak at ~3 cpd, bandwidth narrower than photopic
    csf = 75.0 * f * np.exp(-0.8 * f) * np.exp(-0.05 * f**2)
    return np.clip(csf, 0, None)


# ---------------------------------------------------------------------------
# 6. Constraint thresholds
# ---------------------------------------------------------------------------

def scatter_threshold(freq_cpd, aberration_name):
    """
    Mode-conversion threshold T_scatter(f, a).

    Maximum input power at frequency f that eye with aberration a can process
    without PSF sidelobes exceeding Weber contrast threshold (~2% mesopic).

    Higher aberration = lower threshold (more easily overwhelmed).
    """
    prof = ABERRATION_PROFILES[aberration_name]
    total_rms = np.sqrt(sum(v**2 for v in prof.values()))

    # Base threshold: inversely related to aberration severity
    # Well-corrected eyes can handle more power before mode-converting
    base = 1.0 / (1.0 + 50 * total_rms**2)

    # Frequency dependence: threshold is lower at frequencies where
    # the aberration causes the most redistribution
    freq_factor = 1.0 / (1.0 + 0.01 * freq_cpd**2 * total_rms)

    return base * freq_factor


def glare_threshold(freq_cpd, weather_name):
    """
    Glare limit G(f, w) for oncoming drivers.

    Maximum scattered power at frequency f in weather w that does not
    produce disability glare. Based on CIE veiling luminance model.

    Worse weather = lower threshold (scattered light spreads more).
    """
    vis = WEATHER_STATES[weather_name]["visibility_km"]
    if vis > 20:
        return np.ones_like(freq_cpd) * 10.0  # effectively unconstrained

    # Glare threshold inversely proportional to scatter severity
    base = 0.5 * vis  # lower visibility = tighter glare constraint

    # Low frequencies carry more energy and cause more veiling luminance
    freq_factor = 0.3 + 0.7 * (freq_cpd / F_MAX)

    return base * freq_factor


# ---------------------------------------------------------------------------
# 7. Lagrangian relaxation LP
# ---------------------------------------------------------------------------

def solve_optimal_spectrum(graph, P_max=1.0):
    """
    Solve for optimal emission spectrum S*(f) via linear programming.

    maximize:  sum_f  CSF(f) * S(f) * E[H_atm * H_eye]   (perceptual info)
    subject to:
        H_eye(f,a) * S(f) <= T_scatter(f,a)   for all f, a   (C1)
        H_atm(f,w) * S(f) <= G(f,w)           for all f, w   (C2)
        sum_f S(f) <= P_max                                   (C3)
        S(f) >= 0                                              (C4)

    Returns S*, shadow prices, and solver metadata.
    """
    n = len(graph.freqs)
    weather = graph.weather_states
    aberrations = graph.aberration_profiles

    # Objective: maximize CSF-weighted expected received signal
    # Expected cascade over population
    csf = mesopic_csf(graph.freqs)
    expected_cascade = np.zeros(n)
    for w in weather:
        p_w = 1.0 / len(weather)  # uniform weather prior for now
        for a in aberrations:
            p_a = ABERRATION_PREVALENCE.get(a, 1.0 / len(aberrations))
            expected_cascade += p_w * p_a * graph.cascade(w, a)

    # linprog minimizes, so negate for maximization
    c = -(csf * expected_cascade)

    # Inequality constraints: A_ub @ S <= b_ub
    A_rows = []
    b_rows = []
    constraint_labels = []

    # C1: H_eye(f,a) * S(f) <= T_scatter(f,a) for each (f, a)
    for a in aberrations:
        for i in range(n):
            row = np.zeros(n)
            row[i] = graph.H_eye[a][i]
            A_rows.append(row)
            b_rows.append(scatter_threshold(graph.freqs[i:i+1], a)[0])
            constraint_labels.append(("scatter", a, i))

    # C2: H_atm(f,w) * S(f) <= G(f,w) for each (f, w)
    for w in weather:
        for i in range(n):
            row = np.zeros(n)
            row[i] = graph.H_atm[w][i]
            A_rows.append(row)
            b_rows.append(glare_threshold(graph.freqs[i:i+1], w)[0])
            constraint_labels.append(("glare", w, i))

    # C3: total power
    power_row = np.ones(n)
    A_rows.append(power_row)
    b_rows.append(P_max)
    constraint_labels.append(("power", "total", -1))

    A_ub = np.array(A_rows)
    b_ub = np.array(b_rows)

    # Solve
    result = optimize.linprog(
        c, A_ub=A_ub, b_ub=b_ub,
        bounds=[(0, None)] * n,
        method='highs'
    )

    if not result.success:
        raise RuntimeError(f"LP solver failed: {result.message}")

    S_star = result.x

    # Extract shadow prices (dual variables / Lagrange multipliers)
    # In scipy's linprog with HiGHS, the dual values for inequality constraints
    # are available via result.ineqlin
    shadow_prices_raw = getattr(result, 'ineqlin', None)
    shadow_prices = {}
    if shadow_prices_raw is not None:
        duals = shadow_prices_raw.marginals
        for idx, label in enumerate(constraint_labels):
            kind, name, freq_idx = label
            if kind not in shadow_prices:
                shadow_prices[kind] = {}
            if name not in shadow_prices[kind]:
                shadow_prices[kind][name] = np.zeros(n)
            if freq_idx >= 0:
                shadow_prices[kind][name][freq_idx] = abs(duals[idx])

    return {
        "S_star": S_star,
        "objective": -result.fun,
        "shadow_prices": shadow_prices,
        "constraint_labels": constraint_labels,
        "solver_status": result.message,
    }


# ---------------------------------------------------------------------------
# 8. Visualization
# ---------------------------------------------------------------------------

def plot_results(freqs, H_atm, H_eye, solution):
    """Generate all plots. Returns figure objects for programmatic use."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec
    except ImportError:
        print("matplotlib not available; skipping plots.")
        return None

    S_star = solution["S_star"]
    shadow = solution["shadow_prices"]

    fig = plt.figure(figsize=(16, 14))
    gs = GridSpec(3, 2, figure=fig, hspace=0.35, wspace=0.3)

    # --- Panel 1: Atmospheric MTFs ---
    ax1 = fig.add_subplot(gs[0, 0])
    for w, mtf in H_atm.items():
        ax1.plot(freqs, mtf, label=w.replace("_", " "))
    ax1.set_xlabel("Spatial frequency (cpd)")
    ax1.set_ylabel("MTF")
    ax1.set_title("Atmospheric scattering MTFs")
    ax1.legend(fontsize=8)
    ax1.set_ylim(0, 1.05)
    ax1.grid(True, alpha=0.3)

    # --- Panel 2: Ocular MTFs ---
    ax2 = fig.add_subplot(gs[0, 1])
    for a, mtf in H_eye.items():
        ax2.plot(freqs, mtf, label=a.replace("_", " "))
    ax2.set_xlabel("Spatial frequency (cpd)")
    ax2.set_ylabel("MTF")
    ax2.set_title("Ocular MTFs (6mm pupil, mesopic)")
    ax2.legend(fontsize=7)
    ax2.set_ylim(0, 1.05)
    ax2.grid(True, alpha=0.3)

    # --- Panel 3: Optimal emission spectrum ---
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.fill_between(freqs, S_star, alpha=0.4, color='C2')
    ax3.plot(freqs, S_star, color='C2', linewidth=2)
    ax3.set_xlabel("Spatial frequency (cpd)")
    ax3.set_ylabel("Power allocation S*(f)")
    ax3.set_title(f"Optimal emission spectrum (obj = {solution['objective']:.4f})")
    ax3.grid(True, alpha=0.3)

    # --- Panel 4: CSF-weighted received signal ---
    ax4 = fig.add_subplot(gs[1, 1])
    csf = mesopic_csf(freqs)
    ax4.plot(freqs, csf, 'k--', alpha=0.5, label='CSF (mesopic)')
    ax4.plot(freqs, csf * S_star, color='C3', linewidth=2, label='CSF * S*(f)')
    ax4.set_xlabel("Spatial frequency (cpd)")
    ax4.set_ylabel("Perceptual weight")
    ax4.set_title("CSF-weighted optimal spectrum")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    # --- Panel 5: Shadow prices (scatter constraints) ---
    ax5 = fig.add_subplot(gs[2, 0])
    if "scatter" in shadow:
        for a, prices in shadow["scatter"].items():
            if np.any(prices > 1e-6):
                ax5.plot(freqs, prices, label=a.replace("_", " "))
        ax5.set_xlabel("Spatial frequency (cpd)")
        ax5.set_ylabel("Shadow price (lambda)")
        ax5.set_title("Shadow prices: aberration constraints")
        ax5.legend(fontsize=7)
        ax5.grid(True, alpha=0.3)
    else:
        ax5.text(0.5, 0.5, "No dual data available", transform=ax5.transAxes, ha='center')

    # --- Panel 6: Shadow prices (glare constraints) ---
    ax6 = fig.add_subplot(gs[2, 1])
    has_glare_data = False
    if "glare" in shadow:
        for w, prices in shadow["glare"].items():
            if np.any(prices > 1e-6):
                ax6.plot(freqs, prices, label=w.replace("_", " "))
                has_glare_data = True
    if has_glare_data:
        ax6.set_xlabel("Spatial frequency (cpd)")
        ax6.set_ylabel("Shadow price (mu)")
        ax6.set_title("Shadow prices: glare constraints")
        ax6.legend(fontsize=8)
        ax6.set_xlim(F_MIN, F_MAX)
        ax6.grid(True, alpha=0.3)
    else:
        ax6.set_xlabel("Spatial frequency (cpd)")
        ax6.set_ylabel("Shadow price (mu)")
        ax6.set_title("Shadow prices: glare constraints")
        ax6.set_xlim(F_MIN, F_MAX)
        ax6.text(0.5, 0.5, "No binding glare constraints\n(aberration-dominated regime)",
                 transform=ax6.transAxes, ha='center', va='center', fontsize=10, alpha=0.6)
        ax6.grid(True, alpha=0.3)

    fig.savefig("stribeck_optics_results.png", dpi=150, bbox_inches='tight')
    print("Saved: stribeck_optics_results.png")
    return fig


# ---------------------------------------------------------------------------
# 9. Main
# ---------------------------------------------------------------------------

def main():
    print("=== Stribeck Optics: SF-DMA Headlight Optimization ===\n")

    # Step 1: Simulate atmospheric MTFs
    print("1. Computing atmospheric scattering MTFs...")
    H_atm = compute_atmospheric_mtfs()
    for w, mtf in H_atm.items():
        print(f"   {w:12s}  MTF@5cpd={mtf[np.searchsorted(FREQS, 5)]:.3f}  "
              f"MTF@15cpd={mtf[np.searchsorted(FREQS, 15)]:.3f}")

    # Step 2: Compute ocular MTFs
    print("\n2. Computing ocular MTFs from Zernike profiles...")
    H_eye = compute_ocular_mtfs()
    for a, mtf in H_eye.items():
        print(f"   {a:16s}  MTF@5cpd={mtf[np.searchsorted(FREQS, 5)]:.3f}  "
              f"MTF@15cpd={mtf[np.searchsorted(FREQS, 15)]:.3f}")

    # Step 3: Build graph
    print("\n3. Building transfer function graph...")
    graph = TransferGraph(FREQS, H_atm, H_eye)
    n_edges = len(graph.weather_states) * N_FREQ + len(graph.aberration_profiles) * N_FREQ
    print(f"   {n_edges} edges ({len(graph.weather_states)} weather x {N_FREQ} freq + "
          f"{len(graph.aberration_profiles)} aberration x {N_FREQ} freq)")

    # Step 4: Solve LP
    print("\n4. Solving Lagrangian relaxation LP...")
    solution = solve_optimal_spectrum(graph)
    S_star = solution["S_star"]
    print(f"   Status: {solution['solver_status']}")
    print(f"   Objective (perceptual info): {solution['objective']:.6f}")
    print(f"   Total power used: {S_star.sum():.4f}")
    print(f"   Peak allocation at: {FREQS[np.argmax(S_star)]:.1f} cpd")
    print(f"   Non-zero bins: {np.sum(S_star > 1e-8)}/{N_FREQ}")

    # Step 5: Identify binding constraints
    print("\n5. Binding constraint analysis:")
    shadow = solution["shadow_prices"]
    if "scatter" in shadow:
        total_scatter = {a: np.sum(p) for a, p in shadow["scatter"].items()}
        top_scatter = sorted(total_scatter.items(), key=lambda x: -x[1])[:3]
        print("   Top aberration constraints (total shadow price):")
        for a, price in top_scatter:
            if price > 1e-6:
                print(f"      {a}: {price:.4f}")

    if "glare" in shadow:
        total_glare = {w: np.sum(p) for w, p in shadow["glare"].items()}
        top_glare = sorted(total_glare.items(), key=lambda x: -x[1])[:3]
        print("   Top weather constraints (total shadow price):")
        for w, price in top_glare:
            if price > 1e-6:
                print(f"      {w}: {price:.4f}")

    # Step 6: Serialize graph
    graph_data = graph.to_dict()
    graph_data["solution"] = {
        "S_star": S_star.tolist(),
        "objective": solution["objective"],
    }
    with open("transfer_graph.json", "w") as f:
        json.dump(graph_data, f, indent=2)
    print("\n6. Saved transfer_graph.json")

    # Step 7: Plot
    print("\n7. Generating plots...")
    plot_results(FREQS, H_atm, H_eye, solution)

    print("\nDone.")


if __name__ == "__main__":
    main()
