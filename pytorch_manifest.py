import os
import argparse
import scipy.io.wavfile as wav
import re
import shutil
from tqdm import tqdm
import numpy as np
import sys
import subprocess
import soundfile as sf

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("--data-dir", dest="data_dir", type=str, default="/home/aaron/data/phoenix-files/gaps", help='Directory to read files from')
parser.add_argument("--dst-dir", dest="dst_dir", default="/home/aaron/data/phoenix-files/pytorch", type=str, help="Directory to store dataset to")
parser.add_argument("--min-seconds", dest="min_seconds", default=2.0, type=float, help="Cutoff for minimum duration")
parser.add_argument("--max-seconds", dest="max_seconds", default=20.0, type=float, help="Cutoff for maximum duration")
parser.add_argument("--max-hours", dest="max_hours", default=0, type=int, help="Size of the dataset in hours")
parser.add_argument("--merge-ted", dest="merge_ted", help="Merge with TED dataset", action='store_true', default=False)
parser.add_argument("--dry-run", dest="dry_run", help="Don't write manifest csv's", action='store_true', default=False)
parser.add_argument("--split-ratio", dest="split_ratio", type=float, default=0.01, help="Percent of files to keep in val & test set")
parser.add_argument("--txt-dir", dest="txt_dir", type=str, default="txt", help="Directory name for txt files")
parser.add_argument("--prefix", dest="prefix", type=str, default="unnamed", help="Prefix for manifest files")
parser.add_argument("--manifest-dir", dest="manifest_dir", type=str, default=".", help="Directory for manifest files")
args = parser.parse_args()

parent_dir = os.path.abspath(args.data_dir)
wav_dir = os.path.join(parent_dir,"wav")
txt_dir = os.path.join(parent_dir, args.txt_dir)

dst_dir = os.path.abspath(args.dst_dir)
dst_wav = os.path.join(dst_dir, "wav")
if not os.path.exists(dst_wav):
    os.makedirs(dst_wav)

dst_txt = os.path.join(dst_dir, args.txt_dir)
if not os.path.exists(dst_txt):
    os.makedirs(dst_txt)

def get_duration(wav_file):
    m = re.search("[a-z0-9]+_([0-9]+)_([0-9]+).wav", wav_file)
    if m:
        duration = (int(m.group(2)) - int(m.group(1)))/100.
        return duration

    try:
        f = sf.SoundFile(wav_file)
        if f.samplerate != 16000:
            print("sample rate is {}".format(f.samplerate))
            return 0
        else:
            return len(f)/float(f.samplerate)
    except:
        return 0

def sort_func(element):
    return element[0]

keep_files = []
files= []

FNULL = open(os.devnull, 'w')
out, err = subprocess.Popen("find " + wav_dir + " -type f -size +100c | wc -l", stdout=subprocess.PIPE, shell=True).communicate()
num_files = int(out)

find = subprocess.Popen(["find", wav_dir, "-size" + "+100c", "-type", "f"], stdout=subprocess.PIPE, stderr=FNULL)
for i in tqdm(range(num_files), ncols=100, desc='Finding files'):
    line = find.stdout.readline()
    if len(line.strip()) > 0:
        files.append(os.path.basename(line))
    else:
        break

total_hours = 0

# get filenames wav directory
for i in tqdm(range(num_files), ncols=100, desc='Checking files'):
    filename = files[i]
    fid = os.path.splitext(filename)[0]

    wav_file = os.path.join(wav_dir,"{}.wav".format(fid))
    duration = get_duration(wav_file)
    if duration < args.min_seconds or duration > args.max_seconds:
        continue

    txt_file = os.path.join(txt_dir,"{}.txt".format(fid))
    with open(txt_file) as raw_text:
        transcript = raw_text.read().strip()

    oov = re.search("[^a-zA-Z ']", transcript)
    if oov is not None:
        continue 

    dst_txt_file = os.path.join(dst_txt, "{}.txt".format(fid))
    dst_wav_file = os.path.join(dst_wav, "{}.wav".format(fid))

    if not args.dry_run:
        transcript = re.sub('\s+', ' ', transcript).upper() + "\n"
        with open(dst_txt_file, 'w') as f:
            f.write(transcript)

        if not os.path.isfile(dst_wav_file):
            shutil.copy2(wav_file, dst_wav_file)

    keep_files.append((duration, "{},{}".format(dst_wav_file,dst_txt_file)))

    total_hours += duration/3600
    if args.max_hours != 0 and args.max_hours <= total_hours:
        print("\n")
        break

val_len = int(len(keep_files) * args.split_ratio)

train_set = keep_files[:-val_len*2]
val_set = keep_files[len(train_set):-val_len]
test_set = keep_files[-val_len:]

if args.merge_ted and not args.dry_run:
    ted_train = []
    for line in open("ted_train_manifest.csv","r"):
        ted_train.append(line)

    for i in tqdm(range(len(ted_train)), ncols=100, desc='Merging TED train'):
        line = ted_train[i]
        duration = get_duration(line.split(',')[0])
        train_set.append((duration, line))

    ted_val = []
    for line in open("ted_test_manifest.csv","r"):
        ted_val.append(line)

    for i in tqdm(range(len(ted_val)), ncols=100, desc='Merging TED val'):
        line = ted_val[i]
        duration = get_duration(line.split(',')[0])
        val_set.append((duration, line))

train_set.sort(key=sort_func)
val_set.sort(key=sort_func)
test_set.sort(key=sort_func)

total_train = sum([line[0] for line in train_set])
if not args.dry_run:
    with open(os.path.join(args.manifest_dir, "{}-train-{}.csv".format(args.prefix, int(total_hours))), 'w') as f:
        for line in train_set:
            f.write((line[1].strip() + "\n").encode('utf-8'))

total_val = sum([line[0] for line in val_set])
if not args.dry_run:
    with open(os.path.join(args.manifest_dir, "{}-val-{}.csv".format(args.prefix, int(total_hours))), 'w') as f:
        for line in val_set:
            f.write((line[1].strip() + "\n").encode('utf-8'))

total_test = sum([line[0] for line in test_set])
if not args.dry_run:
    with open(os.path.join(args.manifest_dir, "{}-test-{}.csv".format(args.prefix, int(total_hours))), 'w') as f:
        for line in test_set:
            f.write((line[1].strip() + "\n").encode('utf-8'))

if not args.dry_run:
    # train_set has already been written so modifying in place is ok
    np.random.shuffle(train_set)
    train_subset = train_set[:len(val_set)/2]
    with open(os.path.join(args.manifest_dir, "{}-train-subset-{}.csv".format(args.prefix, int(total_hours))), 'w') as f:
        for line in train_subset:
            f.write((line[1].strip() + "\n").encode("utf-8"))

total = total_train + total_val + total_test

durations = [t[0] for t in train_set]
bins = np.arange(int(args.min_seconds), int(args.max_seconds) + 1)
plt.hist(durations, bins=bins, rwidth=0.8)
plt.xlabel('Seconds')
plt.ylabel('# of files')
plt.grid(color='gray', linestyle='dotted')
plt.xticks(bins)
plt.title("Durations distribution for {} {} hours".format(args.prefix, int(total_hours)))
plt.savefig('durations.png')

print("Total {:.2f} hours, train {:.2f} hours, val {:.2f} hours, test {:.2f}, ratio {:.5f}/{:.5f}/{:.5f}".format(total/3600, total_train/3600, total_val/3600, total_test/3600, total_train/total, total_val/total, total_test/total))
