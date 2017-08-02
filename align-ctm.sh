#!/bin/bash

#set -x
#set -euxo pipefail

if [ $# -lt 2 ]
then
    echo "usage: ./align-ctm.sh filelist index"
    exit 1
fi

filelist=$1
if [ ! -f $filelist ]
then
    echo "$filelist not found"
    exit 1
fi

index=$2

for fid in `tail -n +$index $filelist`
do
	num_files=`find /home/aaron/data/phoenix-files/gaps/txt/${fid}_*.txt 2>/dev/null | wc -l`
	if [ $num_files -eq 0 ]
	then
		index=`grep -n $fid $filelist | cut -d ':' -f1`
		python gaps.py $fid --file-index $index --audio-dir /home/aaron/data/mp3s/ --align-dir ~/data/ctm-alignments/ --dataset-dir /home/aaron/data/phoenix-files/gaps/
	fi
done
