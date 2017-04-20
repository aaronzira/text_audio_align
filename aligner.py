import os
import json
import subprocess


def data_generator(file_id):

    # input -- actually these first two should be in the script
    audio_dir = "./" ### s3, boto
    transcripts_dir = "./" ### "..../records"
    audio_file = os.path.join(audio_dir,"{}.mp3".format(file_id)) ### connect to s3 with shell script
    transcript = os.path.join(transcripts_dir,"{}.txt".format(file_id))

    # output
    text_out_dir = "text_testing" ###"./ds_data/stm"
    wav_out_dir = "audio_testing" ###"./ds_data/wav"

    # save all consecutively captured strings here
    strings = []
    # keep track of start and stop times
    times = []

    # a continuous string of captured words
    current = ""

    # writing out json file from gentle
    temp_json_file = "./output"

    # write the json object out...
    ### will need to specify gentle directory somewhere else
    subprocess.call(["python","../gentle/align.py","{}".format(audio_file),
                    "{}".format(transcript),"-o","{}".format(temp_json_file)])

    # then read it in as a dictionary...
    with open(temp_json_file,"r") as f:
        aligned = json.loads(f.read())

    ### not really necessary to delete temp_json_file because you'll write over it each time

    # every word as returned from gentle
    for catch in aligned["words"]:

        # first word in the file or after a missed word
        if not current:
            if catch["case"] == "success":
                start_time = catch["start"]
                times.append(start_time)
                current = catch["alignedWord"]
                end_time = catch["end"]

        # the previous word was a success
        else:
            # append to current string if the total time is under 20s,
            # otherwise start new string
            if catch["case"] == "success":
                running_time = catch["end"]-start_time

                if running_time > 19.99:
                    # the string ends with the previous word
                    times.append(end_time)
                    strings.append(current)

                    # start the new string with this word
                    start_time = catch["start"]
                    times.append(start_time)
                    current = catch["alignedWord"]

                else:
                    current = " ".join([current,catch["alignedWord"]])
                    end_time = catch["end"]

            # missed word
            else:
                if current:
                    strings.append(current)
                    times.append(end_time)
                    current = ""
                pass

    # the last word was a success but the string hasn't been written yet
    if current:
        times.append(end_time)
        strings.append(current)
        current = ""

    # zip start, end, and duration of each string
    start_end_duration = []
    for start,end in zip(times[::2],times[1::2]):
        start_end_duration.append((float("{:.2f}".format(start)),
                                   float("{:.2f}".format(end)),
                                   float("{:.2f}".format(end-start))))

    # zip strings and times
    text_and_times = list(zip(strings,start_end_duration))

    # write strings to text files and split mp3 file into consituent wav files
    for text,(start,end,duration) in text_and_times:
        with open(os.path.join(text_out_dir,"{}_{}_{}.txt".format(file_id,start,end)),"w") as f:
            f.write(text)
        subprocess.call(["sox","{}".format(audio_file),"-r","16k",
                        "{}_{}_{}.wav".format(os.path.join(wav_out_dir,file_id),start,end),"trim","{}".format(start),
                        "{}".format(duration),"remix","-"])


