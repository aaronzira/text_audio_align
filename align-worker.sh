#!/bin/bash

#set -x

if [ $# -lt 2 ]
then
    echo "usage: ./align-worker.sh filelist index"
    exit 1
fi

filelist=$1
if [ ! -f $filelist ]
then
    echo "$filelist not found"
    exit 1
fi

if [ ! -d ~/align ]
then
    mkdir ~/align
fi

index=$2
host=`hostname`

threads_multiplier=4
if [ $host == 'eesen-worker' ]
then
    threads_multiplier=2
fi

for fid in `tail -n +$index $filelist`
do
    host=`hostname`
    if [ $host == 'eesen-worker' ]
    then
        stat ~/align/${fid}.json 1>/dev/null 2>&1
    else
        ssh eesen-worker "stat ~/align/${fid}.json" 1>/dev/null 2>&1
    fi

    if [ $? -ne 0 ]
    then
        index=`grep -n $fid $filelist | cut -d ':' -f1` 

        if [ $host == 'eesen-worker' ]
        then
            touch ~/align/$1.json
        else 
            while true
            do
                ssh eesen-worker "touch ~/align/$1.json" 1>/dev/null 2>&1
                if [ $? -ne 0 ]
                then
                    sleep 1
                else
                    break
                fi
            done
        fi
        
        scp scribie:~/scribie/records/${fid}.txt ~/align 1>/dev/null 2>&1
        python rename-alignments.py $fid --file_index $index --abort --threads_multiplier $threads_multiplier --use_align_dir 
    fi
done
