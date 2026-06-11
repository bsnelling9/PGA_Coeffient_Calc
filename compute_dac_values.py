import configparser


def signed_24_to_int(hex_str):
    val = int(hex_str, 16)
    if val & 0x800000:
        val -= 0x1000000
    return val


def parse_value(s):
    s = s.strip()
    if s.startswith('0x') or s.startswith('0X'):
        return int(s, 16)
    try:
        return int(s)
    except ValueError:
        return int(s, 16)


def compute_dac_values(cal_input_file='Cal_Input.txt', cal_output_file='Brodie_Cal_Output.txt'):

    settings = {}
    coeffs   = {}

    in_settings = False
    in_coeffs   = False

    with open(cal_output_file, 'r') as f:
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
    adc_res     = 24
    norm_data   = 2 ** (adc_res - 2)
    norm_coeff  = 2 ** 30

    print(f"Loaded settings:")
    print(f"  TADC_GAIN   = {tadc_gain}")
    print(f"  TADC_OFFSET = {tadc_offset}")
    print(f"  PADC_GAIN   = {padc_gain}")
    print(f"  PADC_OFFSET = {padc_offset}")
    print(f"\nLoaded {len(coeffs)} coefficients: {list(coeffs.keys())}")

    config = configparser.ConfigParser()
    config.read(cal_input_file)

    T_points = int(config['General']['T_points'])
    P_points = int(config['General']['P_points'])

    tadc, padc, dac = [], [], []
    for i in range(T_points):
        t_row = [parse_value(x) for x in config['TADC'][f'T{i}'][1:-1].split(',')]
        p_row = [parse_value(x) for x in config['PADC'][f'T{i}'][1:-1].split(',')]
        d_row = [int(x.strip(), 16) for x in config['DAC'][f'T{i}'][1:-1].split(',')]
        tadc.append(t_row)
        padc.append(p_row)
        dac.append(d_row)

    print(f"\n{'='*80}")
    print(f"DAC VERIFICATION - {T_points}T{P_points}P")
    print(f"{'='*80}")
    header = f"{'Point':<7} {'TADC':>12} {'PADC':>12} {'Expected':>10} {'Computed':>10} {'Error':>8}"
    print(header)
    print('-' * len(header))

    coeff_vars = ['h', 'g', 'n', 'm']
    errors = []

    for t in range(T_points):
        for p in range(P_points):
            tadc_val = tadc[t][p]
            padc_val = padc[t][p]
            expected = dac[t][p]

            ts = tadc_val * tadc_gain + tadc_offset
            ps = padc_val * padc_gain + padc_offset
            tn = ts / norm_data
            pn = ps / norm_data

            result = 0.0
            for j in range(P_points):
                for i in range(T_points):
                    name = f"{coeff_vars[j]}{i}"
                    if name in coeffs:
                        result += (tn ** i) * (pn ** j) * (coeffs[name] / norm_coeff)

            computed = int(round(result * norm_data))
            error = abs(expected - computed)
            errors.append(error)

            print(f"T{t}P{p}    {tadc_val:>12}  {padc_val:>12}  0x{expected:06X}  0x{computed:06X}  {error:>8}")

    print(f"\nMax Error:  {max(errors)} codes")
    print(f"Mean Error: {sum(errors)/len(errors):.2f} codes")


if __name__ == "__main__":
    compute_dac_values()