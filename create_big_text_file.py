import random
import string
import sys

def create_big_text_file(filename, size, unit='GB'):
    units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
    size_bytes = int(size * units.get(unit.upper(), units['GB']))
    chars = string.ascii_letters + string.digits + ".,<>/?;\'\\:\"|[]{}=+-_!@#$%^&*(), "
    line_length = 75
    batch_size = 100

    with open(filename, 'w', encoding='utf-8') as f:
        written = 0
        while written < size_bytes:
            lines = []
            for _ in range(batch_size):
                line = ''.join(random.choices(chars, k=line_length)) + '\n'
                lines.append(line)
                written += len(line)
                if written >= size_bytes:
                    break
            f.writelines(lines)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Create a large random text file.')
    parser.add_argument('filename', help='Name of the file to create')
    parser.add_argument('size', type=float, help='Total size of the file')
    parser.add_argument('--unit', choices=['B', 'KB', 'MB', 'GB'], default='GB', help='Unit for file size (default: GB)')
    args = parser.parse_args()
    create_big_text_file(args.filename, args.size, args.unit)