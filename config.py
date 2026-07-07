BASE_PATH = '../Calibration_Data'
CONFIG_PATH = '../Part_Configurations'
LOG_PATH = "C:/PGA305_Data/Log"

ADC_RESOLUTION = 24
 
# Default output voltage
V_MIN = 0.0
V_MAX = 10.0
 
DEFAULT_PRESSURE_SPAN_PSI = 1500

VALID_COEFFICIENTS = [
    'h0', 'h1', 'h2', 'h3',
    'g0', 'g1', 'g2', 'g3',
    'm0', 'm1', 'm2', 'm3',
    'n0', 'n1', 'n2', 'n3'
]
 
VALID_SETTINGS = [
    'OFF_EN', 'TADC_GAIN', 'TADC_OFFSET', 'PADC_GAIN', 'PADC_OFFSET'
]