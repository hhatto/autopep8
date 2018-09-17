import os
import platform
import re

def main():
    os_name  = platform.platform()
    if not re.match('windows', os_name, flags=re.IGNORECASE):
        return

    dir_path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(dir_path, 'suite', 'windows-gb2312.txt')
    print('test old version....')
    os.system('type %s | autopep8 -' % path)

    print('test new version')
    autopep8_path = os.path.join(dir_path, '..', 'autopep8.py')
    os.system('type %s | python %s -' % (path, autopep8_path))


if __name__ == "__main__":
    main()
