import os
import re
import sys
import config


def parse_connected_duts(file_path):

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Connected DUTs file not found: {file_path}")

    sensors = {}

    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            
            if not stripped:
                continue

            parts = re.split(r'\s+', stripped)

            if len(parts) < 4 or not all(parts[:4]):
                continue

            pressure_code = parts[0]
            serial_number = int(parts[1])

            try:
                channel = int(parts[3])
            except ValueError:
                print(f"  WARNING: line {line_num} has a non-numeric channel "
                      f"({parts[3]!r}) — skipping this row.")
                continue

            if channel in sensors:
                print(f"  WARNING: channel {channel} appears more than once "
                      f"(line {line_num}) — keeping the first occurrence, "
                      f"check the file for a duplicate/typo.")
                continue

            sensors[channel] = {
                'pressure_code': pressure_code,
                'serial_number': serial_number
            }

    return sensors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_connected_duts.py 260615_104816")
        sys.exit(1)

    timestamp_str = sys.argv[1]
    file_path = os.path.join(config.LOG_PATH, timestamp_str, "Connected DUTs.txt")

    sensors = parse_connected_duts(file_path)
    print(f"Found {len(sensors)} connected sensor(s):")
    for channel, s in sorted(sensors.items()):
        print(f"  Channel {channel:>3}  |  SN: {s['serial_number']:>6}  |  Pressure Code: {s['pressure_code']}")