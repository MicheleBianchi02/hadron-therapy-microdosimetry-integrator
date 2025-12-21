# MicroDosimeter Control & Analysis Software

This application provides a graphical interface for controlling a microcontroller-based microdosimeter, streaming high-frequency data (2mHz to 2kHz), and performing real-time statistical analysis. It features live data visualization via time-series plots and multichannel analysis (histograms), along with real-time variance calculation.

## Table of Contents
- [Features](#features)
- [Technical Architecture](#technical-architecture)
    - [Threading & Concurrency](#threading--concurrency)
    - [Data Flow & Processing](#data-flow--processing)
    - [Architecture Pattern](#architecture-pattern)
- [Memory Management (Critical)](#memory-management-critical)
    - [Current Limitations](#current-limitations)
    - [Path to Memory Safety](#path-to-memory-safety)
- [Extensibility](#extensibility)
- [Roadmap & TODOs](#roadmap--todos)

---

## Features
- **Serial Communication:** Port selection.
- **Real-Time Visualization:** 
    - **Time Series:** Moving window or full history view.
    - **Multichannel (MCA):** Histogram view of charge/channel counts.
- **Statistical Analysis:** Real-time calculation of Mean, Variance, Standard Deviation, and overflow detection for two channels.
- **Modes of Operation:**
    - **Operational Mode:** Streams calculated differences (efficient).
    - **Debug Mode:** Streams start/stop timer values for deep hardware analysis (verbose).
- **Data Persistence:** Save data to CSV or load previous sessions.

---

## Technical Architecture

### Threading & Concurrency
The application utilizes a **Producer-Consumer** pattern to handle high-frequency data streams without freezing the user interface (UI).

1.  **The Producer (Serial Thread):** 
    - Located in `utils.py` and `serial_comm.py`.
    - A dedicated background thread (`threading.Thread`) continuously reads bytes from the serial port.
    - It parses raw bytes into integers (or tuples in Debug Mode) and appends them to a thread-safe internal buffer.
    - **Locking:** A `threading.Lock` is employed during buffer access to prevent race conditions when the UI thread attempts to read data while the serial thread is writing.

2.  **The Consumer (UI Thread):**
    - The main PyQt event loop (Main Thread).
    - A `QTimer` triggers the `_update_ui` method in `RunningWindow` every `UPDATE_INTERVAL_MS` (default 50ms).
    - This method locks the buffer, retrieves all accumulated data, clears the buffer, and proceeds to update the internal NumPy arrays and UI plots.

### Data Flow & Processing
1.  **Ingestion:** Raw bytes are read from the UART interface.
2.  **Conversion:** Bytes are converted to integer pairs (Channel 1 & Channel 2). In Debug mode, start and stop values are preserved.
3.  **Storage:** Data is appended to dynamic NumPy arrays (`self.data`). If the array capacity is reached, it is resized (doubled) to minimize allocation overhead.
4.  **Statistics:** Variance and Mean are calculated using an online algorithm (combining batches) to ensure efficiency without re-processing the entire dataset every frame.
5.  **Visualization:** `PyQtGraph` is used for high-performance plotting. Downsampling is applied implicitly by the library or explicitly for the "All Time" view to maintain FPS.

### Architecture Pattern
Currently, the application follows a "Smart UI" pattern where logic and presentation are tightly coupled within the Window classes. 
*   **Reasoning:** This approach was chosen for rapid development and because the application scope was initially contained. 
*   **Scaling:** As the application grows, refactoring into **MVC (Model-View-Controller)** or **MVVM** is recommended to separate the serial logic/data processing (Model) from the PyQt widgets (View).

---

## Memory Management (Critical)

**⚠️ The current implementation is NOT memory safe for indefinite duration.**

The application stores the entire measurement history in RAM (NumPy arrays) to allow for "Full History" plotting and analysis.

### Current Usage Metrics
- **Operational Mode:** Consumes ~1 GB of RAM after **67 million** measurements.
- **Debug Mode:** Consumes ~1 GB of RAM after **17 million** measurements (due to storing Start, Stop, and Difference values).

*Note: The application will crash with an `MemoryError` if the system RAM is exhausted.*

### Path to Memory Safety
To convert this into a memory-safe application capable of running for days, the following architectural changes are required:

1.  **Moving Window Plot (Ring Buffer):**
    - Instead of appending to an infinite list, use a **Fixed-Size Ring Buffer**.
    - A `RingBuffer` class implementation is currently provided in the comments of `running_window.py`. This ensures memory usage remains constant regardless of duration.
    
2.  **"All Time" Plot Strategy:**
    - To maintain a full history view without unlimited memory, implement **decimation/downsampling**:
        - Create a secondary buffer that stores only the `Min`, `Max`, and `Mean` of a batch (e.g., every 1000 samples).
        - When this buffer fills, compress it further (merge adjacent points).
    - Alternatively, remove the "Full History" feature for long-running tests.

3.  **Data Persistence (Streaming to Disk):**
    - Currently, data is saved to disk only when the user clicks "Save" or periodically via the UI update loop if a file path is set at the beginning of the setup.
    - **Optimization:** Stream raw data directly to a temporary file (on disk) in the `utils` thread. The UI should only keep the chunk required for visualization in RAM.

4.  **Data Loading:**
    - The current `load_file` method loads the entire CSV into RAM. For large files, use memory mapping (`numpy.memmap`) or chunked reading (Pandas chunking).

---

## Extensibility

The application is designed to be hardware-agnostic regarding the UI. 

**Replacing the Microcontroller:**
If you switch to a new MCU (e.g., FPGA or faster ARM chip) with significantly higher data rates (>2MHz):
1.  **UI Preservation:** The PyQt interface (`RunningWindow`, `TimeWindow`) requires little to no changes.
2.  **Backend Update:** You only need to rewrite `serial_comm.py` and `utils.py`.
3.  **Performance:** For extremely high data rates, the Python serial thread might become a bottleneck. The backend logic can be rewritten in **C** and exposed to Python as a shared library, while keeping the UI in Python.

---

## Roadmap & TODOs

### High Priority (Stability)
- [ ] **Implement Memory Safety:** Integrate the `RingBuffer` for live viewing and stream data to a temp file for storage.
- [ ] **Refactor Range Selector:** The current time-range selector is inefficient for large datasets; redesign or remove it in favor of zoomable plots.
- [ ] **Refactor Data Loading:** Implement chunked loading for large historical files.

### Features
- [ ] **Physics Calibration:** Add settings to input detector sensitivity, allowing the display of **Energy (keV/MeV)** directly instead of Charge (pC) or Channel ID.
- [ ] **Advanced Analysis:** Add support for multiple Regions of Interest (ROI) on the histogram.
- [ ] **Auto-Stop:** Add a "Stop after X seconds" or "Stop after X counts" feature.

### Architecture
- [ ] **Decoupling:** Migrate to an MVC pattern to facilitate unit testing of the variance logic without initializing the GUI.