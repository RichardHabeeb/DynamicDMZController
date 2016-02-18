#!/bin/sh
SCRIPT="mymultiflow"
ETHPORT="eth0"

cp $SCRIPT.py utils.py ./pox/ext/
./pox/pox.py --verbose $SCRIPT --dpi_port=$ETHPORT
rm ./pox/ext/$SCRIPT.py ./pox/ext/utils.py
