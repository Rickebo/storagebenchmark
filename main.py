import argparse
import hashlib
import os
import sys
import tempfile
import time


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--size',
        '-s',
        help='Size of the temporary files written/read during testing',
        dest='size',
        type=int,
        default=1024
    )

    parser.add_argument(
        '--empty',
        '-e',
        help='Empty the contents of the destination directory before testing',
        dest='empty',
        action='store_true',
        default=False
    )

    parser.add_argument(
        '--count',
        '-c',
        help='File count',
        dest='count',
        type=int,
        default=100
    )

    parser.add_argument(
        '--directory',
        '-d',
        help='Directory to read/write temporary files to',
        dest='dir',
        type=str,
        default=None
    )

    parser.add_argument(
        '--buffer-size',
        '-b',
        help='Read/write buffer size',
        dest='buffer_size',
        type=int,
        default=1024
    )

    parser.add_argument(
        '--iterations',
        '-i',
        help='Number of test iterations',
        dest='iterations',
        type=int,
        default=10
    )

    return parser.parse_args(sys.argv[1:])


def write(directory: str, options: argparse.Namespace, files_written: set[str]):
    final_hash = bytes(20)
    for i in range(options.count):
        path = os.path.join(directory, f'{i}.bin')

        if os.path.exists(path):
            continue

        to_write = options.size
        inner_hash = hashlib.sha1()
        with open(path, 'wb') as file:
            files_written.add(path)
            while to_write > 0:
                num_bytes = min(to_write, options.buffer_size)
                file_content = os.urandom(num_bytes)
                to_write -= num_bytes
                file.write(file_content)
                inner_hash.update(file_content)

            file.flush()

        final_hash = bytes(x ^ y for x, y in zip(final_hash, inner_hash.digest()))

    return final_hash.hex()


def read(directory: str, options: argparse.Namespace) -> str:
    final_hash = bytes(20)
    for file_name in os.listdir(directory):
        inner_hash = hashlib.sha1()
        with open(os.path.join(directory, file_name), 'rb') as file:
            while data := file.read(options.buffer_size):
                inner_hash.update(data)

        final_hash = bytes(x ^ y for x, y in zip(final_hash, inner_hash.digest()))

    return final_hash.hex()


def clear(directory: str):
    for file in os.listdir(directory):
        os.remove(os.path.join(directory, file))


def format(number):
    formats = [
        (1024 ** 4, 'TiB'),
        (1024 ** 3, 'GiB'),
        (1024 ** 2, 'MiB'),
        (1024, 'KiB'),
        (1, 'B')
    ]

    for unit_size, unit in formats:
        if number < unit_size:
            continue

        return number / unit_size, unit

    raise ValueError('Invalid number passed.')


def run_benchmark(directory: str, options: argparse.Namespace):
    if options.empty:
        clear(directory)

    write_hashes = set()
    read_hashes = set()

    elapsed_write = 0
    elapsed_read = 0

    print_format = '\rRunning benchmark: %s (%s / %s)\033[K'
    sys.stdout.write(print_format % ('0%', '0', '0'))
    sys.stdout.flush()

    for iteration in range(options.iterations):
        progress = (100 * iteration) / options.iterations
        sys.stdout.write(print_format % (
            f'{progress:.2f}%',
            iteration,
            options.iterations
        ))

        sys.stdout.flush()

        files = set()
        pre_write = time.time()
        write_hash = write(directory, options, files)
        post_write = time.time()

        pre_read = time.time()
        read_hash = read(directory, options)
        post_read = time.time()

        elapsed_read += post_read - pre_read
        elapsed_write += post_write - pre_write

        if read_hash != write_hash:
            write_hashes.add(write_hash)
            read_hashes.add(read_hash)

        for file in files:
            os.remove(file)

    sys.stdout.write(print_format % (
        f'100%',
        options.iterations,
        options.iterations
    ))

    total_size = options.size * options.count

    write_speed, write_unit = format(total_size / elapsed_write)
    read_speed, read_unit = format(total_size / elapsed_read)

    if write_hashes or read_hashes:
        print('Mismatching hashes:')
        print(f'    Write hash: {", ".join(write_hashes)}')
        print(f'     Read hash: {", ".join(read_hashes)}')

    print(f'')
    print(f'Total times:')
    print(f'    Write: {elapsed_write:.2f} s')
    print(f'     Read: {elapsed_read:.2f} s')
    print(f'')
    print(f'Per-file times:')
    print(f'    Write: {(1000 * elapsed_write) / options.count:.2f} ms/file')
    print(f'     Read: {(1000 * elapsed_read) / options.count:.2f} ms/file')
    print(f'')
    print(f'Rates:')
    print(f'    Write: {write_speed:.2f} {write_unit}/s')
    print(f'     Read: {read_speed:.2f} {read_unit}/s')


def main():
    options = parse_args()
    directory = options.dir

    if directory is None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_benchmark(temp_dir, options)
            clear(temp_dir)
    else:
        run_benchmark(directory, options)


if __name__ == '__main__':
    main()
