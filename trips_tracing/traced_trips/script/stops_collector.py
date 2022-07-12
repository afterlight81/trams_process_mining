#!/usr/bin/python3
import sys
import json
import datetime
import os
import csv

STOPS_IN_TRIP_FILENAME = "stopsintrip.json"
STOPS_FILENAME = "stops.json"
STOP_NAMES_DICTIONARY_HEADER = 'id,name'
STOPS_DATA_DIRECTORY = "D:/Informatyka/MAGISTERKA/trips_tracing/traced_trips/script/"
STOP_NAMES_DICTIONARY_TMP_NAME_PREFIX = 'stopNamesDict_'
STOP_NAMES_DICTIONARY_TMP_NAME_SUFFIX =  '_tmp.csv'

def collectTripDataWithStops(routeId, tripId, stopsInTrip, todayStops, stopNamesDictionaryFile):
    tripJson = None
    stops = []
    for stop in stopsInTrip:
        if stop["routeId"] == routeId and stop["tripId"] == tripId and stop["passenger"] == True:
            stops.append(stop)
            if tripJson == None:
                tripJson = {'activationDate':stop["tripActivationDate"]}
    if tripJson == None: #none when 0 matching stops are found for route + trip pair
        #print("TRIP " + str(routeId) + "," + str(tripId) + " NOT FOUND ON THIS DAY!")
        return None
    stops.sort(key=lambda x: x["stopSequence"])
    tripJson['stops'] = []
    for s in stops:
        tripJson['stops'].append(s['stopId'])
        addStopToDictionary(s['stopId'], todayStops, stopNamesDictionaryFile)
    #print("tripData: " + str(tripActivationDate))
    return tripJson

def addStopToDictionary(stopId, todayStops, stopNamesDictionaryFile):
    stopNamesDictionaryFile.seek(0)
    dictReader = csv.DictReader(stopNamesDictionaryFile)
    for line in dictReader:
        if line['id'] == str(stopId):
            return
    stopNamesDictionaryFile.write('\n' + str(stopId) + ',' + getStopName(stopId, todayStops))

def getStopName(stopId, todayStops):
    for stop in todayStops:
        if stopId == stop['stopId']:
            return stop['stopName']
    print("FAILED TO GET STOP NAME FOR STOP=" + str(stopId) + " !!!!")
    return "None"

#
#def removeOldEntriesFromStopNamesDictionary(file):
#    allLines = file.readlines()
#    todayDate = str(datetime.date.today())
 #   file.truncate()
 #   file.write(STOP_NAMES_DICTIONARY_HEADER)
 #   for line in allLines:
 #       print("Checking if [" + line.splitlines()[0] + '] ends with [' + todayDate + ']')
  #      if line.splitlines()[0].endswith(todayDate):
  #          file.write(line)
  #  file.seek(0)
#
def prepareVariantFile(path):
    with open(path, 'w') as f:
        f.write('{"currentlyTracedTrips":[]}')
        f.truncate()

def getVariantFilepath(routeId, tripId):
    return 'D:/Informatyka/MAGISTERKA/trips_tracing/traced_trips/tmp/' + 'T' + str(tripId) + 'R' + str(routeId) + '.trip'

def main():
    variantsToCollectFile = open(sys.argv[1], 'r+')
    variantsToCollect = json.load(variantsToCollectFile)

    stopsInTripFile = open(STOPS_DATA_DIRECTORY + STOPS_IN_TRIP_FILENAME, encoding='utf-8')
    stopsInTripJson = json.load(stopsInTripFile)
    todayStopsInTripJson = stopsInTripJson[str(datetime.date.today())]["stopsInTrip"]

    stopsFile = open(STOPS_DATA_DIRECTORY + STOPS_FILENAME, encoding='utf-8')
    stopsJson = json.load(stopsFile)
    todayStopsJson = stopsJson[str(datetime.date.today())]["stops"]

    routeId = sys.argv[1].rsplit('\\', 1)[1].rsplit('.', 1)[0] 
    stopNamesDictionaryFilepath = STOPS_DATA_DIRECTORY + STOP_NAMES_DICTIONARY_TMP_NAME_PREFIX + routeId + STOP_NAMES_DICTIONARY_TMP_NAME_SUFFIX
    #if not os.path.isfile(stopNamesDictionaryFilepath) or os.path.getsize(stopNamesDictionaryFilepath) == 0:
    with open(stopNamesDictionaryFilepath, 'w') as f:
        f.truncate()
        f.write(STOP_NAMES_DICTIONARY_HEADER)
    stopNamesDictionaryFile = open(stopNamesDictionaryFilepath, 'r+')

    for variant in variantsToCollect["variants"]:
        tripDataJson = collectTripDataWithStops(variant["routeId"], variant["tripId"], todayStopsInTripJson, todayStopsJson, stopNamesDictionaryFile)
        if tripDataJson == None:
            variant['ready'] = False #if stops exists - no found stops per route+trip pair marks change of trip compared to its earlier desired path. trip is not ready to be used - not compliant with desired path.
                                   #if stops do not exist and no trip was found, mark ready to false because it is empty, and always been - route+trip path is probably incorrect
            continue

        try:
            if variant['stops']:
                desiredStopsAlreadySaved = True
            else:
                desiredStopsAlreadySaved = False 
        except KeyError:
            desiredStopsAlreadySaved = False

        if desiredStopsAlreadySaved:
            if variant['stops'] == tripDataJson['stops']:
                variant['ready'] = True
            else:
                variant['ready'] = False #stops for this variant in live database are not compliant with desired path. it might be a temporary case, and when its back to normal, 'ready' mark will be set to True again
        else: 
            variant['activationDate'] = tripDataJson['activationDate']
            variant['stops'] = tripDataJson['stops']
            variant['ready'] = True
        variantFilepath = getVariantFilepath(variant["routeId"], variant["tripId"])
        prepareVariantFile(variantFilepath)
    variantsToCollect['lastUpdateForEventLog'] = str(datetime.date.today())
    variantsToCollectFile.seek(0)
    variantsToCollectFile.write(json.dumps(variantsToCollect))
    variantsToCollectFile.truncate()
    variantsToCollectFile.close()
    stopNamesDictionaryFile.truncate()
    stopNamesDictionaryFile.close()

if __name__ == "__main__":
    main()
