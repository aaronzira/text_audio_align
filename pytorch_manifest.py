import os
import argparse
import scipy.io.wavfile as wav
import re
import shutil
from tqdm import tqdm

parser = argparse.ArgumentParser()
parser.add_argument("--files_dir",default="/home/aaron/data/deepspeech_data",type=str)
parser.add_argument("--dst_dir",default=".",type=str)
parser.add_argument("--merge_ted",default=True,type=bool)
args = parser.parse_args()

parent_dir = os.path.abspath(args.files_dir)
wav_dir = os.path.join(parent_dir,"wav")
txt_dir = os.path.join(parent_dir,"stm")

dst_dir = os.path.abspath(args.dst_dir)

keep_files = []

files = os.listdir(wav_dir)

def get_duration(wav_file):
    # duration (number of frames divided by framerate) greater than one second
    samp_rate,data = wav.read(wav_file)
    duration = len(data)/float(samp_rate)
    return data, duration

def sort_func(element):
    return element[0]

# get filenames wav directory
for i in tqdm(range(len(files)), ncols=100, desc='Copying files'):
    filename = files[i]
    fid = os.path.splitext(filename)[0]

    wav_file = os.path.join(wav_dir,"{}.wav".format(fid))
    try:
        data, duration = get_duration(wav_file)
    except:
        print("skipping %s wav file read failed" % (fid))
        continue

    if duration <= 2. or duration >= 20.:
      continue

    txt_file = os.path.join(txt_dir,"{}.txt".format(fid))
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

    dst_wav = os.path.join(dst_dir, "wav/{}.wav".format(fid))
    if not os.path.isfile(dst_wav):
        with open(dst_wav, 'w') as f:
            f.write(data)
    
    dst_txt = os.path.join(dst_dir, "stm/{}.txt".format(fid))
    if not os.path.isfile(dst_txt):
        with open(dst_txt, 'w') as f:
            f.write(transcript + "\n")

    keep_files.append((duration, "{},{}".format(dst_wav,dst_txt)))

train_len = int(len(keep_files) * 0.90)

train_set = keep_files[:train_len]
val_set = keep_files[train_len:]

if args.merge_ted is True:
    ted_train = []
    for line in open("ted_train_manifest.csv","r"):
        ted_train.append(line)

    for i in tqdm(range(len(ted_train)), ncols=100, desc='Merging TED train'):
        line = ted_train[i]
        _, duration = get_duration(line.split(',')[0])
        train_set.append((duration, line))

    ted_val = []
    for line in open("ted_test_manifest.csv","r"):
        ted_val.append(line)

    for i in tqdm(range(len(ted_val)), ncols=100, desc='Merging TED val'):
        line = ted_val[i]
        _, duration = get_duration(line.split(',')[0])
        val_set.append((duration, line))

train_set.sort(key=sort_func)
val_set.sort(key=sort_func)

total_train = 0
with open('train.csv', 'w') as f:
    for line in train_set:
        f.write((line[1].strip() + "\n").encode('utf-8'))
        total_train += line[0]

total_val = 0
with open('val.csv', 'w') as f:
    for line in val_set:
        f.write((line[1].strip() + "\n").encode('utf-8'))
        total_val += line[0]

print("Train {:.2f} hours, Val {:.2f} hours".format(total_train/3600, total_val/3600))
