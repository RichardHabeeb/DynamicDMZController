#!/bin/sh
SCRIPT="mymultiflow"
ETHPORT="Te 0/2"

cp -r $SCRIPT.py utils.py templates ./pox/ext/
./pox/pox.py --verbose $SCRIPT --dpi_port="$ETHPORT"
rm -r ./pox/ext/$SCRIPT.py ./pox/ext/utils.py ./pox/ext/templates
