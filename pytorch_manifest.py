import os
import argparse
import scipy.io.wavfile as wav


parser = argparse.ArgumentParser()
parser.add_argument("--files_dir",default="/home/aaron/data/deepspeech_data",type=str)
parser.add_argument("--out_file",default="./train_manifest.csv",type=str)
args = parser.parse_args()

parent_dir = os.path.abspath(args.files_dir)
wav_dir = os.path.join(parent_dir,"wav")
txt_dir = os.path.join(parent_dir,"stm")

keep_files = []

# get filenames wav directory
for i,filename in enumerate(os.listdir(wav_dir)):
    if i % 10000 == 0:
        print("Processing file {}".format(i))

    fid = os.path.splitext(filename)[0]

    wav_file = os.path.join(wav_dir,"{}.wav".format(fid))
    samp_rate,data = wav.read(wav_file)

    # duration (number of frames divided by framerate) greater than one second
    if len(data)/float(samp_rate) >= 1.:

        txt_file = os.path.join(txt_dir,"{}.txt".format(fid))
        with open(txt_file) as raw_text:
            transcript = raw_text.read().strip()

            # at least two words in transcript
            if len(transcript.split()) > 1 :

                # probably not necessary, but no accented characters
                # will NOT catch escaped code points such as "\xe9"
                try:
                    transcript.decode("ascii")
                except UnicodeDecodeError:
                    print(txt_file)
                    continue
                else:
                    keep_files.append("{},{}".format(wav_file,txt_file))

with open(args.out_file,"w") as out:
    out.write("\n".join(keep_files))
