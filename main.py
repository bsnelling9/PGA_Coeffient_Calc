import sys
import os
import ctypes
import config
from calculate_coefficients import calculate_coefficients
from dut_file_manager import DUTFileManager
from parse_connected_duts import parse_connected_duts


def open_console_window(title):
    kernel32 = ctypes.windll.kernel32
    kernel32.FreeConsole()
    kernel32.AllocConsole()
    kernel32.SetConsoleTitleW(title)
    sys.stdout = open("CONOUT$", "w", buffering=1)
    sys.stderr = sys.stdout
    sys.stdin = open("CONIN$", "r")


def parse_range_limit(arg):
    if arg is None or arg.lower() == 'x':
        return None
    return float(arg)


def run_single(pressure_code, serial_number, v_min_override=None, v_max_override=None,
               p_min_override=None, p_max_override=None, print_details=True):

    sn_str = f"{serial_number:06d}" if isinstance(serial_number, int) else serial_number

    try:
        dut = DUTFileManager(
            pressure_code=pressure_code,
            serial_number=sn_str,
            v_min=v_min_override,
            v_max=v_max_override,
            print_details=print_details,
        )

        dut.read_part_config()
        dut.read_dut_file()

        dut.coefficients, dut.settings = calculate_coefficients(
            dut,
            p_min=p_min_override,
            p_max=p_max_override,
            print_details=print_details,
        )

        if print_details:
            dut.print_settings()
            dut.print_coefficients()

        label_parts = []
        if v_min_override is not None and v_max_override is not None:
            label_parts.append(f"{v_min_override:g}-{v_max_override:g}V")
        if p_min_override is not None and p_max_override is not None:
            label_parts.append(f"{p_min_override:g}-{p_max_override:g}psi")
        label = "_".join(label_parts) if label_parts else None

        dut.write_coefficients(label=label)
        return True

    except Exception as e:
        print(f"FAILED - {e}")
        return False


def run_batch(timestamp_str):
    open_console_window("PGA305 Coefficient Calculation")

    timestamp_dir = os.path.join(config.LOG_PATH, timestamp_str)
    connected_duts_path = os.path.join(timestamp_dir, "Connected DUTs.txt")

    try:
        sensors = parse_connected_duts(connected_duts_path)
    except Exception as e:
        print(f"Could not read Connected DUTs.txt - {e}")
        input("\nPress Enter to close this window.")
        return False

    if not sensors:
        print("No connected sensors found in Connected DUTs.txt")
        input("\nPress Enter to close this window.")
        return False

    print(f"Found {len(sensors)} sensor(s)\n")

    failed_channels = []
    for channel in sorted(sensors):
        sensor = sensors[channel]
        sn = sensor['serial_number']

        print(f"Calculating coefficients for channel {channel} (SN {sn:06d})... ", end="", flush=True)

        if run_single(pressure_code=sensor['pressure_code'], serial_number=sn, print_details=False):
            print("OK")
        else:
            failed_channels.append(channel)

    passed = len(sensors) - len(failed_channels)
    print(f"\nPassed: {passed}")
    print(f"Failed: {len(failed_channels)}")

    if failed_channels:
        print(f"Failed channels: {', '.join(map(str, failed_channels))}")

    input("\nPress Enter to close this window.")

    return not failed_channels


def main():
    args = sys.argv[1:]

    if len(args) == 2 and args[0].lower() == "log":
        success = run_batch(timestamp_str=args[1])
    elif len(args) in (2, 4, 6):
        pressure_code = args[0]
        serial_number = args[1]
        v_min_override = parse_range_limit(args[2]) if len(args) >= 4 else None
        v_max_override = parse_range_limit(args[3]) if len(args) >= 4 else None
        p_min_override = parse_range_limit(args[4]) if len(args) == 6 else None
        p_max_override = parse_range_limit(args[5]) if len(args) == 6 else None

        success = run_single(pressure_code, serial_number, v_min_override, v_max_override,
                             p_min_override, p_max_override)
    else:
        print("Usage:")
        print("  python main.py <pressure_code> <serial_number> [v_min v_max [p_min p_max]]")
        print("  python main.py Log <timestamp>")
        sys.exit(2)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()