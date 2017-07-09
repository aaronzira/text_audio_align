#!/bin/zsh
for i in `ls *.txt | sort`
do
    echo $i
    echo -en "\033[32m"
    cat $i
    echo -en "\033[0m"
    echo "playing audio..."
    play -q ${i:0:-3}wav 1>/dev/null 2>&1
    echo "press enter to play next file"
    read
done
