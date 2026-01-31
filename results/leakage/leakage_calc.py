import sys

import matplotlib.pyplot as plt
import numpy as np

csv_filename = "/home/michele/MicroDosimeter/src/measurement_I_leak.csv"
CAPACITANCE = 99.73  # pF

# ---------------------------------------------------------
# 2. READ DATA
# ---------------------------------------------------------

try:
    # delimiter=',' : The file is comma separated
    # skiprows=1    : Ignore the first row containing text metadata
    # usecols=(0,1) : Only load column 0 (Time) and column 1 (Value)
    data = np.loadtxt(csv_filename, delimiter=",", skiprows=1, usecols=(0, 1))
except OSError:
    print(f"Error: The file '{csv_filename}' was not found.")
    sys.exit()

# Save columns in two separate arrays
# data[:, 0] means "all rows, column 0"
time_array = data[:, 0]
value_array = data[:, 1] * 5 / 2**12 * CAPACITANCE

print(f"File loaded. Total points: {len(time_array)}")
print(f"Time range available: {time_array[0]:.4f} to {time_array[-1]:.4f}")

# 3 interval
# 1800 -> 2800
# 2900 -> 4400
# 4550 -> 6200

start_t1 = 1850
end_t1 = 2800
start_t2 = 2900
end_t2 = 4438
start_t3 = 4551
end_t3 = 6200


# ---------------------------------------------------------
# 4. FILTER DATA
# ---------------------------------------------------------
# We create a boolean mask (an array of True/False)
mask1 = (time_array >= start_t1) & (time_array <= end_t1)
mask2 = (time_array >= start_t2) & (time_array <= end_t2)
mask3 = (time_array >= start_t3) & (time_array <= end_t3)

mask_list = [mask1, mask2, mask3]

charge = []
current = []
values = []
times = []
interval = 40
for mask in mask_list:
    # Apply the mask to get only the selected interval
    t_selected = time_array[mask]
    v_selected = value_array[mask]

    if len(t_selected) < 2:
        print("Not enough points in the selected range to calculate a slope.")
        sys.exit()

    for i in range(0, len(v_selected), interval):
        j = i + interval

        if j > len(v_selected):
            break

        slope_i, _ = np.polyfit(t_selected[i:j], v_selected[i:j], 1)

        if slope_i < 0:
            current.append(-slope_i * 1000)
            charge.append(v_selected[int(i + interval / 2)])

    values.append(v_selected)
    times.append(t_selected)

# ---------------------------------------------------------
# 6. PLOT
# ---------------------------------------------------------

# for i, val in enumerate(values):
#     tm = times[i]
#     plt.figure(figsize=(10, 6))
#
#     # Plot the raw selected data points
#     plt.scatter(t_selected, v_selected, label="Selected Data", color="blue")
#
#     slope, intercept = np.polyfit(tm, val, 1)
#
#     # Calculate the regression line for visualization
#     # y = mx + q
#     line_values = slope * tm + intercept
#
#     # Plot the regression line
#     plt.plot(tm, line_values, color="red", linestyle="--", label=f"Slope = {slope:.4f}")
#
#     plt.xlabel("Time (Column 0)")
#     plt.ylabel("Value (Column 1)")
#     # plt.title(f"Data Analysis ({start_t}s - {end_t}s)")
#     plt.legend()
#     plt.grid(True)
#     plt.show()

plt.rcParams.update(
    {
        "text.usetex": True,  # Use LaTeX
        "font.family": "serif",  # Same as default LaTeX
        "font.size": 14,  # Global font size
        "axes.labelsize": 16,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 14,
    }
)

tension = [ch / CAPACITANCE for ch in charge]

plt.scatter(tension, current, color="blue", zorder=3)

plt.xlabel("Voltage [$V$]")  # LaTeX math works
plt.ylabel("Leakage Current [$fA$]")
# plt.title(r"\LaTeX\ integrated plot")

plt.grid(True, zorder=0)
plt.tight_layout()
plt.savefig("leakage_current.pdf")
plt.show()

# plt.figure(figsize=(10, 6))
#
# plt.xlabel("Charge [pC]")
# plt.ylabel("Leakage Current [fA]")
#
#
# plt.show()


# ==========================================================


try:
    start_t = float(input("Enter starting time: "))
    end_t = float(input("Enter ending time: "))
except ValueError:
    print("Invalid input. Please enter numeric values.")
    sys.exit()

if start_t >= end_t:
    print("Error: Start time must be smaller than end time.")
    sys.exit()

show = input("Show full graph [y/n]")
if show == "y":
    show = True
else:
    show = False

mask = (time_array >= start_t) & (time_array <= end_t)

t_selected = time_array[mask]
v_selected = value_array[mask]

# Use numpy.polyfit to fit a 1st degree polynomial (a line)
# It returns coefficients [slope, intercept]
# Calculate Slope and Intercept
slope, intercept = np.polyfit(t_selected, v_selected, 1)

# Calculate predicted values (y = mx + q)
v_predicted = slope * t_selected + intercept

# --- Calculate R-Squared (R^2) ---
# Calculate Sum of Squares of Residuals (SS_res)
residuals = v_selected - v_predicted
ss_res = np.sum(residuals**2)

# Calculate Total Sum of Squares (SS_tot)
v_mean = np.mean(v_selected)
ss_tot = np.sum((v_selected - v_mean) ** 2)

# Calculate R^2
# Handle division by zero if all values are identical
if ss_tot == 0:
    r_squared = 0.0
else:
    r_squared = 1 - (ss_res / ss_tot)

print("\n--- Analysis Results ---")
print(f"Slope (m): {slope:.5f}")
print(f"Intercept (q): {intercept:.5f}")
print(f"R-squared: {r_squared:.5f}")


plt.figure(figsize=(10, 6))

# Plot the raw selected data points
plt.scatter(t_selected, v_selected, label="Selected Data", color="blue")

# Calculate the regression line for visualization
# y = mx + q
line_values = slope * t_selected + intercept

# Plot the regression line
plt.plot(
    t_selected, line_values, color="red", linestyle="--", label=f"Slope = {slope:.4f}"
)

if show:
    # (Optional) Plot the rest of the data in grey to show context
    plt.scatter(
        time_array,
        value_array,
        color="gray",
        alpha=0.2,
        s=10,
        zorder=0,
        label="Full Data",
    )


plt.xlabel("Time (Column 0)")
plt.ylabel("Value (Column 1)")
# plt.title(f"Data Analysis ({start_t}s - {end_t}s)")
plt.legend()
plt.grid(True)
plt.show()
