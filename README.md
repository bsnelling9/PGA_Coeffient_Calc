PGA305 Calibration Coefficient Calculator
=============================================

This application provide an algorthim for computing the calibration coefficients for Texas Instruments PGA305 programmable gain amplifiers. 
I write this myself using the TI calcualtor as an example. There were a few bugs that I fixed and the fact the the measured DAC outputs were not taken into consideration.
The tool generates polynomial regression coefficients that define the transfer functions mapping temperature (TADC) and pressure (PADC)measurements to specific DAC output codes

### Key Features

- **Z-score normalization**: Prevents numerical instability in polynomial regression
- **Multiple configurations**: Supports 1P1T to 4P4T calibration configurations
- **ADC resolution options**: Handles both 16-bit and 24-bit ADC resolutions
- **EEPROM Scaling**: Provides integer-scaled coefficients for device storage
- **Error analysis**: Determines prediction error


## Prerequisites

Requires Python >=3.11 and numpy >= 2.3.1. This script uses inline script metadata (PEP 723) to declare its dependencies, allowing compatible package managers to automatically install and run it.


### How to use this script
Make sure to update the config.py file to have the correct directory paths.

Use python main.py PressureCode SerialNumber
    python main.py 100G 000001

