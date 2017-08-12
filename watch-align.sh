#!/bin/bash
inotifywait -mqr -e move "/home/aaron/data/ctm-alignments" | while read path action file
do
        if [ ${file:(-5)} == '.json' ]
        then
		fid=${file:0:-11}
		index=`grep -n $fid ~/phoenix/file-ids-2017.csv | cut -d ':' -f1`
		python gaps.py $fid --file-index $index --audio-dir /home/aaron/data/mp3s/ --align-dir ~/data/ctm-alignments/ --dataset-dir /home/aaron/data/phoenix-files/gaps/
        fi
done
