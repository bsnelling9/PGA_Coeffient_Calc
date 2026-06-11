import os
import configparser


# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────
ADC_RES       = 24
NORM_DATA     = 2 ** (ADC_RES - 2)   # 2^22
NORM_COEFF    = 2 ** 30
FULL_SCALE_V  = 10.0                  # 0–10V output
FULL_SCALE_P  = 1000.0                # 0–1000 PSI
DAC_FULL      = 12928                 # max DAC code = 10V

GAIN_OPTIONS  = [200, 400]            # V/V options to test

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CAL_DATA_DIR  = os.path.join(BASE_DIR, '..', 'Calibration_Data')
CAL_OUTPUT    = os.path.join(BASE_DIR, 'Brodie_Cal_Output.txt')


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────
def signed_24_to_int(hex_str):
    val = int(hex_str, 16)
    if val & 0x800000:
        val -= 0x1000000
    return val


def dac_to_voltage(dac_code):
    return (dac_code / DAC_FULL) * FULL_SCALE_V


def voltage_to_psi(voltage):
    return (voltage / FULL_SCALE_V) * FULL_SCALE_P


def dac_to_psi(dac_code):
    return voltage_to_psi(dac_to_voltage(dac_code))


# ─────────────────────────────────────────────
#  Load coefficients and settings from Cal Output
# ─────────────────────────────────────────────
def load_cal_output(filepath):
    settings = {}
    coeffs   = {}

    in_settings = False
    in_coeffs   = False

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()

            if 'Calibration Settings' in line:
                in_settings = True
                in_coeffs   = False
                continue
            if 'Coefficients' in line and 'Float' not in line:
                in_coeffs   = True
                in_settings = False
                continue
            if 'Calibration Point' in line:
                in_coeffs   = False
                in_settings = False
                continue
            if not line or line.startswith('-') or line.startswith('='):
                continue

            if in_settings:
                parts = line.split()
                if len(parts) >= 3:
                    settings[parts[0]] = parts[2].replace('0x', '').replace('0X', '')

            if in_coeffs:
                parts = line.split()
                if len(parts) >= 3 and parts[0][0] in 'hgnm':
                    coeffs[parts[0]] = signed_24_to_int(parts[2].replace('0x', '').replace('0X', ''))

    tadc_gain   = int(settings['TADC_GAIN'], 16)
    tadc_offset = signed_24_to_int(settings['TADC_OFFSET'])
    padc_gain   = int(settings['PADC_GAIN'], 16)
    padc_offset = signed_24_to_int(settings['PADC_OFFSET'])

    return tadc_gain, tadc_offset, padc_gain, padc_offset, coeffs


# ─────────────────────────────────────────────
#  Load DUT file
# ─────────────────────────────────────────────
def load_dut_file(pressure_code, serial_number):
    dut_path = os.path.join(CAL_DATA_DIR, pressure_code, f'{serial_number}.txt')

    if not os.path.exists(dut_path):
        raise FileNotFoundError(f"DUT file not found: {dut_path}")

    config = configparser.ConfigParser()
    config.read(dut_path)

    if 'ADC_DATA' not in config:
        raise ValueError("ADC_DATA section not found in DUT file")

    points = []
    for key, value in config['ADC_DATA'].items():
        key = key.upper()
        if not (key.startswith('T') and 'P' in key):
            continue
        parts = value.strip('"').split('\t')
        if len(parts) == 4:
            t_idx    = int(key[1])
            p_idx    = int(key[3])
            temp_c   = float(parts[0])
            tadc_val = int(parts[1])
            pres_psi = float(parts[2])
            padc_val = int(parts[3])
            points.append({
                'label':    f'T{t_idx}P{p_idx}',
                'temp_c':   temp_c,
                'tadc':     tadc_val,
                'pres_psi': pres_psi,
                'padc':     padc_val,
            })

    if 'DAC_DATA' not in config:
        raise ValueError("DAC_DATA section not found in DUT file")

    # Build expected DAC codes per T row
    dac_rows = {}
    for key, value in config['DAC_DATA'].items():
        key = key.upper()
        if key.startswith('T') and '.' not in key and len(key) == 2:
            t_idx = int(key[1])
            dac_rows[t_idx] = [int(v.strip()) for v in value.strip('"').split('\t')]

    # Attach expected DAC code and voltage to each point
    p_counts = {}
    for pt in points:
        t_idx = int(pt['label'][1])
        p_idx = int(pt['label'][3])
        if t_idx not in p_counts:
            p_counts[t_idx] = 0
        col = p_counts[t_idx]
        p_counts[t_idx] += 1

        if t_idx in dac_rows and col < len(dac_rows[t_idx]):
            pt['expected_dac'] = dac_rows[t_idx][col]
            pt['expected_v']   = dac_to_voltage(pt['expected_dac'])
            pt['expected_psi'] = dac_to_psi(pt['expected_dac'])
        else:
            pt['expected_dac'] = 0
            pt['expected_v']   = 0.0
            pt['expected_psi'] = 0.0

    return points


# ─────────────────────────────────────────────
#  Polynomial computation
# ─────────────────────────────────────────────
def compute_dac(tadc_val, padc_val,
                tadc_gain, tadc_offset,
                padc_gain, padc_offset,
                coeffs, t_points, p_points):

    ts = tadc_val * tadc_gain + tadc_offset
    ps = padc_val * padc_gain + padc_offset
    tn = ts / NORM_DATA
    pn = ps / NORM_DATA

    coeff_vars = ['h', 'g', 'n', 'm']
    result = 0.0
    for j in range(p_points):
        for i in range(t_points):
            name = f"{coeff_vars[j]}{i}"
            if name in coeffs:
                result += (tn ** i) * (pn ** j) * (coeffs[name] / NORM_COEFF)

    return int(round(result * NORM_DATA))


# ─────────────────────────────────────────────
#  Run test for one gain setting
# ─────────────────────────────────────────────
def run_test(points, tadc_gain, tadc_offset, padc_gain, padc_offset, coeffs, gain_vv):

    t_points = max(int(pt['label'][1]) for pt in points) + 1
    p_points = max(int(pt['label'][3]) for pt in points) + 1

    # Apply P_GAIN_SELECT scaling to padc_gain
    # 200 V/V or 400 V/V scales the effective padc_gain
    gain_scale = gain_vv / 200
    effective_padc_gain = padc_gain * gain_scale

    results = []
    for pt in points:
        computed_dac = compute_dac(
            pt['tadc'], pt['padc'],
            tadc_gain, tadc_offset,
            effective_padc_gain, padc_offset,
            coeffs, t_points, p_points
        )

        computed_v   = dac_to_voltage(computed_dac)
        computed_psi = dac_to_psi(computed_dac)
        error_psi    = abs(pt['expected_psi'] - computed_psi)
        error_pct    = (error_psi / FULL_SCALE_P) * 100

        results.append({
            **pt,
            'computed_dac': computed_dac,
            'computed_v':   computed_v,
            'computed_psi': computed_psi,
            'error_psi':    error_psi,
            'error_pct':    error_pct,
        })

    return results


# ─────────────────────────────────────────────
#  Print results table
# ─────────────────────────────────────────────
def print_results(results, gain_vv):
    print(f"\n{'='*90}")
    print(f"  RESULTS AT {gain_vv} V/V")
    print(f"{'='*90}")
    header = (f"{'Point':<8} {'Temp(°C)':>9} {'Pres(PSI)':>11} "
              f"{'Exp DAC':>9} {'Comp DAC':>9} "
              f"{'Exp(V)':>8} {'Comp(V)':>8} "
              f"{'Err(PSI)':>10} {'Err(%FS)':>10}")
    print(header)
    print('-' * 90)

    for r in results:
        print(f"{r['label']:<8} "
              f"{r['temp_c']:>9.2f} "
              f"{r['pres_psi']:>11.3f} "
              f"{r['expected_dac']:>9} "
              f"{r['computed_dac']:>9} "
              f"{r['expected_v']:>8.4f} "
              f"{r['computed_v']:>8.4f} "
              f"{r['error_psi']:>10.4f} "
              f"{r['error_pct']:>9.4f}%")

    errors    = [r['error_psi'] for r in results]
    max_err   = max(errors)
    mean_err  = sum(errors) / len(errors)
    max_pct   = (max_err  / FULL_SCALE_P) * 100
    mean_pct  = (mean_err / FULL_SCALE_P) * 100

    print(f"\n  Max Error:  {max_err:.4f} PSI  ({max_pct:.4f}% FS)")
    print(f"  Mean Error: {mean_err:.4f} PSI  ({mean_pct:.4f}% FS)")

    return max_err


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  PGA305 End-to-End Calibration Test")
    print("=" * 50)

    pressure_code = input("\nEnter pressure code (e.g. 64G): ").strip()
    serial_number = input("Enter serial number (e.g. 000001): ").strip()

    print(f"\nLoading DUT file:    {pressure_code}/{serial_number}.txt")
    print(f"Loading Cal Output:  Brodie_Cal_Output.txt")

    try:
        tadc_gain, tadc_offset, padc_gain, padc_offset, coeffs = load_cal_output(CAL_OUTPUT)
        points = load_dut_file(pressure_code, serial_number)
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        return
    except ValueError as e:
        print(f"\nERROR: {e}")
        return

    print(f"\nLoaded {len(points)} calibration points")
    print(f"Loaded {len(coeffs)} coefficients: {list(coeffs.keys())}")
    print(f"\nSettings:")
    print(f"  TADC_GAIN   = {tadc_gain}")
    print(f"  TADC_OFFSET = {tadc_offset}")
    print(f"  PADC_GAIN   = {padc_gain}")
    print(f"  PADC_OFFSET = {padc_offset}")

    max_errors = {}
    all_results = {}

    for gain_vv in GAIN_OPTIONS:
        results = run_test(
            points,
            tadc_gain, tadc_offset,
            padc_gain, padc_offset,
            coeffs, gain_vv
        )
        max_err = print_results(results, gain_vv)
        max_errors[gain_vv]  = max_err
        all_results[gain_vv] = results

    # ── Verdict ──
    likely_gain = min(max_errors, key=max_errors.get)
    other_gain  = [g for g in GAIN_OPTIONS if g != likely_gain][0]

    print(f"\n{'='*50}")
    print(f"  LIKELY CONFIGURED GAIN: {likely_gain} V/V")
    print(f"  Max error at {likely_gain} V/V: {max_errors[likely_gain]:.4f} PSI")
    print(f"  Max error at {other_gain} V/V: {max_errors[other_gain]:.4f} PSI")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()