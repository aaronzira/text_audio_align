import argparse
import json
import os
import subprocess
import re

parser = argparse.ArgumentParser()
parser.add_argument("--file_id",help="filename without .json or .mp3 extension")
parser.add_argument("--min_gap",default=0.25,type=float,help="minimum gap between words to use for splitting")
parser.add_argument("--debug",action="store_true")
args = parser.parse_args()


# temporarily running them from "others/"
ctm_file = "".join(("./",args.file_id,"_align.json"))
audio_file = ".".join(("./"+args.file_id,"mp3"))

# leaving offset here in case the algo changes to require it
def trim(base_filename,audio_file,start,end,offset):
    """Write out a segment of an audio file to wav, based on start, end,
    and offset times in seconds.
    """
    FNULL = open("/dev/null")
    # still os.path.join for adding out dir later
    segment = os.path.join("{}_{}_{}.wav".format(
                                    base_filename,
                                   "{:07d}".format(int((offset+start)*100)),
                                   "{:07d}".format(int((offset+end)*100))))
    duration = end-start
    subprocess.call(["sox","{}".format(audio_file),"-r","16k",
                "{}".format(segment),"trim","{}".format(start),
                "{}".format(duration),"remix","-"],
                stdout=FNULL,stderr=FNULL)

    return segment

with open(ctm_file) as f:
    ctms = json.loads(f.read())

    null_word = {'case':None, 'conf':None, 'duration':0, 'end':0, 'orig':None, 'pred':None, 'start':0, 'word':None}
    gaps = [second['start']-first['end'] for first,second in zip([null_word]+ctms,ctms)]

    # we split from one good gap to the next
    # a good gap is when the silence between the words is long
    # and the word *itself* is long and is not a mismatch
    good_gaps = [(i, gap) for i, gap in enumerate(gaps) if gap > args.min_gap and ctms[i]['duration'] > args.min_gap and ctms[i]['case'] != 'mismatch']

    total_written = 0
    for i, g in enumerate(good_gaps):
        ctm_index = g[0]
        gap = g[1]

        # to prevent out of bounds
        if i+1 >= len(good_gaps):
            continue

        # we start splitting from this ctm_index to the next good gap
        start_index = ctm_index
        end_index = good_gaps[i+1][0]

        # this is our clip
        clip = ctms[start_index:end_index]

        n_words = len(clip)
        n_mismatches = sum([word['case'] == 'mismatch' for word in clip])
        words = " ".join([word["word"] for word in clip])

        if n_words >= 5 and n_mismatches >= 1:
            clip_start = clip[0]['start']
            clip_end = clip[-1]['end']

            wav_name = trim(args.file_id, audio_file, clip_start, clip_end, 0)

            # text file is .wav repalced with .txt
            txt_name = re.sub(".wav$", ".txt", wav_name)

            with open(txt_name,"w") as f:
                f.write(words + "\n")

            total_written += clip_end - clip_start

print("Wrote {} seconds out of {} ({:.2f}%).".format(total_written,ctms[-1]['end'],(total_written/ctms[-1]['end'])*100))
