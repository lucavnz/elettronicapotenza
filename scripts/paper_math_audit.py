#!/usr/bin/env python3
"""
Comprehensive Mathematical & Experimental Audit of:
  M. Pahlevaninezhad et al., "A Novel ZVZCS Full-Bridge DC/DC Converter Used
  for Electric Vehicles," IEEE Trans. Power Electron., Vol. 27, No. 6,
  June 2012, pp. 2752-2769 (35.pdf).

Verifies every analytical equation (1)-(32), Tables I-V, Fig. 7 conversion
ratio, BCM/CCM power delivery envelope across 235-431V, and oscilloscope
inconsistencies in Figs. 14-23.
"""

import numpy as np
from pathlib import Path

OUT_FILE = Path(__file__).resolve().parent.parent / "results" / "paper_audit_verification.txt"


def exact_dc_point(D, Vdc=400.0, Vo=300.0, Vd=1.5, Lseq=11.8e-6, k=1.0/1.18, fs=220e3):
    """Exact piecewise-linear steady-state DCM + CCM solver for the Proposed Converter."""
    Ts = 1.0 / fs
    ton = D * Ts / 2.0
    tzero = (1.0 - D) * Ts / 2.0
    Vref = k * (Vo + 2.0 * Vd)
    if Vdc <= Vref:
        return dict(mode="OFF", ton=ton, toff=0.0, Ip=0.0, I0=0.0, Iavg=0.0, Irms=0.0, Po=0.0, tz=0.0)
    m1 = (Vdc + Vref) / Lseq
    m2 = (Vdc - Vref) / Lseq
    m3 = -Vref / Lseq
    toff_dcm = ton * (Vdc - Vref) / Vref
    if ton + toff_dcm <= Ts / 2.0:
        Ip = m2 * ton
        Iavg = 0.5 * Ip * (ton + toff_dcm) / (Ts / 2.0)
        Irms = Ip * np.sqrt((ton + toff_dcm) / (3.0 * Ts / 2.0))
        Po = k * Vo * Iavg
        return dict(mode="DCM", ton=ton, toff=toff_dcm, Ip=Ip, I0=0.0, Iavg=Iavg, Irms=Irms, Po=Po, tz=0.0)
    else:
        I0 = (m2 * ton + m3 * tzero) / (1.0 + m2 / m1)
        tz = I0 / m1
        Ip = m2 * (ton - tz)
        area = 0.5 * I0 * tz + 0.5 * Ip * (ton - tz) + 0.5 * (Ip + I0) * tzero
        Iavg = area / (Ts / 2.0)
        Irms = np.sqrt((I0**2 * tz + Ip**2 * (ton - tz) + (Ip**2 + Ip * I0 + I0**2) * tzero) / (3.0 * Ts / 2.0))
        Po = k * Vo * Iavg
        return dict(mode="CCM", ton=ton, toff=tzero, Ip=Ip, I0=I0, Iavg=Iavg, Irms=Irms, Po=Po, tz=tz)


def exact_gv_vs_psi(psi_deg, Re, Vdc=400.0, Vd=0.0, Lseq=11.8e-6, k=1.0/1.18, fs=220e3, td=0.0):
    """Exact steady-state voltage gain gv = Vo / Vdc (handles BOTH DCM and CCM!)."""
    Ts = 1.0 / fs
    ton = max((psi_deg / 360.0) * Ts - td, 0.0)
    D = min(ton / (Ts / 2.0), 1.0)
    if D <= 1e-6:
        return 0.0, "OFF"
    # Solve Po(Vo) = Vo^2 / Re by bisection on Vo in (0, Vdc/k - 2Vd)
    lo, hi = 1e-4, Vdc / k - 2.0 * Vd - 1e-4
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        r = exact_dc_point(D, Vdc=Vdc, Vo=mid, Vd=Vd, Lseq=Lseq, k=k, fs=fs)
        if r["Po"] > mid**2 / Re:
            lo = mid
        else:
            hi = mid
    Vo_sol = 0.5 * (lo + hi)
    r = exact_dc_point(D, Vdc=Vdc, Vo=Vo_sol, Vd=Vd, Lseq=Lseq, k=k, fs=fs)
    return Vo_sol / Vdc, r["mode"]


def main():
    lines = []
    p = lines.append

    Vdc = 400.0
    Vo = 300.0
    Vd = 1.5
    Po_max = 3000.0
    fs = 220e3
    Ts = 1.0 / fs
    k = 1.0 / 1.18
    Lseq = 11.8e-6
    Laux = 67e-6
    Cf = 1e-6
    LM = 1500e-6
    Cso = 650e-12  # Realistic STW77N65M5 + CPW2-0600S010B + Cs effective capacitance

    p("=" * 84)
    p("VERIFICA ANALITICA E AUDIT CRITICO DI 35.pdf (Pahlevaninezhad et al., IEEE TPEL 2012)")
    p("=" * 84)

    # 1. Mode I-II Equations (1)-(11)
    IPA = Vdc / (8.0 * Laux * fs)
    t1 = 2.0 * k * (Vo + 2 * Vd) * (Lseq + LM) * Cso / (LM * IPA)
    t2 = 2.0 * Vdc * Cso / IPA
    is_t1 = IPA / (4.0 * (Lseq + LM) * Cso) * t1**2
    is_eq8_t2 = IPA / (4.0 * Lseq * Cso) * (t2 - t1)**2 - k * (Vo + 2 * Vd) / Lseq * (t2 - t1)
    is_true_t2 = is_t1 + IPA / (4.0 * Lseq * Cso) * (t2 - t1)**2
    p("\n[1] EQUAZIONI MODO I - III: Eqs. (4)-(11)")
    p(f"  IPA (Eq.20) = {IPA:.3f} A, I_LAUX_rms = {IPA/np.sqrt(3):.3f} A (Table II: 2A rms -> OK)")
    p(f"  Con Cso=650pF, LM=1.5mH: t1 = {t1*1e9:.2f} ns, t2 = {t2*1e9:.2f} ns")
    p(f"  Eq.(4)  is(t1) = {is_t1*1e3:.3f} mA")
    p(f"  Eq.(8)  PAPER is(t2) = {is_eq8_t2:+.3f} A  <-- ERRORE! Corrente NEGATIVA in conduzione diretta!")
    p(f"          (Causa: Eq.(6) integra da t0 anziche t1; Eq.(7) pone v_AB(t1)=0 anziche k(Vo+2Vd))")
    p(f"  CORRETTA is(t2)      = {is_true_t2:+.3f} A  (strettamente positiva)")

    # 2. Mode IV Equations (13)-(14)
    wr = 1.0 / np.sqrt(2.0 * Cso * Lseq)
    paper_coeff = Vdc / (Lseq * np.sqrt(2.0 * Cso * Lseq))
    true_coeff = Vdc * np.sqrt(2.0 * Cso * Lseq) / Lseq
    p("\n[2] EQUAZIONI MODO IV: Eqs. (13)-(14)")
    p(f"  omega_r = 1/sqrt(2*Cso*Lseq) = {wr:.3e} rad/s (fr = {wr/(2*np.pi)/1e6:.2f} MHz)")
    p(f"  Errore 1 (Eq.13-14): argomento sin/cos = (t/sqrt(2*Cso*Lseq) - t3) sottrae secondi a radianti!")
    p(f"  Errore 2 (Eq.14): coefficiente Vdc / (Lseq*sqrt(2*Cso*Lseq)) = {paper_coeff:.3e} A/s^2 (10^14 A!!)")
    p(f"                    invece di Vdc*sqrt(2*Cso*Lseq)/Lseq = {true_coeff:.2f} A (ha diviso invece di moltiplicare!)")
    p(f"  Errore 3 (Eq.14): manca (-1) nel coseno => is(t3) != Ip!")

    # 3. Steady-state gain Eqs. (16)-(18) & Fig. 7
    p("\n[3] GUADAGNO STAZIONARIO: Eqs. (16)-(18) E FIG. 7")
    p("  Eq.(16) PAPER:    I = (2/Ts) * ton^2 * (Vdc/(k*Vo)) * (Vdc-k*Vo)/Lseq  <-- ERRORE FATTORE 2!")
    p("  Eq.(16) CORRETTA: I = (1/Ts) * ton^2 * (Vdc/(k*Vo)) * (Vdc-k*Vo)/Lseq")
    p("  Eq.(18) PAPER:    4*Lseq / (Ts * Re * ton^2)  <-- ERRORE DIMENSIONALE! Unita [1/s^2], Ts a denominatore!")
    p(f"          Valore numerico letterale Eq.(18) a psi=90°, Re=30Ω: "
      f"{2/(k + np.sqrt(k**2 + 4*Lseq/(Ts*30*(Ts/4)**2))):.6e}  (praticamente ZERO!)")
    p("  Eq.(18) CORRETTA (DCM): gv = 2 / (k + sqrt(k^2 + 4*Ts*Lseq / (Re * ton^2)))")
    p("  Confronto a psi=90°, Re=30Ω (td=0):")
    gv_true_dcm = 2.0 / (k + np.sqrt(k**2 + 4 * Ts * Lseq / (30.0 * (Ts / 4.0)**2)))
    gv_paper_fig7 = 2.0 / (k + np.sqrt(k**2 + 1 * Ts * Lseq / (30.0 * (Ts / 4.0)**2)))  # C = Lseq*fs
    gv_exact_dcm_ccm, m90 = exact_gv_vs_psi(90.0, 30.0, td=0.0)
    gv_exact_171, m171 = exact_gv_vs_psi(171.0, 30.0, td=0.0)
    gv_fig7_171 = 2.0 / (k + np.sqrt(k**2 + 1 * Ts * Lseq / (30.0 * (171.0/360.0 * Ts)**2)))
    p(f"    - Fig. 7 del paper (curva plottata, C = Lseq*fs = 2.60Ω): gv(90°, 30Ω) = {gv_paper_fig7:.3f}, gv(171°, 30Ω) = {gv_fig7_171:.3f}")
    p(f"    - Formula DCM corretta (C = 4*Lseq*fs = 10.38Ω):          gv(90°, 30Ω) = {gv_true_dcm:.3f} [{m90}]")
    p(f"    - Modello esatto DCM+CCM (fisico):                        gv(90°, 30Ω) = {gv_exact_dcm_ccm:.3f} [{m90}], gv(171°, 30Ω) = {gv_exact_171:.3f} [{m171}]")
    p("    => Fig. 7 e' stata plottata con una costante 4x piu' piccola del vero (equivalente a psi/180 invece di psi/360)!")

    # 4. Auxiliary inductor design Eqs. (20)-(24)
    Cso_eq23 = 1.0 / (128.0 * Laux * fs**2)
    td_eq24 = 2.0 * Cso_eq23 * Vdc / IPA
    p("\n[4] PROGETTO INDUTTORI AUSILIARI: Eqs. (20)-(24)")
    p(f"  Combinando Eq.(20), (23), (24): td = Ts/8 = {td_eq24*1e9:.1f} ns (fisso al 12.5% del periodo = 45°!)")
    p(f"  Per Laux=67uH @ 220kHz, Eq.(23) implica Cso = {Cso_eq23*1e9:.2f} nF (circa 3.5x piu' grande di Coss reale)")

    # 5. Series inductor design Eqs. (25)-(26) & Fig. 9
    Lseq_eq26 = (1.0 + k * Vo / Vdc) * (Vo**2 / Po_max) * (Ts / 64.0)
    Lseq_exact_bcm = k**2 * (1.0 - k * Vo / Vdc) * (Vo**2 / Po_max) * (Ts / 4.0)
    Lseq_exact_bcm_vd = k**2 * (1.0 - k * (Vo + 2*Vd) / Vdc) * (Vo * (Vo + 2*Vd) / Po_max) * (Ts / 4.0)
    p("\n[5] PROGETTO INDUTTORE SERIE IN BCM: Fig. 9 e Eqs. (25)-(26)")
    p("  Fig. 9: etichetta picco primario come 2*k*Io anziche 2*Io/k (inversione del rapporto spire k=Np/Ns)")
    p("  Eq.(25): unita [H*s] per fattore spurio Ts/2, e manca k al denominatore!")
    p(f"  Eq.(26) PAPER (segno + errato e fattore Ts/64): Lseq = {Lseq_eq26*1e6:.2f} uH")
    p(f"  Eq.(26) CORRETTA ideale (Vo=300V, Po=3kW):      Lseq = {Lseq_exact_bcm*1e6:.2f} uH")
    p(f"  Eq.(26) CORRETTA con Vd=1.5V:                   Lseq = {Lseq_exact_bcm_vd*1e6:.2f} uH")
    p(f"  Tabella II (prototipo):                         Lseq = {Lseq*1e6:.2f} uH  (NON coincide ne' con Eq.26 ne' con BCM a 3kW!)")

    # 6. Power Delivery Envelope across Table I (235-431 V)
    p("\n[6] POTENZA MASSIMA EROGABILE CON Lseq=11.8uH (Tabella II) SU RANGE BATTERIA 235-431V (Tabella I)")
    p(f"  {'Vo(V)':>6} | {'Po_BCM(W)':>10} | {'Po_max_ideal(D=1)':>18} | {'Po_max_prac(td=165ns,Vd=1.5V)':>30} | {'Regime @ 3kW':>14}")
    p("  " + "-" * 86)
    for V in [235, 270, 300, 330, 355, 380, 400, 431]:
        p_bcm = k**2 * (1.0 - k * V / Vdc) * V**2 * Ts / (4.0 * Lseq)
        r_id = exact_dc_point(1.0, Vdc=Vdc, Vo=V, Vd=0.0, Lseq=Lseq)
        D_max_p = 1.0 - 165e-9 / (Ts / 2.0)
        r_pr = exact_dc_point(D_max_p, Vdc=Vdc, Vo=V, Vd=1.5, Lseq=Lseq)
        reg = "IMPOSSIBILE" if r_pr["Po"] < 2990 else ("CCM" if p_bcm < 3000 else "DCM/BCM")
        p(f"  {V:6d} | {p_bcm:10.1f} | {r_id['Po']:18.1f} | {r_pr['Po']:30.1f} | {reg:>14}")
    p("  => CON Lseq=11.8uH e Vdc=400V, il BCM si raggiunge gia' a 2268W (75% carico), NON a 3000W!")
    p("  => A 3000W (Fig. 21) il convertitore e' in CCM profondo (contraddicendo il testo a p.2766)!")
    p("  => A Vo=431V (estremo superiore Tabella I) la potenza massima fisica scende a soli ~1050W!")

    # 7. Transformer leakage equations (27)-(31)
    p("\n[7] INDUTTANZA DI DISPERSIONE TRASFORMATORE: Eqs. (27)-(31)")
    p("  Eqs.(27)-(28): errore tipografico H(rho^2) invece di [H(rho)]^2.")
    p("  Eqs.(29)-(31): MANCA la lunghezza media della spira MLT [m] => unita [H/m] invece di [H]!")

    # 8. Output capacitor Eq. (32) & Fig. 11
    dV_1uF = (Po_max / Vo) / (8.0 * fs * Cf)
    p("\n[8] CONDENSATORE DI FILTRO Cf: Eq.(32) E FIG. 11")
    p(f"  Eq.(32) Cf = Io/(8*fs*dVCf): CORRETTA in BCM! Con Cf=1uF, Io=10A => dVCf = {dV_1uF:.2f} V ({dV_1uF/Vo*100:.2f}%)")
    p("  Fig. 11(a): etichetta picco i_Cf come Ip/k invece di k*Ip - Io (inversione di k e manca -Io).")

    # 9. Experimental Scope Forensic Discrepancies (Figs. 14-23)
    p("\n[9] INCONGRUENZE SPERIMENTALI NEGLI OSCILLOGRAMMI (Figs. 14-23)")
    p("  1) Figs. 16-20 (Proposed 10%-85%, data 19/07/2011): il testo a p.2765 dichiara Vo=300VDC,")
    p("     ma la traccia C3 (Output Diode Voltage, 100V/div, offset 0V) misura -356V (e ringing attorno")
    p("     a -178V = -Vo/2), E il rapporto indipendente dalla sonda toff/ton ~ 0.31-0.34 dimostra")
    p("     k*Vo/Vdc ~ 0.75 => Vo reale ~ 355V (con Vdc ~ 405-410V), NON 300V (che darebbe toff/ton = 0.56)!")
    p("  2) Fig. 21 (Proposed 100%, data 18/07/2011): corrente i_s in CCM profondo (passa da -15A a +20A")
    p("     senza intervallo a zero), smentendo ZCS sui MOSFET leading-leg e sui diodi d'uscita a pieno carico.")
    p("  3) Fig. 14(a)-(b) (Conventional FB, LeCroy58.bmp / LeCroy48.bmp): frequenza misurata ~150 kHz")
    p("     (3 cicli in 20us @ 2us/div) e Vdc ~ 320-355V, NON 220 kHz / 400V come dichiarato in Tabella I.")
    p("  4) Fig. 15 (No-load): C1 segna 2.00 V/div (manca fattore sonda 100x => 200 V/div).")
    p("  5) Fig. 22(b) (LeCroy41.bmp): onda quadra 50% duty (~286 kHz @ 1us/div) senza carico specificato.")
    p("  6) Fig. 23 (Efficienza): etichetta asse Y troncata ('E ff ic ie n') e legenda mancante per 'Proposed'.")
    p("  7) Tabella II omette CB, LM, td; Tabella IV chiama i diodi d'uscita 'D_PFC' (refuso da Tab. III);")
    p("     Fig. 3 (D2,D3) vs Fig. 4 (D1,D4) in contraddizione sul semiperiodo positivo.")

    report_text = "\n".join(lines) + "\n"
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(report_text, encoding="utf-8")
    print(report_text)


if __name__ == "__main__":
    main()
