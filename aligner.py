import os
import sys
import re
import multiprocessing
import json
import subprocess
import hashlib
import random

import boto3
import gentle
import logging

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s - %(message)s",datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("info_logger")

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

def data_generator(file_id,seed):
    """Given a file id, align the audio and text versions after dividing into
    single-speaker utterances, and write out texts of unbroken captured strings
    with their corresponding audio segments when the latter are less than
    max_length seconds.
    """

    random.seed(seed)
    max_length = random.randint(5,20)

    logger.info("Processing file id {}...".format(file_id))

    # transcript
    txt_file = "/home/aaron/data/records/{}.txt".format(file_id)

    # grab audio file from s3
    mp3 = "/home/aaron/data/mp3s/{}.mp3".format(file_id)

    if not os.path.isfile(mp3):
        bucket = boto3.resource("s3").Bucket("cgws")
        logger.info("Downloading file {} from S3...".format(file_id))
        try:
            bucket.download_file("{}.mp3".format(file_id),mp3)
        except:
            logger.warning("File {} does not exist on S3.".format(file_id))
            return


    # output
    text_out_dir = "/home/aaron/data/deepspeech_data/stm"
    wav_out_dir = "/home/aaron/data/deepspeech_data/wav"
    json_out_dir = "/home/aaron/data/deepspeech_data/alignments"

    # reading json from alignment using gentle
    logger.info("Reading transcript...")
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
    resources = gentle.Resources()

    # taking one speaker at a time, find unbroken alignments up to max_length
    # and write out corresponding files
    for i,paragraph in enumerate(paragraphs):
        logger.info("Paragraph {}: \n{}".format(i,paragraph))
        logger.info("Cleaning and trimming paragraph {}...".format(i))

        paragraph_start, paragraph_end = times[i], times[i+1]
        if paragraph_end-paragraph_start < .2: continue

        cleaned = clean(paragraph)
        temp_wav = trim(file_id,mp3,paragraph_start,paragraph_end,0,"./temp")

        result = None

        paragraph_hash = hashlib.sha1("{}{}{}{}".format(
                            file_id,paragraph,
                            paragraph_start,paragraph_end)).hexdigest()
        json_file = os.path.join(json_out_dir,"{}.json".format(paragraph_hash))

        if not os.path.isfile(json_file):

            logger.info("Resampling paragraph {}...".format(i))
            try:
                with gentle.resampled(temp_wav) as wav_file:
                    aligner = gentle.ForcedAligner(resources,cleaned,
                                               nthreads=multiprocessing.cpu_count(),
                                               disfluency=False,conservative=False,
                                               disfluencies=set(["uh","um"]))
                    logger.info("Transcribing audio segment {} with gentle...".format(i))
                    result = aligner.transcribe(wav_file)
            except:
                logger.warning("Paragraph {} - {} ".format(i,sys.exc_info()[2]))

            if not result:
                os.remove(temp_wav)
                continue
            # dictionary of aligned words
            aligned_words = result.to_json()
            aligned = json.loads(aligned_words)

            with open(json_file,"w") as f:
                f.write(aligned_words)

        else:
            logger.info("Found alignment of paragraph {} -- \
                skipping alignment and transcription by gentle".format(i))
            with open(json_file) as f:
                aligned = json.loads(f.read())

        # save all consecutively captured strings
        # and keep track of their start and stop times
        captures = []
        current,start,end = None,None,None

        # loop through every word as returned from gentle
        logger.info("Aligning words in paragraph {}...".format(i))
        for catch in aligned["words"]:

            # successful capture
            if catch["case"] == "success" and catch["alignedWord"] != "<unk>":

                # beginning of a capture group
                if not current:
                    start_time = catch["start"]
                    current = catch["alignedWord"]
                    end_time = catch["end"]

                # continuation of a capture group
                else:
                    running_time = catch["end"]-start_time

                    # save current alignment and start another if adding this
                    # word would exceed max_length
                    if running_time >= max_length:
                        captures.append({"start":start_time,"end":end_time,
                                        "string":current,
                                        "duration":round(end_time-start_time,2)})

                        max_length = random.randint(5,20)
                        start_time = catch["start"]
                        current = catch["alignedWord"]
                        end_time = catch["end"]

                    # continue capturing
                    else:
                        current = " ".join([current,catch["alignedWord"]])
                        end_time = catch["end"]

            # a miss after prior success(es)
            elif current:
                captures.append({"start":start_time,"end":end_time,
                                "string":current,
                                "duration":round(end_time-start_time,2)})
                current = None

        # last word was a success but current capture hasn't been saved yet
        if current:
            captures.append({"start":start_time,"end":end_time,
                "string":current,"duration":round(end_time-start_time,2)})
            current = None

        # write strings and split audio into consituent segments
        logger.info("Writing text and audio segments from paragraph {}...".format(i))
        for result in captures:
            # don't write files shorter than 2 seconds
            if result["duration"] < 2.: continue

            txt_segment = os.path.join(text_out_dir,"{}_{}_{}.txt".format(
                        file_id,
                        "{:07d}".format(int((times[i]+result["start"])*100)),
                        "{:07d}".format(int((times[i]+result["end"])*100))))
            with open(txt_segment,"w") as f:
                f.write("{}\n".format(result["string"]))

            segment = trim(file_id,temp_wav,result["start"],result["end"],
                           times[i],wav_out_dir)
            segment_dur = get_duration(segment)
            assert segment_dur - result["duration"] <= .01

            total_captures += 1
            captures_dur += segment_dur

        # delete the clip of this speaker
        os.remove(temp_wav)

    # basic logging
    total_dur = get_duration(mp3)
    logger.info("Wrote {} segments from {}, totalling {} seconds, out of a possible {}."\
          .format(total_captures,file_id,captures_dur,total_dur))
    print("Wrote {} segments from {}, totalling {} seconds, out of a possible {}."\
          .format(total_captures,file_id,captures_dur,total_dur))

    # delete entire audio file
    os.remove(mp3)
    return


