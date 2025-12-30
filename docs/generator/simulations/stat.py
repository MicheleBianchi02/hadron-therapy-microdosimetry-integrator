import multiprocessing as mp

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from scipy.stats import poisson

# --- Global Constants ---
CLOCK_US = 1
N_MEASURES = 50_000
CHUNK_SIZE = 2_000
MIN_T = CLOCK_US * 300
# MAX_T = CLOCK_US * 2**18
MAX_T = 2e10


def compute_worker(args):
    """
    Worker function for parallel processing.
    args: (t_s, mean_n_target)
    """
    t_s, mean_n_target = args
    t_measure = mean_n_target * t_s

    n_events_list = []
    for _ in range(N_MEASURES // CHUNK_SIZE):
        # Generate and discretize
        sample_pool = np.random.exponential(scale=t_s, size=(CHUNK_SIZE, int(mean_n_target * 3)))
        sample_pool = np.floor(sample_pool / CLOCK_US) * CLOCK_US
        sample_pool = np.clip(sample_pool, MIN_T, MAX_T)

        cumsum_times = np.cumsum(sample_pool, axis=1)
        finished = cumsum_times[:, -1] > t_measure
        n_events_list.append(np.argmax(cumsum_times > t_measure, axis=1)[finished])

    n_events = np.concatenate(n_events_list)
    # Return useful metrics
    return t_s, mean_n_target, np.mean(n_events), np.std(n_events), n_events


def run_simulations():
    # User Input
    try:
        t_s_input = float(input("Enter T_s [us]: "))
        mean_n_1 = int(float(input("Enter n: ")))
    except ValueError:
        t_s_input = 100.0
        mean_n_1 = 1000
        print("Invalid input, using T_s:100us and n:1000.")

    calc_all = input("Do you want to calculate all [y/n]: ")
    if calc_all == "y":
        calc_all = True
    else:
        calc_all = False

    print("--- Starting Parallel Computations ---")
    # Determine number of processes
    pool = mp.Pool(processes=mp.cpu_count())

    # --- PART 1: Single Distribution Visualization ---
    _, mean_n_target_1, actual_mean_1, actual_std_1, n_events_1 = compute_worker(
        (t_s_input, mean_n_1)
    )

    raw_samples = np.random.exponential(scale=t_s_input, size=5_000_000)
    clipped_samples_1 = np.clip(np.ceil(raw_samples / CLOCK_US) * CLOCK_US, MIN_T, MAX_T)

    if calc_all:
        # --- PART 2: Scan over mean_n ---
        # Prepare tasks
        mean_n_ranges = [
            range(5, 20, 1),
            range(20, 100, 7),
            range(100, 1000, 250),
            range(1000, 10_001, 3000),
        ]
        mean_n_tasks = [(t_s_input, m) for r in mean_n_ranges for m in r]

        print(f"Calculating Ratio Scan ({len(mean_n_tasks)} points)...")
        results_ratio = pool.map(compute_worker, mean_n_tasks)

        # --- PART 3: Scan over t_s ---
        mean_n_fixed = 20
        t_s_ranges = [
            range(5, 20, 2),
            range(20, 100, 10),
            [150],
            range(200, 1000, 200),
            [2000, 3000],
            range(4000, 100_000, 25_000),
            range(100_000, 2_000_001, 300_000),
        ]
        t_s_tasks_1 = [(ts, mean_n_fixed) for r in t_s_ranges for ts in r]

        mean_n_fixed = 200
        t_s_tasks_2 = [(ts, mean_n_fixed) for r in t_s_ranges for ts in r]

        print(f"Calculating Difference Scan ({len(t_s_tasks_1)} points)...")
        results_diff_1 = pool.map(compute_worker, t_s_tasks_1)
        print(f"Calculating Difference Scan ({len(t_s_tasks_2)} points)...")
        results_diff_2 = pool.map(compute_worker, t_s_tasks_2)

        pool.close()
        pool.join()
    print("--- Computations Complete. ---")

    mean_ts = np.mean(clipped_samples_1)
    mean_ts = round(mean_ts, 4)
    rate = 1 / mean_ts * 1e3  # khz
    rate = round(rate, 4)

    print("\nResults:")
    print(f"mean n_measured: {round(actual_mean_1, 4)}")
    print(f"std_measured: {round(actual_std_1, 4)}")
    print(f"mean T_s: {mean_ts} us")
    print(f"Rate: {rate} kHz")

    # --- PLOTTING STYLE ---
    plt.rcParams.update(
        {
            "text.usetex": True,  # Use LaTeX
            "font.family": "serif",  # Same as default LaTeX
            "font.size": 14,  # Global font size
            "axes.labelsize": 16,
            "xtick.labelsize": 14,
            "ytick.labelsize": 14,
            "legend.fontsize": 12,
        }
    )

    # Figure 1: Distribution
    fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    target_num_bins = 300
    max_ticks = np.max(clipped_samples_1 / CLOCK_US)

    # Calculate how many ticks must be grouped into one bin
    ticks_per_bin = int(max_ticks / target_num_bins)
    if ticks_per_bin < 1:
        ticks_per_bin = 1

    # Calculate the physical width of this bin in us
    bin_width_ns = ticks_per_bin * CLOCK_US

    clipped_samples_1 = np.sort(clipped_samples_1)

    bins_linear = np.arange(0, np.max(clipped_samples_1) + bin_width_ns, bin_width_ns)

    ax1.hist(
        clipped_samples_1,
        bins=bins_linear,
        density=True,
        color="#1f77b4",
        alpha=0.7,
        label=f"Data ({ticks_per_bin} ticks/bin)",
    )

    t_vals = np.linspace(0, np.max(clipped_samples_1), 1000)

    lam_ns = 1 / t_s_input
    pdf_vals = lam_ns * np.exp(-lam_ns * t_vals)
    ax1.plot(t_vals, pdf_vals, "r-", lw=2, label=rf"Theory (mean$={t_s_input} \mu s$)")

    ax1.set_title(
        rf"Exponential Truth (Clock=${CLOCK_US}\mu s$,  Mean $\sim"
        rf"{np.mean(clipped_samples_1):.1f} \mu s$)"
    )
    ax1.set_xlabel(r"Time $t$ [$\mu s$]")
    ax1.set_ylabel(r"Probability Density [$1 / \mu s$]")
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    x1_min, x1_max = ax1.get_xlim()
    ax1.set_xlim(x1_min, x1_max * 0.3)

    # --- INSET (Stem Plot) ---
    axins = inset_axes(
        ax1,
        width="40%",
        height="40%",
        loc="upper right",
        bbox_to_anchor=(0, 0, 1, 0.9),  # full axes box
        bbox_transform=ax1.transAxes,
        borderpad=2,
    )

    # First 500 ticks only
    zoom_ticks = 500
    unique_ticks, counts = np.unique(clipped_samples_1 / CLOCK_US, return_counts=True)
    mask = unique_ticks <= zoom_ticks
    zoom_x_ticks = unique_ticks[mask]
    zoom_counts = counts[mask]

    stem_x_ns = zoom_x_ticks * CLOCK_US
    n_total = len(clipped_samples_1)
    stem_heights = (zoom_counts / n_total) / CLOCK_US

    markerline, stemlines, baseline = axins.stem(
        stem_x_ns,
        stem_heights,
        linefmt="b-",
        markerfmt="bo",
        basefmt=" ",
    )
    plt.setp(stemlines, "linewidth", 1.5)
    plt.setp(markerline, "markersize", 4)

    # Overlay Theory on Inset
    t_zoom = np.linspace(0, zoom_ticks * CLOCK_US, 100)
    axins.plot(t_zoom, lam_ns * np.exp(-lam_ns * t_zoom), "r-", lw=2, alpha=0.8)

    axins.set_xlabel(r"Time [$\mu s$]", fontsize=10)
    axins.set_xlim(-CLOCK_US, zoom_ticks * CLOCK_US + CLOCK_US)  # Add padding
    axins.set_ylim(0, max(stem_heights.max(), lam_ns) * 1.2)
    axins.grid(True, alpha=0.3, linestyle="--")
    axins.tick_params(axis="both", labelsize=8)

    # --- Poisson plot ---
    bins_p = np.arange(int(min(n_events_1)), int(max(n_events_1)) + 2) - 0.5
    counts_p, bin_edges_p = np.histogram(n_events_1, bins=bins_p, density=True)
    bin_centers_p = (bin_edges_p[:-1] + bin_edges_p[1:]) / 2

    ax2.step(bin_centers_p, counts_p, where="mid", label="Sampled Count", color="orchid")
    ax2.fill_between(bin_centers_p, 0, counts_p, step="mid", alpha=0.2, color="orchid")

    # Comparison curves
    x_max = max(max(n_events_1), mean_n_target_1 + 3 * np.sqrt(mean_n_target_1))
    x_min = min(min(n_events_1), mean_n_target_1 - 3 * np.sqrt(mean_n_target_1))
    x_range = np.arange(int(x_min), int(x_max) + 1)
    ax2.plot(
        x_range,
        poisson.pmf(x_range, mean_n_target_1),
        "r--",
        label=f"Theoretical Line (mean={mean_n_target_1:.2f})",
    )

    # Theory curve (Accounting for Clipping & Discretization)
    ax2.plot(
        x_range,
        poisson.pmf(x_range, actual_mean_1),
        "k:",
        label=f"Empirical Line (mean={actual_mean_1:.2f})",
    )

    ax2.set_title(rf"Counting Distribution ($n={mean_n_target_1}$)")
    ax2.set_xlabel(r"Number of Events ($n$)")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    if calc_all:
        # Figure 2: Ratio vs n_th with Dual Axis
        fig2, ax_ratio = plt.subplots(figsize=(8, 6))

        # Data
        expected_ns = np.array([res[1] for res in results_ratio])
        ratios_n = np.array([res[2] / res[1] for res in results_ratio])
        ratios_std = np.array([res[3] ** 2 / res[1] for res in results_ratio])

        # Sorting
        sort_idx = np.argsort(expected_ns)
        expected_ns = expected_ns[sort_idx]
        ratios_n = ratios_n[sort_idx]
        ratios_std = ratios_std[sort_idx]

        # Left Axis (Mean Ratio)
        color_left = "blue"
        (l1,) = ax_ratio.plot(
            expected_ns,
            ratios_n,
            "o-",
            markersize=4,
            color=color_left,
            label=r"$n_{meas} / n_{th}$",
        )
        ax_ratio.set_xlabel(r"$n_{th}$")
        ax_ratio.set_ylabel(r"$n_{meas} / n_{th}$")
        ax_ratio.tick_params(axis="y")
        ax_ratio.set_xscale("log")
        ax_ratio.grid(True, which="both", alpha=0.3)
        ax_ratio.set_title(rf"$T_{{s}}={t_s_input} \mu s$")

        # Right Axis (Std Ratio)
        ax_ratio2 = ax_ratio.twinx()
        color_right = "red"
        (l2,) = ax_ratio2.plot(
            expected_ns,
            ratios_std,
            "s--",
            markersize=4,
            color=color_right,
            label=r"$\sigma_{meas}^2 / n_{th}$",
        )
        ax_ratio2.set_ylabel(r"$\sigma_{meas}^2 / n_{th}$")
        ax_ratio2.tick_params(axis="y")

        # Asymptotic Line (left axis)
        l3 = ax_ratio.axhline(
            y=ratios_n[-1],
            linestyle="--",
            color=color_left,
            linewidth=2,
            alpha=0.5,
            label="Asymptotic",
        )

        lines = [l1, l2, l3]
        labels = [l.get_label() for l in lines]
        ax_ratio.legend(lines, labels)

        # Figure 3: Difference vs T_s (Dual Axis for Mean and Std)
        fig3, ax_diff = plt.subplots(figsize=(8, 6))

        # --- Data Prep ---
        # Dataset for n=20 (results_diff_1)
        ts_list_1 = np.array([res[0] for res in results_diff_1])
        # Mean Difference: (n_th - n_meas) / n_th
        mean_diffs_1 = np.array([(res[1] - res[2]) / res[1] for res in results_diff_1])
        # var Difference: (n_th - std_meas^2) / n_th
        var_diffs_1 = np.array([(res[1] - res[3] ** 2) / res[1] for res in results_diff_1])

        # Sort by time
        idx1 = np.argsort(ts_list_1)
        ts_sorted_1 = ts_list_1[idx1]
        mean_diffs_1 = mean_diffs_1[idx1]
        var_diffs_1 = var_diffs_1[idx1]

        # Dataset for n=200 (results_diff_2)
        ts_list_2 = np.array([res[0] for res in results_diff_2])
        mean_diffs_2 = np.array([(res[1] - res[2]) / res[1] for res in results_diff_2])
        var_diffs_2 = np.array([(res[1] - res[3] ** 2) / res[1] for res in results_diff_2])

        idx2 = np.argsort(ts_list_2)
        ts_sorted_2 = ts_list_2[idx2]
        mean_diffs_2 = mean_diffs_2[idx2]
        var_diffs_2 = var_diffs_2[idx2]

        # --- Plotting Main Axes ---

        # Left Axis: Mean Difference (Solid lines)
        (l1,) = ax_diff.plot(
            ts_sorted_1,
            mean_diffs_1,
            "o-",
            markersize=4,
            color="crimson",
            label=rf"Mean Diff ($n={results_diff_1[0][1]}$)",
        )
        (l2,) = ax_diff.plot(
            ts_sorted_2,
            mean_diffs_2,
            "s-",
            markersize=4,
            color="royalblue",
            label=rf"Mean Diff ($n={results_diff_2[0][1]}$)",
        )

        ax_diff.set_xscale("log")
        ax_diff.set_xlabel(r"$T_s$ [$\mu s$]")
        ax_diff.set_ylabel(r"$(n_{th} - n_{meas}) / n_{th}$")
        ax_diff.grid(True, which="both", alpha=0.3)

        # Right Axis: Var Difference (Dashed lines, open markers)
        ax_diff_r = ax_diff.twinx()
        (l3,) = ax_diff_r.plot(
            ts_sorted_1,
            var_diffs_1,
            "o--",
            markersize=4,
            color="darkorange",
            markerfacecolor="none",
            label=rf"Var Diff ($n={results_diff_1[0][1]}$)",
        )
        (l4,) = ax_diff_r.plot(
            ts_sorted_2,
            var_diffs_2,
            "s--",
            markersize=4,
            color="black",
            markerfacecolor="none",
            label=rf"Var Diff ($n={results_diff_2[0][1]}$)",
        )
        ax_diff_r.set_ylabel(r"$(n_{th} - \sigma_{meas}^2) / n_{th}$")

        # Combine legends from both axes
        lines = [l1, l2, l3, l4]
        labels = [l.get_label() for l in lines]
        ax_diff.legend(lines, labels, loc="best")
        y1_min, y1_max = ax_diff.get_ylim()
        y2_min, y2_max = ax_diff_r.get_ylim()

        global_min = min(y1_min, y2_min)
        global_max = max(y1_max, y2_max)

        ax_diff.set_ylim(global_min, global_max)
        ax_diff_r.set_ylim(global_min, global_max)

        # --- ADDING THE INSET ---
        ax_ins = ax_diff.inset_axes([0.4, 0.5, 0.4, 0.42])

        # Plot Mean Diff on Inset Left Axis
        ax_ins.plot(ts_sorted_1, mean_diffs_1, "o-", markersize=3, color="crimson")
        ax_ins.plot(ts_sorted_2, mean_diffs_2, "s-", markersize=3, color="royalblue")

        # Plot var Diff on Inset Right Axis
        ax_ins_r = ax_ins.twinx()
        ax_ins_r.plot(
            ts_sorted_1,
            var_diffs_1,
            "o--",
            markersize=3,
            color="darkorange",
            markerfacecolor="none",
        )
        ax_ins_r.plot(
            ts_sorted_2, var_diffs_2, "s--", markersize=3, color="black", markerfacecolor="none"
        )

        y1_min, y1_max = ax_ins.get_ylim()
        y2_min, y2_max = ax_ins_r.get_ylim()

        global_min = min(y1_min, y2_min)
        global_max = max(y1_max, y2_max)

        ax_ins.set_ylim(-0.1, global_max)
        ax_ins_r.set_ylim(-0.1, global_max)

        ax_ins.set_xscale("log")
        ax_ins.set_xlim(MIN_T, 500 * MIN_T)

        ax_ins.grid(True, which="both", alpha=0.2)
        ax_ins.tick_params(labelsize=8)
        ax_ins_r.tick_params(labelsize=8)

    plt.show()


if __name__ == "__main__":
    run_simulations()
