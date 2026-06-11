import sys
import configparser
import numpy as np
from create_cal_input_file import CreateCalInputFile
from calculate_coefficients import calculate_coefficients
from pga_coefficient_calculator import PGACoeffCalculator
from dut_file_manager import DUTFileManager

if len(sys.argv) != 3:
    print("Usage: python main.py <part_number> <serial_number>")
    print("Example: python main.py 64G 000006")
    sys.exit(1)

part_number   = sys.argv[1]
serial_number = sys.argv[2]

cal_input_file = CreateCalInputFile(
    part_number=part_number,
    serial_number=serial_number
)
cal_input_file.create_file()

calculate_coefficients(
    cal_input_file='Cal_Input.txt',
    output_file='Brodie_Cal_Output.txt',
    off_en=0
)

config = configparser.ConfigParser()
config.read('Cal_Input.txt')

T_points = int(config['General']['T_points'])
P_points = int(config['General']['P_points'])
adc_res  = int(config['General']['adc_resolution'])

tadc = [[int(x.strip()) for x in config['TADC'][f'T{i}'][1:-1].split(',')] for i in range(T_points)]
padc = [[int(x.strip()) for x in config['PADC'][f'T{i}'][1:-1].split(',')] for i in range(T_points)]
dac  = [[int(x.strip(), 16) for x in config['DAC'][f'T{i}'][1:-1].split(',')] for i in range(T_points)]

cc = PGACoeffCalculator(
    cal_point=(T_points, P_points),
    adc_resolution=adc_res,
    tad_matrix=tadc,
    pad_matrix=padc,
    dac_matrix=dac,
)
cc.recommend_calibration(offset_enabled=False)
cc.normalize_data()
cc.calculate_regression()

with open('TI_Cal_Output.txt', 'w') as f:
    sys.stdout = f
    cc.summarize_results()
    sys.stdout = sys.__stdout__

print("TI_Cal_Output.txt written successfully")

dut = DUTFileManager(part_number, serial_number)
dut.parse_cal_output('Brodie_Cal_Output.txt')
dut.print_settings()
dut.print_coefficients()
dut.write_coefficients()