from __future__ import print_function
from os import getenv
from datetime import datetime


def vprint(*a, **k):
    if not getenv('VERBOSE'):
        return
    print(datetime.now(), ' ', end='')
    print(*a, **k)
