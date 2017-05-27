import os
import sys
import re
import multiprocessing
import json
import subprocess
import hashlib
import random
import logging
import argparse

import boto3
import gentle

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s - %(message)s",datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("info_logger")

data_dir = '/home/aaron/data'
records_dir = os.path.join(data_dir, 'records')
mp3_dir = os.path.join(data_dir, 'mp3s')
text_out_dir = os.path.join(data_dir, 'deepspeech_data/stm')
wav_out_dir = os.path.join(data_dir, 'deepspeech_data/wav')
json_out_dir = os.path.join(data_dir, 'deepspeech_data/alignments')
use_filename_json = False

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

    if not os.path.isfile(segment):
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

def save_capture(capture_list,start,end,strings):
    """Save the current successfully captured words and times to capture_list"""

    capture = {"start":start,"end":end,"string":" ".join(strings),
                "duration":round(end-start,2)}
    capture_list.append(capture)

    return

def data_generator(file_id,min_dur=2,max_dur=(5,20),randomize=False):
    """Given a file id and random seed, align the audio and text versions after
    dividing into single-speaker utterances, and write out texts of unbroken
    captured strings and their corresponding audio segments when the latter are
    between 2 and max_length seconds.
    """

    if randomize:
        seed = ord(file_id[-1])
        random.seed(seed)
        max_length = random.randint(max_dur[0],max_dur[1])
    else:
        max_length = max_dur[1]

    logger.info("Processing file id {}...".format(file_id))

    # grab audio file from s3
    mp3 = os.path.join(mp3_dir, "{}.mp3".format(file_id))

    if not os.path.isfile(mp3):
        bucket = boto3.resource("s3").Bucket("cgws")
        logger.info("Downloading file {} from S3...".format(file_id))
        try:
            bucket.download_file("{}.mp3".format(file_id),mp3)
        except:
            logger.warning("Could not download file {} from S3.".format(file_id))
            return

    wav = os.path.join("/tmp", "{}.wav".format(file_id))
    if not os.path.isfile(wav):
        FNULL = open(os.devnull, 'w')
        subprocess.call(["sox","{}".format(mp3),"-r","16k",
                    "{}".format(wav),
                    "remix","-"], stdout=FNULL, stderr=FNULL)

    # transcript
    txt_file = os.path.join(records_dir, "{}.txt".format(file_id))
    logger.info("Reading transcript {}...".format(file_id))
    try:
        with open(txt_file,"r") as tr:
            transcript = tr.read()
    except IOError:
        logger.warning("File {} does not exist.".format(txt_file))
        return

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

    # taking one speaker at a time, find unbroken alignments up to max_length
    # and write out corresponding files
    for i,paragraph in enumerate(paragraphs):
        logger.info("Cleaning and trimming paragraph {}: \n{}".format(i,paragraph))

        paragraph_start, paragraph_end = times[i], times[i+1]
        # don't bother with short files
        if paragraph_end-paragraph_start < min_dur:
            logger.info("Skipping paragraph {} (too short)...".format(i))
            continue
        if len(paragraph.split()) < 2:
            logger.info("Skipping paragraph {} (too few words)...".format(i))
            continue

        temp_wav = trim(file_id,wav,paragraph_start,paragraph_end,0,"/tmp")

        # unique name of json object to read/write
        paragraph_hash = hashlib.sha1("{}{}{}{}".format(
                            file_id,paragraph,
                            paragraph_start,paragraph_end)).hexdigest()

        if use_filename_json is True:
            json_file = os.path.join(json_out_dir,"{}_{}_{}.json".format(file_id, paragraph_start, paragraph_end))
        else:
            json_file = os.path.join(json_out_dir,"{}.json".format(paragraph_hash))

        result = None

        # check if json object has been written from a previous run
        if not os.path.isfile(json_file):
            logger.info("JSON file with hash {} not found.".format(paragraph_hash))

            try:
                logger.info("Resampling paragraph {}...".format(i))
                with gentle.resampled(temp_wav) as wav_file:
                    resources = gentle.Resources()
                    cleaned = clean(paragraph)
                    logger.info("Aligning paragraph {} with gentle...".format(i))
                    aligner = gentle.ForcedAligner(resources,cleaned,
                                               nthreads=multiprocessing.cpu_count(),
                                               disfluency=False,conservative=False,
                                               disfluencies=set(["uh","um"]))
                    logger.info("Transcribing audio segment {} with gentle...".format(i))
                    result = aligner.transcribe(wav_file)
            except:
                logger.warning("Paragraph {} - {} ".format(i,sys.exc_info()[2]))
                os.remove(temp_wav)
                continue

            aligned_words = result.to_json()
            with open(json_file,"w") as f:
                f.write(aligned_words)

            if not result:
                logger.info("Empty result for paragraph {}.".format(i))
                os.remove(temp_wav)
                continue

        else:
            logger.info("Found JSON of paragraph {} -- skipping alignment and transcription by gentle".format(i))

        # dictionary of aligned words
        with open(json_file) as f:
            aligned = json.loads(f.read())

        # save all consecutively captured strings
        # and keep track of their start and stop times
        captures = []
        current,start_time,end_time = [],0,0

        # loop through every word as returned from gentle
        logger.info("Capturing strings in paragraph {}...".format(i))

        if not "words" in aligned:
            logger.info("No words in paragraph {}.".format(i))
            os.remove(temp_wav)
            continue

        # first two seconds will be skipped even if it contains a capture
        for catch in aligned["words"]:
            # successful capture
            if catch["case"] == "success" and catch["alignedWord"] != "<unk>" and catch['start'] > 5 and catch['end'] - catch['start'] > .07:

                # new capture group
                if not current:
                    # begin capturing if it has been two seconds since the last word
                    if catch["start"]-end_time > 1:
                        current = [catch["alignedWord"]]
                        start_time = catch["start"]
                        end_time = catch["end"]

                # continuation of a capture group
                else:
                    # large gap between last capture and this one
                    # likely that something was missing in the transcript
                    if catch["start"]-end_time > 1:
                        save_capture(captures,start_time,end_time,current)
                        current = []

                    # adding this word would equal or exceed max_length
                    elif catch["end"]-start_time >= max_length:
                        save_capture(captures,start_time,end_time,current)
                        current = []
                        if randomize:
                            max_length = random.randint(max_dur[0],max_dur[1])

                    # continue capturing
                    else:
                        current.append(catch["alignedWord"])
                        end_time = catch["end"]

            # a miss after prior success(es)
            elif current:
                save_capture(captures,start_time,end_time,current)
                current = []

        # last word was a success but current capture hasn't been saved yet
        if current:
            save_capture(captures,start_time,end_time,current)

        # write strings and split audio into consituent segments
        logger.info("Writing text and audio segments from paragraph {}...".format(i))
        for result in captures:
            # don't write short files
            if result["duration"] < min_dur:
                logger.info("Skipping capture from paragraph {} (too short)...".format(i))
                continue
            if len(result["string"].split()) < 2:
                logger.info("Skipping capture from paragraph {} (too few words)...".format(i))
                continue

            txt_segment = os.path.join(text_out_dir,"{}_{}_{}.txt".format(
                        file_id,
                        "{:07d}".format(int((times[i]+result["start"])*100)),
                        "{:07d}".format(int((times[i]+result["end"])*100))))
            with open(txt_segment,"w") as f:
                f.write("{}\n".format(result["string"]))

            segment = trim(file_id,temp_wav,result["start"],result["end"],
                           times[i],wav_out_dir)
            # make sure durations match
            segment_dur = get_duration(segment)
            assert segment_dur - result["duration"] <= .01

            total_captures += 1
            captures_dur += segment_dur

        # delete the clip of this speaker
        os.remove(temp_wav)

    os.remove(wav)

    # per-file logging
    total_dur = get_duration(mp3)
    logger.info("Wrote {} segments from {}, totalling {} seconds, out of a possible {}, ratio {:.2f}."\
          .format(total_captures,file_id,captures_dur,total_dur,captures_dur/total_dur))

    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate deepspeech data from Scribie transcripts')
    parser.add_argument('file_id', type=str, help='file id to process')
    parser.add_argument('--data_dir', type=str, help='path to data dir', default='/home/rajiv/host/align')
    parser.add_argument('--use_filename_json', type=bool, help='read alignment json from filename_start_end.json file', default=True)
    args = parser.parse_args()

    data_dir = args.data_dir
    records_dir = args.data_dir
    mp3_dir = args.data_dir
    text_out_dir = args.data_dir
    wav_out_dir = args.data_dir
    json_out_dir = args.data_dir
    use_filename_json = True

    data_generator(args.file_id)
