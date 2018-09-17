import os


def main():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    path = dir_path + '\\suite\\windows-gb2312.txt'
    print('test old version....')
    os.system('type %s | autopep8 -' % path)

    print('test new version')
    autopep8_path = dir_path + '\\..\\autopep8.py'
    os.system('type %s | python %s -' % (path, autopep8_path))


if __name__ == "__main__":
    main()
