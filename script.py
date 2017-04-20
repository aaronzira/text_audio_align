import sys
import os

from aligner import data_generator

if len(sys.argv) != 2:
    print("Please enter a directory of audio or text files.")

for _file in os.listdir(sys.argv[1]):
    # sanity check for osx (testing) and making sure there are no
    # underscores in filenames
    filename = os.path.basename(os.path.splitext(_file)[0])
    if filename.isalnum():
        data_generator(filename)


