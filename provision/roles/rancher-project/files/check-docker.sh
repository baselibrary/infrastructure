#!/bin/bash
N=`ps aux | grep /usr/bin/docker | grep -v grep | wc -l`
if [ $N = 0 ]; then
    exit 1
fi
exit 0