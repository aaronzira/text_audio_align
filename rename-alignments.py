import os
import sys
import re
import multiprocessing
import json
import subprocess
import hashlib
import random
import logging
from shutil import copyfile

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s - %(message)s",datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("info_logger")

def get_duration(audio_file):
    """Determine the length of an audio file in seconds"""

    duration = float(subprocess.Popen(
                            ["soxi","-D","{}".format(audio_file)],
                            stdout=subprocess.PIPE).stdout.read().strip())

    return duration

if __name__ == '__main__':

    file_id = sys.argv[1]

    # output
    text_out_dir = "/home/aaron/data/deepspeech_data/stm"
    wav_out_dir = "/home/aaron/data/deepspeech_data/wav"
    json_out_dir = "/home/aaron/data/deepspeech_data/alignments"

    # transcript
    txt_file = "/home/aaron/data/records/{}.txt".format(file_id)
    mp3 = "/home/aaron/data/mp3s/{}.mp3".format(file_id)
    logger.info("Reading transcript {}...".format(file_id))

    try:
        with open(txt_file,"r") as tr:
            transcript = tr.read()
    except IOError:
        logger.warning("File {} does not exist.".format(txt_file))
        sys.exit()

    # split transcript by speaker, and get timestamps (as seconds)
    # of the boundaries of each paragraph
    logger.info("Splitting transcript by speaker...")
    paragraphs = []
    times = []
    for paragraph in transcript.split("\n"):
        catch = re.match("\d:\d+:\d+\.\d",paragraph)
        if catch:
            timestamp = catch.group()
            h,m,s = timestamp.split(":")
            time = int(h)*60*60 + int(m)*60 + float(s)
            paragraphs.append(paragraph)
            times.append(time)
    file_end = get_duration(mp3)
    times.append(file_end)

    total_captures,captures_dur = 0,0

    for i,paragraph in enumerate(paragraphs):
        paragraph_start, paragraph_end = times[i], times[i+1]

        # unique name of json object to read/write
        paragraph_hash = hashlib.sha1("{}{}{}{}".format(
                            file_id,paragraph,
                            paragraph_start,paragraph_end)).hexdigest()
        json_file = os.path.join(json_out_dir,"{}.json".format(paragraph_hash))

        if not os.path.isfile(json_file):
            logger.info("JSON file with hash {} not found.".format(paragraph_hash))
        else:
            logger.info("Found JSON of paragraph {} -- skipping alignment and transcription by gentle".format(i))

            new_json_file = os.path.join(json_out_dir,"{}_{}_{}.json".format(file_id, paragraph_start, paragraph_end))
            copyfile(json_file, new_json_file)
