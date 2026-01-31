
# Measurement Data

This directory contains the results of the experimental measurements. The data is stored in CSV format, organized by folders.

## File Format

Each measurement file follows a specific CSV structure containing metadata in the header and raw data in subsequent rows.

### Header
The first row of every file contains the configuration parameters for the measurement:
- **Integration time [s]**
- **Reset time [s]**
- **Sample frequency [Hz]**

### Data Columns
Following the header, the data is arranged in three columns:

| Column | Description | Unit | Note |
| :--- | :--- | :--- | :--- |
| **1** | Relative Timestamp | Seconds [s] | Time elapsed since start of measurement |
| **2** | Channel 1 Data | ADC Counts | **Main measurement data** |
| **3** | Channel 2 Data | ADC Counts | *Unused / Irrelevant* |

**Example of raw file content:**
```csv
integration time [s]: 0.200012, reset time [s]: 0.000427, sample frequency [Hz]: 4.989037
0.2004395,3229,1473
0.4008789,3464,1737
0.6013184,3167,1535
0.8017578,3205,1598
```

## Data Specifications

-   **ADC Resolution:** 12-bit (Values range from 0 to 4095).
    
-   **Units:** The data in columns 2 and 3 are **raw ADC values**. They have not been converted to Voltage (V) or Charge (pC).
    
-   **Channel Usage:** Only **Channel 1** (the middle column) contains valid measurement data. Channel 2 should be ignored as it contains data not relative to the current measurement.
    


## Leakage Current Analysis

The `leakage/` subdirectory contains data and analysis tools specifically for leakage current characterization.

**Contents:**
*   **Raw Data:** Measurement files specific to leakage tests.
*   **Python Script:** A script used to calculate the leakage current as a function of the applied voltage.
*   **Plots:** Generated images visualizing the results of the calculation.

### Leakage File Format
The CSV files in the `leakage` folder have a different column structure than the standard measurement files.

**Example of leakage raw data:**
```csv
integration time [s]: 0.5, reset time [s]: 0.000793, sample frequency [Hz]: 1.996831
0.5007935,4052,4054,2844,3220
1.0015869,4056,4055,3449,3352
1.5023804,4054,4054,3476,3381
2.0031738,4055,4056,3481,3390
```

### Column Mapping

| Column | Description               | Note                          |
|--------|---------------------------|-------------------------------|
| 1      | Relative Timestamp [s]    |                               |
| 2      | Channel 1 Start           | Start of integration (ADC counts) |
| 3      | Channel 1 Stop            | Stop of integration (ADC counts)  |
| 4      | Channel 2 Start           | Unused / Irrelevant           |
| 5      | Channel 2 Stop            | Unused / Irrelevant           |

### Notes

- Only **Channel 1** (Columns 2 and 3) is relevant for analysis.
- The **Start** and **Stop** values (Columns 2 and 3) may appear very similar. This is expected behavior due to both the short integration time and the low magnitude of the leakage current being measured.

    
## Channel 2 Behavior

Although Channel 2 is not used for the primary analysis, you may observe two distinct behaviors in the raw data depending on the hardware configuration at the time of measurement:

1.  **Crosstalk (Floating Input):**
    In some measurements, the distribution of Channel 2 appears similar to Channel 1 (exhibiting a Gaussian distribution with a smaller mean and slightly larger variance). This is an artifact caused by the Channel 2 ADC input being left unconnected (floating). Due to complex capacitive crosstalk between the inputs, the floating potential on Channel 2 tracks the potential of Channel 1.

2.  **Zero Reading (Grounded Input):**
    In other measurements, Channel 2 reads consistently as 0. In these instances, the input for Channel 2 was physically shorted to ground.
