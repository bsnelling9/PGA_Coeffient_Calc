import os
import configparser


class CreateCalInputFile:

    def __init__(self, part_number, serial_number,
                 base_path='../Calibration_Data',
                 config_path='../Part_Configurations',
                 adc_resolution=24):
        """
        Args:
            part_number:    e.g. 'A10619'
            serial_number:  e.g. '000001'
            base_path:      root directory for calibration data
            config_path:    root directory for part configuration files
            adc_resolution: ADC resolution in bits (default 24)
        """
        self.part_number    = part_number
        self.serial_number  = serial_number
        self.base_path      = base_path
        self.config_path    = config_path
        self.adc_resolution = adc_resolution
        self.dut_path       = os.path.join(base_path, part_number, f'{serial_number}.txt')
        self.cal_points     = None

        self.tadc_data = {}
        self.padc_data = {}
        self.dac_data  = {}
        self.t_points  = 0
        self.p_points  = 0

    def read_part_config(self):
        """
        Read P Cal Points from the part configuration file.
        File is located at ../Part_Configurations/A10619.configuration
        """
        config_file = os.path.join(self.config_path, f'{self.part_number}.ini')

        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Part configuration file not found: {config_file}")

        config = configparser.ConfigParser()
        config.read(config_file)

        if 'Default Cal' not in config:
            raise ValueError(f"Default Cal section not found in {config_file}")

        # Parse P Cal Points e.g. "0,1,3" -> [0, 1, 3]
        p_cal_points = config['Default Cal']['P Cal Points'].strip('"')
        self.cal_points = [int(x.strip()) for x in p_cal_points.split(',')]

        print(f"Read part config: {config_file}")
        print(f"P Cal Points: {self.cal_points}")

    def read_dut_file(self):
        """
        Parse ADC_DATA and DAC_DATA sections from the DUT file.
        """
        if not os.path.exists(self.dut_path):
            raise FileNotFoundError(f"DUT file not found: {self.dut_path}")

        config = configparser.ConfigParser()
        config.read(self.dut_path)

        if 'ADC_DATA' not in config:
            raise ValueError("ADC_DATA section not found in DUT file")

        # Parse each T#P# entry
        adc_raw = {}
        for key, value in config['ADC_DATA'].items():
            key = key.upper()
            parts = value.strip('"').split('\t')
            if len(parts) == 4:
                t_idx = int(key[1])
                p_idx = int(key[3])
                adc_raw[(t_idx, p_idx)] = {
                    'tadc': int(parts[1]),
                    'padc': int(parts[3])
                }

        # Determine number of temperature and pressure points
        max_t = max(k[0] for k in adc_raw.keys()) + 1
        max_p = max(k[1] for k in adc_raw.keys()) + 1
        self.t_points = max_t

        # Use all pressure points if cal_points not loaded yet
        if self.cal_points is None:
            self.cal_points = list(range(max_p))
        self.p_points = len(self.cal_points)

        # Build TADC and PADC arrays using selected cal points
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

        if 'DAC_DATA' not in config:
            raise ValueError("DAC_DATA section not found in DUT file")

        # Parse DAC rows — T0, T1 etc. Skip DAC_Test_Codes and T#.DMM rows
        for key, value in config['DAC_DATA'].items():
            key = key.upper()
            if key.startswith('T') and '.' not in key and len(key) == 2:
                t_idx = int(key[1])
                parts = value.strip('"').split('\t')
                dac_values = []
                for p in self.cal_points:
                    if p < len(parts):
                        val = parts[p].strip()
                        # DAC values are decimal integers — convert to hex
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
        """
        Write Cal_Input.txt from the parsed DUT data.
        """
        if not self.tadc_data:
            raise ValueError("No data loaded. Call read_dut_file() first.")

        with open(output_file, 'w') as f:
            f.write('[General]\n')
            f.write(f'adc_resolution = {self.adc_resolution}\n')
            f.write(f'T_points = {self.t_points}\n')
            f.write(f'P_points = {self.p_points}\n')

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

        print(f"Cal_Input.txt written to {output_file}")

    def create_file(self, output_file='Cal_Input.txt'):
        """
        Read part config and DUT file then write Cal_Input.txt.
        """
        self.read_part_config()
        self.read_dut_file()
        self.write_cal_input(output_file)