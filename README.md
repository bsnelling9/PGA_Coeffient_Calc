PGA305 Calibration Coefficient Calculator
=========================================

Computes calibration coefficients for the TI PGA305 from measured ADC and DAC
data, and writes them back into the DUT file for the EEPROM programmer.

The fit is a least-squares solve of DAC = sum(c_ij * T^i * P^j), where T and P
are the TADC and PADC readings after gain and offset scaling. Coefficients are
scaled to 2^30 fixed point for EEPROM.


## Requires

Python 3.11 or newer, numpy 2.3.1 or newer.


## Setup

Update the paths in config.py before first use:

- BASE_PATH    calibration data, DUT files live in <BASE_PATH>/<pressure_code>/
- CONFIG_PATH  part configuration .ini files
- LOG_PATH     LabVIEW log directory, used for batch runs


## Running

Single unit:

    python main.py <pressure_code> <serial_number>
    python main.py 400G 000165

Single unit with a different output voltage span:

    python main.py <pressure_code> <serial_number> <v_min> <v_max>
    python main.py 400G 000165 0.5 4.5

Single unit with a different pressure span. Use x for the voltage arguments to
leave the span at the part default:

    python main.py <pressure_code> <serial_number> <v_min> <v_max> <p_min> <p_max>
    python main.py 400G 000165 x x 0 1500

All units from a LabVIEW run:

    python main.py Log <timestamp>
    python main.py Log 260923_100326

The batch reads Connected DUTs.txt from <LOG_PATH>/<timestamp>/ and processes
every channel listed. A unit that fails is reported and the run continues.


## Input files

    <BASE_PATH>/<pressure_code>/<serial_number>.txt   DUT file, written by LabVIEW
    <CONFIG_PATH>/<pressure_code>.ini                 part configuration
    <LOG_PATH>/<timestamp>/Connected DUTs.txt         batch runs only

The DUT file needs an [ADC_DATA] section with TxPy rows of
temperature, TADC, pressure, PADC, and a [DAC_DATA] section with the DAC test
codes and the measured DMM voltages.


## Output

Two working files are created and deleted at the end of each run:

    Cal_Input_<serial>.txt          input to the calculator
    Brodie_Cal_Output_<serial>.txt  calibration report

The settings and coefficients are written back into the DUT file under
[CalibrationSettings] and [Coefficients]. If a voltage or pressure span was
given on the command line, the sections are suffixed with that span, for
example [Coefficients_0.5-4.5V_0-1500psi].


## Notes

PADC and TADC are 24-bit two's complement, per the PGA305 datasheet sections
6.12 and 6.14. Values arrive already converted from LabVIEW.

PADC_OFFSET is anchored on the 0 psi reading at the lower temperature, so that
point normalizes to zero.

The calibration point comparison in the report shows zero error at every point
for an 8 point, 8 coefficient fit. That is the solve being exactly determined,
not a measure of accuracy. Check accuracy at pressures that were not
calibration points.

config.ENABLE_DAC_CORRECTION applies a quadratic fit of DAC code against
measured DMM voltage. It is off. With it enabled, one unit read 10.04 V at
1500 psi against 10.004 V with it disabled.