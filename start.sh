#!/bin/sh
SCRIPT="mymultiflow"
ETHPORT="eth6"

cp -r $SCRIPT.py utils.py templates ./pox/ext/
./pox/pox.py --verbose $SCRIPT --dpi_port=$ETHPORT
rm -r ./pox/ext/$SCRIPT.py ./pox/ext/utils.py ./pox/ext/templates
