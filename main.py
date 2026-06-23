import sys
from create_cal_input_file import CreateCalInputFile
from calculate_coefficients import calculate_coefficients
from dut_file_manager import DUTFileManager

# Only needed if re-enabling the TI reference comparison block below.
# from calculate_coefficients import load_cal_input
# from pga_coefficient_calculator import PGACoeffCalculator

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

# --- TI reference comparison (not used) ---
# Runs the same Cal_Input.txt data through TI's PGACoeffCalculator and
# writes TI_Cal_Output.txt, so the two implementations can be diffed
# against each other. Uncomment if you need to re-verify against TI's
# reference math again.
#
# loaded = load_cal_input('Cal_Input.txt')
#
# cc = PGACoeffCalculator(
#     cal_point=(loaded['T_points'], loaded['P_points']),
#     adc_resolution=loaded['adc_res'],
#     tad_matrix=loaded['tadc'],
#     pad_matrix=loaded['padc'],
#     dac_matrix=loaded['dac'],
# )
#
# cc.recommend_calibration(offset_enabled=False)
# cc.normalize_data()
# cc.calculate_regression()
#
# with open('TI_Cal_Output.txt', 'w') as f:
#     sys.stdout = f
#     cc.summarize_results()
#     sys.stdout = sys.__stdout__
#
# print("TI_Cal_Output.txt written successfully")
# --- end TI reference comparison ---

dut = DUTFileManager(part_number, serial_number)
dut.parse_cal_output('Brodie_Cal_Output.txt')
dut.print_settings()
dut.print_coefficients()
dut.write_coefficients()