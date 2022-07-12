#!/usr/bin/python3
import sys
import json
import datetime
from urllib.error import URLError
from dateutil.parser import isoparse
import csv
import os
from urllib.request import urlopen

#variant = T + tripId + R + routeId
# ADD CRON SCRIPT WHICH DAILY DOWNLOADS VEHICLE INFO
TRIP_DEPARTURES_EVENT_LOG_DIRECTORY = '~/process_mining/prepared_data/'
LAST_TRIP_UPDATES_DIRECTORY = '~/process_mining/trips_tracing/traced_trips/tmp/'
STOPS_DATA_DIRECTORY = '~/process_mining/trips_tracing/traced_trips/script/'
STOP_NAMES_DICTIONARY_FILENAME = 'stopNamesDictionary.csv'
TRIP_DEPARTURES_EVENT_LOG_CSV_HEADER = 'trip,stopId,stopName,timestamp,delay,variant,status' # stop<activity>='stopId', trip<case>='trip', variant<resource>=variant, potem dodac jeszcze inne info
TRIP_VEHICLES_CSV_HEADER = 'id,code,service,usedInTrip,brand,model,productionYear,floorHeight,passengersDoors'
VEHICLES_DATA_FILEPATH = '~/process_mining/trips_tracing/baza-pojazdow.json'
MERGE_STOP_DICTIONARIES_REQUIRED_EXIT_CODE = 1
DEFAULT_EXIT_CODE = 0

def updateStopsForRoute(filepath):
    os.system("python3 " + STOPS_DATA_DIRECTORY + "stops_collector.py " + filepath)

def addToEventLogDataFromVariant(variantJson):
    createDeparturesRouteDirectory(variantJson['routeId'])
    lastTripsUpdateFileName = getVariantString(variantJson['tripId'], variantJson['routeId']) + '.trip'
    lastTripsUpdateFile = open(LAST_TRIP_UPDATES_DIRECTORY + lastTripsUpdateFileName, 'r+')
    lastTripsUpdateJson = json.load(lastTripsUpdateFile)

    print(routePrefix + "evaluating new data(" + str(datetime.datetime.now())[:19] + ")")
    handleDeparturesUpdate(variantJson['stops'][0], variantJson['routeId'], variantJson['tripId'], lastTripsUpdateJson, True)
    for stopId in variantJson['stops'][1:]:
        handleDeparturesUpdate(stopId, variantJson['routeId'], variantJson['tripId'], lastTripsUpdateJson, False)

    #terminate timed out trips
    for trip in lastTripsUpdateJson['currentlyTracedTrips']:
        if isoparse(trip['scheduledStartTime']).replace(tzinfo=None) + datetime.timedelta(hours=4) < datetime.datetime.now(): ############ TRISTAR DATA IS -2H, we use timeout of 2h, it equals to 4h addition of datetime.timedelta(hours=4) needed
            print(routePrefix + "Removing trip " + str(trip['trip']) + " due to timeout")
            lastTripsUpdateJson['currentlyTracedTrips'].remove(trip)
    
    lastTripsUpdateFile.seek(0)
    json.dump(lastTripsUpdateJson, lastTripsUpdateFile)
    lastTripsUpdateFile.truncate()
    lastTripsUpdateFile.close()

def handleDeparturesUpdate(stopId, routeId, tripId, lastTripsUpdateJson, isFirstStop):
    stopUrl = "https://ckan2.multimediagdansk.pl/departures?stopId=" + str(stopId)
    try:
        stopFile = urlopen(stopUrl)
    except URLError:
        print(routePrefix + "Cannot open stop URL " + stopUrl)
        return
    stopLiveDataJson = json.loads(stopFile.read())
    #evaluating existing data -> event log

    adjustStopLiveDataToOriginalTripNumbers(lastTripsUpdateJson['currentlyTracedTrips'], stopLiveDataJson, stopId, routeId, tripId)
    addVehicleDataToFileIfNotDoneBefore(lastTripsUpdateJson['currentlyTracedTrips'], stopLiveDataJson)
    if lastTripsUpdateJson.get(str(stopId)) is not None:
        addDataFromStopToEventLog(stopId, routeId, tripId, lastTripsUpdateJson, stopLiveDataJson)

    #adding new data
    addNewDataToTripsTrackingFile(stopId, routeId, tripId, lastTripsUpdateJson, isFirstStop, stopLiveDataJson)

def adjustStopLiveDataToOriginalTripNumbers(currentlyTracedTrips, stopLiveDataJson, stopId, routeId, tripId):
    for departure in stopLiveDataJson['departures']:
        if departure['routeId'] != routeId or departure['tripId'] != tripId:
            continue
        for tracedTrip in currentlyTracedTrips:
            if tracedTrip['scheduledStartTime'] == departure['scheduledTripStartTime']:
                if tracedTrip['trip'] != departure['trip']:
                    print(routePrefix + "Adjusting changed trip number " + str(departure['trip']) + " to its original number " + str(tracedTrip['trip']) + " for stop " + str(stopId))
                    departure['trip'] = tracedTrip['trip']
                break

def addVehicleDataToFileIfNotDoneBefore(currentlyTracedTrips, stopLiveDataJson):
    for tracedTrip in currentlyTracedTrips:
        if tracedTrip['vehicleDataSaved'] == True:
            continue
        for departure in stopLiveDataJson['departures']:
            if tracedTrip['trip'] == departure['trip']:
                if departure['status'] == 'REALTIME':
                    saveVehicleDataToFile(departure)
                    tracedTrip['vehicleDataSaved'] = True
                break

def saveVehicleDataToFile(departure):
    filepath = TRIP_DEPARTURES_EVENT_LOG_DIRECTORY + str(departure['routeId']) + '/' + str(datetime.date.today()) + '_vehicles.csv'
    if not os.path.isfile(filepath) or os.path.getsize(filepath) == 0:
        with open(filepath, 'w') as f:
            f.write(TRIP_VEHICLES_CSV_HEADER)

    brand = model = productionYear = floorHeight = passengersDoors = None
    vehiclesDataFile = open(VEHICLES_DATA_FILEPATH, 'r')
    vehiclesDataJson = json.load(vehiclesDataFile)
    for vehicle in vehiclesDataJson['results']:
        if vehicle['vehicleCode'] == str(departure['vehicleCode']):
            brand = vehicle['brand']
            model = vehicle['model']
            productionYear = vehicle['productionYear']
            floorHeight = vehicle['floorHeight']
            passengersDoors = vehicle['passengersDoors']
            break
    vehiclesDataFile.close()

    if brand == None or model == None or floorHeight == None or productionYear == None or passengersDoors == None:
        print(routePrefix + "Incomplete vehicle data found for vehicle=" + str(departure['vehicleCode']) + ". Saving anyways")
    else:
        print(routePrefix + "TRIP VEHICLES>>>" + str(departure['trip']) + ',' + str(departure['vehicleCode']) + ',' + departure['vehicleService'])

    with open(filepath, 'a') as f:
        f.write('\n' + str(departure['vehicleId']) + ',' + str(departure['vehicleCode']) + ',' + departure['vehicleService'] + \
                ',' + str(departure['trip']) + ',' + str(brand) + ',' + str(model) + ',' + str(productionYear) + ',' + str(floorHeight) + ',' + str(passengersDoors))

def addDataFromStopToEventLog(stopId, routeId, tripId, lastTripsUpdateJson, stopLiveDataJson):
    lastTripsForStopJson = lastTripsUpdateJson[str(stopId)]
    for lastTripUpdate in lastTripsForStopJson:
        if isTripGoneFromStop(lastTripUpdate['trip'], stopLiveDataJson['departures']):
            saveDepartureToEventLog(stopId, routeId, tripId, lastTripUpdate)
            lastTripsForStopJson.remove(lastTripUpdate) 

def saveDepartureToEventLog(stopId, routeId, tripId, lastTripUpdate): # save everything to one eventlog + one chosen route(R12) to eventlog + one chosen route+trip(?) to separate file.
    print(routePrefix + "EVENT LOG>>>" + str(lastTripUpdate['trip']) + ", " + str(stopId) + ", " + str(isoparse(lastTripUpdate['estimatedTime']) + datetime.timedelta(hours=2))[:19] + " | " + str(lastTripUpdate['status']))

    filepath = TRIP_DEPARTURES_EVENT_LOG_DIRECTORY + str(routeId) + '/' + str(datetime.date.today()) + '_departures_' + getVariantString(tripId, routeId) + '.csv'
    if not os.path.isfile(filepath) or os.path.getsize(filepath) == 0:
        with open(filepath, 'w') as f:
            f.write(TRIP_DEPARTURES_EVENT_LOG_CSV_HEADER)
        
    # we will delete every entry before, even realtime, before it could change from realtime to scheduled in the dead window where we couldnt get updated data and then disappear
    # even scheduled need to be checked out, because in special cases realtime entries are sent to event log for some realtime stops in a far future who out of sudden disappear
    with open(filepath, 'r+') as f:
        allLines = f.readlines()
        f.seek(0)
        previousDepartureLogSwapped = False
        for index in range(len(allLines)):
            if allLines[index].startswith(str(lastTripUpdate['trip']) + ',' + str(stopId) + ','):
                if previousDepartureLogSwapped:
                    raise Exception(routePrefix + "Incorrect multiple amount of departures (STRING=" + str(lastTripUpdate['trip']) + ',' + str(stopId) + "|TRIP=" + str(tripId) + \
                                    ") for a trip from a single stop found in event log")
                f.write(getEventLogEntryToWrite(lastTripUpdate, stopId, tripId, routeId))
                if index != len(allLines) - 1:
                    f.write('\n')
                previousDepartureLogSwapped = True
                print(routePrefix + 'swapped [[' + str(allLines[index])[:-1] + ']] with [[' + getEventLogEntryToWrite(lastTripUpdate, stopId, tripId, routeId) + ']]')
            else:
                f.write(allLines[index])
        if not previousDepartureLogSwapped:
            f.write('\n' + getEventLogEntryToWrite(lastTripUpdate, stopId, tripId, routeId))
        else:
            f.truncate()

def getEventLogEntryToWrite(lastTripUpdate, stopId, tripId, routeId):
    return str(lastTripUpdate['trip']) + ',' + str(stopId) + ',' + getStopName(stopId) + ',' + str(isoparse(lastTripUpdate['estimatedTime']) + datetime.timedelta(hours=2))[:19] + \
        ',' + str(lastTripUpdate['delayInSeconds']) + ',' + getVariantString(tripId, routeId) + ',' + str(lastTripUpdate['status']) ## TIME + 2H - TRISTAR DATA SHOWS TIMESTAMP 2H BEHIND REAL 

def getStopName(stopId):
    stopNamesDictionaryFile = open(STOPS_DATA_DIRECTORY + STOP_NAMES_DICTIONARY_FILENAME, 'r')
    dictReader = csv.DictReader(stopNamesDictionaryFile)
    for line in dictReader:
        if line['id'] == str(stopId):
            return line['name']
    return "None"

def addNewDataToTripsTrackingFile(stopId, routeId, tripId, lastTripsUpdateJson, isFirstStop, stopLiveDataJson):
    if isFirstStop:
        startTracingNewlyFoundTrips(stopLiveDataJson, lastTripsUpdateJson, routeId, tripId)

    if lastTripsUpdateJson.get(str(stopId)) is None:
        print(routePrefix + "For variant " + getVariantString(tripId, routeId) + " lastTripsUpdateJson has no stopId=" + str(stopId) + ". Adding it")
        lastTripsUpdateJson[str(stopId)] = []
        for departure in stopLiveDataJson['departures']:
            if not isTripOfDepartureTraced(departure['trip'], lastTripsUpdateJson):
                continue
            lastTripsUpdateJson[str(stopId)].append(prepareStopEntryFromDeparture(departure))
    else:
        for departure in stopLiveDataJson['departures']:
            if not isTripOfDepartureTraced(departure['trip'], lastTripsUpdateJson):
                continue
            if isANewDepartureOnCurrentStop(departure, lastTripsUpdateJson[str(stopId)]):
                lastTripsUpdateJson[str(stopId)].append(prepareStopEntryFromDeparture(departure))
            else:
                updateTripStatusOnCurrentStop(departure, lastTripsUpdateJson[str(stopId)])

def isTripOfDepartureTraced(trip, lastTripsUpdateJson):
    for tracedTrip in lastTripsUpdateJson['currentlyTracedTrips']:
        if tracedTrip['trip'] == trip:
            return True
    return False

def isTripGoneFromStop(trip, stopLiveDepartures):
    for departure in stopLiveDepartures:
        if departure['trip'] == trip:
            return False
    return True

def isANewDepartureOnCurrentStop(departure, lastTripsOnStop):
    for trip in lastTripsOnStop:
        if trip['trip'] == departure['trip']:
            return False
    return True

def updateTripStatusOnCurrentStop(departure, lastTripsOnStop):
    for trip in lastTripsOnStop:
        if trip['trip'] == departure['trip']:
            trip['delayInSeconds'] = departure['delayInSeconds']
            trip['estimatedTime'] = departure['estimatedTime']# ISO-8601
            trip['timestamp'] = departure['timestamp']
            trip['status'] = departure['status']
            return
    raise Exception("Should have found a trip on this stop to update")

def startTracingNewlyFoundTrips(stopLiveDataJson, lastTripsUpdateJson, routeId, tripId):
    for departure in stopLiveDataJson['departures']:
        if departure["routeId"] == routeId and departure["tripId"] == tripId and not isTripAlreadyTraced(departure, lastTripsUpdateJson['currentlyTracedTrips']):
            lastTripsUpdateJson['currentlyTracedTrips'].append(prepareTripEntryFromDeparture(departure))
    
def isTripAlreadyTraced(departure, tracedTrips):
    for trip in tracedTrips:
        if departure['trip'] == trip['trip']:
            return True
    return False

def prepareStopEntryFromDeparture(departure):
    stopEntry = {}
    stopEntry['trip'] = departure['trip']
    stopEntry['delayInSeconds'] = departure['delayInSeconds']
    stopEntry['estimatedTime'] = departure['estimatedTime']# ISO-8601
    stopEntry['timestamp'] = departure['timestamp']
    stopEntry['status'] = departure['status']
    return stopEntry

def prepareTripEntryFromDeparture(departure):
    tripEntry = {}
    tripEntry['trip'] = departure['trip']
    tripEntry['scheduledStartTime'] = departure['scheduledTripStartTime']
    tripEntry['vehicleDataSaved'] = False
    return tripEntry

def getVariantString(tripId, routeId):
    return 'T' + str(tripId) + 'R' + str(routeId)

def createDeparturesRouteDirectory(routeId):
    if not os.path.isdir(TRIP_DEPARTURES_EVENT_LOG_DIRECTORY + str(routeId)):
        os.mkdir(TRIP_DEPARTURES_EVENT_LOG_DIRECTORY + str(routeId))

def main():
    filepath = sys.argv[1]
    routeFile = open(filepath, )
    routeJson = json.load(routeFile)
    exitCode = DEFAULT_EXIT_CODE
    if routeJson.get('lastUpdateForEventLog') is None or routeJson['lastUpdateForEventLog'] != str(datetime.date.today()):
        routeFile.close()
        updateStopsForRoute(filepath)
        exitCode = MERGE_STOP_DICTIONARIES_REQUIRED_EXIT_CODE
        routeFile = open(filepath, )
        routeJson = json.load(routeFile)
    for variant in routeJson['variants']:
        if variant.get('stops') is not None and len(variant['stops']) > 1 and variant['ready'] == True:
            addToEventLogDataFromVariant(variant)

    routeFile.close()
    return exitCode

if __name__ == '__main__':
    routePrefix = ('[' + sys.argv[1].rsplit('\\', 1)[1].rsplit('.', 1)[0] + ']').ljust(5)
    
    exitCode = main()
    print(routePrefix + "finish(" + str(datetime.datetime.now())[:19] + ")")
    sys.exit(exitCode)
