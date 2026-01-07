# ESP-32 Nuclear Pulse Simulation

This repository contains a statistical simulation of nuclear pulse generation using an ESP-32 microcontroller. The project analyzes the impact of hardware limitations—specifically dead time and clock discretization—on the resulting statistical distributions (Exponential and Poisson).
## Overview

When generating random pulses to emulate nuclear decay events, ideal theoretical models assume continuous time and zero processing delay. However, microcontroller implementations introduce two specific constraints:

- **Dead Time ($T_{\text{dead}}$)**: The minimum time required to process a pulse. In this implementation, a fixed dead time of $300 μs$ is introduced (simulated via signal clipping).

- **Discretization ($T_{\text{clock}}$​)**: The ESP-32 `delayMicroseconds` function forces time intervals to be integers. This creates a discrete time domain with a step size of $1μs$.

These constraints distort the ideal Exponential distribution of inter-arrival times, subsequently altering the counting statistics (Poisson distribution). This simulation quantifies these distortions to determine the valid operating range for the pulse generator.

## Simulation Methodology

The Python script [`stat.py`](stat.py) performs the following steps:

1) **Generation**: Samples are drawn from an ideal Exponential distribution with a target mean inter-arrival time  $T_{\text{s}}$.

2) **Discretization**: Values are floored to the nearest clock tick ($1μs$).

3) **Clipping (Dead Time)**: Any value below $T_{\text{dead}}​$ ($300μs$) is clipped to exactly $300μs$.
	- $P(t<300μs)=0$
	- $P(t=300μs)$ is artificially inflated (probability pile-up).

4) **Analysis**: The script calculates the resulting mean event rates, variances, and counting distributions for various target $T_{\text{s}}$​.

## Results and Analysis

Two primary test cases were simulated to illustrate the "dead time effect": a low-period case ($Ts​=800μs$) and a high-period case ($Ts​=10000μs$).

### 1. Distribution Distortion ($T_{\text{s}}=800μs$)

When the target mean time ($800μs$) is close to the dead time ($300μs$), the distortion is significant.

<img width="1594" height="820" alt="distributions" src="https://github.com/user-attachments/assets/eb35ef69-4ff6-4bbf-91cb-3031f13eeb0e" />

*Figure 1: Comparison of Theoretical vs. Simulated distributions for* $Ts​=800μs$.

- **Left (Time Domain)**: The inset highlights the discretization and the "pile-up" at $300μs$. The probability of generating a pulse $<300μs$ is zero.

- **Right (Counting Domain)**: The resulting counting distribution (purple histogram) deviates from the theoretical Poisson distribution (red dashed line). It behaves more like a Gaussian distribution with reduced variance. Because many events are forced to the minimum dead time, the randomness is suppressed, leading to a "stiffer" pulse train with lower standard deviation ($\sigma_{meas}​<\sigma_{th}$​).

### 2. Quasi-Ideal Behavior ($T_{\text{s}}=10000 μs$)

When the target mean time is significantly larger than the dead time, the hardware effects are negligible.

<img width="1685" height="822" alt="distributions" src="https://github.com/user-attachments/assets/17311dd3-8a60-47f2-bd69-3e204cc99531" />

*Figure 2: Comparison of Theoretical vs. Simulated distributions for* $T_{\text{s}}=10000 μs$.

The generated distribution closely follows the theoretical Poisson curve. The clipping at the lower bound has a minimal impact on the overall statistics because the probability density at $t<300μs$ is naturally low for this mean value.

Note that in the left plot, the peak corresponding to the dead-time position is not visible because the bin width is too large, effectively averaging out the peak.

### 3. Asymptotic Ratios

We analyzed the ratio between measured and theoretical values for both the number of events ($n$) and the variance ($\sigma^2$) as the total measurement time increases.

<img width="1402" height="997" alt="results" src="https://github.com/user-attachments/assets/85bb0ba8-0a30-499d-b977-0bec5e870f93" />

*Figure 3: Convergence of measured/theoretical ratios for* $T_{\text{s}}=800μs$.

For $T_{\text{s}}=800μs$, the ratios approach an asymptotic value **not equal to 1**. This indicates a systematic error proportional to the measurement time. While the generator is stable, the output statistics (mean count and variance) require correction factors if used in this range. Conversely, for $T_{\text{s}}=10000 μs$, the asymptote is effectively 1.0.

<img width="1747" height="1086" alt="results" src="https://github.com/user-attachments/assets/8452aea7-88d4-4d12-893e-a1339e3f5c0d" />

*Figure 4: Convergence of measured/theoretical ratios for* $T_{\text{s}}=10000μs$.

Notice that the theoretical number of events is obtained by varying the measuring time.
The figure below shows the behaviour of the generated $T_{\text{s}}$ and $n$ for a
fixed measuring time.

<img width="1646" height="691" alt="fig_fixed_t_meas" src="https://github.com/user-attachments/assets/af3a2d45-9955-4898-ace7-a319824fd017" />


*Figure 5:* $n$ *and* $T_{\text{s}}$ *for a fixed measuring time*.

### 4. Operating Range Sweep

To determine the safe operating range, a sweep over mean inter-arrival times ($T_{\text{s}}$) was performed. The plot below shows the relative error in the number of events (left axis) and variance (right axis).

<img width="1493" height="908" alt="period" src="https://github.com/user-attachments/assets/c052d1a2-1719-4e7c-a9ac-8aed3a2c2a13" />

*Figure 6: Relative error of Mean and Variance vs.* $T_{\text{s}}$​.

- **Low $T_{\text{s}}$**: The error is massive due to the dominance of the dead time.

- **Transition**: The error drops as Ts​ increases.

- **Suggestion**: For a system with a $300μs$ dead time, a mean period of $30000 \- 40000μs$ (or higher) is recommended to ensure the generated pulses adhere to standard Poisson statistics without significant correction. If the dead time is decreased, these values reduces accordingly. 

- **Notes**: In the real waveform generator (ESP-32), the dead time is not constant. Instead, it depends on the statistics of the generated pulses and on the time required to generate a random number, which is not constant on this device.
  Consequently, if we assume that the generated pulse has a Gaussian shape in the time domain, the resulting dead-time distribution is also expected to be Gaussian. The total number of generated events still exhibits the behavior shown previously,
  as it follows the mean of the distribution. However, the estimated standard deviation becomes slightly larger for values of $T_{\text{s}}$.
	​

## Usage


To run the simulation and generate the plots:

``` bash
python stat.py
```

The script will prompt for:

1.  **$T_{\text{s}}$ Input:** The target mean time in microseconds.
    
2.  **$n$ Input:** The target number of events.
    
3.  **Calculate All:** Enter `y` to perform the full parameter sweep (Part 2 & 3 of the script) which generates the data for the ratio and period plots.
    
### Dependencies

-   Python 3.x
-   `numpy`
-   `matplotlib`
-   `scipy`
