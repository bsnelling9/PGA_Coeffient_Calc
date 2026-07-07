import os
import configparser
import config


class CreateCalInputFile:

    def __init__(self, pressure_code, serial_number, base_path=None, config_path=None, adc_resolution=None, v_min=None, v_max=None, pressure_span=None):

        self.pressure_code = pressure_code
        self.serial_number = serial_number
        self.base_path = base_path or config.BASE_PATH
        self.config_path = config_path or config.CONFIG_PATH
        self.adc_resolution = adc_resolution or config.ADC_RESOLUTION
        self.v_min = v_min if v_min is not None else config.V_MIN
        self.v_max = v_max if v_max is not None else config.V_MAX
        self.pressure_span = pressure_span or config.DEFAULT_PRESSURE_SPAN_PSI

        self.dut_path = os.path.join(self.base_path, pressure_code, f'{serial_number}.txt')
        self.cal_points = None

        self.tadc_data = {}
        self.padc_data = {}
        self.dac_data  = {}
        self.dmm_data  = {}
        self.t_points  = 0
        self.p_points  = 0

    def read_part_config(self):
        config_file = os.path.join(self.config_path, f'{self.pressure_code}.ini')

        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Part configuration file not found: {config_file}")

        part_config = configparser.ConfigParser()
        part_config.read(config_file)

        if 'Default Cal' not in part_config:
            raise ValueError(f"Default Cal section not found in {config_file}")

        p_cal_points = part_config['Default Cal']['P Cal Points'].strip('"')
        self.cal_points = [int(x.strip()) for x in p_cal_points.split(',')]

        if part_config.has_option('Default Cal', 'Pressure Span PSI'):
            self.pressure_span = float(part_config['Default Cal']['Pressure Span PSI'])

        if part_config.has_option('Default Cal', 'V Min'):
            self.v_min = float(part_config['Default Cal']['V Min'])

        if part_config.has_option('Default Cal', 'V Max'):
            self.v_max = float(part_config['Default Cal']['V Max'])

        print(f"Read part config: {config_file}")
        print(f"P Cal Points: {self.cal_points}")
        print(f"Pressure Span (psi): {self.pressure_span}, V Min: {self.v_min}, V Max: {self.v_max}")

    def read_dut_file(self):
        if not os.path.exists(self.dut_path):
            raise FileNotFoundError(f"DUT file not found: {self.dut_path}")

        dut_config = configparser.ConfigParser()
        dut_config.read(self.dut_path)

        if 'ADC_DATA' not in dut_config:
            raise ValueError("ADC_DATA section not found in DUT file")

        adc_raw = {}
        for key, value in dut_config['ADC_DATA'].items():
            key = key.upper()
            parts = value.strip('"').split('\t')
            if len(parts) == 4:
                t_idx = int(key[1])
                p_idx = int(key[3])
                adc_raw[(t_idx, p_idx)] = {
                    'tadc': int(parts[1]),
                    'padc': int(parts[3])
                }

        max_t = max(k[0] for k in adc_raw.keys()) + 1
        max_p = max(k[1] for k in adc_raw.keys()) + 1
        self.t_points = max_t

        if self.cal_points is None:
            self.cal_points = list(range(max_p))
        self.p_points = len(self.cal_points)

        for t in range(max_t):
            self.tadc_data[t] = []
            self.padc_data[t] = []

            for p in self.cal_points:
                if (t, p) in adc_raw:
                    self.tadc_data[t].append(adc_raw[(t, p)]['tadc'])
                    self.padc_data[t].append(adc_raw[(t, p)]['padc'])
                else:
                    print(f"WARNING: Missing data point T{t}P{p} — using 0")
                    self.tadc_data[t].append(0)
                    self.padc_data[t].append(0)

        if 'DAC_DATA' not in dut_config:
            raise ValueError("DAC_DATA section not found in DUT file")

        for key, value in dut_config['DAC_DATA'].items():
            key = key.upper()

            if key.startswith('T') and len(key) >= 2:
                parts = value.strip('"').split('\t')

                if '.DMM' in key:
                    t_idx = int(key[1])
                    dmm_values = []
                    for p in self.cal_points:
                        if p < len(parts):
                            dmm_values.append(parts[p].strip())
                        else:
                            dmm_values.append('0.0')
                    self.dmm_data[t_idx] = dmm_values

                elif '.' not in key and len(key) == 2:
                    t_idx = int(key[1])
                    dac_values = []
                    for p in self.cal_points:
                        if p < len(parts):
                            val = parts[p].strip()
                            try:
                                dac_values.append(format(int(val), 'X'))
                            except ValueError:
                                dac_values.append(val)
                        else:
                            dac_values.append('0')
                    self.dac_data[t_idx] = dac_values

        print(f"Read DUT file: {self.dut_path}")
        print(f"Found {self.t_points}T x {self.p_points}P calibration points")

    def write_cal_input(self, output_file='Cal_Input.txt'):
        if not self.tadc_data:
            raise ValueError("No data loaded. Call read_dut_file() first.")

        with open(output_file, 'w') as f:
            f.write('[General]\n')
            f.write(f'adc_resolution = {self.adc_resolution}\n')
            f.write(f'T_points = {self.t_points}\n')
            f.write(f'P_points = {self.p_points}\n')
            f.write(f'v_min = {self.v_min}\n')
            f.write(f'v_max = {self.v_max}\n')
            f.write(f'pressure_span_psi = {self.pressure_span}\n')

            f.write('\n[TADC]\n')
            for t in range(self.t_points):
                values = ','.join(str(v) for v in self.tadc_data[t])
                f.write(f'T{t} = "{values}"\n')

            f.write('\n[PADC]\n')
            for t in range(self.t_points):
                values = ','.join(str(v) for v in self.padc_data[t])
                f.write(f'T{t} = "{values}"\n')

            f.write('\n[DAC]\n')
            for t in sorted(self.dac_data.keys()):
                values = ','.join(self.dac_data[t])
                f.write(f'T{t} = "{values}"\n')

            if self.dmm_data:
                f.write('\n[DAC_DATA]\n')
                for t in sorted(self.dmm_data.keys()):
                    values = ','.join(self.dmm_data[t])
                    f.write(f'T{t} = "{values}"\n')

        print(f"Cal_Input.txt written to {output_file}")

    def create_file(self, output_file='Cal_Input.txt'):
        self.read_part_config()
        self.read_dut_file()
        self.write_cal_input(output_file)