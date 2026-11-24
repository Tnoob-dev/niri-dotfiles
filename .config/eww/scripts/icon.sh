#!/bin/sh
case "$1" in
    cpu)   printf '\357\213\233' ;;
    mem)   printf '\357\224\270' ;;
    power) printf '\357\200\221' ;;
esac
