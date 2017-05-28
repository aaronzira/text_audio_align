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
parser.add_argument("--min_seconds",default="2",type=float, help="Cutoff for minimum duration")
parser.add_argument("--max_seconds",default="20",type=float, help="Cutoff for maximum duration")
parser.add_argument("--no_ted", help="Merge with TED dataset", action='store_true', default=False)
parser.add_argument("--dry_run", help="Don't write csv's or copy files", action='store_true', default=False)
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

keep_files = []

files = os.listdir(wav_dir)

def get_duration(wav_file):
    f = sf.SoundFile(wav_file)
    return float(len(f)/f.samplerate)

def sort_func(element):
    return element[0]

# get filenames wav directory
for i in tqdm(range(len(files)), ncols=100, desc='Copying files'):
    filename = files[i]
    fid = os.path.splitext(filename)[0]

    wav_file = os.path.join(wav_dir,"{}.wav".format(fid))
    dst_wav_file = os.path.join(dst_wav, "{}.wav".format(fid))

    if not os.path.isfile(dst_wav_file):
        duration = get_duration(wav_file)
    else:
        duration = get_duration(dst_wav_file)

    if duration < args.min_seconds or duration > args.max_seconds:
        continue

    if args.dry_run is False:
        shutil.copy2(wav_file, dst_wav_file)

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

        if args.dry_run is False:
            with open(dst_txt_file, 'w') as f:
                f.write(transcript + "\n")

    keep_files.append((duration, "{},{}".format(dst_wav_file,dst_txt_file)))

train_len = int(len(keep_files) * 0.90)

train_set = keep_files[:train_len]
val_set = keep_files[train_len:]

if args.no_ted is False:
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

total_train = 0
with open('train.csv', 'w') as f:
    for line in train_set:
        if args.dry_run is False:
            f.write((line[1].strip() + "\n").encode('utf-8'))
        total_train += line[0]

total_val = 0
with open('val.csv', 'w') as f:
    for line in val_set:
        if args.dry_run is False:
            f.write((line[1].strip() + "\n").encode('utf-8'))
        total_val += line[0]

durations = [t[0] for t in train_set]
h, b = np.histogram(durations, bins=np.arange(args.min_seconds, args.max_seconds + 1))
plt.bar(np.arange(args.min_seconds + 1, args.max_seconds + 1), h, align='center')
plt.xlabel('Seconds')
plt.ylabel('# of files')
plt.grid(color='gray', linestyle='dashed')
plt.title('Durations distribution')
plt.savefig('durations.png')

print("Total {:.2f} hours, train {:.2f} hours, val {:.2f} hours, ratio {:.2f}".format((total_train + total_val)/3600, total_train/3600, total_val/3600, total_val/total_train))
