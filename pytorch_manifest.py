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
parser.add_argument("--data_dir",default="/home/aaron/data/deepspeech_data",type=str,help='Directory to read files from')
parser.add_argument("--dst_dir",default=".",type=str, help="Directory to store dataset to")
parser.add_argument("--min_seconds",default=1.0,type=float, help="Cutoff for minimum duration")
parser.add_argument("--max_seconds",default=20.0,type=float, help="Cutoff for maximum duration")
parser.add_argument("--no_ted", help="Merge with TED dataset", action='store_true', default=False)
parser.add_argument("--dry_run", help="Don't write manifest csv's", action='store_true', default=False)
parser.add_argument("--split_ratio", help="Percent of files to keep in val set", type=float, default=0.01)
args = parser.parse_args()

parent_dir = os.path.abspath(args.data_dir)
wav_dir = os.path.join(parent_dir,"wav")
txt_dir = os.path.join(parent_dir,"stm")

dst_dir = os.path.abspath(args.dst_dir)
dst_wav = os.path.join(dst_dir, "wav")
if not os.path.exists(dst_wav):
    os.makedirs(dst_wav)

dst_txt = os.path.join(dst_dir, "stm")
if not os.path.exists(dst_txt):
    os.makedirs(dst_txt)

def get_duration(wav_file):
    f = sf.SoundFile(wav_file)
    if f.samplerate != 16000:
        print("sample rate is {}".format(f.samplerate))
        return 0
    else:
        return float(len(f)/f.samplerate)

def sort_func(element):
    return element[0]

keep_files = []
files= []

FNULL = open(os.devnull, 'w')
out, err = subprocess.Popen("find " + wav_dir + " -type f | wc -l", stdout=subprocess.PIPE, shell=True).communicate()
num_files = int(out)

find = subprocess.Popen(["find", wav_dir, "-type", "f"], stdout=subprocess.PIPE, stderr=FNULL)
for i in tqdm(range(num_files), ncols=100, desc='Finding files'):
    line = find.stdout.readline()
    if len(line.strip()) > 0:
        files.append(os.path.basename(line))
    else:
        break

# get filenames wav directory
for i in tqdm(range(num_files), ncols=100, desc='Copying files'):
    filename = files[i]
    fid = os.path.splitext(filename)[0]

    wav_file = os.path.join(wav_dir,"{}.wav".format(fid))
    dst_wav_file = os.path.join(dst_wav, "{}.wav".format(fid))

    if not os.path.isfile(dst_wav_file):
        duration = get_duration(wav_file)
        shutil.copy2(wav_file, dst_wav_file)
    else:
        duration = get_duration(dst_wav_file)

    if duration < args.min_seconds or duration > args.max_seconds:
        continue

    txt_file = os.path.join(txt_dir,"{}.txt".format(fid))
    dst_txt_file = os.path.join(dst_txt, "{}.txt".format(fid))
    if not os.path.isfile(dst_txt_file):
        with open(txt_file) as raw_text:
            transcript = raw_text.read().strip()

        if len(transcript) == 0:
            continue 

        transcript = re.sub('\s+', ' ', transcript)

        # at least two words in transcript
        num_words = len(transcript.split())
        if num_words <= 1:
            print("skipping %s as num word is %d" % (fid, num_words))
            continue 

        oov = re.search("[^a-zA-Z ']", transcript)
        if oov is not None:
            print("skipping %s due to oov, %s" % (fid, transcript))
            continue 

        with open(dst_txt_file, 'w') as f:
            f.write(transcript.upper() + "\n")

    keep_files.append((duration, "{},{}".format(dst_wav_file,dst_txt_file)))

val_len = int(len(keep_files) * args.split_ratio)

train_set = keep_files[:-val_len]
val_set = keep_files[-val_len:]

if not args.no_ted and not args.dry_run:
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

total_train = sum([line[0] for line in train_set])
if not args.dry_run:
    with open('train.csv', 'w') as f:
        for line in train_set:
            f.write((line[1].strip() + "\n").encode('utf-8'))

total_val = sum([line[0] for line in val_set])
if not args.dry_run:
    with open('val.csv', 'w') as f:
        for line in val_set:
            f.write((line[1].strip() + "\n").encode('utf-8'))

if not args.dry_run:
    # train_set has already been written so modifying in place is ok
    np.random.shuffle(train_set)
    train_subset = train_set[:len(val_set)]
    with open('train_subset.csv', 'w') as f:
        for line in train_subset:
            f.write((line[1].strip() + "\n").encode("utf-8"))

total = total_train + total_val

durations = [t[0] for t in train_set]
bins = np.arange(int(args.min_seconds), int(args.max_seconds) + 1)
plt.hist(durations, bins=bins, rwidth=0.8)
plt.xlabel('Seconds')
plt.ylabel('# of files')
plt.grid(color='gray', linestyle='dotted')
plt.xticks(bins)
plt.title("Durations distribution @ {} hours".format(int(total/3600)))
plt.savefig('durations.png')

print("Total {:.2f} hours, train {:.2f} hours, val {:.2f} hours, ratio {:.2f}".format(total/3600, total_train/3600, total_val/3600, total_val/total_train))
