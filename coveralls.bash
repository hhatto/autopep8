#!/bin/bash -ex
#
# Run coverage tests and send results to Coveralls.

pip install --quiet coverage
make coverage
pip install --quiet coveralls
coveralls
