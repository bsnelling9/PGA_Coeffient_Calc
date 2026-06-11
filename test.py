import configparser
import numpy as np
import sys
from pga_coefficient_calculator import PGACoeffCalculator

#remove this code, this is for the TI calcualtor
config = configparser.ConfigParser()
config.read('Cal_Input.txt')

if not config.sections():
    print("Error: Could not read Cal_Input.txt.")
    sys.exit(1)

temperature_points = int(config['General']['T_points'])
pressure_points = int(config['General']['P_points'])

tadc = np.zeros((temperature_points, pressure_points), dtype='i')
padc = np.zeros((temperature_points, pressure_points), dtype='i')
dac  = np.zeros((temperature_points, pressure_points), dtype='i')

def parse_adc(s):
    return int(s.strip())

def parse_dac(s):
    return int(s.strip(), 16)

for i in range(temperature_points):
    for j in range(pressure_points):
        tadc[i,j] = parse_adc((config['TADC']['T'+str(i)])[1:-1].split(',')[j])
        padc[i,j] = parse_adc((config['PADC']['T'+str(i)])[1:-1].split(',')[j])
        dac[i,j]  = parse_dac((config['DAC']['T'+str(i)])[1:-1].split(',')[j])

cc = PGACoeffCalculator(
    cal_point=(temperature_points, pressure_points),
    adc_resolution=int(config['General']['adc_resolution']),
    tad_matrix=tadc.tolist(),
    pad_matrix=padc.tolist(),
    dac_matrix=dac.tolist(),
)

cc.recommend_calibration(offset_enabled=False)
cc.normalize_data()
cc.calculate_regression()

print("CALIBRATION VERIFICATION RESULTS ")

for i in range(temperature_points):
    for j in range(pressure_points):
        t_val = tadc[i, j]
        p_val = padc[i, j]
        target_dac = dac[i, j]
        
        computed_dac = cc.compute_dac_value(int(t_val), int(p_val))
        
        print(f"Point: T{i}P{j}")
        print(f"TADC: {t_val}")
        print(f"PADC: {p_val}")
        print(f"DAC Target: 0x{target_dac:04X} ({target_dac})")
        print(f"DAC Computed: 0x{computed_dac:04X} ({computed_dac})")
        print("-" * 30)
print("AT DESK READING ------------------------------")
computed = cc.compute_dac_value(1878523, -8069568)
print(f"At desk reading: DAC = {computed}")

print("--- 500 psi ---")
computed_500psi = cc.compute_dac_value(1915218, -2451860)
print(f"At 500 psi: DAC = {computed_500psi}")