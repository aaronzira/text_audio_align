import os
import re
import multiprocessing
import json
import subprocess

import boto3
import gentle


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
    ###print("Trimming from {} to {}, a duration of {}".format(offset+start,offset+end,duration))
    ###print("Outbound file name: {}".format(os.path.basename(segment)))
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

def data_generator(file_id,max_length=20.0):
    """Given a file id, align the audio and text versions after dividing into
    single-speaker utterances, and write out texts of unbroken captured strings
    with their corresponding audio segments when the latter are less than
    max_length.
    """

    print("Processing file id {}".format(file_id))

    # transcript
    txt_file = "/home/aaron/records/{}.txt".format(file_id)

    # grab audio file from s3
    mp3 = "./{}.mp3".format(file_id)
    bucket = boto3.resource("s3").Bucket("cgws")
    bucket.download_file("{}.mp3".format(file_id),mp3)

    # output
    text_out_dir = "/home/aaron/deepspeech_data/stm"
    wav_out_dir = "/home/aaron/deepspeech_data/wav"

    # reading json from alignment using gentle
    with open(txt_file,"r") as tr:
        transcript = tr.read()

    # split transcript by speaker
    paragraphs = [paragraph for paragraph in transcript.split("\n")
                    if re.match("\d:\d+:\d+\.\d",paragraph)]

    # get timestamps (as seconds) of the boundaries of each paragraph
    timestamps = [re.match("\d:\d+:\d+\.\d",p).group() for p in paragraphs]
    times = [int(h)*60*60 + int(m)*60 + float(s)
                for h,m,s in [time.split(":") for time in timestamps]]
    file_end = get_duration(mp3)
    times.append(file_end)

    total_captures,captures_dur = 0,0
    resources = gentle.Resources()

    # taking one speaker at a time, find unbroken alignments up to max_length
    # and write out corresponding files
    for i,paragraph in enumerate(paragraphs):

        cleaned = clean(paragraph)
        temp_wav = trim(file_id,mp3,times[i],times[i+1],0,"./temp")

        ### didn't want to have to resample again, but not a big deal
        with gentle.resampled(temp_wav) as wav_file:
            aligner = gentle.ForcedAligner(resources,transcript,
                                           nthreads=multiprocessing.cpu_count(),
                                           disfluency=False,conservative=False,
                                           disfluencies=set(["uh","um"]))
            result = aligner.transcribe(wav_file)

        # dictionary of aligned words
        aligned = json.loads(result.to_json())

        # save all consecutively captured strings
        # and keep track of their start and stop times
        captures = []
        current,start,end = None,None,None

        # loop through every word as returned from gentle
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
        for result in captures:
            txt_segment = os.path.join(text_out_dir,"{}_{}_{}.txt".format(
                        file_id,
                        "{:07d}".format(int((times[i]+result["start"])*100)),
                        "{:07d}".format(int((times[i]+result["end"])*100))))
            with open(txt_segment,"w") as f:
                f.write(result["string"])

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
    print("Wrote {} segments from {}, totalling {} seconds out of a possible {}."\
          .format(total_captures,file_id,captures_dur,total_dur))

    # delete entire audio file
    os.remove(mp3)


