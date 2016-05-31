#!/bin/sh

echo "\n======================\n= Running autorun.sh =\n======================\n"

##########
#Variables
getInputs=1
start=0
end=2
speed=1000
speedIncrease=100
sendingPort=2000
receivingPort=2000
interval=1
numRepeats=2
ipAddress="192.168.2.102"

#Checks if an input is an integer (strictly positive)
#Example "testInputIsNum 5" or "testInputIsNum $variable"
testInputIsNum()
{
	if ! [ "$1" -eq "$1" ] 2>/dev/null
	then
		echo "Error: Not a valid number"
		exit 1
	fi
}

###################################
#THE FOLLOWING CODE IS NOT WORKING#
###################################
#echo -n "Do you want to enter specs manually? Enter (y/n): "
#read getInputs
#if [ "$getInputs" -eq "y" ]
#then
#	getInputs=1
#fi

#################################
#Get some variables from the user
if [ "$getInputs" -eq "1" ]
then
	echo -n "How many tests do you want to run? Input a number: "
	read end
	testInputIsNum $end

	echo -n "What is the start speed? Input a number (in M): "
	read speed
	testInputIsNum $speed

	echo -n "How much should the speed increase after each test? Input a number (in M): "
	read speedIncrease
	testInputIsNum $speedIncrease

	echo -n "How many seconds should each test wait to poll results? Input a number: "
	read interval
	testInputIsNum $interval

	echo -n "How many times should each test poll results? Input a number: "
	read numRepeats
	testInputIsNum $numRepeats
fi


###################
#Set up directories

#Create the main results folder if it doesn't exist
mkdir "allResults"

#Name of the folder for this run and create it in the allResults folder
dir="results_$(date +%y-%m-%d_%H-%M-%S)"
mkdir "allResults/$dir"

#The path to the results for this run
path="allResults/$dir"


##############
#Do main work
echo "\nTesting nuttcp"
while [ $start -lt $end ]
do
	#Print to the console
	echo "Test $((start+1))/$end:   Speed: $((speed))M   Sending Port: $((sendingPort))   Receiving Port: $((receivingPort))   Sent to: $ipAddress   Polling $((numRepeats)) times every $((interval)) seconds   Start: $(date +%H:%M:%S)"

	#Print runtime information into the results file
	echo "./nuttcp -i $((interval)) -T $((numRepeats)) -p$((sendingPort)):$((receivingPort)) -R$((speed))M -Ri$((speed))M $ipAddress" > $path/results$((speed))M.txt

	#Run the program and redirect it's results into an appropriate file
	      ./nuttcp -i $((interval)) -T $((numRepeats)) -p$((sendingPort)):$((receivingPort)) -R$((speed))M -Ri$((speed))M $ipAddress >> $path/results$((speed))M.txt

	#Update variables
	start=$((start + 1))
	speed=$((speed + speedIncrease))
	sendingPort=$((sendingPort + 1))
	receivingPort=$((receivingPort + 1))

	#Wait for 1 second before looping
	sleep 1
done
echo "nuttcp tests finished\n"


###############################################
#Take each results file and generate a data csv
echo "Generating output tsv files."
index=0
for name in $(ls $path)
do
	index=$((index+1))
	#Print to the console
	echo "Generating tsv $((index))/$end"

	python parse.py "$path/$name"
done
echo "Finished generating output tsv files."


echo "\nautorun.sh has finished running\n"
