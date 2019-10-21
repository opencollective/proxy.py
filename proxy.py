#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    proxy.py
    ~~~~~~~~
    ⚡⚡⚡ Fast, Lightweight, Programmable Proxy Server in a single Python file.

    :copyright: (c) 2013-present by Abhinav Singh and contributors.
    :license: BSD, see LICENSE for more details.
"""
import sys
from core.main import main


if __name__ == '__main__':
    main(sys.argv[1:])  # pragma: no cover
