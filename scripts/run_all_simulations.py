#!/usr/bin/env python3
"""
Compile all 17 LTspice .asc schematics -> .net, execute every simulation in
native macOS LTspice batch mode, parse all .meas logs & waveforms, and also
run the full 2D (7 Re x 12 psi) Fig. 7 gain sweep and Table I (235-431V) power
envelope sweep in LTspice.

Saves all numerical metrics to results/simulation_metrics.json.
"""

import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import numpy as np
from spicelib import RawRead

ROOT = Path(__file__).resolve().parent.parent
LTSPICE_DIR = ROOT / "ltspice"
RESULTS_DIR = ROOT / "results"
LTSPICE_BIN = "/Applications/LTspice.app/Contents/MacOS/LTspice"

sys.path.insert(0, str(ROOT / "scripts"))
from asc_compiler import compile_asc_to_net
from schematic_templates import build_proposed_schematic


def read_ltspice_log(log_path):
    raw_bytes = Path(log_path).read_bytes()
    # macOS LTspice 17.2 writes UTF-16LE (often without BOM)
    if b"\x00" in raw_bytes[:200]:
        return raw_bytes.decode("utf-16-le", errors="ignore")
    return raw_bytes.decode("utf-8", errors="ignore")


def parse_meas_from_log(log_text):
    """Parse both single-run and .step multi-run .meas results from an LTspice .log file."""
    results = {}
    # Single-run pattern: "name: expr=VALUE ..."
    for m in re.finditer(r"^([a-zA-Z0-9_]+):\s+[^\n]*?=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", log_text, re.M):
        name, val = m.group(1).lower(), float(m.group(2))
        results[name] = val

    # Stepped table pattern:
    # Measurement: pout
    #   step    AVG(...)   FROM   TO
    #      1    310.2      ...
    step_tables = {}
    blocks = re.split(r"Measurement:\s+", log_text)
    for blk in blocks[1:]:
        lines = [ln.strip() for ln in blk.splitlines() if ln.strip()]
        if not lines:
            continue
        mname = lines[0].lower()
        rows = []
        for ln in lines[2:]:
            if ln.startswith(("Direct ", "Total ", "Date:", "Measurement:", "Heightened")):
                break
            toks = ln.split()
            if len(toks) >= 2 and toks[0].isdigit():
                try:
                    rows.append((int(toks[0]), float(toks[1])))
                except ValueError:
                    pass
        if rows:
            step_tables[mname] = [v for _, v in rows]
    if step_tables:
        results["steps"] = step_tables
    return results


def run_one_asc(asc_path):
    t0 = time.time()
    net_path, info = compile_asc_to_net(asc_path, strict=True)
    proc = subprocess.run(
        [LTSPICE_BIN, "-b", str(net_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    elapsed = time.time() - t0
    if proc.returncode != 0:
        raise RuntimeError(f"LTspice failed on {asc_path.name} (rc={proc.returncode})")
    log_path = net_path.with_suffix(".log")
    log_txt = read_ltspice_log(log_path)
    meas = parse_meas_from_log(log_txt)
    return {
        "file": asc_path.name,
        "elapsed_s": round(elapsed, 2),
        "components": info["num_components"],
        "nets": info["num_nets"],
        "meas": meas,
    }


def run_fig07_full_2d_sweep():
    """Run all 7 Re curves x 12 psi values in LTspice for exact Fig. 7 verification."""
    print("\nRunning full 2D LTspice sweep for Fig. 7 (7 loads x 12 phase-shifts = 84 points)...")
    scratch = ROOT / "results" / "_tmp_sweeps"
    scratch.mkdir(parents=True, exist_ok=True)
    re_list = [30, 50, 80, 120, 170, 230, 300]
    psi_list = [18, 25, 35, 45, 60, 75, 90, 105, 120, 140, 160, 172]

    def run_re(re_val):
        asc = scratch / f"fig07_re_{re_val}.asc"
        psi_str = " ".join(str(p) for p in psi_list)
        # Note: use smaller Cout=4.7uF so RC settling time tau = Re*Cout <= 300*4.7u = 1.4ms => settled by 4.5ms!
        txt = build_proposed_schematic(
            f"Fig7 Re={re_val}",
            vdc=400, vo=300, fs=220e3, psi_deg=90.0, td_ns=165,
            lseq_uH=11.8, cb_uF=10.0, cf_uF=1.0, lf_uH=40.0,
            load_mode="resistor", re_ohm=re_val, cw_pF=0.0,
            r_pri=0.01, r_aux=0.05, r_lf=0.01,
            tran_cmd=".tran 0 4.5m 4.46m 25n",
            extra_directives=(
                f".step param psi list {psi_str}\n"
                ".meas tran Vo_ss AVG V(Vo,gnd_sec) FROM 5u TO 35u\n"
                ".meas tran gv PARAM Vo_ss/Vdc"
            ),
            ic_cf=250.0,
        )
        # Reduce Cout from 47u to 4.7u for fast exact settling across Re=30..300 ohm
        txt = txt.replace("SYMATTR Value 47u", "SYMATTR Value 4.7u")
        asc.write_text(txt, encoding="utf-8")
        net, _ = compile_asc_to_net(asc, strict=True)
        subprocess.run([LTSPICE_BIN, "-b", str(net)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_txt = read_ltspice_log(net.with_suffix(".log"))
        meas = parse_meas_from_log(log_txt)
        gvs = meas.get("steps", {}).get("gv", [])
        return re_val, gvs

    out = {"psi_deg": psi_list, "Re_curves": {}}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(run_re, r) for r in re_list]
        for f in as_completed(futs):
            re_val, gvs = f.result()
            out["Re_curves"][str(re_val)] = [round(v, 4) for v in gvs]
            print(f"  [Fig.7] Re={re_val:3d} Ohm -> {len(gvs)} points (gv_min={min(gvs):.3f}, gv_max={max(gvs):.3f})")

    # Cleanup temp files
    for p in scratch.glob("*"):
        p.unlink()
    scratch.rmdir()
    return out


def run_battery_envelope_sweep():
    """Verify max deliverable power across Table I Vo=235..431V in LTspice for Lseq=11.8uH vs 8.5uH."""
    print("\nRunning Table I battery voltage power-envelope verification (235V - 431V) in LTspice...")
    scratch = ROOT / "results" / "_tmp_env"
    scratch.mkdir(parents=True, exist_ok=True)
    vo_list = [235, 270, 300, 330, 355, 380, 400, 431]
    res = {"Vo_V": vo_list, "L11p8uH_maxW": [], "L8p5uH_maxW": []}

    for l_val, key in [(11.8, "L11p8uH_maxW"), (8.5, "L8p5uH_maxW")]:
        asc = scratch / f"env_{l_val}.asc"
        vo_str = " ".join(str(v) for v in vo_list)
        txt = build_proposed_schematic(
            f"Envelope Lseq={l_val}uH",
            vdc=400, vo=300, fs=220e3, psi_deg=172.0, td_ns=165,
            lseq_uH=l_val, cb_uF=22.0, load_mode="battery",
            cw_pF=0.0, tran_cmd=".tran 0 700u 680u 5n",
            extra_directives=(
                f".step param Vo list {vo_str}\n"
                ".meas tran Pout AVG V(Vo,gnd_sec)*I(Lf) FROM 2u TO 15.636u"
            ),
            ic_cf="{Vo}",
        )
        asc.write_text(txt, encoding="utf-8")
        net, _ = compile_asc_to_net(asc, strict=True)
        subprocess.run([LTSPICE_BIN, "-b", str(net)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_txt = read_ltspice_log(net.with_suffix(".log"))
        meas = parse_meas_from_log(log_txt)
        pouts = [round(v, 1) for v in meas.get("steps", {}).get("pout", [])]
        res[key] = pouts
        print(f"  [Envelope Lseq={l_val}uH] Po_max(235..431V) = {pouts}")

    for p in scratch.glob("*"):
        p.unlink()
    scratch.rmdir()
    return res


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    asc_files = sorted(LTSPICE_DIR.glob("*.asc"))
    print(f"Running all {len(asc_files)} LTspice schematics in parallel batch mode...")

    summary = {"schematics": {}}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(run_one_asc, p): p for p in asc_files}
        for f in as_completed(futs):
            r = f.result()
            summary["schematics"][r["file"]] = r
            m = r["meas"]
            if "steps" in m:
                n_steps = len(next(iter(m["steps"].values())))
                pouts = m["steps"].get("pout")
                effs = m["steps"].get("eff")
                extra = ""
                if pouts and effs:
                    extra = f" | Po=[{min(pouts):.0f}..{max(pouts):.0f}]W, Eff=[{min(effs):.1f}..{max(effs):.1f}]%"
                elif "gv" in m["steps"]:
                    gvs = m["steps"]["gv"]
                    extra = f" | gv=[{min(gvs):.3f}..{max(gvs):.3f}]"
                print(f"  [DONE] {r['file']:38s} ({r['elapsed_s']:5.2f}s, {n_steps} steps){extra}")
            else:
                po = m.get("pout", float("nan"))
                eff = m.get("eff", float("nan"))
                ispk = m.get("is_pk", float("nan"))
                vd2 = m.get("vd2_min", float("nan"))
                vsec = m.get("vsec_pk", float("nan"))
                print(f"  [DONE] {r['file']:38s} ({r['elapsed_s']:5.2f}s) | Po={po:6.1f}W, Eff={eff:5.2f}%, Is_pk={ispk:5.2f}A, Vd2_min={vd2:6.1f}V, Vsec_pk={vsec:6.1f}V")

    # Sort keys nicely
    summary["schematics"] = dict(sorted(summary["schematics"].items()))
    out_json = RESULTS_DIR / "simulation_metrics.json"
    if "--skip-sweeps" in sys.argv and out_json.exists():
        prev = json.loads(out_json.read_text(encoding="utf-8"))
        summary["fig07_2d_sweep"] = prev["fig07_2d_sweep"]
        summary["battery_envelope_235_431V"] = prev["battery_envelope_235_431V"]
    else:
        summary["fig07_2d_sweep"] = run_fig07_full_2d_sweep()
        summary["battery_envelope_235_431V"] = run_battery_envelope_sweep()

    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSaved complete simulation metrics -> {out_json}")


if __name__ == "__main__":
    main()
