import math

import numpy as np

import config


def signed_int_to_hex24(value):
    if not -(1 << 23) <= value <= (1 << 23) - 1:
        raise ValueError(f"{value} does not fit in signed 24-bit")
    if value < 0:
        value = (1 << 24) + value
    return f"{value:06X}"


def gain_for_span(v_min, v_max):
    gain = config.SPAN_TO_GAIN.get((v_min, v_max))
    if gain is None:
        raise ValueError(f"No known gain for voltage span ({v_min}, {v_max}) — add it to SPAN_TO_GAIN.")
    return gain


def interpolate_with_extrapolation(x, xp, fp):
    x = np.atleast_1d(np.asarray(x, dtype=np.float64))
    xp = np.asarray(xp, dtype=np.float64)
    fp = np.asarray(fp, dtype=np.float64)

    result = np.interp(x, xp, fp)

    below = x < xp[0]
    if np.any(below):
        slope = (fp[1] - fp[0]) / (xp[1] - xp[0])
        result[below] = fp[0] + slope * (x[below] - xp[0])

    above = x > xp[-1]
    if np.any(above):
        slope = (fp[-1] - fp[-2]) / (xp[-1] - xp[-2])
        result[above] = fp[-1] + slope * (x[above] - xp[-1])

    return result


def print_results(t_points, p_points, offset_enable, tadc_gain, tadc_offset, padc_gain, padc_offset,
                  coefficient_labels, coefficients, eeprom_coefficients, tadc, padc, dac_target,
                  normalization_scale, current_gain=None, target_gain=None):

    print('=' * 80)
    print(f'CALIBRATION SUMMARY - {t_points}T{p_points}P Configuration')
    print('=' * 80)
    print()
    if current_gain is not None and target_gain is not None:
        print(f"DAC gain: current={current_gain} -> target={target_gain}"
              f"{'  (using target-gain sweep table)' if current_gain != target_gain else '  (unchanged)'}")
        print()

    print('Calibration Settings:')
    print(f"{'Setting':<20} {'Value':<14} {'EEPROM (Hex)':>12}")
    print('-' * 48)
    print(f"{'OFF_EN':<20} {offset_enable:<14} {'0x{:02X}'.format(offset_enable):>12}")
    print(f"{'TADC_GAIN':<20} {tadc_gain:<14} {'0x{:06X}'.format(tadc_gain & 0xFFFFFF):>12}")
    print(f"{'TADC_OFFSET':<20} {tadc_offset:<14} {'0x{:06X}'.format(tadc_offset & 0xFFFFFF):>12}")
    print(f"{'PADC_GAIN':<20} {padc_gain:<14} {'0x{:06X}'.format(padc_gain & 0xFFFFFF):>12}")
    print(f"{'PADC_OFFSET':<20} {padc_offset:<14} {'0x{:06X}'.format(padc_offset & 0xFFFFFF):>12}")

    print()
    print('Coefficients:')
    print(f"{'Name':<6} {'Float Value':>16}   {'EEPROM (Hex)':>12}")
    print('-' * 38)
    for label, coefficient, eeprom_value in zip(coefficient_labels, coefficients, eeprom_coefficients):
        print(f"{label:<6} {coefficient:>16.6e}     0x{signed_int_to_hex24(eeprom_value)}")

    print()
    print('Calibration Point Comparison:')
    header = f"{'Point':<7} {'TADC (Hex)':<12} {'PADC (Hex)':<12} {'Expected':<10} {'Computed':<10} {'Error':<6}"
    print(header)
    print('-' * len(header))

    tadc_flat = tadc.flatten()
    padc_flat = padc.flatten()
    dac_target_flat = dac_target.flatten()

    errors = []
    point_index = 0
    for t_index in range(t_points):
        for p_index in range(p_points):
            tadc_value = tadc_flat[point_index]
            padc_value = padc_flat[point_index]
            expected = int(round(dac_target_flat[point_index]))

            if offset_enable:
                tadc_scaled = (tadc_value + tadc_offset) * tadc_gain
                padc_scaled = (padc_value + padc_offset) * padc_gain
            else:
                tadc_scaled = tadc_value * tadc_gain + tadc_offset
                padc_scaled = padc_value * padc_gain + padc_offset

            tadc_norm = tadc_scaled / normalization_scale
            padc_norm = padc_scaled / normalization_scale

            basis = []
            for j in range(p_points):
                for i in range(t_points):
                    basis.append((tadc_norm ** i) * (padc_norm ** j))
            basis = np.array(basis)

            computed = int(round(np.dot(coefficients, basis) * normalization_scale))
            error = abs(expected - computed)
            errors.append(error)

            print(f"T{t_index}P{p_index}    0x{signed_int_to_hex24(int(tadc_value))}   "
                  f"0x{signed_int_to_hex24(int(padc_value))}   0x{signed_int_to_hex24(expected)}   "
                  f"0x{signed_int_to_hex24(computed)}   {error:<6}")
            point_index += 1

    print()
    print('Error Statistics:')
    max_error = max(errors)
    mean_error = sum(errors) / len(errors)
    print(f"  Max Error:   {max_error:>6} codes  ({max_error * 1e6 / normalization_scale:>6.1f} ppm FSR)")
    print(f"  Mean Error:  {mean_error:>6.2f} codes  ({mean_error * 1e6 / normalization_scale:>6.1f} ppm FSR)")


def calculate_coefficients(dut, p_min=None, p_max=None, dac_fs_voltage=None,
                           current_v_min=None, current_v_max=None, print_details=True):

    t_points = dut.t_points
    p_points = dut.p_points
    adc_resolution_bits = dut.adc_resolution

    v_min = dut.v_min
    v_max = dut.v_max

    current_v_min_used = current_v_min if current_v_min is not None else config.V_MIN
    current_v_max_used = current_v_max if current_v_max is not None else config.V_MAX

    target_gain = gain_for_span(v_min, v_max)
    current_gain = gain_for_span(current_v_min_used, current_v_max_used)

    bracket_fs_voltage = dac_fs_voltage if dac_fs_voltage is not None else config.V_MAX

    pressure_values = list(dut.pressure_values)

    p_min_used = p_min if p_min is not None else min(pressure_values)
    p_max_used = p_max if p_max is not None else max(pressure_values)

    if p_max_used <= p_min_used:
        raise ValueError(f"p_max ({p_max_used}) must be greater than p_min ({p_min_used})")

    adc_min_code = -(2 ** (adc_resolution_bits - 1))
    adc_max_code = (2 ** (adc_resolution_bits - 1)) - 1

    normalization_scale = 2 ** (adc_resolution_bits - 2)
    coefficient_fixed_point_scale = 2 ** 30

    tadc, padc, dac_codes = [], [], []

    for t_index in range(t_points):
        tadc_row = list(dut.tadc_data[t_index])
        padc_row = list(dut.padc_data[t_index])
        dac_row = [int(x, 16) for x in dut.dac_data[t_index]]
        for value in tadc_row + padc_row:
            if value < adc_min_code or value > adc_max_code:
                raise ValueError(f"T{t_index}: value {value} exceeds {adc_resolution_bits}-bit ADC range "
                                 f"[{adc_min_code}, {adc_max_code}]")

        tadc.append(tadc_row)
        padc.append(padc_row)
        dac_codes.append(dac_row)

    tadc = np.array(tadc, dtype=np.float64)
    padc = np.array(padc, dtype=np.float64)
    dac_codes = np.array(dac_codes, dtype=np.float64)
    pressure_values = np.array(pressure_values, dtype=np.float64)

    sort_order = np.argsort(pressure_values)
    pressure_sorted = pressure_values[sort_order]

    for p_index in range(p_points):
        pressure = pressure_values[p_index]
        clamped_pressure = None
        if pressure > p_max_used:
            clamped_pressure = p_max_used
        elif pressure < p_min_used:
            clamped_pressure = p_min_used

        if clamped_pressure is not None:
            for t_index in range(t_points):
                padc[t_index, p_index] = np.interp(clamped_pressure, pressure_sorted, padc[t_index][sort_order])
                tadc[t_index, p_index] = np.interp(clamped_pressure, pressure_sorted, tadc[t_index][sort_order])
            if print_details:
                print(f"P{p_index}: pressure {pressure} outside new span [{p_min_used}, {p_max_used}] - "
                      f"replaced with PADC/TADC interpolated at {clamped_pressure} psi")
            pressure_values[p_index] = clamped_pressure

    padc_min = np.min(padc)
    padc_max = np.max(padc)
    tadc_min = np.min(tadc)
    tadc_max = np.max(tadc)

    padc_center = (padc_min + padc_max) / 2
    tadc_center = (tadc_min + tadc_max) / 2

    if config.OFF_EN:
        padc_offset = -int(padc_center)
        tadc_offset = -math.floor(tadc_center)

        padc_abs_max = max(abs(padc_min + padc_offset), abs(padc_max + padc_offset))
        tadc_abs_max = max(abs(tadc_min + tadc_offset), abs(tadc_max + tadc_offset))

        padc_gain = int(np.floor(adc_max_code / padc_abs_max))
        tadc_gain = int(np.floor(adc_max_code / tadc_abs_max))
        # Cap the TADC gain to avoid saturation
        tadc_gain = min(tadc_gain, config.TADC_GAIN_MAX)

        tadc_norm = ((tadc + tadc_offset) * tadc_gain) / normalization_scale
        padc_norm = ((padc + padc_offset) * padc_gain) / normalization_scale
    else:
        tadc_abs_max = max(abs(tadc_min), abs(tadc_max))
        padc_abs_max = max(abs(padc_min), abs(padc_max))

        padc_gain = int(np.floor(adc_max_code / padc_abs_max))
        tadc_gain = int(np.floor(adc_max_code / tadc_abs_max))

        tadc_offset = -math.floor(tadc_gain * tadc_center)
        padc_offset = -int(padc_gain * padc_center)

        tadc_norm = (tadc * tadc_gain + tadc_offset) / normalization_scale
        padc_norm = (padc * padc_gain + padc_offset) / normalization_scale

    has_dac_data = bool(dut.dmm_data or dut.dac_test_codes)

    if config.ENABLE_DAC_CORRECTION and has_dac_data:
        measured_dac_voltages = []
        
        for t_index in range(t_points):
            measured_dac_voltages.append([float(x.strip()) for x in dut.dmm_data[t_index]])
        measured_dac_voltages = np.array(measured_dac_voltages, dtype=np.float64)

        voltage_span = v_max - v_min
        dac_target = np.zeros((t_points, p_points))

        for t_index in range(t_points):
            # Fit measured voltage = a*code^2 + b*code + c, then solve for the code at each target voltage
            a, b, c = np.polyfit(dac_codes[t_index], measured_dac_voltages[t_index], 2)

            for p_index in range(p_points):
                target_voltage = v_min + (p_index / (p_points - 1)) * voltage_span
                discriminant = b**2 - 4*a*(c - target_voltage)

                if a == 0:
                    corrected_code = (target_voltage - c) / b
                elif discriminant >= 0:
                    corrected_code = (-b + np.sqrt(discriminant)) / (2*a)
                else:
                    raise ValueError(f"T{t_index}P{p_index}: no real DAC code gives {target_voltage} V")

                dac_target[t_index][p_index] = corrected_code
    else:
        dac_test_code_count = dac_codes.shape[1]

        if dac_test_code_count == p_points:
            if dut.dac_test_codes:
                dac_test_codes = [int(x.strip()) for x in dut.dac_test_codes]
                dac_target_row = np.array(dac_test_codes)
            else:
                dac_target_row = dac_codes[0]
        else:
            target_voltages = [
                v_min + ((pressure - p_min_used) / (p_max_used - p_min_used)) * (v_max - v_min)
                for pressure in pressure_values
            ]

            if target_gain != current_gain:
                # Gain is changing, so the codes this unit was tested against
                # (at current_gain) no longer describe its behavior at
                # target_gain. Use the characterized sweep for the target
                # gain instead of the production-test bracket data.
                sweep = config.DAC_CODE_VOLTAGE_SWEEPS.get(target_gain)
                if sweep is None:
                    raise ValueError(f"No fixed voltage sweep for gain {target_gain}")

                sweep_codes = sorted(sweep.keys())
                xp = np.array([sweep[code] for code in sweep_codes], dtype=np.float64)
                fp = np.array(sweep_codes, dtype=np.float64)
            else:
                if dac_test_code_count != len(config.DAC_TEST_CODE_FRACTIONS):
                    raise ValueError(
                        f"Don't know the bracket-voltage layout for {dac_test_code_count} DAC "
                        f"columns - update DAC_TEST_CODE_FRACTIONS in config."
                    )

                if not dut.dac_test_codes:
                    raise ValueError("DAC_Test_Codes required for bracket-based targeting.")

                dac_test_codes = np.array([int(x.strip()) for x in dut.dac_test_codes], dtype=np.float64)

                bracket_voltages = np.array(config.DAC_TEST_CODE_FRACTIONS) * bracket_fs_voltage
                xp, fp = bracket_voltages, dac_test_codes

            dac_target_row = interpolate_with_extrapolation(target_voltages, xp, fp)

        dac_target = np.tile(dac_target_row, (t_points, 1))

    dac_norm = dac_target / normalization_scale

    tadc_norm_flat = tadc_norm.flatten()
    padc_norm_flat = padc_norm.flatten()
    dac_norm_flat = dac_norm.flatten()

    coefficient_letters = ['h', 'g', 'n', 'm']
    coefficient_labels = []
    basis_columns = []
    for j in range(p_points):
        for i in range(t_points):
            coefficient_labels.append(f"{coefficient_letters[j]}{i}")
            basis_columns.append((tadc_norm_flat ** i) * (padc_norm_flat ** j))

    design_matrix = np.column_stack(basis_columns)

    coefficients, _, _, _ = np.linalg.lstsq(design_matrix, dac_norm_flat, rcond=None)
    eeprom_coefficients = [int(round(coefficient * coefficient_fixed_point_scale))
                           for coefficient in coefficients]

    if print_details:
        print_results(t_points, p_points, config.OFF_EN, tadc_gain, tadc_offset, padc_gain, padc_offset,
                      coefficient_labels, coefficients, eeprom_coefficients, tadc, padc, dac_target,
                      normalization_scale, current_gain=current_gain, target_gain=target_gain)

    settings = {
        'OFF_EN':      {'value': str(config.OFF_EN), 'hex': f"{config.OFF_EN:02X}"},
        'TADC_GAIN':   {'value': str(tadc_gain),     'hex': f"{tadc_gain & 0xFFFFFF:06X}"},
        'TADC_OFFSET': {'value': str(tadc_offset),   'hex': f"{tadc_offset & 0xFFFFFF:06X}"},
        'PADC_GAIN':   {'value': str(padc_gain),     'hex': f"{padc_gain & 0xFFFFFF:06X}"},
        'PADC_OFFSET': {'value': str(padc_offset),   'hex': f"{padc_offset & 0xFFFFFF:06X}"},
    }
    settings = {name: data for name, data in settings.items() if name in config.VALID_SETTINGS}

    coefficients_hex = {
        label: signed_int_to_hex24(eeprom_value)
        for label, eeprom_value in zip(coefficient_labels, eeprom_coefficients)
        if label in config.VALID_COEFFICIENTS
    }

    return coefficients_hex, settings