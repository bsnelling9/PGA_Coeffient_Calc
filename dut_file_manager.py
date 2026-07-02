import os
from datetime import datetime
import config


def _remove_section(content, section_header):
    start = content.find(section_header)
    if start == -1:
        return content

    next_section_start = content.find('\n[', start + len(section_header))
    if next_section_start == -1:
        end = len(content)
    else:
        end = next_section_start + 1  # keep the newline that starts the next section

    return content[:start] + content[end:]


class DUTFileManager:

    def __init__(self, part_number, serial_number, base_path=None):
        self.part_number = part_number
        self.serial_number = serial_number
        self.base_path = base_path or config.BASE_PATH
        self.dut_path = os.path.join(self.base_path, part_number, f'{serial_number}.txt')
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

    def write_coefficients(self, v_min, v_max, pressure_span_psi=None, mark_active=True):

        if not self.coefficients:
            print("ERROR: No coefficients to write. Call parse_cal_output() first.")
            return

        if not os.path.exists(self.dut_path):
            print(f"ERROR: DUT file not found: {self.dut_path}")
            return

        label = f"{v_min}-{v_max}V"
        settings_header = f'[CalibrationSettings_{label}]'
        coeff_header = f'[Coefficients_{label}]'

        with open(self.dut_path, 'r') as f:
            content = f.read()

        content = _remove_section(content, coeff_header)
        content = _remove_section(content, settings_header)
        content = _remove_section(content, '[ActiveConfig]')

        settings_section = f'\n{settings_header}\n'
        for name in config.VALID_SETTINGS:
            if name in self.settings:
                hex_val = self.settings[name]['hex']
                settings_section += f'{name} = "{hex_val}"\n'
            else:
                settings_section += f'{name} = ""\n'

        coeff_section = f'\n{coeff_header}\n'
        for name in config.VALID_COEFFICIENTS:
            value = self.coefficients.get(name, '')
            coeff_section += f'{name} = "{value}"\n'

        active_section = ''
        if mark_active:
            timestamp = datetime.now().strftime('%y%m%d_%H%M%S')
            active_section = '\n[ActiveConfig]\n'
            active_section += f'Output_Label = "{label}"\n'
            active_section += f'V_Min = "{v_min}"\n'
            active_section += f'V_Max = "{v_max}"\n'
            if pressure_span_psi is not None:
                active_section += f'Pressure_Span_PSI = "{pressure_span_psi}"\n'
            active_section += f'Last_Configured = "{timestamp}"\n'

        with open(self.dut_path, 'w') as f:
            f.write(content.rstrip() + '\n' + settings_section + coeff_section + active_section)

        print(f"Wrote variant '{label}' to {self.dut_path}")
        if mark_active:
            print(f"[ActiveConfig] now points to '{label}'")

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