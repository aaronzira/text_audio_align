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
from tqdm import tqdm
import traceback

import boto3
import gentle

parser = argparse.ArgumentParser(description='Generate paragraph level alignments from Scribie data')
parser.add_argument('file_id', type=str, help='file id to process')
parser.add_argument('--file_index', type=str, help='file index to print', default="1")
parser.add_argument('--abort', help='Abort if alignemnt already exists', action='store_true', default=False)
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
    FNULL = open(os.devnull, 'w')
    subprocess.call(["sox","{}".format(audio_file),"-r","16k",
                "{}".format(segment),"trim","{}".format(start),
                "{}".format(duration),"remix","-"], stdout=FNULL, stderr=FNULL)

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
    mp3_dir = "/home/aaron/data/mp3s/"
    txt_file = "/home/aaron/data/records/{}.txt".format(file_id)

    '''
    wav_out_dir = "/home/rajiv/host/align/"
    json_out_dir = "/home/rajiv/host/align/"
    mp3_dir = "/home/rajiv/host/align/"
    txt_file = "/home/rajiv/host/align/{}.txt".format(file_id)
    '''

    mp3 = "{}/{}.mp3".format(mp3_dir,file_id)
    wav = "{}/{}.wav".format(mp3_dir,file_id)

    try:
        with open(txt_file,"r") as tr:
            transcript = tr.read()
    except IOError:
        print("File {} does not exist.".format(txt_file))
        sys.exit()

    if not os.path.isfile(wav):
        if not os.path.isfile(mp3):
            bucket = boto3.resource("s3").Bucket("cgws")
            try:
                bucket.download_file("{}.mp3".format(file_id),mp3)
            except:
                print("Could not download file {} from S3.".format(file_id))
                sys.exit()

        FNULL = open(os.devnull, 'w')
        subprocess.call(["sox","{}".format(mp3),"-r","16k",
                    "{}".format(wav),
                    "remix","-"], stdout=FNULL, stderr=FNULL)

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

    for i in tqdm(range(len(paragraphs)), desc="({}) {}".format(args.file_index, file_id), ncols=100):
        paragraph = paragraphs[i]
        paragraph_start, paragraph_end = times[i], times[i+1]

        if paragraph_end - paragraph_start <= 0.2:
            continue

        # unique name of json object to read/write
        paragraph_hash = hashlib.sha1("{}{}{}{}".format(
                            file_id,paragraph,
                            paragraph_start,paragraph_end)).hexdigest()
        json_file = os.path.join(json_out_dir,"{}.json".format(paragraph_hash))
        new_json_file = os.path.join(json_out_dir,"{}_{}_{}.json".format(file_id, paragraph_start, paragraph_end))
        if os.path.isfile(new_json_file):
            if args.abort:
                print("aborting")
                break
        else:
            if not os.path.isfile(json_file):

                temp_wav = trim(file_id,wav,paragraph_start,paragraph_end,0,"/tmp")

                if not os.path.isfile(temp_wav):
                    continue

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
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    print ''.join(line for line in lines)
                    continue

            copyfile(json_file, new_json_file)
