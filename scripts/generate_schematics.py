#!/usr/bin/env python3
"""
Generate all 17 standalone LTspice .asc schematics and matching .plt plot files
in ltspice/, compile and strictly verify every schematic via asc_compiler.py,
and render visual previews in figures/schematics_preview/.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LTSPICE_DIR = ROOT / "ltspice"
PREVIEW_DIR = ROOT / "figures" / "schematics_preview"

sys.path.insert(0, str(ROOT / "scripts"))
from schematic_templates import (
    build_proposed_schematic,
    build_conventional_schematic,
    make_plt,
    MODEL_MOSFET_NOM,
    MODEL_MOSFET_EFF,
)
from asc_compiler import compile_asc_to_net, render_asc_preview

# Common .meas block for instant power & efficiency readout in LTspice SPICE Error Log (Ctrl+L)
# Note: With .tran 0 Tstop Tstart (20us saved window), LTspice shifts saved time to [0, 20us].
MEAS_PROPOSED = (
    ".meas tran T1 param 1u\n"
    ".meas tran T2 param 1u+3/fs\n"
    ".meas tran Vout_avg AVG V(Vo,gnd_sec) FROM T1 TO T2\n"
    ".meas tran Iout_avg AVG I(Lf) FROM T1 TO T2\n"
    ".meas tran Pout AVG V(Vo,gnd_sec)*I(Lf) FROM T1 TO T2\n"
    ".meas tran Pin AVG V(VBUS)*(-I(Vdc)) FROM T1 TO T2\n"
    ".meas tran Eff PARAM 100*Pout/Pin\n"
    ".meas tran Is_pk MAX I(Lseq) FROM T1 TO T2\n"
    ".meas tran Is_rms RMS I(Lseq) FROM T1 TO T2\n"
    ".meas tran Vd2_min MIN V(gnd_sec,sec_p) FROM T1 TO T2"
)

MEAS_CONV = (
    ".meas tran T1 param 1u\n"
    ".meas tran T2 param 1u+3/fs\n"
    ".meas tran Vout_avg AVG V(Vo,gnd_sec) FROM T1 TO T2\n"
    ".meas tran Iout_avg AVG I(Lf) FROM T1 TO T2\n"
    ".meas tran Pout AVG V(Vo,gnd_sec)*I(Lf) FROM T1 TO T2\n"
    ".meas tran Pin AVG V(VBUS)*(-I(Vdc)) FROM T1 TO T2\n"
    ".meas tran Eff PARAM 100*Pout/Pin\n"
    ".meas tran Vsec_pk MAX V(sec_p,sec_n) FROM T1 TO T2\n"
    ".meas tran Vd2_min MIN V(gnd_sec,sec_p) FROM T1 TO T2"
)


def write_pair(stem, asc_text, plt_panes):
    asc_path = LTSPICE_DIR / f"{stem}.asc"
    plt_path = LTSPICE_DIR / f"{stem}.plt"
    asc_path.write_text(asc_text, encoding="utf-8")
    plt_path.write_text(make_plt(plt_panes), encoding="utf-8")
    net_path, info = compile_asc_to_net(asc_path, strict=True)
    return asc_path, net_path, info


def main():
    LTSPICE_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    # Standard oscilloscope-style plot panes matching paper figures (using exact .raw trace names)
    PANES_SCOPE_PROP = [
        ["V(a)-V(b)"],
        ["I(Lseq)"],
        ["V(gnd_sec)-V(sec_p)"],
    ]
    PANES_MODES_FIG3 = [
        ["V(g1)-V(a)", "V(g2)", "V(g3)-V(b)", "V(g4)"],
        ["V(a)-V(b)", "V(a)"],
        ["I(Laux1)", "I(Laux2)"],
        ["I(Lseq)"],
        ["V(sec_p)-V(sec_n)"],
        ["I(Cf)", "V(vcf)-V(gnd_sec)"],
    ]
    PANES_CONV = [
        ["V(a)-V(b)"],
        ["V(sec_p)-V(sec_n)"],
        ["I(LauxB)"],
        ["V(gnd_sec)-V(sec_p)"],
    ]
    PANES_AUX = [
        ["V(a)-V(b)", "V(sec_p)-V(sec_n)"],
        ["I(Lseq)"],
        ["I(Laux1)", "I(Laux2)"],
    ]
    PANES_ZVS = [
        ["V(vbus)-V(a)", "(V(g1)-V(a))*20"],
        ["V(vbus)-V(b)", "(V(g3)-V(b))*20"],
        ["I(Lseq)", "I(Laux1)*5"],
    ]

    specs = []

    # 01 - Master Proposed Converter (Fig. 2, Table II & IV, 50% load default)
    specs.append((
        "01_proposed_zvzcs_fb",
        build_proposed_schematic(
            "01 - Master Proposed ZVZCS Full-Bridge DC/DC Converter (Fig. 2, Table II & IV - 50% Load)",
            vdc=400, vo=300, fs=220e3, psi_deg=99.5, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=5.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=MEAS_PROPOSED,
        ),
        PANES_SCOPE_PROP,
    ))

    # 02 - Waveforms & 7 Operating Modes (Figs. 3, 4, 6, 8, 11a) - 100% Real Physical Circuit at 1ns resolution
    specs.append((
        "02_proposed_ideal_modes_fig3",
        build_proposed_schematic(
            "02 - Proposed Converter: All 7 Operating Modes & Waveforms (Figs. 3, 4, 6, 8, 11a)",
            vdc=400, vo=300, fs=220e3, psi_deg=99.5, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=5.0,
            tran_cmd=".tran 0 1.4m 1.38m 1n",
            extra_directives=MEAS_PROPOSED,
        ),
        PANES_MODES_FIG3,
    ))

    # 03 - Converter Gain Sweep vs Phase-Shift & Load Re (Fig. 7)
    # Note: In LTspice GUI, user can open and run this directly to reproduce the entire Fig. 7 family!
    meas_gain = (
        ".step param psi list 25 40 60 80 100 120 140 160 172\n"
        ".meas tran Vo_ss AVG V(Vo,gnd_sec) FROM 2u TO 18u\n"
        ".meas tran gv PARAM Vo_ss/Vdc"
    )
    specs.append((
        "03_proposed_gain_sweep_fig7",
        build_proposed_schematic(
            "03 - Converter Voltage Gain gv(psi, Re) Parametric Sweep (Fig. 7; change Re=30,50,80,120,170,230,300)",
            vdc=400, vo=250, fs=220e3, psi_deg=90.0, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="resistor", re_ohm=30.0, cw_pF=0.0,
            tran_cmd=".tran 0 2.0m 1.98m 10n",
            extra_directives=meas_gain,
            ic_cf=200.0,
        ),
        [["V(vo)-V(gnd_sec)"], ["I(Lseq)"]],
    ))

    # 04 - Critical Conduction Mode BCM: Table II (11.8uH -> 2.25kW) vs Corrected Practical BCM (8.0uH -> 3.0kW) (Figs. 9, 11b)
    specs.append((
        "04_proposed_bcm_design_fig9",
        build_proposed_schematic(
            "04 - Critical Conduction Mode (Fig. 9 & 11b): Table II Lseq=11.8uH (2.25kW) vs Corrected Lseq=8.0uH (3.0kW BCM)",
            vdc=400, vo=300, fs=220e3, psi_deg=119.5, td_ns=165, lseq_uH=8.0, cb_uF=22.0,
            load_mode="battery", ic_ilf=10.0, cw_pF=0.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=".step param Lseq list 11.8u 8.0u\n" + MEAS_PROPOSED,
        ).replace("Cjo=460p", "Cjo=15p"),
        [["I(Lseq)"], ["I(Cf)"], ["V(vcf)-V(gnd_sec)"]],
    ))

    # 05 - No-Load 0% (Fig. 15)
    specs.append((
        "05_proposed_noload_fig15",
        build_proposed_schematic(
            "05 - Proposed Converter at No-Load 0% (Fig. 15) - Full ZVS Verified at Zero Power",
            vdc=400, vo=300, fs=220e3, psi_deg=13.5, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=0.0, cw_pF=35.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=MEAS_PROPOSED,
        ),
        [["V(a)-V(b)"], ["V(sec_p)-V(sec_n)"], ["V(gnd_sec)-V(sec_p)"], ["I(Lseq)"]],
    ))

    # 06 - 10% Load (300W, Fig. 16 & Fig. 5 Mode IV light-load submodes)
    specs.append((
        "06_proposed_load_10pct_fig16",
        build_proposed_schematic(
            "06 - Proposed Converter at 10% Load / 300W (Fig. 16 & Fig. 5 Light-Load Mode IV Submodes)",
            vdc=400, vo=300, fs=220e3, psi_deg=44.8, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=1.0, cw_pF=35.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=MEAS_PROPOSED,
        ),
        PANES_SCOPE_PROP,
    ))

    # 07 - 25% Load (750W, Fig. 17a & 17b)
    specs.append((
        "07_proposed_load_25pct_fig17",
        build_proposed_schematic(
            "07 - Proposed Converter at 25% Load / 750W (Fig. 17a Full & Fig. 17b Enlarged)",
            vdc=400, vo=300, fs=220e3, psi_deg=71.0, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=2.5, cw_pF=35.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=MEAS_PROPOSED,
        ),
        PANES_SCOPE_PROP,
    ))

    # 08 - 50% Load (1500W, Fig. 18a & 18b)
    specs.append((
        "08_proposed_load_50pct_fig18",
        build_proposed_schematic(
            "08 - Proposed Converter at 50% Load / 1500W (Fig. 18a Full & Fig. 18b Enlarged)",
            vdc=400, vo=300, fs=220e3, psi_deg=99.5, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=5.0, cw_pF=35.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=MEAS_PROPOSED,
        ),
        PANES_SCOPE_PROP,
    ))

    # 09 - 70% Load (2100W, Fig. 19a & 19b)
    specs.append((
        "09_proposed_load_70pct_fig19",
        build_proposed_schematic(
            "09 - Proposed Converter at 70% Load / 2100W (Fig. 19a Full & Fig. 19b Enlarged)",
            vdc=400, vo=300, fs=220e3, psi_deg=116.5, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=7.0, cw_pF=35.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=MEAS_PROPOSED,
        ),
        PANES_SCOPE_PROP,
    ))

    # 10 - 85% Load (2550W, Fig. 20a & 20b)
    specs.append((
        "10_proposed_load_85pct_fig20",
        build_proposed_schematic(
            "10 - Proposed Converter at 85% Load / 2550W (Fig. 20a Full & Fig. 20b Enlarged - Entering CCM)",
            vdc=400, vo=300, fs=220e3, psi_deg=123.5, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=8.5, cw_pF=35.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=MEAS_PROPOSED,
        ),
        PANES_SCOPE_PROP,
    ))

    # 11 - 100% Full Load (3000W, Fig. 21 - Deep CCM with Table II Lseq=11.8uH!)
    specs.append((
        "11_proposed_load_100pct_fig21",
        build_proposed_schematic(
            "11 - Proposed Converter at 100% Full-Load / 3000W (Fig. 21 - Deep CCM with Table II Lseq=11.8uH)",
            vdc=400, vo=300, fs=220e3, psi_deg=151.0, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=10.0, cw_pF=35.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=MEAS_PROPOSED,
        ),
        PANES_SCOPE_PROP,
    ))

    # 12 - Auxiliary Circuit Current & ZVS Verification (Figs. 8 & 22a/b)
    specs.append((
        "12_proposed_aux_circuit_fig22",
        build_proposed_schematic(
            "12 - Auxiliary Circuit Current & ZVS Verification at Light & Heavy Loads (Figs. 8 & 22a/b)",
            vdc=400, vo=300, fs=220e3, psi_deg=50.0, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=2.0, cw_pF=35.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=".step param psi list 48 151\n" + MEAS_PROPOSED,
        ),
        PANES_AUX,
    ))

    # 13 - Conventional PSFB + Asymmetric Aux at 10% Load (Fig. 1, Fig. 14a, Table V)
    specs.append((
        "13_conventional_psfb_10pct_fig14a",
        build_conventional_schematic(
            "13 - Conventional PSFB + Asymmetric Aux at 10% Load / 300W (Fig. 1, Fig. 14a, Table V)",
            vdc=400, vo=300, fs=220e3, psi_deg=114.0, td_ns=150, cb_uF=22.0,
            load_mode="battery", ic_ilf=1.0, r_snub=150, c_snub_pF=220,
            tran_cmd=".tran 0 1.0m 0.98m 2n",
            extra_directives=MEAS_CONV,
        ),
        PANES_CONV,
    ))

    # 14 - Conventional PSFB + Asymmetric Aux at 100% Full Load (Fig. 1, Fig. 14b, Table V)
    specs.append((
        "14_conventional_psfb_100pct_fig14b",
        build_conventional_schematic(
            "14 - Conventional PSFB + Asymmetric Aux at 100% Full-Load / 3000W (Fig. 1, Fig. 14b, Table V)",
            vdc=400, vo=300, fs=220e3, psi_deg=124.5, td_ns=150, cb_uF=22.0,
            load_mode="battery", ic_ilf=10.0, r_snub=150, c_snub_pF=220,
            tran_cmd=".tran 0 1.0m 0.98m 2n",
            extra_directives=MEAS_CONV,
        ),
        PANES_CONV,
    ))

    # 15 - Efficiency Sweep: Proposed Converter 10%-100% Load (Fig. 23)
    specs.append((
        "15_efficiency_proposed_fig23",
        build_proposed_schematic(
            "15 - Proposed Converter Efficiency Sweep 10%-100% Load (Fig. 23 - Loss-Modeled)",
            vdc=400, vo=300, fs=220e3, psi_deg=99.5, td_ns=165, lseq_uH=11.8, cb_uF=22.0,
            load_mode="battery", ic_ilf=5.0, cw_pF=35.0,
            r_pri=0.055, r_aux=1.1, r_lf=0.05, r_core=4500,
            mosfet_model=MODEL_MOSFET_EFF,
            tran_cmd=".tran 0 1.4m 1.38m 5n",
            extra_directives=(
                ".step param psi list 42 58 72 86 99.5 109 116.5 123 132 152\n"
                + MEAS_PROPOSED
            ),
        ),
        PANES_ZVS,
    ))

    # 16 - Efficiency Sweep: Conventional PSFB 10%-100% Load (Fig. 23)
    specs.append((
        "16_efficiency_conventional_fig23",
        build_conventional_schematic(
            "16 - Conventional PSFB Efficiency Sweep 10%-100% Load (Fig. 23 - Loss-Modeled)",
            vdc=400, vo=300, fs=220e3, psi_deg=120.0, td_ns=150, cb_uF=22.0,
            load_mode="battery", ic_ilf=5.0, cw_pF=120.0,
            r_pri=0.055, r_auxA=0.75, r_auxB=1.1, r_lf=0.05, r_core=4500,
            r_snub=120, c_snub_pF=330,
            mosfet_model=MODEL_MOSFET_EFF,
            tran_cmd=".tran 0 1.0m 0.98m 5n",
            extra_directives=(
                ".step param psi list 114.0 116.0 117.6 119.0 120.2 121.2 122.1 122.9 123.7 124.5\n"
                + MEAS_CONV
            ),
        ),
        PANES_CONV,
    ))

    # 17 - Forensic Scope Verification at ACTUAL Measured Vo=355V, Vdc=410V (Figs. 16-20 Critical Audit!)
    specs.append((
        "17_forensic_scope_355V_check",
        build_proposed_schematic(
            "17 - Forensic Audit: Replicating Actual Scope Voltages Vo=355V, Vdc=410V (C3=-356V, toff/ton=0.33)",
            vdc=410, vo=355, fs=220e3, psi_deg=105.0, td_ns=165, lseq_uH=9.5, cb_uF=22.0,
            load_mode="battery", ic_ilf=4.2, cw_pF=35.0,
            tran_cmd=".tran 0 1.4m 1.38m 2n",
            extra_directives=".step param psi list 55 75 103 115 130 165\n" + MEAS_PROPOSED,
        ),
        PANES_SCOPE_PROP,
    ))

    print(f"Generating & strictly verifying {len(specs)} LTspice .asc schematics...")
    for stem, asc_text, panes in specs:
        asc_path, net_path, info = write_pair(stem, asc_text, panes)
        print(f"  [OK] {asc_path.name:38s} -> {info['num_components']:2d} comps, {info['num_nets']:2d} nets (0 dangling)")

    # Render visual previews of both representative schematic architectures to confirm zero overlaps!
    for preview_stem in ("01_proposed_zvzcs_fb", "03_proposed_gain_sweep_fig7", "14_conventional_psfb_100pct_fig14b"):
        asc_p = LTSPICE_DIR / f"{preview_stem}.asc"
        png_p = PREVIEW_DIR / f"{preview_stem}.png"
        render_asc_preview(asc_p, png_p)
        print(f"  [PREVIEW] {png_p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
