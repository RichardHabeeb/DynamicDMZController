#!/bin/sh
SCRIPT="mymultiflow"
ETHPORT="eth0"

cp $SCRIPT.py ./pox/ext/
./pox/pox.py --verbose $SCRIPT --dpi_port=eth0
rm ./pox/ext/$SCRIPT.py
