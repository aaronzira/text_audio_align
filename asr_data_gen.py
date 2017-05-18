import sys

from aligner import data_generator


if len(sys.argv) != 2:
    print("Please enter a file id.")
    sys.exit()

filename = sys.argv[1]
seed = ord(filename[-1])
data_generator(filename,seed)


