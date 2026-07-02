import sys
from create_cal_input_file import CreateCalInputFile
from calculate_coefficients import calculate_coefficients
from dut_file_manager import DUTFileManager


def parse_voltage_arg(arg):
    if arg is None or arg.lower() == 'x':
        return None
    return float(arg)

args = sys.argv[1:]
if len(args) not in (2, 4):
    sys.exit(1)

part_number   = args[0]
serial_number = args[1]

v_min_override = parse_voltage_arg(args[2]) if len(args) == 4 else None
v_max_override = parse_voltage_arg(args[3]) if len(args) == 4 else None

cal_input_file = CreateCalInputFile(
    part_number=part_number,
    serial_number=serial_number,
    v_min=v_min_override,
    v_max=v_max_override,
)

cal_input_file.create_file()

calculate_coefficients(
    cal_input_file='Cal_Input.txt',
    output_file='Brodie_Cal_Output.txt',
    off_en=0
)

dut = DUTFileManager(part_number, serial_number)
dut.parse_cal_output('Brodie_Cal_Output.txt')
dut.print_settings()
dut.print_coefficients()
dut.write_coefficients(
    v_min=cal_input_file.v_min,
    v_max=cal_input_file.v_max,
    pressure_span_psi=cal_input_file.pressure_span,
)

# Only needed if re-enabling the TI reference comparison block below.
# from calculate_coefficients import load_cal_input
# from pga_coefficient_calculator import PGACoeffCalculator


# --- TI reference comparison (not used in the normal flow) ---
# Runs the same Cal_Input.txt data through TI's PGACoeffCalculator and
# writes TI_Cal_Output.txt, so the two implementations can be compared
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