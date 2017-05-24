import argparse

from aligner import data_generator

parser = argparse.ArgumentParser()
parse.add_argument("--file",default=None,type=str)
parse.add_argument("--min_duration",default=2,type=int)
parse.add_argument("--max_duration",default=(5,20),type=tuple)
parse.add_argument("--randomize",default=False,type=bool)
args = parser.parse_args()

data_generator(args.file,args.min_duration,args.max_duration,args.randomize)


