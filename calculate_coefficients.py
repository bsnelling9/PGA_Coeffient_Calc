import configparser
import numpy as np
import math
import sys


def signed_int_to_hex24(value):
    if value < 0:
        value = (1 << 24) + value
    return hex(value)[2:].upper().zfill(6)


def parse_value(s):
    s = s.strip()
    if s.startswith('0x') or s.startswith('0X'):
        return int(s, 16)
    try:
        return int(s)
    except ValueError:
        return int(s, 16)


def print_results(T_points, P_points, off_en, tadc_gain, tadc_offset, padc_gain, padc_offset,
                  names, coeffs, eeprom, tadc, padc, dac, norm_data):

    print('=' * 80)
    print(f'CALIBRATION SUMMARY - {T_points}T{P_points}P Configuration')
    print('=' * 80)
    print()
    print('Calibration Settings:')
    print(f"{'Setting':<20} {'Value':<14} {'EEPROM (Hex)':>14}")
    print('-' * 50)
    print(f"{'OFF_EN':<20} {off_en:<14} {'0x{:02X}'.format(off_en):>14}")
    print(f"{'TADC_GAIN':<20} {tadc_gain:<14} {'0x{:06X}'.format(tadc_gain & 0xFFFFFF):>14}")
    print(f"{'TADC_OFFSET':<20} {tadc_offset:<14} {'0x{:06X}'.format(tadc_offset & 0xFFFFFF):>14}")
    print(f"{'PADC_GAIN':<20} {padc_gain:<14} {'0x{:06X}'.format(padc_gain & 0xFFFFFF):>14}")
    print(f"{'PADC_OFFSET':<20} {padc_offset:<14} {'0x{:06X}'.format(padc_offset & 0xFFFFFF):>14}")
    print()
    print('Calibration Settings Verification:')
    print(f"  PADC anchor point (room temp, 0 PSI): {int(padc.flatten()[0])}")
    print(f"  PADC range after offset:")
    padc_flat = padc.flatten()
    for i, val in enumerate(padc_flat):
        shifted = val * padc_gain + padc_offset
        pn = shifted / norm_data
        status = "WARNING: NEGATIVE" if pn < 0 else "OK"
        print(f"    Point {i}: raw={int(val):>10}  shifted={int(shifted):>12}  pn={pn:>8.4f}  {status}")
    print()
    print('Coefficients:')
    print(f"{'Name':<6} {'Float Value':>16}   {'EEPROM (Hex)':>12}")
    print('-' * 38)
    for name, c, e in zip(names, coeffs, eeprom):
        print(f"{name:<6} {c:>16.6e}     0x{signed_int_to_hex24(e)}")

    print()
    print('Calibration Point Comparison:')
    header = f"{'Point':<7} {'TADC (Hex)':<14} {'PADC (Hex)':<14} {'Expected':<10} {'Computed':<10} {'Error':<6}"
    print(header)
    print('-' * len(header))

    tadc_flat = tadc.flatten()
    padc_flat = padc.flatten()
    dac_flat  = dac.flatten()

    errors = []
    idx = 0
    for t in range(T_points):
        for pr in range(P_points):
            tadc_val = tadc_flat[idx]
            padc_val = padc_flat[idx]
            expected = int(dac_flat[idx])

            if off_en:
                ts = (tadc_val + tadc_offset) * tadc_gain
                ps = (padc_val + padc_offset) * padc_gain
            else:
                ts = tadc_val * tadc_gain + tadc_offset
                ps = padc_val * padc_gain + padc_offset

            tn = ts / norm_data
            pn = ps / norm_data

            vec = []
            for j in range(P_points):
                for i in range(T_points):
                    vec.append((tn ** i) * (pn ** j))
            vec = np.array(vec)

            computed = int(round(np.dot(coeffs, vec) * norm_data))
            error = abs(expected - computed)
            errors.append(error)

            print(f"T{t}P{pr}    0x{signed_int_to_hex24(int(tadc_val))}   0x{signed_int_to_hex24(int(padc_val) & 0xFFFFFF)}   0x{signed_int_to_hex24(expected)}   0x{signed_int_to_hex24(computed)}   {error}")
            idx += 1

    print()
    print('Error Statistics:')
    max_err  = max(errors)
    mean_err = sum(errors) / len(errors)
    print(f"  Max Error:   {max_err:>6} codes  ({max_err * 1e6 / norm_data:>6.1f} ppm FSR)")
    print(f"  Mean Error:  {mean_err:>6.2f} codes  ({mean_err * 1e6 / norm_data:>6.1f} ppm FSR)")


def calculate_coefficients(cal_input_file='Cal_Input.txt', output_file='Brodie_Cal_Output.txt', off_en=0):
    config = configparser.ConfigParser()
    config.read(cal_input_file)

    T_points  = int(config['General']['T_points'])
    P_points  = int(config['General']['P_points'])
    adc_res   = int(config['General']['adc_resolution'])
    norm_data  = 2 ** (adc_res - 2)
    norm_coeff = 2 ** 30

    tadc, padc, dac = [], [], []
    for i in range(T_points):
        t_row = [parse_value(x) for x in config['TADC'][f'T{i}'][1:-1].split(',')]
        p_row = [parse_value(x) for x in config['PADC'][f'T{i}'][1:-1].split(',')]
        d_row = [int(x.strip(), 16) for x in config['DAC'][f'T{i}'][1:-1].split(',')]
        tadc.append(t_row)
        padc.append(p_row)
        dac.append(d_row)

    tadc = np.array(tadc, dtype=np.float64)
    padc = np.array(padc, dtype=np.float64)
    dac  = np.array(dac,  dtype=np.float64)

    padc_min = np.min(padc)
    padc_max = np.max(padc)
    tadc_min = np.min(tadc)
    tadc_max = np.max(tadc)

    # Room temperature 0 PSI anchor point — T0P0 is always room temp, 0 PSI
    # This ensures pn = 0 at room temp zero pressure, preventing negative pn
    # clamping the DAC output to zero below the midpoint of the pressure range.
    # NOTE: if sub-zero temperatures are added, room temperature must still be T0.
    padc_zero_anchor = padc[0][0]

    if off_en:
        # OFF_EN=1: center first, then gain
        # PADC anchored to room temp 0 PSI instead of midpoint
        padc_offset = -int(padc_zero_anchor)
        tadc_offset = -math.floor((tadc_min + tadc_max) / 2)

        padc_abs_max = max(abs(padc_min + padc_offset), abs(padc_max + padc_offset))
        tadc_abs_max = max(abs(tadc_min + tadc_offset), abs(tadc_max + tadc_offset))

        padc_gain = int(np.floor((2**(adc_res-1) - 1) / padc_abs_max))
        tadc_gain = int(np.floor((2**(adc_res-1) - 1) / tadc_abs_max))

        T_norm = ((tadc + tadc_offset) * tadc_gain) / norm_data
        P_norm = ((padc + padc_offset) * padc_gain) / norm_data
    else:
        # OFF_EN=0: gain first, then offset
        tadc_abs_max = max(abs(tadc_min), abs(tadc_max))
        padc_abs_max = max(abs(padc_min), abs(padc_max))

        padc_gain = int(np.floor((2**(adc_res-1) - 1) / padc_abs_max))
        tadc_gain = int(np.floor((2**(adc_res-1) - 1) / tadc_abs_max))

        # TADC offset: standard midpoint centering (unchanged)
        tadc_offset = -math.floor(tadc_gain * (tadc_min + tadc_max) / 2)

        # PADC offset: anchored to room temp 0 PSI (T0P0) instead of midpoint
        # This prevents pn going negative below 500 PSI and clamping DAC to zero
        padc_offset = -int(padc_gain * padc_zero_anchor)

        T_norm = (tadc * tadc_gain + tadc_offset) / norm_data
        P_norm = (padc * padc_gain + padc_offset) / norm_data

    D_norm = dac / norm_data

    T_flat = T_norm.flatten()
    P_flat = P_norm.flatten()
    D_flat = D_norm.flatten()

    coeff_vars = ['h', 'g', 'n', 'm']
    names    = []
    features = []
    for j in range(P_points):
        for i in range(T_points):
            names.append(f"{coeff_vars[j]}{i}")
            features.append((T_flat ** i) * (P_flat ** j))

    A = np.column_stack(features)

    coeffs, _, _, _ = np.linalg.lstsq(A, D_flat, rcond=None)
    eeprom = [int(round(c * norm_coeff)) for c in coeffs]

    print_results(T_points, P_points, off_en, tadc_gain, tadc_offset, padc_gain, padc_offset,
                  names, coeffs, eeprom, tadc, padc, dac, norm_data)

    with open(output_file, 'w') as f:
        sys.stdout = f
        print_results(T_points, P_points, off_en, tadc_gain, tadc_offset, padc_gain, padc_offset,
                      names, coeffs, eeprom, tadc, padc, dac, norm_data)
        sys.stdout = sys.__stdout__

    print(f"Output written to {output_file}")


if __name__ == "__main__":
    calculate_coefficients()