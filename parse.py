import sys
import re

DEBUG = 0

if (len(sys.argv) < 2):
	print("Error: An input file with directory (arg1) is required. Exiting...\n")
	sys.exit(-1)
elif (len(sys.argv) > 2):
	print("Error: This program only takes 1 argument. An input file with directory (arg1). Exiting...\n")
	sys.exit(-1)

#Open the input file
inFileName = sys.argv[1]
inFile = open(inFileName, "r")

#Get directory and file information
#RegEx example: "file.ext"
name, ext = re.match(r"(.+)\.(.+)", inFileName).groups()
dir = name[0:name.rfind("/")]
name = name[name.rfind("/"):len(name)]

#Open an output tsv file of the same name
outFile = open("{d}/{n}.{e}".format(d=dir, n=name, e="tsv"), "w")


# Get the first line of the input file
line = inFile.readline().strip()

# Regex for reading the first line
#RegEx example line: "-i 1 -T 5 -p4021:4021 -R1G -Ri1G 192.168.2.2"
pattern = re.compile(r".*-i\s+(\d+)\s+-T\s+(\d+)\s+-p(\d+):(\d+)\s+-R(\d+[a-zA-Z]+)\s+-Ri(\d+[a-zA-Z]+)\s+(\d+.\d+.\d+.\d+).*")
results = pattern.match(line)
groups = results.groups()
i     = int(groups[0])
t     = int(groups[1])
port1 = int(groups[2])
port2 = int(groups[3])
speed = groups[4]
ip    = groups[6]


# Get the lines with data. There should be t lines (found from the first line)
count = 0
while (count < t):
	line = inFile.readline().strip()
	
	#Only work with non empty lines
	if line != "":
		count = count + 1
		
		#ReGex example line: "  109.9375 MB /   1.00 sec =  922.2327 Mbps     0 retrans   "
		pattern = re.compile(r".*?(\d+.\d+)\s+([a-zA-Z]+)\s+/\s+(\d+.\d+)\s+([a-zA-Z]+)\s+=\s+(\d+.\d+)\s+([a-zA-Z]+)\s+(\d+)\s+([a-zA-Z]+).*")
		results = pattern.match(line)
		groups = results.groups()
		
		#Data from the line broken down by the RegEx
		data              = float(groups[0])
		dataLabel         = groups[1]
		timeInterval      = float(groups[2])
		timeIntervalLabel = groups[3]
		dataSpeed         = groups[4]
		dataSpeedLabel    = groups[5]
		retrans           = groups[6]
		retransLabel      = groups[7]
		
		#Print if debug is on
		if (DEBUG): print(groups)
		
		#Write to the output file
		outFile.write("{d}\t{dS}\t{r}\n".format(d=data, dS=dataSpeed, r=retrans))

#Close the files
inFile.close()
outFile.close()

#Program is finished
sys.exit(1)
