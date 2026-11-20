# Progetto di Elettronica di Potenza — Replica LTspice e Analisi Critica di `35.pdf`

**Articolo di riferimento:**
M. Pahlevaninezhad, P. Das, J. Drobnik, P. K. Jain, and A. Bakhshai, *"A Novel ZVZCS Full-Bridge DC/DC Converter Used for Electric Vehicles"*, **IEEE Transactions on Power Electronics**, Vol. 27, No. 6, pp. 2752–2769, June 2012 ([35.pdf](35.pdf)).

---

## Struttura della Repository

```text
progetto_elettronica_di_potenza/
├── 35.pdf                                   # Articolo originale IEEE TPEL 2012
├── README.md                                # Questa guida rapida
├── RELAZIONE_TECNICA_E_ANALISI_CRITICA.md   # Relazione completa + Audit critico errori del paper + Guida orale 30L
├── ltspice/                                 # 17 schematici .asc 100% standalone + .plt auto-caricanti
│   ├── 01_proposed_zvzcs_fb.asc             # Schema principale del convertitore proposto (Fig. 2, Tab. II & IV)
│   ├── 02_proposed_ideal_modes_fig3.asc     # Forme d'onda ideali e 7 modi di funzionamento (Figg. 3, 4, 6, 8, 11a)
│   ├── 03_proposed_gain_sweep_fig7.asc      # Sweep parametrico guadagno gv(psi, Re) (Fig. 7)
│   ├── 04_proposed_bcm_design_fig9.asc      # Critical Conduction Mode: Lseq=11.8uH vs 8.0uH corretto (Figg. 9, 11b)
│   ├── 05_proposed_noload_fig15.asc         # Carico 0% / No-Load (Fig. 15) — verifica ZVS a vuoto
│   ├── 06_proposed_load_10pct_fig16.asc     # Carico 10% / 300 W (Fig. 16 & Fig. 5 sottomodi Modo IV)
│   ├── 07_proposed_load_25pct_fig17.asc     # Carico 25% / 750 W (Fig. 17a/b)
│   ├── 08_proposed_load_50pct_fig18.asc     # Carico 50% / 1500 W (Fig. 18a/b)
│   ├── 09_proposed_load_70pct_fig19.asc     # Carico 70% / 2100 W (Fig. 19a/b)
│   ├── 10_proposed_load_85pct_fig20.asc     # Carico 85% / 2550 W (Fig. 20a/b)
│   ├── 11_proposed_load_100pct_fig21.asc    # Carico 100% / 3000 W (Fig. 21 — prova CCM con Lseq=11.8uH!)
│   ├── 12_proposed_aux_circuit_fig22.asc    # Corrente circuito ausiliario a due carichi (Figg. 8, 22a/b)
│   ├── 13_conventional_psfb_10pct_fig14a.asc  # Full-Bridge convenzionale + aux asimmetrico, 10% (Figg. 1, 14a, Tab. V)
│   ├── 14_conventional_psfb_100pct_fig14b.asc # Full-Bridge convenzionale + aux asimmetrico, 100% (Figg. 1, 14b, Tab. V)
│   ├── 15_efficiency_proposed_fig23.asc     # Sweep efficienza 10%-100% — Topologia Proposta (Fig. 23)
│   ├── 16_efficiency_conventional_fig23.asc # Sweep efficienza 10%-100% — Topologia Convenzionale (Fig. 23)
│   └── 17_forensic_scope_355V_check.asc     # Verifica forense: oscillogrammi reali a Vo=355V, Vdc=410V!
├── figures/                                 # Tutti i 21 grafici ad alta risoluzione generati dai .raw LTspice
│   ├── fig03_ideal_waveforms_modes.png      # ... fino a fig23_efficiency_comparison.png
│   ├── bonus01_zvs_zvzcs_mosfet_verification.png
│   ├── bonus02_proposed_vs_conventional_diode_spikes.png
│   ├── bonus03_forensic_355V_vs_300V_comparison.png
│   ├── bonus04_table1_power_envelope_235_431V.png
│   └── schematics_preview/                  # Anteprime grafiche degli schematici .asc
├── results/
│   ├── simulation_metrics.json              # Tutte le misure numeriche estratte da LTspice (.meas)
│   └── paper_audit_verification.txt         # Verifica analitica automatizzata di Eqs. (1)-(32)
└── scripts/                                 # Pipeline Python 100% riproducibile
    ├── asc_compiler.py                      # Compilatore .asc -> .net con validatore pin/connettivita'
    ├── schematic_templates.py               # Modelli SPICE (STW77N65M5, CPW2-0600S010B, D_FRED_1200V) e builder
    ├── generate_schematics.py               # Genera tutti i 17 file .asc + .plt
    ├── run_all_simulations.py               # Esegue tutte le simulazioni in LTspice batch (-b)
    ├── plot_all_figures.py                  # Produce i 21 grafici PNG ad alta risoluzione
    └── paper_math_audit.py                  # Audit matematico delle equazioni del paper
```

---

## Come Aprire e Simulare Qualsiasi Circuito su LTspice (macOS)

Ogni file `.asc` dentro [`ltspice/`](ltspice/) è **completamente autonomo** (contiene direttamente i `.model` dei MOSFET `STW77N65M5` e dei diodi SiC `CPW2_0600S010B` / `D_FRED_1200V`, nessun file esterno richiesto) ed è affiancato da un file `.plt` omonimo:

1. Fai doppio clic su qualsiasi file `ltspice/*.asc` (si apre direttamente in **LTspice**).
2. Premi il pulsante **Run** (omino che corre, oppure `Cmd + R`).
3. Grazie al file `.plt` abbinato, LTspice apre automaticamente le tracce principali (`V(a,b)`, `I(Lseq)`, `V(gnd_sec,sec_p)`, `V(sec_p,sec_n)`, `I(Laux1)`, ecc.) già impilate.
4. Per leggere i valori esatti di potenza (`Pout`, `Pin`), efficienza (`Eff`), picchi di corrente (`Is_pk`) e tensione sui diodi (`Vd2_min`, `Vsec_pk`), apri il **SPICE Error Log** (`View → SPICE Error Log`, oppure `Cmd + L`).
5. Per variare il punto di lavoro sullo schema master [`01_proposed_zvzcs_fb.asc`](ltspice/01_proposed_zvzcs_fb.asc), basta modificare il parametro `.param psi=...` (sfasamento in gradi tra gamba leading e lagging, da `13.5°` a vuoto fino a `151°` a pieno carico 3 kW).

---

## Come Rigenerare Tutto da Terminale (Opzionale)

Se vuoi ricompilare tutti gli schematici, rilanciare tutte le simulazioni in batch su LTspice e rigenerare tutti i 21 grafici:

```bash
python3 scripts/paper_math_audit.py
python3 scripts/generate_schematics.py
python3 scripts/run_all_simulations.py
python3 scripts/plot_all_figures.py
```
