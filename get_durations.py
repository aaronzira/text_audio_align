import os
import argparse
import numpy as np
import scipy.io.wavfile as wav


parser = argparse.ArgumentParser()
parser.add_argument("--files_dir",default="/home/aaron/data/deepspeech_data/wav",type=str)
args = parser.parse_args()


durations = []

for i,filename in enumerate(os.listdir(args.files_dir)):
    if i % 10000 == 0:
        print("Processing file {}".format(i))

    fid = os.path.splitext(filename)[0]

    wav_file = os.path.join(args.files_dir,"{}.wav".format(fid))
    samp_rate,data = wav.read(wav_file)
    duration = len(data)/float(samp_rate)
    durations.append(duration)

durations = np.asarray(durations)


np.save("./durations_binary.npy",durations)
