# Current Integrator for Microdosimetry in Clinical Hadron Therapy

This repository contains the design, firmware, and validation of a custom
microcontroller-based Data Acquisition (DAQ) system designed for microdosimetry in
clinical hadron therapy.

This project was developed for a university course in the **MSc in Nuclear Engineering**
program at **Politecnico di Milano** and is integrated into the **ATOMIQA** project of
the **INFN (Istituto Nazionale di Fisica Nucleare)**.

## Project Overview

Conventional microdosimetry using Tissue-Equivalent Proportional Counters (TEPCs) in
pulse-counting mode faces significant limitations in modern clinical therapy due to
"pile-up"—a phenomenon where high particle fluence rates cause signals to overlap,
making individual events impossible to resolve.

To overcome this, our system utilizes the **variance-covariance method**. Instead of
attempting to count individual pulses, the system integrates the detector's output
current over fixed time intervals. By analyzing the statistical fluctuations (variance)
of this integrated signal, we can accurately reconstruct microdosimetric quantities
even in high-intensity beam environments.

## Key Features

- **Analog Front-End (AFE):** Features a gated integrator topology designed to process
  signals from two synchronized detectors.
- **Correlated Double Sampling (CDS):** Employs a technique that calculates the difference
  between the voltage at the end and the start of the integration to eliminate DC
  offsets and switching artifacts.
- **High-Precision Timing:** The firmware is written in **Assembly language** for the
  PIC18F8723 microcontroller to ensure strict timing determinism and a jitter of only 100 ns.
- **Stochastic Signal Simulator:** Includes a custom **ESP32-based hardware emulator**
  that replicates the random temporal structure of radiation events for rigorous system validation.
- **Dynamic Range:** Capable of measuring currents ranging from **1 pA to 1.7 μA**.

## Technical Architecture

The system is built around high-performance analog components to ensure signal integrity:

- **Operational Amplifier:** AD8626 (chosen for its ultra-low input bias current to minimize
  drift).
- **CMOS Switch:** ADG1234 (utilized for low charge injection during reset phases).
- **Reference Clock:** 32.768 kHz external crystal for superior long-term stability
  compared to internal oscillators.

## Mathematical Foundation

The charge accumulation ($Q$) is modeled as a compound stochastic process.
The variance of the signal is the primary metric for characterization:

$$Q = \sum_{j=1}^{n} I_{inj} T_{1,j} + I_{gen} t_{int}$$

$$\sigma_{Q}^{2} = I_{inj}^{2} \overline{n} (\sigma_{T_{1}}^{2} + \overline{T_{1}}^{2})$$

Our experimental trials confirmed the system's accuracy with a relative error of
only **0.3%** when reconstructing combined stochastic processes.

## The Application

We developed a custom software application to interface with the hardware, providing
real-time data acquisition, control, and statistical analysis.


## Authors

This project was a collaborative effort by:

- **Alberto Allegretti** – MSc in Nuclear Engineering, Politecnico di Milano.
- **Michele Bianchi** – MSc in Nuclear Engineering, Politecnico di Milano.

## Acknowledgments

We would like to thank the **INFN** and the **ATOMIQA** project team for providing the
framework for this research, and our professors at **Politecnico di Milano** for their support.
