import os
import sys
import re
import multiprocessing
import json
import subprocess
import hashlib
import random
from shutil import copyfile
import argparse

import boto3
import gentle

parser = argparse.ArgumentParser(description='Generate paragraph alignments from Scribie transcripts')
parser.add_argument('file_id', type=str, help='file id to process')
args = parser.parse_args()

def clean(text):
    """Clean transcript of timestamps and speaker trackings, metas,
    punctuation, and extra whitespace.
    """

    text = re.sub("\d:\d+:\d+\.\d S(\d+|\?): ","",text)
    text = re.sub("\[.+?\]","",text)
    text = re.sub("\-"," ",text)
    text = re.sub(r"[^a-zA-Z0-9\' ]","",text,re.UNICODE)
    ### don't worry about converting to ascii for now
    cleaned = re.sub("\s{2,}"," ",text)

    return cleaned

def trim(base_filename,audio_file,start,end,offset,out_directory):
    """Write out a segment of an audio file to wav, based on start, end,
    and offset times in seconds.
    """

    segment = os.path.join(out_directory,"{}_{}_{}.wav".format(
                                    base_filename,
                                   "{:07d}".format(int((offset+start)*100)),
                                   "{:07d}".format(int((offset+end)*100))))

    duration = end-start
    subprocess.call(["sox","{}".format(audio_file),"-r","16k",
                "{}".format(segment),"trim","{}".format(start),
                "{}".format(duration),"remix","-"])

    return segment

def get_duration(audio_file):
    """Determine the length of an audio file in seconds"""

    duration = float(subprocess.Popen(
                            ["soxi","-D","{}".format(audio_file)],
                            stdout=subprocess.PIPE).stdout.read().strip())

    return duration

if __name__ == '__main__':

    file_id = args.file_id

    # output
    wav_out_dir = "/home/aaron/data/deepspeech_data/wav"
    json_out_dir = "/home/aaron/data/deepspeech_data/alignments"
    txt_file = "/home/aaron/data/records/{}.txt".format(file_id)
    mp3 = "/home/aaron/data/mp3s/{}.mp3".format(file_id)

    #wav_out_dir = "/home/rajiv/host/align/"
    #json_out_dir = "/home/rajiv/host/align/"
    #txt_file = "/home/rajiv/host/align/{}.txt".format(file_id)
    #mp3 = "/home/rajiv/host/align/{}.mp3".format(file_id)

    try:
        with open(txt_file,"r") as tr:
            transcript = tr.read()
    except IOError:
        print("File {} does not exist.".format(txt_file))
        sys.exit()

    # split transcript by speaker, and get timestamps (as seconds)
    # of the boundaries of each paragraph
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

        if paragraph_end - paragraph_start <= 0:
            continue

        # unique name of json object to read/write
        paragraph_hash = hashlib.sha1("{}{}{}{}".format(
                            file_id,paragraph,
                            paragraph_start,paragraph_end)).hexdigest()
        json_file = os.path.join(json_out_dir,"{}.json".format(paragraph_hash))

        if not os.path.isfile(json_file):

            temp_wav = trim(file_id,mp3,paragraph_start,paragraph_end,0,"/tmp")

            try:
                with gentle.resampled(temp_wav) as wav_file:
                    resources = gentle.Resources()
                    cleaned = clean(paragraph)
                    aligner = gentle.ForcedAligner(resources,cleaned,
                                               nthreads=multiprocessing.cpu_count(),
                                               disfluency=False,conservative=False,
                                               disfluencies=set(["uh","um"]))
                    result = aligner.transcribe(wav_file)

                aligned_words = result.to_json()
                with open(json_file,"w") as f:
                    f.write(aligned_words)

            except:
                print(sys.exc_info())
                os.remove(temp_wav)
                continue

        new_json_file = os.path.join(json_out_dir,"{}_{}_{}.json".format(file_id, paragraph_start, paragraph_end))
        copyfile(json_file, new_json_file)
