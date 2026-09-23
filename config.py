BASE_PATH = '../Calibration_Data'
CONFIG_PATH = '../Part_Configurations'
LOG_PATH = "C:/PGA305_Data/Log"

ADC_RESOLUTION = 24
 
# Default output voltage
V_MIN = 0.0
V_MAX = 10.0
 
DEFAULT_PRESSURE_SPAN_PSI = 1500

# Flag to enable/disable DAC correction during coefficient calculation.
# there was a bug or something but basically on the same unit with this enabled
# at 1500 psi the output was 10.04V, with it disabled it was 10.004V
ENABLE_DAC_CORRECTION = False

DAC_TEST_CODE_FRACTIONS = [0, 1/3, 1/2, 2/3, 3/4, 1, 1.1]

#Because of Off_En = 1, the tadc_gain was saturating. I need to set a max gain
TADC_GAIN_MAX = 3

SPAN_TO_GAIN = {
    (0.0, 10.0): 10.0,
    (0.5, 4.5):  4.0,
    (1.0, 6.0):  6.67,
    (1.0, 5.0):  6.67,
}

GAIN_DAC_CODE = {
    10.0: [0, 4301, 8624, 9696, 12928, 14221],
    4.0: [0, 1000, 1625, 4305, 9696, 12928, 16000],
    6.67: [0, 1000, 1625, 4305, 9696, 12928, 16000],
}

DAC_CODE_VOLTAGE_SWEEPS = {
    10.0: {
        0: 0,
        4301: 3.333,
        8624: 6.667,
        9696: 7.75,
        12928: 10.0,
        14221: 11,
    },
    4.0: {
        0: 0,
        1625: 0.500,
        4305: 1.3213,
        9696: 2.973,
        12928: 3.964,
        14676: 4.50,
        16383: 5.02
    },
    6.67: {
        0: 0,
        1948: 1.00,
        3896: 2.00,
        8767: 4.50,
        9741: 5.00,
        11689: 6.00,
        16383: 8.409
    }
}


VALID_COEFFICIENTS = [
    'h0', 'h1', 'h2', 'h3',
    'g0', 'g1', 'g2', 'g3',
    'm0', 'm1', 'm2', 'm3',
    'n0', 'n1', 'n2', 'n3'
]
 
VALID_SETTINGS = [
    'OFF_EN', 'TADC_GAIN', 'TADC_OFFSET', 'PADC_GAIN', 'PADC_OFFSET'
]