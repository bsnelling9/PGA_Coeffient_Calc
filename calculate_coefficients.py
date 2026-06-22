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
                  names, coeffs, eeprom, tadc, padc, dac, norm_data,
                  dac_fit=None, dac_dmm=None):

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

    if dac_fit is not None:
        print('DAC Output-Stage Correction (from measured DAC_DMM data):')
        for t, (a, b, c) in enumerate(dac_fit):
            print(f"  T{t}: measured_V = {a:.6e} * code^2 + {b:.8f} * code + {c:.6f}")
        
        print("  (Calibration targets below are corrected for this before fitting h/g/n/m)")
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

    if dac_dmm is not None:
        header2 = f"{'Point':<7} {'Code':<10} {'DAC outputs (V)':<16} {'Ideal (V)':<10} {'Error (V)':<10} {'%FSO':<8}"
        print(header2)
        print('-' * len(header2))
        idx = 0
        fs_voltage = 10.0
        fso_errors = []
        
        for t in range(T_points):
            a, b, c = dac_fit[t]
            
            for pr in range(P_points):
                tadc_val = tadc_flat[idx]
                padc_val = padc_flat[idx]
                
                if off_en:
                    ts = (tadc_val + tadc_offset) * tadc_gain
                    ps = (padc_val + padc_offset) * padc_gain
                else:
                    ts = tadc_val * tadc_gain + tadc_offset
                    ps = padc_val * padc_gain + padc_offset
                
                tn, pn = ts / norm_data, ps / norm_data
                vec = np.array([(tn ** i) * (pn ** j) for j in range(P_points) for i in range(T_points)])
                code = np.dot(coeffs, vec) * norm_data
                
                actual_v = a * code**2 + b * code + c
                ideal_v = (pr / (P_points - 1)) * fs_voltage
                
                err_v = actual_v - ideal_v
                err_fso = abs(err_v) / fs_voltage * 100
                fso_errors.append(err_fso)
                
                print(f"T{t}P{pr}    {code:>8.1f}  {actual_v:>14.4f}  {ideal_v:>8.4f}  {err_v:>+9.4f}  {err_fso:>6.4f}%")
                idx += 1

        max_fso = max(fso_errors)
        
        if T_points not in (1, 3, 4):
            print(f"  NOTE: this run used {T_points} temperature point(s) — not one of TI's")
            print(f"        characterized configurations above, so there is no published")
            print(f"        accuracy guarantee to directly compare this result against.")
        else:
            spec_lookup = {1: 0.13, 3: 0.08, 4: 0.08}
            spec = spec_lookup[T_points]
            status = "PASS" if max_fso <= spec else "FAIL"
            print(f"  Closest TI spec row ({T_points} temp): {spec}% typ  ->  {status} (max {max_fso:.4f}%)")


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
    
    if 'DAC_DATA' in config:
        dac_dmm_rows = []
        for i in range(T_points):

            raw_val = config['DAC_DATA'][f'T{i}'].strip('"')
            v_row = [float(x.strip()) for x in raw_val.split(',')]
            dac_dmm_rows.append(v_row)
        dac_dmm = np.array(dac_dmm_rows, dtype=np.float64)

        fs_voltage = 10.0          

        dac_fit = []
        dac_corrected = np.zeros_like(dac)
        
        for t in range(T_points):
            codes_row = dac[t]
            volts_row = dac_dmm[t]
                        
            p_coeff = np.polyfit(codes_row, volts_row, 2)
            dac_fit.append(p_coeff) 
            
            for p in range(P_points):
                ideal_v = (p / (P_points - 1)) * fs_voltage             

                a, b, c = p_coeff
                c_prime = c - ideal_v
                discriminant = b**2 - 4*a*c_prime
                
                if discriminant >= 0 and a != 0:
                    corrected_code = (-b + np.sqrt(discriminant)) / (2*a)
                else:
                   
                    corrected_code = (ideal_v - b) / a
                    
                dac_corrected[t][p] = corrected_code

        D_norm = dac_corrected / norm_data
    else:
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
                  names, coeffs, eeprom, tadc, padc, dac, norm_data,
                  dac_fit=dac_fit, dac_dmm=dac_dmm)

    with open(output_file, 'w') as f:
        sys.stdout = f
        print_results(T_points, P_points, off_en, tadc_gain, tadc_offset, padc_gain, padc_offset,
                      names, coeffs, eeprom, tadc, padc, dac, norm_data,
                      dac_fit=dac_fit, dac_dmm=dac_dmm)
        sys.stdout = sys.__stdout__

    print(f"Output written to {output_file}")


if __name__ == "__main__":
    calculate_coefficients()