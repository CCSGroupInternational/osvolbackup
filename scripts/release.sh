#!/bin/sh
set -e
rm -rf dist
m2r --overwrite README.md
python setup.py sdist bdist_wheel
twine upload dist/*
