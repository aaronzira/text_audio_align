import sys
import os

from aligner import data_generator

if len(sys.argv) != 2:
    print("Please enter a file id.")

data_generator(filename)


