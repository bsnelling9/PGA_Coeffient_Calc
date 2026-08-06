import sys
import os
import config
from create_cal_input_file import CreateCalInputFile
from calculate_coefficients import calculate_coefficients
from dut_file_manager import DUTFileManager
from parse_connected_duts import parse_connected_duts


def parse_voltage_arg(arg):
    if arg is None or arg.lower() == 'x':
        return None
    return float(arg)


def run_single(pressure_code, serial_number, v_min_override=None, v_max_override=None,
               dac_fs_voltage=None, p_min_override=None, p_max_override=None):
    
    sn_str = f"{serial_number:06d}" if isinstance(serial_number, int) else serial_number

    cal_input_filename = f'Cal_Input_{sn_str}.txt'
    output_filename = f'Brodie_Cal_Output_{sn_str}.txt'

    cal_input_file = CreateCalInputFile(
        pressure_code=pressure_code,
        serial_number=sn_str,
        v_min=v_min_override,
        v_max=v_max_override,
    )
    
    cal_input_file.create_file(output_file=cal_input_filename)

    calculate_coefficients(
        cal_input_file=cal_input_filename,
        output_file=output_filename,
        off_en=0,
        dac_fs_voltage=dac_fs_voltage,
        p_min=p_min_override,
        p_max=p_max_override,
    )

    dut = DUTFileManager(pressure_code, sn_str)
    dut.parse_cal_output(output_filename)
    dut.print_settings()
    dut.print_coefficients()

    label_parts = []
    if v_min_override is not None and v_max_override is not None:
        label_parts.append(f"{v_min_override:g}-{v_max_override:g}V")
    if p_min_override is not None and p_max_override is not None:
        label_parts.append(f"{p_min_override:g}-{p_max_override:g}psi")
    label = "_".join(label_parts) if label_parts else None

    dut.write_coefficients(label=label)

    os.remove(cal_input_filename)
    os.remove(output_filename)


def run_batch(timestamp_str):
    timestamp_dir = os.path.join(config.LOG_PATH, timestamp_str)
    connected_duts_path = os.path.join(timestamp_dir, "Connected DUTs.txt")

    sensors = parse_connected_duts(connected_duts_path)

    if not sensors:
        print("No connected sensors found in Connected DUTs.txt")
        return

    print(f"Found {len(sensors)} connected sensor(s):")

    all_ok = True
    for channel in sorted(sensors.keys()):
        s = sensors[channel]
        sn = s['serial_number']
        pressure_code = s['pressure_code']

        print(f"\n--- Channel {channel} | SN {sn:06d} | Pressure Code {pressure_code} ---")
        try:
            run_single(pressure_code=pressure_code, serial_number=sn)
        except Exception as e:
            print(f"ERROR processing SN {sn:06d}: {e}")
            all_ok = False
            continue
    
    return all_ok

def main():
    args = sys.argv[1:]

    try:
        if len(args) == 2 and args[0].lower() == "log":
            success = run_batch(timestamp_str=args[1])
        elif len(args) in (2, 4, 5, 7):
            pressure_code = args[0]
            serial_number = args[1]
            v_min_override = parse_voltage_arg(args[2]) if len(args) >= 4 else None
            v_max_override = parse_voltage_arg(args[3]) if len(args) >= 4 else None
            dac_fs_voltage = parse_voltage_arg(args[4]) if len(args) >= 5 else None
            p_min_override = parse_voltage_arg(args[5]) if len(args) == 7 else None
            p_max_override = parse_voltage_arg(args[6]) if len(args) == 7 else None
            run_single(pressure_code, serial_number, v_min_override, v_max_override,
                       dac_fs_voltage, p_min_override, p_max_override)
            success = True
        else:
            print("Usage:")
            print("  python main.py <part_number> <serial_number> [v_min v_max [dac_fs_voltage [p_min p_max]]]")
            print("  python main.py Log <timestamp>")
            sys.exit(2)

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"CRITICAL FAULT: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()