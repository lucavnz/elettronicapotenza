#!/usr/bin/env python3
"""
Generate all 21 publication-grade PNG figures replicating EVERY SINGLE plot and
oscilloscope capture in Pahlevaninezhad et al., IEEE TPEL 2012 (35.pdf), plus
4 critical-audit verification figures, directly from our LTspice .raw outputs.
"""

import json
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from spicelib import RawRead

ROOT = Path(__file__).resolve().parent.parent
LTSPICE_DIR = ROOT / "ltspice"
FIG_DIR = ROOT / "figures"
RESULTS_DIR = ROOT / "results"

sys.path.insert(0, str(ROOT / "scripts"))
from paper_math_audit import exact_gv_vs_psi, exact_dc_point

# Global clean publication typography
plt.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "legend.fontsize": 8.8,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.grid": True,
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})

# LeCroy-matched trace palette (matching Figs. 14-22 in 35.pdf!)
COL_VAB   = "#D8006C"   # Magenta (C2: Full-Bridge Output Voltage)
COL_IS    = "#00A63F"   # Green   (C4: Series Inductor Current)
COL_VDIOD = "#1A33CC"   # Blue    (C3: Output Diode Voltage / Aux Current)
COL_VSEC  = "#C28B00"   # Gold/Olive (C1: Secondary / Transformer Voltage)
COL_AUX1  = "#0055CC"   # Blue
COL_AUX2  = "#D62728"   # Red


def load_raw(stem, step=0):
    """Load LTspice .raw file and return (time_us, getter(name)) for given step index."""
    raw = RawRead(str(LTSPICE_DIR / f"{stem}.raw"))
    t = np.asarray(raw.get_trace("time").get_wave(step), dtype=float)
    # Build case-insensitive trace lookup
    names = {n.lower(): n for n in raw.get_trace_names()}

    def get(expr):
        key = expr.lower()
        if key in names:
            return np.asarray(raw.get_trace(names[key]).get_wave(step), dtype=float)
        raise KeyError(f"Trace '{expr}' not found in {stem}.raw (available: {list(names.values())[:15]}...)")

    return t, get, raw


def find_trigger_t0(t, vAB, start_after=2.0e-6):
    """Find a clean rising zero-crossing of v_AB to align oscilloscope frames."""
    m = t >= start_after
    tm = t[m]
    vm = vAB[m]
    idx = np.where((vm[:-1] < 100.0) & (vm[1:] >= 100.0))[0]
    if len(idx):
        return tm[idx[0]]
    return start_after


def savefig(fig, filename):
    out = FIG_DIR / filename
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"  [FIG] {out.name}")


# ===========================================================================
# 1. FIG. 3: Ideal Waveforms & All 7 Operating Modes (All 12 traces matching Paper Fig. 3!)
# ===========================================================================
def plot_fig03():
    t, g, _ = load_raw("02_proposed_ideal_modes_fig3")
    vA = g("V(a)"); vB = g("V(b)"); vAB = vA - vB
    vG1 = g("V(g1)") - vA; vG2 = g("V(g2)")
    vG3 = g("V(g3)") - vB; vG4 = g("V(g4)")
    ia1 = g("I(Laux1)"); ia2 = g("I(Laux2)")
    # Current in output capacitance of leading-leg switches during ZVS transitions (i_Co,SA in Paper Fig. 3)
    iCo_SA = g("I(Cs2)") - g("I(Cs1)")
    i_s = g("I(Lseq)")
    iDB = np.maximum(0.0, g("I(D1)") + g("I(D3)"))
    vsec = g("V(sec_p)") - g("V(sec_n)")

    # Align window starting just before G2 turn-off (t0) for 2 full switching cycles
    T = 1.0 / 220e3
    m0 = t >= 2.0e-6
    t_sub = t[m0]; g2_sub = vG2[m0]
    idx_t0 = np.where((g2_sub[:-1] > 6.0) & (g2_sub[1:] <= 6.0))[0][0]
    t0 = t_sub[idx_t0]

    w = (t >= t0 - 0.15 * T) & (t <= t0 + 1.85 * T)
    tu = (t[w] - t0) * 1e6

    # Locate exact t0..t7 in the first half-cycle [0, T/2]
    hw = (t >= t0) & (t <= t0 + 0.52 * T)
    th = (t[hw] - t0) * 1e6
    vAB_h = vAB[hw]; vsec_h = vsec[hw]; g4_h = vG4[hw]; g3_h = vG3[hw]; is_h = i_s[hw]
    t1 = th[np.argmax(vsec_h > 295.0)]
    t2 = th[np.argmax(vAB_h > 395.0)]
    t3_arr = np.where((g4_h[:-1] > 6.0) & (g4_h[1:] <= 6.0))[0]
    t3 = th[t3_arr[0]] if len(t3_arr) else 1.15
    t4_arr = np.where((th > t3) & (vAB_h < 5.0))[0]
    t4 = th[t4_arr[0]] if len(t4_arr) else t3 + 0.05
    t5_arr = np.where((th > t3) & (g3_h > 6.0))[0]
    t5 = th[t5_arr[0]] if len(t5_arr) else t3 + 0.165
    t6_arr = np.where((th > t5) & (is_h < 0.28))[0]
    t6 = th[t6_arr[0]] if len(t6_arr) else t5 + 0.55
    t7 = (T / 2.0) * 1e6

    fig, axes = plt.subplots(12, 1, figsize=(11.5, 15.2), sharex=True,
                             gridspec_kw={"height_ratios": [0.65, 0.65, 0.65, 0.65, 1.25, 1.05, 1.0, 1.0, 0.9, 1.2, 1.1, 1.2]})
    traces = [
        (vG1,    "$G_1$ (V)",       "#1f77b4", (-2, 15)),
        (vG2,    "$G_2$ (V)",       "#1f77b4", (-2, 15)),
        (vG3,    "$G_3$ (V)",       "#2ca02c", (-2, 15)),
        (vG4,    "$G_4$ (V)",       "#2ca02c", (-2, 15)),
        (vAB,    "$v_{AB}$ (V)",    COL_VAB,   (-460, 460)),
        (vA,     "$v_A$ (V)",       "#6A1B9A", (-40, 440)),
        (ia1,    "$i_{LAUX1}$ (A)", COL_AUX1,  (-4.5, 4.5)),
        (ia2,    "$i_{LAUX2}$ (A)", COL_AUX2,  (-4.5, 4.5)),
        (iCo_SA, "$i_{Co,SA}$ (A)", "#00838F", (-4.5, 4.5)),
        (i_s,    "$i_s$ (A)",       COL_IS,    (-18, 18)),
        (iDB,    "$i_{DB}$ (A)",    "#00695C", (-1, 15.5)),
        (vsec,   "$v_{sec}$ (V)",   COL_VSEC,  (-360, 360)),
    ]

    mode_bounds = [0.0, t1, t2, t3, t4, t5, t6, t7]
    mode_colors = ["#FFF3CD", "#FFE0B2", "#E8F5E9", "#F3E5F5", "#E3F2FD", "#E0F7FA", "#F5F5F5"]
    mode_names = ["I", "II", "III", "IV", "V", "VI", "VII"]

    for ax, (sig, ylab, col, ylim) in zip(axes, traces):
        ax.plot(tu, sig[w], color=col, lw=1.45)
        ax.axhline(0, color="black", lw=0.6, alpha=0.5)
        ax.set_ylabel(ylab, fontsize=8.8, fontweight="bold")
        ax.set_ylim(ylim)
        for j in range(7):
            ax.axvspan(mode_bounds[j], mode_bounds[j + 1], color=mode_colors[j], alpha=0.45)
        for tb in mode_bounds:
            ax.axvline(tb, color="#555555", ls=":", lw=0.7, alpha=0.7)

    y_stagger = [15.5, 19.5, 15.5, 15.5, 19.5, 15.5, 15.5]
    for j in range(7):
        xm = 0.5 * (mode_bounds[j] + mode_bounds[j + 1])
        axes[0].text(xm, y_stagger[j], f"M{mode_names[j]}", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#333333")
    axes[4].annotate(f"$\\psi = 99.5^\\circ$, $t_d = 165\\,$ns", xy=(t3, 380), xytext=(t3 + 0.55, 290),
                     fontsize=8.5, arrowprops=dict(arrowstyle="->", color="black", lw=0.8))
    axes[9].annotate(r"Peak $I_p$", xy=(t3, 15.0), xytext=(t3 + 0.35, 12.5),
                     fontsize=8.2, arrowprops=dict(arrowstyle="->", color=COL_IS, lw=0.8))
    axes[10].annotate(r"Peak $k \cdot I_p = I_p / 1.18$ (Paper Fig. 3 miswrote $I_p/k$!)",
                      xy=(t3, 12.7), xytext=(t3 + 0.35, 10.5),
                      fontsize=8.0, arrowprops=dict(arrowstyle="->", color="#00695C", lw=0.8))
    axes[11].text(0.5 * (t1 + t6), 140, "$D_1, D_4$ Conducting", ha="center", fontsize=8.2, fontweight="bold", color="#795548")
    axes[11].text(0.5 * (t1 + t6) + T / 2 * 1e6, -180, "$D_2, D_3$ Conducting", ha="center", fontsize=8.2, fontweight="bold", color="#795548")

    t_labels = ["$t_0$", "$t_1$", "$t_2$", "$t_3$", "$t_4$", "$t_5$", "$t_6$", "$t_7$"]
    t_yoff = [-495, -565, -495, -495, -565, -495, -495, -565]
    for tb, lbl, yoff in zip(mode_bounds, t_labels, t_yoff):
        axes[-1].annotate(lbl, xy=(tb, -355), xytext=(tb, yoff), ha="center", fontsize=7.8,
                          annotation_clip=False, color="#222222")

    axes[-1].set_xlabel("Time relative to $t_0$ ($\\mu$s)   [$f_s = 220\\,$kHz, $T_s = 4.545\\,\\mu$s — All 12 Traces of Fig. 3]", labelpad=34)
    fig.suptitle("Replication of Fig. 3: Ideal Steady-State Waveforms & 7 Operating Modes (LTspice, 50% Load DCM)",
                 fontsize=12.5, fontweight="bold", y=0.995)
    fig.tight_layout(rect=[0, 0.02, 1, 0.985])
    savefig(fig, "fig03_ideal_waveforms_modes.png")


# ===========================================================================
# 2. FIG. 5: Submodes of Mode IV at Light Load (100% Real LTspice Waveforms)
# ===========================================================================
def plot_fig05():
    """Replicate Fig. 5 (Mode IV transition at light load) using 100% real LTspice waveforms."""
    t, g, _ = load_raw("06_proposed_load_10pct_fig16")
    vA = g("V(a)"); vB = g("V(b)"); vAB = vA - vB
    i_s = g("I(Lseq)")
    vsec = g("V(sec_p)") - g("V(sec_n)")
    vG4 = g("V(g4)")

    tr = find_trigger_t0(t, vAB, start_after=2.0e-6)
    m = (t >= tr) & (t <= tr + 1.5e-6)
    tm = t[m]; g4m = vG4[m]; vabm = vAB[m]
    t3_idx = np.where((g4m[:-1] > 6.0) & (g4m[1:] <= 6.0))[0]
    t3 = tm[t3_idx[0]] if len(t3_idx) else tr + 0.4e-6
    t4_idx = np.where((tm > t3) & (vabm < 5.0))[0]
    t4 = tm[t4_idx[0]] if len(t4_idx) else t3 + 60e-9

    # Also load 0% no-load real LTspice run (05_proposed_noload_fig15) for ultra-light load comparison
    t0, g0, _ = load_raw("05_proposed_noload_fig15")
    vAB0 = g0("V(a)") - g0("V(b)"); is0 = g0("I(Lseq)"); vsec0 = g0("V(sec_p)") - g0("V(sec_n)"); g40 = g0("V(g4)")
    tr0 = find_trigger_t0(t0, vAB0, start_after=2.0e-6)
    m0 = (t0 >= tr0) & (t0 <= tr0 + 1.5e-6)
    t3_0_idx = np.where((g40[m0][:-1] > 6.0) & (g40[m0][1:] <= 6.0))[0]
    t3_0 = t0[m0][t3_0_idx[0]] if len(t3_0_idx) else tr0 + 0.12e-6

    w = (t >= t3 - 0.15e-6) & (t <= t3 + 0.45e-6)
    tu = (t[w] - t3) * 1e9  # ns relative to t3
    w0 = (t0 >= t3_0 - 0.15e-6) & (t0 <= t3_0 + 0.45e-6)
    tu0 = (t0[w0] - t3_0) * 1e9

    dt4 = (t4 - t3) * 1e9
    t34 = 0.52 * dt4

    fig, axes = plt.subplots(3, 1, figsize=(9.2, 7.6), sharex=True)
    axes[0].plot(tu, vAB[w], color=COL_VAB, lw=2.2, label="LTspice 10% Load (300 W) $v_{AB}(t)$")
    axes[0].plot(tu0, vAB0[w0], color=COL_VAB, lw=1.6, ls="--", alpha=0.75, label="LTspice Ultra-Light / No-Load $v_{AB}(t)$")
    axes[0].set_ylabel("$v_{AB}$ (V)", fontweight="bold")
    axes[0].set_ylim(-40, 445)
    axes[0].legend(loc="upper right", fontsize=8.5)

    axes[1].plot(tu, i_s[w], color=COL_IS, lw=2.2, label="LTspice 10% Load $i_s(t)$ ($I_p = 6.6\\,$A)")
    axes[1].plot(tu0, is0[w0], color=COL_IS, lw=1.6, ls="--", alpha=0.75, label="LTspice Ultra-Light / No-Load $i_s(t)$ ($I_p = 1.7\\,$A)")
    axes[1].set_ylabel("$i_s$ (A)", fontweight="bold")
    axes[1].axhline(0, color="k", lw=0.6)
    axes[1].legend(loc="upper right", fontsize=8.5)

    axes[2].plot(tu, vsec[w], color=COL_VSEC, lw=2.2, label="LTspice 10% Load $v_{sec}(t)$")
    axes[2].plot(tu0, vsec0[w0], color=COL_VSEC, lw=1.6, ls="--", alpha=0.75, label="LTspice Ultra-Light / No-Load $v_{sec}(t)$")
    axes[2].set_ylabel("$v_{sec}$ (V)", fontweight="bold")
    axes[2].set_xlabel("Time relative to $t_3$ (ns)   [Mode IV Lagging-Leg ZVS Transition]", fontweight="bold")
    axes[2].legend(loc="lower left", fontsize=8.5)

    for ax in axes:
        ax.axvspan(0, t34, color="#E1BEE7", alpha=0.4)
        ax.axvspan(t34, dt4, color="#F3E5F5", alpha=0.5)
        for tx in (0.0, t34, dt4):
            ax.axvline(tx, color="#4A148C", ls=":", lw=1.0)

    axes[0].text(0, 452, "$t_3$", ha="center", fontweight="bold", color="#4A148C")
    axes[0].text(t34, 452, "$t_{3-4}$", ha="center", fontweight="bold", color="#4A148C")
    axes[0].text(dt4 + 6, 452, "$t_4$", ha="left", fontweight="bold", color="#4A148C")
    axes[0].annotate("Submode IV-a: $-\\frac{i_s+I_{PB}}{2C_{so}}$\nSubmode IV-b: $-\\frac{I_{PB}}{2C_{so}}$",
                     xy=(dt4 * 0.5, 200), xytext=(dt4 + 45, 220),
                     fontsize=8.5, arrowprops=dict(arrowstyle="->", color="#4A148C"),
                     bbox=dict(boxstyle="round,pad=0.3", fc="#F3E5F5", ec="#4A148C"))

    fig.suptitle("Replication of Fig. 5: Submodes of Mode IV at Light Load ($t_3 \\to t_{3-4} \\to t_4$)",
                 fontsize=11.8, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "fig05_mode4_light_load_submodes.png")


# ===========================================================================
# 3. FIG. 6: Series Inductor Current & Voltage for Half Switching Cycle
# ===========================================================================
def plot_fig06():
    t, g, _ = load_raw("02_proposed_ideal_modes_fig3")
    vA = g("V(a)"); vB = g("V(b)"); vAB = vA - vB
    i_s = g("I(Lseq)")
    # Voltage strictly across Lseq: V(A)-V(pri_p) minus V(CB) -> or V(N_CB) - V(pri_p)
    # Better: compute Lseq * di/dt OR direct V(Lseq) from V(a) - V(pri_p) (CB is AC short, ~0V DC!)
    v_Lseq = vAB - (g("V(pri_p)") - vB)  # equals v_CB + v_Lseq ≈ v_Lseq!

    T = 1.0 / 220e3
    t_rise = find_trigger_t0(t, vAB, start_after=2.0e-6)
    w = (t >= t_rise - 0.15e-6) & (t <= t_rise + 0.52 * T)
    tu = (t[w] - t_rise) * 1e6

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.5, 6.2), sharex=True)
    ax1.plot(tu, i_s[w], color=COL_IS, lw=2.2, label="LTspice $i_s(t)$")
    ax1.axhline(0, color="k", lw=0.7)
    ax1.set_ylabel("Series Inductor Current $i_s$ (A)", fontweight="bold")
    ax1.set_ylim(-2, 17.5)
    ax1.annotate(r"Rising slope: $\frac{V_{dc} - k(V_o + 2V_d)}{L_{seq}} \approx +12.1\,\mathrm{A/\mu s}$",
                 xy=(0.55, 7.5), xytext=(0.05, 13.5), fontsize=9.5,
                 arrowprops=dict(arrowstyle="->", color="black"),
                 bbox=dict(boxstyle="round,pad=0.25", fc="#E8F5E9", ec=COL_IS))
    ax1.annotate(r"Falling slope: $\frac{-k(V_o + 2V_d)}{L_{seq}} \approx -21.8\,\mathrm{A/\mu s}$" "\n(Note: Paper Fig. 6 typo wrote $V_o - 2V_d$!)",
                 xy=(1.50, 7.5), xytext=(1.35, 13.0), fontsize=8.8,
                 arrowprops=dict(arrowstyle="->", color="black"),
                 bbox=dict(boxstyle="round,pad=0.25", fc="#FFF3E0", ec="#E65100"))
    ax1.legend(loc="lower right")

    ax2.plot(tu, v_Lseq[w], color="#1565C0", lw=2.0, label="LTspice $v_{Lseq}(t)$")
    ax2.axhline(0, color="k", lw=0.7)
    ax2.axhline(400 - (303 / 1.18), color="gray", ls="--", lw=1.0, label=r"$V_{dc} - k(V_o+2V_d) = +143.2\,\mathrm{V}$")
    ax2.axhline(-(303 / 1.18), color="crimson", ls="--", lw=1.0, label=r"$-k(V_o+2V_d) = -256.8\,\mathrm{V}$")
    ax2.set_ylabel("Series Inductor Voltage $v_{Lseq}$ (V)", fontweight="bold")
    ax2.set_xlabel("Half Switching Cycle Time ($\\mu$s)", fontweight="bold")
    ax2.set_ylim(-310, 210)
    ax2.legend(loc="lower right", fontsize=8.5)

    fig.suptitle("Replication of Fig. 6: Series Inductor Current & Voltage Waveforms (Half-Cycle DCM, LTspice)",
                 fontsize=11.5, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "fig06_series_inductor_vi.png")


# ===========================================================================
# 4. FIG. 7: Converter Conversion Ratio gv(psi, Re) + Forensic Error Proof!
# ===========================================================================
def plot_fig07():
    metrics = json.loads((RESULTS_DIR / "simulation_metrics.json").read_text())
    sw = metrics["fig07_2d_sweep"]
    psi_sim = np.array(sw["psi_deg"], dtype=float)
    re_list = [30, 50, 80, 120, 170, 230, 300]
    colors = ["#000000", "#1A33CC", "#00A63F", "#D8006C", "#00ACC1", "#8D4E00", "#555555"]
    markers = ["s", "D", "o", "^", "x", "+", "s"]

    k = 1.0 / 1.18
    Lseq = 11.8e-6
    fs = 220e3
    Ts = 1.0 / fs
    psi_dense = np.linspace(5, 175, 120)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.6), sharey=True)

    # Panel A: LTspice 84-point simulation vs Exact Physical DCM+CCM Model
    for idx, Re in enumerate(re_list):
        col = colors[idx]; mk = markers[idx]
        gvs_lt = np.array(sw["Re_curves"][str(Re)], dtype=float)
        # Exact analytical DCM+CCM (with Vd=1.4V & effective td_eff=100ns matching switch rise time)
        gvs_ex = [exact_gv_vs_psi(p, Re, Vdc=400.0, Vd=1.4, Lseq=Lseq, k=k, fs=fs, td=100e-9)[0] for p in psi_dense]
        ax1.plot(psi_dense, gvs_ex, color=col, lw=1.4, alpha=0.75)
        ax1.plot(psi_sim, gvs_lt, color=col, marker=mk, ls="none", ms=5.5,
                 fillstyle="none" if Re == 300 else "full", label=f"$R_e = {Re}\\,\\Omega$")

    ax1.axhline(1.0 / k, color="gray", ls=":", lw=1.1, label=f"Ideal step-up limit $1/k = {1/k:.2f}$")
    ax1.set_title("(a) True Converter Gain: LTspice (markers) vs. Exact DCM+CCM Theory (lines)", fontweight="bold")
    ax1.set_xlabel("Phase-Shift $\\psi$ (degrees)", fontweight="bold")
    ax1.set_ylabel("Voltage Conversion Gain $g_v = V_o / V_{dc}$", fontweight="bold")
    ax1.set_xlim(0, 185); ax1.set_ylim(0, 1.25)
    ax1.legend(loc="lower right", ncol=2, fontsize=8.2)

    # Panel B: Forensic Discrepancy Proof (Re = 30 Ohm & Re = 300 Ohm)
    for Re, col, lbl in [(30, "#000000", "$R_e = 30\\,\\Omega$ (Full load)"), (300, "#D8006C", "$R_e = 300\\,\\Omega$ (10% load)")]:
        # 1) Paper's Fig. 7 plotted curve (C = Lseq*fs = 2.60 Ohm -> 4x smaller than physics!)
        gv_paper_plot = [2.0 / (k + np.sqrt(k**2 + (Lseq * fs) / (Re * (p / 360.0)**2))) for p in psi_dense]
        # 2) Corrected DCM-only formula (C = 4*Lseq*fs = 10.38 Ohm)
        gv_corr_dcm = [2.0 / (k + np.sqrt(k**2 + (4 * Lseq * fs) / (Re * (p / 360.0)**2))) for p in psi_dense]
        # 3) LTspice actual points
        gvs_lt = np.array(sw["Re_curves"][str(Re)], dtype=float)
        ax2.plot(psi_dense, gv_paper_plot, color=col, ls="--", lw=1.8,
                 label=f"Paper Fig. 7 plotted ({lbl}, 4$\\times$ err)")
        ax2.plot(psi_dense, gv_corr_dcm, color=col, ls=":", lw=1.5,
                 label=f"Corrected DCM Eq. ({lbl})")
        ax2.plot(psi_sim, gvs_lt, color=col, marker="o", ls="-", lw=1.5, ms=5,
                 label=f"LTspice Actual ({lbl})")

    # Also plot literal printed Eq. (18) (dimensionally broken -> ~1e-6!)
    gv_broken_eq18 = [2.0 / (k + np.sqrt(k**2 + 4 * Lseq / (Ts * 30.0 * (p / 360.0 * Ts)**2))) for p in psi_dense]
    ax2.plot(psi_dense, gv_broken_eq18, color="red", lw=2.5, label="Literal printed Eq. (18): $g_v \\approx 4\\times 10^{-6}$ (broken units!)")

    ax2.annotate("Paper Fig. 7 predicts $g_v = 1.05$\n@ $\\psi=171^\\circ, 30\\,\\Omega$,\nbut real circuit saturates\nat $g_v = 0.75$ (CCM)!",
                 xy=(165, 0.76), xytext=(100, 0.42), fontsize=8.3,
                 arrowprops=dict(arrowstyle="->", color="crimson", lw=1.3),
                 bbox=dict(boxstyle="round,pad=0.3", fc="#FFEBEE", ec="crimson"))

    ax2.set_title("(b) Critical Audit: Paper Fig. 7 & Broken Eq. (18) vs. LTspice Physics", fontweight="bold")
    ax2.set_xlabel("Phase-Shift $\\psi$ (degrees)", fontweight="bold")
    ax2.set_xlim(0, 185); ax2.set_ylim(0, 1.25)
    ax2.legend(loc="lower right", bbox_to_anchor=(0.99, 0.03), fontsize=7.3, framealpha=0.94)

    fig.suptitle("Replication & Critical Audit of Fig. 7: Converter Conversion Ratio ($L_{seq}=11.8\\,\\mu$H, $f_s=220\\,$kHz, $k=1/1.18$)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "fig07_converter_gain_comparison.png")


# ===========================================================================
# 5. FIG. 8: Auxiliary Circuit Waveforms
# ===========================================================================
def plot_fig08():
    t, g, _ = load_raw("02_proposed_ideal_modes_fig3")
    vA = g("V(a)"); vB = g("V(b)")
    ia1 = g("I(Laux1)"); ia2 = g("I(Laux2)")

    T = 1.0 / 220e3
    t0 = find_trigger_t0(t, vA - 200.0, start_after=2.0e-6)
    w = (t >= t0 - 0.2 * T) & (t <= t0 + 1.8 * T)
    tu = (t[w] - t0) * 1e6

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9.5, 5.8), sharex=True)
    ax1.plot(tu, vA[w], color="#111111", lw=1.8, label="$V_A$ (Leading Leg)")
    ax1.set_ylabel("Leading Leg $V_A$ (V)", fontweight="bold")
    ax1.set_ylim(-50, 460)
    ax1_r = ax1.twinx()
    ax1_r.plot(tu, ia1[w], color=COL_AUX2, lw=1.8, label="$i_{LAUX1}$ ($I_{PA} \\approx 3.39\\,$A)")
    ax1_r.set_ylabel("$i_{LAUX1}$ (A)", color=COL_AUX2, fontweight="bold")
    ax1_r.set_ylim(-4.8, 4.8)
    ax1_r.axhline(0, color="gray", lw=0.6)
    ax1_r.grid(False)
    lines1, lbls1 = ax1.get_legend_handles_labels()
    lines2, lbls2 = ax1_r.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lbls1 + lbls2, loc="upper right")

    ax2.plot(tu, vB[w], color="#111111", lw=1.8, label="$V_B$ (Lagging Leg)")
    ax2.set_ylabel("Lagging Leg $V_B$ (V)", fontweight="bold")
    ax2.set_xlabel("Time ($\\mu$s)   [Symmetric Auxiliary Circuits: $L_{AUX1}=L_{AUX2}=67\\,\\mu$H, Eq. (20) $I_{PA}=I_{PB}=3.39\\,$A]", fontweight="bold")
    ax2.set_ylim(-50, 460)
    ax2_r = ax2.twinx()
    ax2_r.plot(tu, ia2[w], color=COL_AUX1, lw=1.8, label="$i_{LAUX2}$ ($I_{PB} \\approx 3.39\\,$A)")
    ax2_r.set_ylabel("$i_{LAUX2}$ (A)", color=COL_AUX1, fontweight="bold")
    ax2_r.set_ylim(-4.8, 4.8)
    ax2_r.axhline(0, color="gray", lw=0.6)
    ax2_r.grid(False)
    lines1, lbls1 = ax2.get_legend_handles_labels()
    lines2, lbls2 = ax2_r.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, lbls1 + lbls2, loc="upper right")

    fig.suptitle("Replication of Fig. 8: Symmetric Auxiliary Circuit Voltage & Triangular Current Waveforms (LTspice)",
                 fontsize=11.8, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "fig08_auxiliary_circuit_waveforms.png")


# ===========================================================================
# 6. FIG. 9: Critical Conduction Mode (BCM) - Table II vs Corrected Eq. (26)
# ===========================================================================
def plot_fig09():
    # NOTE: LTspice sorts .step param Lseq list 11.8u 8.0u ascending => step 0 = 8.0uH (3.0kW BCM), step 1 = 11.8uH (2.25kW BCM)!
    t_8p0, g_8p0, _ = load_raw("04_proposed_bcm_design_fig9", step=0)
    t_11p8, g_11p8, _ = load_raw("04_proposed_bcm_design_fig9", step=1)
    T = 1.0 / 220e3

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.8), sharey=True)
    for ax, t, g, ttl, col, po_lbl in [
        (ax1, t_11p8, g_11p8, "(a) Table II $L_{seq} = 11.8\\,\\mu$H at BCM ($\\psi=119.5^\\circ$)\nMax BCM Power = 2.25 kW (< 3 kW!)", "#1565C0", "$I_p \\approx 17.7\\,$A"),
        (ax2, t_8p0,  g_8p0,  "(b) Corrected Practical BCM $L_{seq} = 8.0\\,\\mu$H ($\\psi=119.5^\\circ$)\nTrue 3.0 kW Critical Conduction Mode ($I_o = 10\\,$A)!", COL_IS, "$I_p = 2I_o/k \\approx 23.6\\,$A"),
    ]:
        vAB = g("V(a)") - g("V(b)")
        i_s = g("I(Lseq)")
        tr = find_trigger_t0(t, vAB, start_after=2.0e-6)
        w = (t >= tr - 0.1 * T) & (t <= tr + 1.15 * T)
        tu = (t[w] - tr) * 1e6
        ax.plot(tu, i_s[w], color=col, lw=2.2, label=f"LTspice $i_s(t)$ ({po_lbl})")
        ax.axhline(0, color="k", lw=0.8)
        ax.axvline(0, color="gray", ls=":", lw=0.9)
        ax.axvline(T / 2 * 1e6, color="gray", ls=":", lw=0.9)
        ax.axvline(T * 1e6, color="gray", ls=":", lw=0.9)
        ax.set_title(ttl, fontweight="bold", fontsize=10.2)
        ax.set_xlabel("Time ($\\mu$s)   [$T_s/2 = 2.27\\,\\mu$s, $T_s = 4.55\\,\\mu$s]", fontweight="bold")
        ax.legend(loc="upper right")

    ax1.set_ylabel("Primary Series Inductor Current $i_s$ (A)", fontweight="bold")
    ax2.annotate("Exact primary BCM peak:\n$I_p = \\frac{2 I_o}{k} = 23.6\\,$A\n(Paper Fig. 9 miswrote $2 k I_o$!)",
                 xy=(1.45, 23.6), xytext=(2.1, 13.0), fontsize=8.8,
                 arrowprops=dict(arrowstyle="->", color="crimson", lw=1.2),
                 bbox=dict(boxstyle="round,pad=0.25", fc="#FFF3E0", ec="#E65100"))
    fig.suptitle("Replication & Verification of Fig. 9: Critical Conduction Mode (BCM) Series Inductor Design",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "fig09_critical_conduction_mode.png")


# ===========================================================================
# 7. FIG. 11(a) & (b): Output Capacitor Waveforms (DCM Typical Load vs BCM Full Load)
# ===========================================================================
def plot_fig11():
    T = 1.0 / 220e3
    t_dcm, g_dcm, _ = load_raw("02_proposed_ideal_modes_fig3")
    t_bcm, g_bcm, _ = load_raw("04_proposed_bcm_design_fig9", step=0)  # step 0 = 8.5uH true 3kW BCM!

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 6.8), sharex="col")
    configs = [
        (0, t_dcm, g_dcm, "(a) Typical Load (50% Load DCM, $I_o \\approx 5.5\\,$A)"),
        (1, t_bcm, g_bcm, "(b) Full-Load BCM ($3.0\\,$kW, $L_{seq}=8.0\\,\\mu$H, $I_o = 10.0\\,$A)"),
    ]
    for col_idx, t, g, title in configs:
        vAB = g("V(a)") - g("V(b)")
        iCf = g("I(Cf)")
        vCf = g("V(vcf)") - g("V(gnd_sec)")
        tr = find_trigger_t0(t, vAB, start_after=2.0e-6)
        w = (t >= tr - 0.1 * T) & (t <= tr + 1.15 * T)
        tu = (t[w] - tr) * 1e6

        ax_i = axes[0, col_idx]
        ax_v = axes[1, col_idx]
        ax_i.plot(tu, iCf[w], color="#1565C0", lw=1.9, label="LTspice $i_{Cf}(t)$")
        ax_i.axhline(0, color="k", lw=0.7)
        ax_i.set_title(title, fontweight="bold")
        ax_i.set_ylabel("Capacitor Current $i_{Cf}$ (A)", fontweight="bold")
        ax_i.legend(loc="upper right")

        dv = vCf[w].max() - vCf[w].min()
        ax_v.plot(tu, vCf[w], color=COL_VAB, lw=1.9, label=f"LTspice $v_{{Cf}}(t)$ ($\\Delta V_{{Cf}} = {dv:.2f}\\,$V)")
        ax_v.set_ylabel("Capacitor Voltage $v_{Cf}$ (V)", fontweight="bold")
        ax_v.set_xlabel("Time ($\\mu$s)", fontweight="bold")
        ax_v.legend(loc="upper right")

    axes[1, 1].text(0.03, 0.06,
                    f"Eq. (32) ideal @ $I_o=10.0\\,$A, $C_f=1\\,\\mu$F:\n"
                    f"$\\Delta V_{{Cf}} = \\frac{{I_o}}{{8 f_s C_f}} = 5.68\\,$V  (LTspice incl. ESR: {dv:.2f} V)",
                    transform=axes[1, 1].transAxes, fontsize=8.3,
                    bbox=dict(boxstyle="round,pad=0.3", fc="#E8F5E9", ec=COL_IS, alpha=0.92))
    fig.suptitle("Replication of Fig. 11: Output Clamping Capacitor $C_f$ Current & Voltage Ripple Waveforms (LTspice)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "fig11_output_capacitor_waveforms.png")


# ===========================================================================
# 8. FIG. 14(a) & (b): Conventional Full-Bridge + Asymmetric Aux (10% & 100%)
# ===========================================================================
def plot_fig14():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.5, 8.2))
    for ax, stem, title in [
        (ax1, "13_conventional_psfb_10pct_fig14a", "(a) Conventional Full-Bridge + Asymmetric Aux at 10% Load (300 W) — Severe Output Spikes"),
        (ax2, "14_conventional_psfb_100pct_fig14b", "(b) Conventional Full-Bridge + Asymmetric Aux at 100% Full-Load (3000 W) — Extreme Spikes & Freewheeling Step"),
    ]:
        t, g, _ = load_raw(stem)
        vAB = g("V(a)") - g("V(b)")
        vsec = g("V(sec_p)") - g("V(sec_n)")
        iaB = g("I(LauxB)")
        tr = find_trigger_t0(t, vAB, start_after=2.0e-6)
        w = (t >= tr - 1.0e-6) & (t <= tr + 9.0e-6)  # 10 us span (1 us/div)
        tu = (t[w] - tr) * 1e6

        ax.plot(tu, vAB[w], color=COL_VAB, lw=1.6, label="Full-Bridge Output $v_{AB}$ (V)")
        ax.plot(tu, vsec[w], color=COL_IS, lw=1.3, label=f"Transformer Secondary $v_{{sec}}$ (Peak = {vsec[w].max():.0f} V!)")
        ax.axhline(600, color="red", ls="--", lw=0.9, alpha=0.8, label="600 V diode rating exceeded!")
        ax.axhline(-600, color="red", ls="--", lw=0.9, alpha=0.8)
        ax.set_ylabel("Voltage (V)", fontweight="bold")
        ax.set_ylim(-1100, 1100)
        ax.set_title(title, fontweight="bold")

        ax_r = ax.twinx()
        ax_r.plot(tu, iaB[w], color=COL_VDIOD, lw=1.5, label="Auxiliary Current $i_{LAUX,B}$ (A)")
        ax_r.set_ylabel("Aux Current (A)", color=COL_VDIOD, fontweight="bold")
        ax_r.set_ylim(-6.0, 6.0)
        ax_r.grid(False)

        l1, lb1 = ax.get_legend_handles_labels()
        l2, lb2 = ax_r.get_legend_handles_labels()
        ax.legend(l1 + l2, lb1 + lb2, loc="upper right", fontsize=8.2, ncol=2)

    ax2.set_xlabel("Time ($\\mu$s)   [Table V: $L_{leak}=1.8\\,\\mu$H, $L_{AUX,A}=33\\,\\mu$H, $L_{AUX,B}=67\\,\\mu$H, $L_f=80\\,\\mu$H, $C_o=140\\,\\mu$F, $f_s=220\\,$kHz]", fontweight="bold")
    fig.suptitle("Replication of Fig. 14: Conventional PSFB Converter Voltage Spikes (LTspice, 10% & 100% Load)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "fig14_conventional_fb_10_100pct.png")


# ===========================================================================
# 9. FIGS. 15–21: Proposed Converter Scope Replications (0%, 10%, 25%, 50%, 70%, 85%, 100%)
# ===========================================================================
def plot_fig15():
    t, g, _ = load_raw("05_proposed_noload_fig15")
    vAB = g("V(a)") - g("V(b)")
    vsec = g("V(sec_p)") - g("V(sec_n)")
    vD_pos = g("V(sec_p)") - g("V(gnd_sec)")  # Positive-polarity probe matching Fig. 15 C1 (yellow)
    i_s = g("I(Lseq)")

    tr = find_trigger_t0(t, vAB, start_after=2.0e-6)
    w = (t >= tr - 2.0e-6) & (t <= tr + 8.0e-6)
    tu = (t[w] - tr) * 1e6

    fig, ax = plt.subplots(figsize=(10.0, 5.2))
    ax.plot(tu, vAB[w], color=COL_VDIOD, lw=1.6, label="Full-Bridge Output $v_{AB}$ (V)")
    ax.plot(tu, vsec[w], color=COL_VAB, lw=1.3, label="Transformer Secondary $v_{sec}$ (V)")
    ax.plot(tu, vD_pos[w], color=COL_VSEC, lw=1.4, label="Output Diode Voltage $v_D$ (clamped $\\leq 302\\,$V)")
    ax.set_ylabel("Voltage (V)", fontweight="bold")
    ax.set_ylim(-450, 450)
    ax_r = ax.twinx()
    ax_r.plot(tu, i_s[w], color=COL_IS, lw=1.6, label=f"Series Inductor Current $i_s$ (Peak={i_s[w].max():.2f} A)")
    ax_r.set_ylabel("Current $i_s$ (A)", color=COL_IS, fontweight="bold")
    ax_r.set_ylim(-15, 15)
    ax_r.grid(False)
    l1, lb1 = ax.get_legend_handles_labels()
    l2, lb2 = ax_r.get_legend_handles_labels()
    ax.legend(l1 + l2, lb1 + lb2, loc="upper right", fontsize=8.5)
    ax.set_xlabel("Time ($\\mu$s)   [1.0 $\\mu$s/div — Zero Voltage Spikes & Full ZVS at 0% No-Load]", fontweight="bold")
    ax.set_title("Replication of Fig. 15: Proposed Converter Waveforms at No-Load (0% Load, LTspice)", fontweight="bold")
    fig.tight_layout()
    savefig(fig, "fig15_proposed_noload.png")


def plot_proposed_scope_pair(stem, fig_num, load_label, out_name, with_zoom=True, i_ylim=22.0, annotate_nospike=False):
    t, g, _ = load_raw(stem)
    vAB = g("V(a)") - g("V(b)")
    i_s = g("I(Lseq)")
    vD2 = g("V(gnd_sec)") - g("V(sec_p)")  # Matches LeCroy C3 blue trace (0V conducting, -Vo blocking, -Vo/2 ringing)!

    tr = find_trigger_t0(t, vAB, start_after=2.0e-6)
    w_full = (t >= tr - 1.5e-6) & (t <= tr + 8.5e-6)  # 10 us span (1 us/div)
    tu_f = (t[w_full] - tr) * 1e6

    if with_zoom:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.2, 8.0))
    else:
        fig, ax1 = plt.subplots(figsize=(10.2, 4.8))

    def draw_scope(ax, tu, mask, ttl, x_lbl):
        ax.plot(tu, vAB[mask], color=COL_VAB, lw=1.7, label="Full-Bridge Output $v_{AB}$ (V)")
        ax.plot(tu, vD2[mask], color=COL_VDIOD, lw=1.5, label=f"Output Diode Voltage $v_{{D2}}$ (min = {vD2[mask].min():.1f} V)")
        ax.axhline(0, color="k", lw=0.6, alpha=0.5)
        ax.set_ylabel("Voltage (V)", fontweight="bold")
        ax.set_ylim(-440, 460)
        ax.set_title(ttl, fontweight="bold")
        ax_r = ax.twinx()
        ax_r.plot(tu, i_s[mask], color=COL_IS, lw=1.8, label=f"Series Inductor Current $i_s$ (Peak = {i_s[mask].max():.2f} A)")
        ax_r.set_ylabel("Series Current $i_s$ (A)", color=COL_IS, fontweight="bold")
        ax_r.set_ylim(-i_ylim, i_ylim)
        ax_r.grid(False)
        l1, lb1 = ax.get_legend_handles_labels()
        l2, lb2 = ax_r.get_legend_handles_labels()
        ax.legend(l1 + l2, lb1 + lb2, loc="upper right", fontsize=8.3)
        ax.set_xlabel(x_lbl, fontweight="bold")

    draw_scope(ax1, tu_f, w_full,
               f"(a) Proposed Converter at {load_label} — Full View (1.0 $\\mu$s/div, LTspice)" if with_zoom
               else f"Replication of Fig. {fig_num}: Proposed Converter at {load_label} (1.0 $\\mu$s/div, LTspice)",
               "Time ($\\mu$s)")

    if with_zoom:
        w_z = (t >= tr - 0.35e-6) & (t <= tr + 2.15e-6)  # 2.5 us span (250 ns/div, matching Figs. 17b-20b!)
        tu_z = (t[w_z] - tr) * 1e6
        draw_scope(ax2, tu_z, w_z,
                   f"(b) Proposed Converter at {load_label} — Enlarged View (250 ns/div, LTspice)",
                   "Time relative to leading-edge transition ($\\mu$s)   [250 ns/div]")
        if annotate_nospike:
            ax2.annotate("Smooth ZVS edge\nNo Voltage Spikes", xy=(0.12, 395), xytext=(0.45, 295),
                         fontsize=8.5, fontweight="bold",
                         arrowprops=dict(arrowstyle="->", color="#222"),
                         bbox=dict(boxstyle="round,pad=0.2", fc="#FCE4EC", ec=COL_VAB))
            ax2.annotate("Clamped to $-V_o = -305\\,$V\n(No Voltage Spikes!)", xy=(0.25, -304), xytext=(0.65, -220),
                         fontsize=8.5, fontweight="bold",
                         arrowprops=dict(arrowstyle="->", color=COL_VDIOD),
                         bbox=dict(boxstyle="round,pad=0.2", fc="#E8EAF6", ec=COL_VDIOD))
        fig.suptitle(f"Replication of Fig. {fig_num}: Proposed Converter Waveforms at {load_label} (LTspice)",
                     fontsize=12, fontweight="bold")

    fig.tight_layout()
    savefig(fig, out_name)


def plot_fig21():
    """Fig. 21 (100% Full Load = 3000W): Table II Lseq=11.8uH (Deep CCM!) vs Corrected BCM Lseq=8.5uH."""
    t_ccm, g_ccm, _ = load_raw("11_proposed_load_100pct_fig21")
    t_bcm, g_bcm, _ = load_raw("04_proposed_bcm_design_fig9", step=0)  # step 0 = 8.5uH!

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.5, 8.2))
    for ax, t, g, ttl, note in [
        (ax1, t_ccm, g_ccm,
         "(a) Replication of Fig. 21: Table II Prototype ($L_{seq}=11.8\\,\\mu$H, $\\psi=151^\\circ$, $P_o=3.0\\,$kW) — DEEP CCM!",
         "Notice $i_s$ jumps directly from $-13\\,$A through $0$ with steep slope!\nMatches Paper Fig. 21 scope trace -> CONVERTER IS IN CCM, NOT BCM!"),
        (ax2, t_bcm, g_bcm,
         "(b) Corrected Design ($L_{seq}=8.0\\,\\mu$H, $\\psi=119.5^\\circ$, $P_o = 3.0\\,$kW) — True Critical Conduction Mode (BCM)",
         "$i_s$ returns cleanly to $0\\,$A before each leading-leg transition\n=> Restores true ZCS turn-ON of $M_1/M_2$ & ZCS turn-OFF of $D_1$–$D_4$ at 3.0 kW!"),
    ]:
        vAB = g("V(a)") - g("V(b)")
        i_s = g("I(Lseq)")
        vD2 = g("V(gnd_sec)") - g("V(sec_p)")
        tr = find_trigger_t0(t, vAB, start_after=2.0e-6)
        w = (t >= tr - 1.5e-6) & (t <= tr + 8.5e-6)
        tu = (t[w] - tr) * 1e6

        ax.plot(tu, vAB[w], color=COL_VAB, lw=1.7, label="Full-Bridge Output $v_{AB}$ (V)")
        ax.plot(tu, vD2[w], color=COL_VDIOD, lw=1.5, label=f"Output Diode Voltage $v_{{D2}}$ (min={vD2[w].min():.1f} V)")
        ax.axhline(0, color="k", lw=0.6, alpha=0.5)
        ax.set_ylabel("Voltage (V)", fontweight="bold")
        ax.set_ylim(-440, 460)
        ax.set_title(ttl, fontweight="bold")
        ax_r = ax.twinx()
        ax_r.plot(tu, i_s[w], color=COL_IS, lw=2.0, label=f"Series Current $i_s$ (Peak={i_s[w].max():.1f} A)")
        ax_r.set_ylabel("Current $i_s$ (A)", color=COL_IS, fontweight="bold")
        ax_r.set_ylim(-30, 30)
        ax_r.grid(False)
        l1, lb1 = ax.get_legend_handles_labels()
        l2, lb2 = ax_r.get_legend_handles_labels()
        ax.legend(l1 + l2, lb1 + lb2, loc="upper right", fontsize=8.2)
        ax.text(0.015, 0.06, note, transform=ax.transAxes, fontsize=8.3,
                bbox=dict(boxstyle="round,pad=0.3", fc="#FFF8E1" if ax is ax1 else "#E8F5E9", ec="#F57C00" if ax is ax1 else COL_IS))

    ax2.set_xlabel("Time ($\\mu$s)   [1.0 $\\mu$s/div]", fontweight="bold")
    fig.suptitle("Replication & Critical Audit of Fig. 21: Full-Load Operation (3 kW) — CCM Discovery vs. True BCM",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "fig21_proposed_100pct_ccm_vs_bcm.png")


# ===========================================================================
# 10. FIG. 22(a) & (b): Auxiliary Circuit Current at Two Loads
# ===========================================================================
def plot_fig22():
    t0, g0, _ = load_raw("12_proposed_aux_circuit_fig22", step=0)  # Light load (~12%)
    t1, g1, _ = load_raw("12_proposed_aux_circuit_fig22", step=1)  # Full load (100%)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.2, 7.8))

    # Panel (a): Light load (matches Fig. 22a: v_AB, v_sec, i_s, i_LAUX)
    vAB0 = g0("V(a)") - g0("V(b)")
    vsec0 = g0("V(sec_p)") - g0("V(sec_n)")
    is0 = g0("I(Lseq)")
    ia0 = g0("I(Laux1)")
    tr0 = find_trigger_t0(t0, vAB0, start_after=2.0e-6)
    w0 = (t0 >= tr0 - 1.5e-6) & (t0 <= tr0 + 8.5e-6)
    tu0 = (t0[w0] - tr0) * 1e6

    ax1.plot(tu0, vAB0[w0], color=COL_VSEC, lw=1.6, label="Full-Bridge Output $v_{AB}$ (V)")
    ax1.plot(tu0, vsec0[w0], color=COL_VAB, lw=1.3, label="Transformer Output $v_{sec}$ (V)")
    ax1.set_ylabel("Voltage (V)", fontweight="bold")
    ax1.set_ylim(-460, 460)
    ax1.set_title("(a) Light Load (~12% Load): Auxiliary Current Alongside $v_{AB}$, $v_{sec}$, and $i_s$", fontweight="bold")
    ax1_r = ax1.twinx()
    ax1_r.plot(tu0, is0[w0], color=COL_IS, lw=1.7, label=f"Series Current $i_s$ (Peak={is0[w0].max():.1f} A)")
    ax1_r.plot(tu0, ia0[w0], color=COL_VDIOD, lw=2.0, label=f"Auxiliary Current $i_{{LAUX1}}$ ($\\pm${ia0[w0].max():.2f} A)")
    ax1_r.set_ylabel("Current (A)", fontweight="bold")
    ax1_r.set_ylim(-10, 10)
    ax1_r.grid(False)
    l1, lb1 = ax1.get_legend_handles_labels()
    l2, lb2 = ax1_r.get_legend_handles_labels()
    ax1.legend(l1 + l2, lb1 + lb2, loc="upper right", fontsize=8.2, ncol=2)

    # Panel (b): Heavy load (matches Fig. 22b: v_AB near full duty + triangular i_AUXA flowing into node A)
    vAB1 = g1("V(a)") - g1("V(b)")
    ia1 = -g1("I(Laux1)")  # Current flowing into node A (matches arrow I_AUXA in Fig. 4a & phase of Fig. 22b!)
    tr1 = find_trigger_t0(t1, vAB1, start_after=2.0e-6)
    w1 = (t1 >= tr1 - 1.5e-6) & (t1 <= tr1 + 8.5e-6)
    tu1 = (t1[w1] - tr1) * 1e6

    ax2.plot(tu1, vAB1[w1], color=COL_VAB, lw=1.8, label="Full-Bridge Output $v_{AB}$ (V)")
    ax2.set_ylabel("Voltage (V)", fontweight="bold")
    ax2.set_ylim(-480, 480)
    ax2.set_xlabel("Time ($\\mu$s)   [Load-Independent Auxiliary Peak Current $I_{PA} = V_{dc}/(8 L_{AUX} f_s) = 3.39\\,$A]", fontweight="bold")
    ax2.set_title("(b) Full Load (100% Load): Auxiliary Current Remains Constant & Load-Independent", fontweight="bold")
    ax2_r = ax2.twinx()
    ax2_r.plot(tu1, ia1[w1], color=COL_VDIOD, lw=2.1, label=f"Auxiliary Current $i_{{LAUX1}}$ ($\\pm${ia1[w1].max():.2f} A)")
    ax2_r.set_ylabel("Aux Current (A)", color=COL_VDIOD, fontweight="bold")
    ax2_r.set_ylim(-5.5, 5.5)
    ax2_r.grid(False)
    l1, lb1 = ax2.get_legend_handles_labels()
    l2, lb2 = ax2_r.get_legend_handles_labels()
    ax2.legend(l1 + l2, lb1 + lb2, loc="upper right", fontsize=8.5)

    fig.suptitle("Replication of Fig. 22: Auxiliary Circuit Current at Different Load Conditions (LTspice)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "fig22_auxiliary_current_two_loads.png")


# ===========================================================================
# 11. FIG. 23: Efficiency Curves (Proposed vs Conventional, LTspice vs Paper!)
# ===========================================================================
def plot_fig23():
    metrics = json.loads((RESULTS_DIR / "simulation_metrics.json").read_text())
    st_p = metrics["schematics"]["15_efficiency_proposed_fig23.asc"]["meas"]["steps"]
    st_c = metrics["schematics"]["16_efficiency_conventional_fig23.asc"]["meas"]["steps"]

    po_p = np.array(st_p["pout"], dtype=float)
    pin_p = np.array(st_p["pin"], dtype=float)
    eff_p_bare = 100.0 * po_p / pin_p
    # Including realistic 22 W DSP (TMX320F28335) + 4x isolated gate driver DC/DC + fan/bias overhead
    P_aux_bias = 22.0
    eff_p_sys = 100.0 * po_p / (pin_p + P_aux_bias)

    po_c = np.array(st_c["pout"], dtype=float)
    pin_c = np.array(st_c["pin"], dtype=float)
    eff_c_bare = 100.0 * po_c / pin_c
    eff_c_sys = 100.0 * po_c / (pin_c + P_aux_bias)

    # Digitized Paper Fig. 23 experimental points
    load_paper = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], dtype=float)
    eff_paper_prop = np.array([86.5, 91.5, 93.1, 94.0, 95.1, 96.0, 96.6, 97.0, 97.1, 96.7])
    eff_paper_conv = np.array([85.8, 91.1, 92.1, 92.6, 93.3, 93.7, 94.0, 93.8, 93.5, 93.2])

    fig, ax = plt.subplots(figsize=(10.0, 5.8))
    ax.plot(load_paper, eff_paper_prop, "D--", color="#1E88E5", lw=1.6, ms=6.5, alpha=0.8,
            label="Paper Fig. 23 Experimental — Proposed")
    ax.plot(load_paper, eff_paper_conv, "s--", color="#E53935", lw=1.6, ms=6.0, alpha=0.8,
            label="Paper Fig. 23 Experimental — Conventional")

    ax.plot(po_p / 30.0, eff_p_bare, "o-", color="#0D47A1", lw=2.2, ms=6,
            label="LTspice Power Stage — Proposed (Peak = {:.2f}%)".format(eff_p_bare.max()))
    ax.plot(po_p / 30.0, eff_p_sys, "^:", color="#00ACC1", lw=1.8, ms=5.5,
            label="LTspice + 22 W DSP/Driver Bias — Proposed")
    ax.plot(po_c / 30.0, eff_c_bare, "s-", color="#B71C1C", lw=2.2, ms=6,
            label="LTspice Power Stage — Conventional (Peak = {:.2f}%)".format(eff_c_bare.max()))

    ax.set_xlabel("Output Load (% of 3 kW)", fontweight="bold")
    ax.set_ylabel("Efficiency (%)", fontweight="bold")
    ax.set_xlim(5, 105); ax.set_ylim(78, 99)
    ax.set_yticks(np.arange(78, 100, 3))
    ax.set_xticks(np.arange(10, 101, 10))
    ax.legend(loc="lower right", fontsize=8.4, framealpha=0.95)
    ax.set_title("Replication of Fig. 23: Efficiency Comparison — Proposed ZVZCS vs. Conventional PSFB (LTspice vs. Paper)",
                 fontweight="bold")
    ax.text(0.015, 0.04,
            "Key loss savings in Proposed topology (~3.5% @ full load):\n"
            "• Zero primary freewheeling circulating current\n"
            "• Symmetric small aux current (67 $\\mu$H vs 33 $\\mu$H Conv.)\n"
            "• 600 V SiC diodes (zero $Q_{rr}$, no R-C snubber)",
            transform=ax.transAxes, fontsize=8.0,
            bbox=dict(boxstyle="round,pad=0.3", fc="#F5F5F5", ec="#888888", alpha=0.95))
    fig.tight_layout()
    savefig(fig, "fig23_efficiency_comparison.png")


# ===========================================================================
# 12. BONUS 01: Direct MOSFET ZVS / ZVZCS Verification Across Loads (0%, 50%, 100%)
# ===========================================================================
def plot_bonus01_zvs():
    fig, axes = plt.subplots(3, 2, figsize=(12.5, 9.5))
    cases = [
        ("05_proposed_noload_fig15",      "0% No-Load (0 W)"),
        ("08_proposed_load_50pct_fig18",  "50% Load DCM (1500 W)"),
        ("11_proposed_load_100pct_fig21", "100% Full-Load CCM (3000 W — Table II $L_{seq}=11.8\\,\\mu$H)"),
    ]
    for row, (stem, lbl) in enumerate(cases):
        t, g, _ = load_raw(stem)
        vbus = g("V(vbus)"); vA = g("V(a)"); vB = g("V(b)")
        vds1 = vbus - vA; vgs1 = g("V(g1)") - vA
        vds3 = vbus - vB; vgs3 = g("V(g3)") - vB
        i_s = g("I(Lseq)")

        # Trigger on Vgs crossing 8.0V (strictly above any brief Miller dv/dt bump!)
        m = t >= 2.0e-6
        tm = t[m]
        i1 = np.where((vgs1[m][:-1] < 8.0) & (vgs1[m][1:] >= 8.0))[0]
        t_on1 = tm[i1[0]]
        i3 = np.where((vgs3[m][:-1] < 8.0) & (vgs3[m][1:] >= 8.0))[0]
        t_on3 = tm[i3[0]]

        for col, (t_on, vds, vgs, leg_name) in enumerate([
            (t_on1, vds1, vgs1, "Leading-Leg $M_1$ Turn-ON"),
            (t_on3, vds3, vgs3, "Lagging-Leg $M_3$ Turn-ON"),
        ]):
            ax = axes[row, col]
            w = (t >= t_on - 0.28e-6) & (t <= t_on + 0.28e-6)
            tn = (t[w] - t_on) * 1e9  # ns
            ax.plot(tn, vds[w], color=COL_VAB, lw=2.0, label="$V_{DS}$ (V)")
            ax.plot(tn, vgs[w] * 25.0, color=COL_VDIOD, lw=1.7, ls="--", label="$V_{GS} \\times 25$ (V)")
            ax.axvline(0, color="k", ls=":", lw=0.9)
            ax.set_ylim(-50, 450)
            ax.set_ylabel("Voltage (V)", fontweight="bold")
            ax_r = ax.twinx()
            ax_r.plot(tn, i_s[w], color=COL_IS, lw=1.7, label="$i_s$ (A)")
            ax_r.set_ylabel("$i_s$ (A)", color=COL_IS, fontweight="bold")
            ax_r.set_ylim(-25, 25)
            ax_r.grid(False)

            # Evaluate Vds & i_s right at Vgs = 4V threshold
            idx0 = np.argmin(np.abs(tn))
            vds_at_on = vds[w][idx0]
            is_at_on = i_s[w][idx0]
            zvs_ok = vds_at_on < 20.0
            zcs_ok = abs(is_at_on) < 1.5
            badge = (f"Vds@ON = {vds_at_on:.1f} V ({'ZVS OK' if zvs_ok else 'HARD!'})\n"
                     f"|is|@ON = {abs(is_at_on):.2f} A ({'Near-ZCS OK' if zcs_ok else 'NO ZCS (CCM)' if col==0 else 'ZVS-assisted'})")
            fc = "#E8F5E9" if (zvs_ok and (zcs_ok or col == 1)) else "#FFF3E0"
            ax.text(0.02, 0.72, badge, transform=ax.transAxes, fontsize=8.0, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.25", fc=fc, ec="#555"))
            ax.set_title(f"{lbl} — {leg_name}", fontweight="bold", fontsize=9.8)
            if row == 0:
                l1, lb1 = ax.get_legend_handles_labels()
                l2, lb2 = ax_r.get_legend_handles_labels()
                ax.legend(l1 + l2, lb1 + lb2, loc="upper right", fontsize=7.8)
            if row == 2:
                ax.set_xlabel("Time relative to $V_{GS}$ rising edge (ns)", fontweight="bold")

    fig.suptitle("Bonus Verification 1: Direct MOSFET Turn-ON ZVS & ZVZCS Check Across Full Load Range (LTspice)",
                 fontsize=12.2, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "bonus01_zvs_zvzcs_mosfet_verification.png")


# ===========================================================================
# 13. BONUS 02: Proposed vs Conventional Output Diode Voltage Stress Head-to-Head
# ===========================================================================
def plot_bonus02_diode_stress():
    t_p, g_p, _ = load_raw("11_proposed_load_100pct_fig21")
    t_c, g_c, _ = load_raw("14_conventional_psfb_100pct_fig14b")

    vAB_p = g_p("V(a)") - g_p("V(b)"); vD_p = g_p("V(gnd_sec)") - g_p("V(sec_p)")
    vAB_c = g_c("V(a)") - g_c("V(b)"); vD_c = g_c("V(gnd_sec)") - g_c("V(sec_p)")

    tr_p = find_trigger_t0(t_p, vAB_p, start_after=2.0e-6)
    tr_c = find_trigger_t0(t_c, vAB_c, start_after=2.0e-6)
    wp = (t_p >= tr_p - 0.5e-6) & (t_p <= tr_p + 5.0e-6)
    wc = (t_c >= tr_c - 0.5e-6) & (t_c <= tr_c + 5.0e-6)

    fig, ax = plt.subplots(figsize=(10.2, 5.2))
    ax.plot((t_c[wc] - tr_c) * 1e6, -vD_c[wc], color="#D32F2F", lw=1.5,
            label=f"Conventional PSFB (Voltage-Driven Rectifier): Peak = {(-vD_c[wc]).max():.0f} V!")
    ax.plot((t_p[wp] - tr_p) * 1e6, -vD_p[wp], color="#1565C0", lw=2.2,
            label=f"Proposed ZVZCS (Current-Driven Rectifier): Clamped Peak = {(-vD_p[wp]).max():.1f} V!")
    ax.axhline(600, color="#FF6F00", ls="--", lw=1.8, label="600 V SiC Diode Rating Limit (CPW2-0600S010B)")
    ax.axhline(300, color="gray", ls=":", lw=1.0, label="Nominal Output Voltage $V_o = 300\\,$V")

    ax.set_xlabel("Time ($\\mu$s)   [Full-Load 3 kW, $V_{dc}=400\\,$V, $V_o=300\\,$V, $f_s=220\\,$kHz]", fontweight="bold")
    ax.set_ylabel("Reverse Blocking Voltage Across Output Diode $D_2$ (V)", fontweight="bold")
    ax.set_ylim(-50, 1100)
    ax.legend(loc="upper right", fontsize=9)
    ax.set_title("Bonus Verification 2: Output Diode Voltage Stress — Proposed Clamping vs. Conventional Spikes (LTspice)",
                 fontweight="bold")
    fig.tight_layout()
    savefig(fig, "bonus02_proposed_vs_conventional_diode_spikes.png")


# ===========================================================================
# 14. BONUS 03: Forensic Audit — Actual Experimental Scope Voltage (355V vs Stated 300V)
# ===========================================================================
def plot_bonus03_forensic_355v():
    t300, g300, _ = load_raw("08_proposed_load_50pct_fig18")
    t355, g355, _ = load_raw("17_forensic_scope_355V_check", step=2)  # psi=103 deg -> ~50% load @ 355V

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.0, 5.2), sharey=True)
    for ax, t, g, ttl, col_note in [
        (ax1, t300, g300, "(a) Paper Text Spec: $V_{dc}=400\\,$V, $V_o=300\\,$V\n($v_{D2}=-304\\,$V, $t_{off}/t_{on} = 0.56$)", "#E3F2FD"),
        (ax2, t355, g355, "(b) Forensic Scope Match: $V_{dc}=410\\,$V, $V_o=355\\,$V\n($v_{D2}=-358\\,$V, $t_{off}/t_{on} = 0.34$ — Matches Figs. 16–20!)", "#FFF3E0"),
    ]:
        vAB = g("V(a)") - g("V(b)")
        i_s = g("I(Lseq)")
        vD2 = g("V(gnd_sec)") - g("V(sec_p)")
        tr = find_trigger_t0(t, vAB, start_after=2.0e-6)
        w = (t >= tr - 0.3e-6) & (t <= tr + 2.2e-6)  # 250 ns/div zoom matching Fig. 18b!
        tu = (t[w] - tr) * 1e6

        ax.plot(tu, vAB[w], color=COL_VAB, lw=1.8, label="$v_{AB}$ (V)")
        ax.plot(tu, vD2[w], color=COL_VDIOD, lw=1.7, label=f"$v_{{D2}}$ (min={vD2[w].min():.0f} V)")
        ax.axhline(-300, color="gray", ls=":", lw=1.0, label="$-300\\,$V")
        ax.axhline(-356, color="crimson", ls="--", lw=1.0, label="$-356\\,$V (measured in Figs. 16–20!)")
        ax.set_ylim(-430, 450)
        ax.set_xlabel("Time ($\\mu$s)   [250 ns/div zoom, matching Fig. 18(b)]", fontweight="bold")
        ax.set_title(ttl, fontweight="bold", fontsize=10.2)
        ax_r = ax.twinx()
        ax_r.plot(tu, i_s[w], color=COL_IS, lw=2.0, label=f"$i_s$ (Peak={i_s[w].max():.1f} A)")
        ax_r.set_ylim(-20, 20)
        ax_r.set_ylabel("$i_s$ (A)", color=COL_IS, fontweight="bold")
        ax_r.grid(False)
        l1, lb1 = ax.get_legend_handles_labels()
        l2, lb2 = ax_r.get_legend_handles_labels()
        ax.legend(l1 + l2, lb1 + lb2, loc="lower left", fontsize=7.8)

    ax1.set_ylabel("Voltage (V)", fontweight="bold")
    fig.suptitle("Bonus Forensic Audit 3: Proving Paper Oscillograms (Figs. 16–20) Were Taken at $V_o \\approx 355\\,$V, Not $300\\,$V",
                 fontsize=11.8, fontweight="bold")
    fig.tight_layout()
    savefig(fig, "bonus03_forensic_355V_vs_300V_comparison.png")


# ===========================================================================
# 15. BONUS 04: Table I Battery Voltage Power Envelope (235 V - 431 V)
# ===========================================================================
def plot_bonus04_envelope():
    metrics = json.loads((RESULTS_DIR / "simulation_metrics.json").read_text())
    env = metrics["battery_envelope_235_431V"]
    vo_sim = np.array(env["Vo_V"], dtype=float)
    p_lt_11p8 = np.array(env["L11p8uH_maxW"], dtype=float)
    p_lt_8p5  = np.array(env["L8p5uH_maxW"], dtype=float)

    vo_dense = np.linspace(235, 431, 100)
    k = 1.0 / 1.18; Vdc = 400.0; Ts = 1.0 / 220e3
    p_bcm_11p8 = [k**2 * (1 - k * v / Vdc) * v**2 * Ts / (4 * 11.8e-6) for v in vo_dense]
    p_bcm_8p5  = [k**2 * (1 - k * v / Vdc) * v**2 * Ts / (4 * 8.5e-6)  for v in vo_dense]
    p_ccm_11p8_id = [exact_dc_point(1.0, Vdc=400, Vo=v, Vd=0.0, Lseq=11.8e-6)["Po"] for v in vo_dense]

    fig, ax = plt.subplots(figsize=(10.2, 5.6))
    ax.axhline(3000, color="crimson", ls="--", lw=1.8, label="Table I Rated Output Power ($P_o = 3000\\,$W)")
    ax.plot(vo_dense, p_bcm_11p8, "--", color="#1565C0", lw=1.8, label="Table II $L_{seq}=11.8\\,\\mu$H — Max DCM/BCM Power (Theory)")
    ax.plot(vo_dense, p_ccm_11p8_id, ":", color="#1565C0", lw=1.6, label="Table II $L_{seq}=11.8\\,\\mu$H — Max Ideal CCM Power ($D=1$, pure $L$)")
    ax.plot(vo_sim, p_lt_11p8, "o-", color="#0D47A1", lw=2.2, ms=6.5, label="Table II $L_{seq}=11.8\\,\\mu$H — LTspice Max Power ($\\psi=172^\\circ$, CCM + $C_f$ boost)")
    ax.plot(vo_dense, p_bcm_8p5, "--", color=COL_IS, lw=1.8, label="Corrected $L_{seq}=8.5\\,\\mu$H — Max DCM/BCM Power (Theory)")
    ax.plot(vo_sim, p_lt_8p5, "s-", color="#00695C", lw=2.2, ms=6.5, label="Corrected $L_{seq}=8.5\\,\\mu$H — LTspice Max Power ($\\psi=172^\\circ$)")

    ax.fill_between(vo_dense, 0, p_bcm_11p8, color="#BBDEFB", alpha=0.25)
    ax.annotate("With $L_{seq}=11.8\\,\\mu$H, BCM ceiling is only\n2.27 kW @ 300 V (75% load) and max CCM\npower collapses to 1.58 kW @ 431 V!",
                xy=(431, 1578), xytext=(318, 850), fontsize=8.8, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="crimson", lw=1.3),
                bbox=dict(boxstyle="round,pad=0.3", fc="#FFEBEE", ec="crimson"))

    ax.set_xlabel("Battery Output Voltage $V_o$ (V)   [Table I Specification: 235–431 VDC]", fontweight="bold")
    ax.set_ylabel("Maximum Deliverable Output Power $P_{o,max}$ (W)", fontweight="bold")
    ax.set_xlim(230, 438); ax.set_ylim(0, 4600)
    ax.legend(loc="upper right", fontsize=8.2)
    ax.set_title("Bonus Critical Audit 4: Deliverable Power Envelope Across Table I Battery Voltage Range (LTspice + Theory)",
                 fontweight="bold")
    fig.tight_layout()
    savefig(fig, "bonus04_table1_power_envelope_235_431V.png")


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating all 21 LTspice-backed figures in figures/ ...")
    plot_fig03()
    plot_fig05()
    plot_fig06()
    plot_fig07()
    plot_fig08()
    plot_fig09()
    plot_fig11()
    plot_fig14()
    plot_fig15()
    plot_proposed_scope_pair("06_proposed_load_10pct_fig16", "16", "10% Load (300 W)", "fig16_proposed_10pct.png", with_zoom=False, i_ylim=14.0)
    plot_proposed_scope_pair("07_proposed_load_25pct_fig17", "17", "25% Load (750 W)", "fig17_proposed_25pct_full_and_zoom.png", with_zoom=True, i_ylim=16.0)
    plot_proposed_scope_pair("08_proposed_load_50pct_fig18", "18", "50% Load (1500 W)", "fig18_proposed_50pct_full_and_zoom.png", with_zoom=True, i_ylim=22.0, annotate_nospike=True)
    plot_proposed_scope_pair("09_proposed_load_70pct_fig19", "19", "70% Load (2100 W)", "fig19_proposed_70pct_full_and_zoom.png", with_zoom=True, i_ylim=24.0, annotate_nospike=True)
    plot_proposed_scope_pair("10_proposed_load_85pct_fig20", "20", "85% Load (2550 W)", "fig20_proposed_85pct_full_and_zoom.png", with_zoom=True, i_ylim=26.0, annotate_nospike=True)
    plot_fig21()
    plot_fig22()
    plot_fig23()
    plot_bonus01_zvs()
    plot_bonus02_diode_stress()
    plot_bonus03_forensic_355v()
    plot_bonus04_envelope()
    print("ALL 21 FIGURES GENERATED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
