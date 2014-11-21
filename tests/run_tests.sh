#!/bin/bash

set -e
cd `dirname $0`

PYTHONPATH=.. python -m coverage run --source networktables,networktables2 -m pytest $@
python -m coverage report -m

