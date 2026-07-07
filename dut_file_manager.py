import os
import config


class DUTFileManager:

    def __init__(self, pressure_code, serial_number, base_path=None):
        self.pressure_code = pressure_code
        self.serial_number = serial_number
        self.base_path = base_path or config.BASE_PATH
        self.dut_path = os.path.join(self.base_path, pressure_code, f'{serial_number}.txt')
        self.coefficients = {}
        self.settings = {}

    def parse_cal_output(self, cal_output_file='Cal_Output.txt'):

        self.coefficients = {}
        self.settings = {}

        in_coeffs_section = False
        in_settings_section = False

        with open(cal_output_file, 'r') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()

            if 'Calibration Settings' in line:
                in_settings_section = True
                in_coeffs_section = False
                continue

            if 'Name' in line and 'Float Value' in line:
                in_coeffs_section = True
                in_settings_section = False
                continue

            if 'Calibration Point Comparison' in line:
                in_coeffs_section = False
                in_settings_section = False
                continue

            if not line or line.startswith('-') or line.startswith('='):
                continue

            if in_settings_section:
                parts = line.split()
                if len(parts) >= 3 and parts[0] in config.VALID_SETTINGS:
                    self.settings[parts[0]] = {
                        'value': parts[1],
                        'hex':   parts[2].replace('0x', '')
                    }

            if in_coeffs_section:
                parts = line.split()
                if len(parts) >= 3 and parts[0] in config.VALID_COEFFICIENTS:
                    self.coefficients[parts[0]] = parts[2].replace('0x', '')

        print(f"Parsed {len(self.coefficients)} coefficients and {len(self.settings)} settings from {cal_output_file}")

        return self.coefficients, self.settings

    def write_coefficients(self):
        if not self.coefficients:
            print("ERROR: No coefficients to write. Call parse_cal_output() first.")
            return

        if not os.path.exists(self.dut_path):
            print(f"ERROR: DUT file not found: {self.dut_path}")
            return

        with open(self.dut_path, 'r') as f:
            content = f.read()

        for section in ['[Coefficients]', '[CalibrationSettings]']:
            if section in content:
                content = content[:content.index(section)]
                content = content.rstrip() + '\n'

        settings_section = '\n[CalibrationSettings]\n'
        for name in config.VALID_SETTINGS:
            if name in self.settings:
                hex_val = self.settings[name]['hex']
                settings_section += f'{name} = "{hex_val}"\n'
            else:
                settings_section += f'{name} = ""\n'

        coeff_section = '\n[Coefficients]\n'
        for name in config.VALID_COEFFICIENTS:
            value = self.coefficients.get(name, '')
            coeff_section += f'{name} = "{value}"\n'

        with open(self.dut_path, 'w') as f:
            f.write(content + settings_section + coeff_section)

        print(f"Settings and coefficients written to {self.dut_path}")

    def print_coefficients(self):
        if not self.coefficients:
            print("No coefficients loaded.")
            return
        for name, hex_val in self.coefficients.items():
            print(f"  {name} = {hex_val}")

    def print_settings(self):
        if not self.settings:
            print("No settings loaded.")
            return
        for name, data in self.settings.items():
            print(f"  {name} = {data['value']} (0x{data['hex']})")