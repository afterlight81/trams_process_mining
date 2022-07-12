#!/usr/bin/python3
import glob
import subprocess
import datetime
import csv
import os
ROUTES_DIRECTORY = '~/process_mining/trips_tracing/traced_trips/'
STOPS_DATA_DIRECTORY = "~/process_mining/trips_tracing/traced_trips/script/"
UPDATING_EVENT_LOG_FOR_ROUTE_SCRIPT_FILEPATH = "~/process_mining/trips_tracing/updateEventLogForRoute.py"
STOP_NAMES_DICTIONARY_TMP_NAME_PREFIX = 'stopNamesDict_'
STOP_NAMES_DICTIONARY_TMP_NAME_SUFFIX =  '_tmp.csv'
STOP_NAMES_DICTIONARY_NAME = 'stopNamesDictionary.csv'
STOP_NAMES_DICTIONARY_HEADER = 'id,name'
MERGE_STOP_DICTIONARIES_REQUIRED_EXIT_CODE = 1

def createStopNamesDictionaryFileIfNotPresent():
    stopNamesDictionaryFilepath = STOPS_DATA_DIRECTORY + STOP_NAMES_DICTIONARY_NAME
    if not os.path.isfile(stopNamesDictionaryFilepath) or os.path.getsize(stopNamesDictionaryFilepath) == 0:
        with open(stopNamesDictionaryFilepath, 'w') as f:
            f.write(STOP_NAMES_DICTIONARY_HEADER)
        
def main():
    print("starting updateeventlog")
    createStopNamesDictionaryFileIfNotPresent()
    processes = []
    routeIds = []
    for filepath in glob.glob(ROUTES_DIRECTORY + "*.route"):
        processes.append(subprocess.Popen(["python3",UPDATING_EVENT_LOG_FOR_ROUTE_SCRIPT_FILEPATH, filepath]))
        routeIds.append(filepath.rsplit('\\', 1)[1].rsplit('.', 1)[0])

    exitCodes = [p.wait() for p in processes]
    print("DEBUG: ALL EXIT CODES: " + str(exitCodes))
    stopNamesDictionaryFile = open(STOPS_DATA_DIRECTORY + STOP_NAMES_DICTIONARY_NAME, 'r+')
    if all(code == MERGE_STOP_DICTIONARIES_REQUIRED_EXIT_CODE for code in exitCodes):
        stopNamesDictionaryFile.truncate()
        stopNamesDictionaryFile.write(STOP_NAMES_DICTIONARY_HEADER)

    for index in range(len(processes)):
        if exitCodes[index] == MERGE_STOP_DICTIONARIES_REQUIRED_EXIT_CODE:
            with open(STOPS_DATA_DIRECTORY + STOP_NAMES_DICTIONARY_TMP_NAME_PREFIX + routeIds[index] + STOP_NAMES_DICTIONARY_TMP_NAME_SUFFIX, 'r') as tmpFile:
                allLines = tmpFile.readlines()
                for line in allLines[1:]:
                    addStopToMergedDictionary(line, stopNamesDictionaryFile)
            os.remove(STOPS_DATA_DIRECTORY + STOP_NAMES_DICTIONARY_TMP_NAME_PREFIX + routeIds[index] + STOP_NAMES_DICTIONARY_TMP_NAME_SUFFIX)
    stopNamesDictionaryFile.close()

def addStopToMergedDictionary(lineToWrite, stopNamesDictionaryFile):
    stopNamesDictionaryFile.seek(0)
    dictReader = csv.DictReader(stopNamesDictionaryFile)
    stopId = getStopIdFromCsvLine(lineToWrite)
    for line in dictReader:
        if line['id'] == stopId:
            return
    stopNamesDictionaryFile.write(moveNewLineToTheBeginningOfLineString(lineToWrite))

def moveNewLineToTheBeginningOfLineString(line):
    line = '\n' + line
    if line.endswith('\n'):
        return line[:-1]
    return line

def getStopIdFromCsvLine(line):
    return line.rsplit(',', 1)[0]

if __name__ == '__main__':
    print("_________________" + str(datetime.datetime.now())[:19] + "_________________")
    main()
