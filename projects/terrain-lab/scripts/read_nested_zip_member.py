"""Write one exact member from a possibly nested ZIP to stdout without extracting files."""

import io
import sys
import zipfile


def main() -> int:
    if len(sys.argv) < 3:
        print('usage: read_nested_zip_member.py ARCHIVE.zip MEMBER [NESTED_MEMBER ...]', file=sys.stderr)
        return 2
    try:
        with zipfile.ZipFile(sys.argv[1]) as archive:
            payload = archive.read(sys.argv[2])
        for member in sys.argv[3:]:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                payload = archive.read(member)
        sys.stdout.buffer.write(payload)
        return 0
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        print(f'archive member error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
