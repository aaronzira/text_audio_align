import argparse
import json
import os
import subprocess
import re
from tqdm import tqdm
import logging

parser = argparse.ArgumentParser()
parser.add_argument('file_id', type=str, help='file id to process')
parser.add_argument("--min-gap", default=0.25, type=float, dest="min_gap", help="minimum gap between words to use for splitting")
parser.add_argument('--file-index', type=str, default="1", dest="file_index", help='file index to print')
parser.add_argument('--audio-dir', type=str, dest="audio_dir", default='.', help='Path to the directory containing audio files')
parser.add_argument('--align-dir', type=str, dest="align_dir", default=".", help='Path to the directory containing alignments')
parser.add_argument('--dataset-dir', type=str, dest="dataset_dir", default='.', help='Path to the dataset directory')
args = parser.parse_args()

logging.basicConfig(filename='gaps.log', level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("info_logger")

# temporarily running them from "others/"
ctm_file = os.path.join(args.align_dir, args.file_id + "_align.json")
audio_file = os.path.join(args.audio_dir, args.file_id + ".mp3")

# leaving offset here in case the algo changes to require it
def sox_trim(start, end):
    """Write out a segment of an audio file to wav, based on start, end,
    """
    FNULL = open("/dev/null")
    wav_file = os.path.join(args.dataset_dir, "wav/{}_{:07d}_{:07d}.wav".format(args.file_id, int(start*100), int(end*100))) 
    subprocess.call(["sox", audio_file, "-r", "16k", wav_file, "trim", str(start), str(end - start), "remix", "-"], stdout=FNULL, stderr=FNULL)

with open(ctm_file) as f:
    ctms = json.loads(f.read())

    null_word = {'start': 0, 'end':0}
    gaps = [second['start']-first['end'] for first, second in zip([null_word]+ctms, ctms)]

    # we split from one good gap to the next
    # a good gap is when the silence between the words is long
    # and the word *itself* is long and is not a mismatch
    good_gaps = [(i, gap) for i, gap in enumerate(gaps) if gap > args.min_gap and ctms[i]['duration'] > args.min_gap and ctms[i]['case'] != 'mismatch']

    total_written = 0
    for i in tqdm(range(len(good_gaps)), desc="({}) {}".format(args.file_index, args.file_id), ncols=100):
        ctm_index = good_gaps[i][0]
        gap = good_gaps[i][1]

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
            start_sec = clip[0]['start']
            end_sec = clip[-1]['end']

            sox_trim(start_sec, end_sec)

            txt_file = os.path.join(args.dataset_dir, "txt/{}_{:07d}_{:07d}.txt".format(args.file_id, int(start_sec*100), int(end_sec*100))) 

            with open(txt_file, "w") as f:
                f.write(words + "\n")

            duration = end_sec - start_sec
            logger.info("{}: gap {}s, start {}s, end {}s, duration {}s".format(ctm_index, gap, start_sec, end_sec, duration))

            total_written += duration

logger.info("Wrote {} seconds out of {} ({:.2f}%) for {}.".format(total_written,ctms[-1]['end'],(total_written/ctms[-1]['end'])*100, args.file_id))
