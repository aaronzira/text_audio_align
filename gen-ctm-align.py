import argparse
import os
import subprocess
from tqdm import tqdm

parser = argparse.ArgumentParser()
parser.add_argument('manifest', type=str, help='list of file ids')
args = parser.parse_args()

files = open(args.manifest).read().strip().split('\n')

for i in tqdm(range(len(files)), ncols=100):
    if os.path.exists(files[i] + ".ctm"):
        subprocess.call("node ctm-align.js " + files[i], shell=True)

