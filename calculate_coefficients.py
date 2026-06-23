import configparser
import numpy as np
import math
import sys
import config


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
                  names, coeffs, eeprom, tadc, padc, dac_target, norm_data):

    print('=' * 80)
    print(f'CALIBRATION SUMMARY - {T_points}T{P_points}P Configuration')
    print('=' * 80)
    print()
    print('Calibration Settings:')
    print(f"{'Setting':<20} {'Value':<14} {'EEPROM (Hex)':>12}")
    print('-' * 48)
    print(f"{'OFF_EN':<20} {off_en:<14} {'0x{:02X}'.format(off_en):>12}")
    print(f"{'TADC_GAIN':<20} {tadc_gain:<14} {'0x{:06X}'.format(tadc_gain & 0xFFFFFF):>12}")
    print(f"{'TADC_OFFSET':<20} {tadc_offset:<14} {'0x{:06X}'.format(tadc_offset & 0xFFFFFF):>12}")
    print(f"{'PADC_GAIN':<20} {padc_gain:<14} {'0x{:06X}'.format(padc_gain & 0xFFFFFF):>12}")
    print(f"{'PADC_OFFSET':<20} {padc_offset:<14} {'0x{:06X}'.format(padc_offset & 0xFFFFFF):>12}")

    print()
    print('Coefficients:')
    print(f"{'Name':<6} {'Float Value':>16}   {'EEPROM (Hex)':>12}")
    print('-' * 38)
    for name, c, e in zip(names, coeffs, eeprom):
        print(f"{name:<6} {c:>16.6e}     0x{signed_int_to_hex24(e)}")

    print()
    print('Calibration Point Comparison:')
    header = f"{'Point':<7} {'TADC (Hex)':<12} {'PADC (Hex)':<12} {'Expected':<10} {'Computed':<10} {'Error':<6}"
    print(header)
    print('-' * len(header))

    tadc_flat = tadc.flatten()
    padc_flat = padc.flatten()
    dac_target_flat = dac_target.flatten()

    errors = []
    idx = 0
    for t in range(T_points):
        for pr in range(P_points):
            tadc_val = tadc_flat[idx]
            padc_val = padc_flat[idx]
            expected = int(round(dac_target_flat[idx]))

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

            print(f"T{t}P{pr}    0x{signed_int_to_hex24(int(tadc_val))}   0x{signed_int_to_hex24(int(padc_val) & 0xFFFFFF)}   0x{signed_int_to_hex24(expected)}   0x{signed_int_to_hex24(computed)}   {error:<6}")
            idx += 1

    print()
    print('Error Statistics:')
    max_err  = max(errors)
    mean_err = sum(errors) / len(errors)
    print(f"  Max Error:   {max_err:>6} codes  ({max_err * 1e6 / norm_data:>6.1f} ppm FSR)")
    print(f"  Mean Error:  {mean_err:>6.2f} codes  ({mean_err * 1e6 / norm_data:>6.1f} ppm FSR)")


def calculate_coefficients(cal_input_file='Cal_Input.txt', output_file='Brodie_Cal_Output.txt', off_en=0):
    cal_config = configparser.ConfigParser()
    cal_config.read(cal_input_file)

    T_points = int(cal_config['General']['T_points'])
    P_points = int(cal_config['General']['P_points'])
    adc_res  = int(cal_config['General']['adc_resolution'])

    v_min = float(cal_config['General'].get('v_min', config.V_MIN))
    v_max = float(cal_config['General'].get('v_max', config.V_MAX))
    pressure_span_psi = float(cal_config['General'].get('pressure_span_psi', config.DEFAULT_PRESSURE_SPAN_PSI))

    min_code = -(2 ** (adc_res - 1))
    max_code = (2 ** (adc_res - 1)) - 1

    norm_data  = 2 ** (adc_res - 2)
    norm_coeff = 2 ** 30

    tadc, padc, dac = [], [], []
    for i in range(T_points):
        t_row = [parse_value(x) for x in cal_config['TADC'][f'T{i}'][1:-1].split(',')]
        p_row = [parse_value(x) for x in cal_config['PADC'][f'T{i}'][1:-1].split(',')]
        d_row = [int(x.strip(), 16) for x in cal_config['DAC'][f'T{i}'][1:-1].split(',')]
        for v in t_row + p_row:
            if v < min_code or v > max_code:
                raise ValueError(f"T{i}: value {v} exceeds {adc_res}-bit ADC range [{min_code}, {max_code}]")

        tadc.append(t_row)
        padc.append(p_row)
        dac.append(d_row)

    tadc = np.array(tadc, dtype=np.float64)
    padc = np.array(padc, dtype=np.float64)
    dac  = np.array(dac, dtype=np.float64)

    padc_min = np.min(padc)
    padc_max = np.max(padc)
    tadc_min = np.min(tadc)
    tadc_max = np.max(tadc)

    padc_zero_anchor = padc[0][0]

    if off_en:
        padc_offset = -int(padc_zero_anchor)
        tadc_offset = -math.floor((tadc_min + tadc_max) / 2)

        padc_abs_max = max(abs(padc_min + padc_offset), abs(padc_max + padc_offset))
        tadc_abs_max = max(abs(tadc_min + tadc_offset), abs(tadc_max + tadc_offset))

        padc_gain = int(np.floor((2**(adc_res-1) - 1) / padc_abs_max))
        tadc_gain = int(np.floor((2**(adc_res-1) - 1) / tadc_abs_max))

        T_norm = ((tadc + tadc_offset) * tadc_gain) / norm_data
        P_norm = ((padc + padc_offset) * padc_gain) / norm_data
    else:

        tadc_abs_max = max(abs(tadc_min), abs(tadc_max))
        padc_abs_max = max(abs(padc_min), abs(padc_max))

        padc_gain = int(np.floor((2**(adc_res-1) - 1) / padc_abs_max))
        tadc_gain = int(np.floor((2**(adc_res-1) - 1) / tadc_abs_max))

        tadc_offset = -math.floor(tadc_gain * (tadc_min + tadc_max) / 2)

        padc_offset = -int(padc_gain * padc_zero_anchor)

        T_norm = (tadc * tadc_gain + tadc_offset) / norm_data
        P_norm = (padc * padc_gain + padc_offset) / norm_data

    dac_fit = None
    dac_dmm = None

    if 'DAC_DATA' in cal_config:
        dac_dmm_rows = []

        for i in range(T_points):
            raw_val = cal_config['DAC_DATA'][f'T{i}'].strip('"')
            v_row = [float(x.strip()) for x in raw_val.split(',')]
            dac_dmm_rows.append(v_row)

        dac_dmm = np.array(dac_dmm_rows, dtype=np.float64)

        fs_voltage = v_max - v_min

        dac_fit = []
        dac_corrected = np.zeros_like(dac)

        for t in range(T_points):
            codes_row = dac[t]
            volts_row = dac_dmm[t]

            p_coeff = np.polyfit(codes_row, volts_row, 2)
            dac_fit.append(p_coeff)

            for p in range(P_points):
                ideal_v = v_min + (p / (P_points - 1)) * fs_voltage

                a, b, c = p_coeff
                c_prime = c - ideal_v
                discriminant = b**2 - 4*a*c_prime

                if discriminant >= 0 and a != 0:
                    corrected_code = (-b + np.sqrt(discriminant)) / (2*a)
                else:
                    corrected_code = (ideal_v - b) / a

                dac_corrected[t][p] = corrected_code

        # The fit target is the DAC-corrected codes, not the raw nominal
        # dac codes — this is what print_results compares against.
        dac_target = dac_corrected
        D_norm = dac_corrected / norm_data
    else:
        # No DAC_DMM data, so there's nothing to correct against —
        # the raw nominal codes are the fit target as-is.
        dac_target = dac
        D_norm = dac / norm_data

    T_flat = T_norm.flatten()
    P_flat = P_norm.flatten()
    D_flat = D_norm.flatten()

    coeff_vars = ['h', 'g', 'n', 'm']
    coeff_label = []
    coeff_value = []
    for j in range(P_points):
        for i in range(T_points):
            coeff_label.append(f"{coeff_vars[j]}{i}")
            coeff_value.append((T_flat ** i) * (P_flat ** j))

    A = np.column_stack(coeff_value)

    coeffs, _, _, _ = np.linalg.lstsq(A, D_flat, rcond=None)
    eeprom = []
    for coefficient in coeffs:
        fixed_point_value = coefficient * norm_coeff
        eeprom.append(int(round(fixed_point_value)))

    print_results(T_points, P_points, off_en, tadc_gain, tadc_offset, padc_gain, padc_offset,
                  coeff_label, coeffs, eeprom, tadc, padc, dac_target, norm_data)

    with open(output_file, 'w') as f:
        sys.stdout = f
        print_results(T_points, P_points, off_en, tadc_gain, tadc_offset, padc_gain, padc_offset,
                      coeff_label, coeffs, eeprom, tadc, padc, dac_target, norm_data)
        sys.stdout = sys.__stdout__

    print(f"Output written to {output_file}")


if __name__ == "__main__":
    calculate_coefficients()