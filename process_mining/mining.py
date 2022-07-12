import pandas
import pm4py
import csv
import datetime 
from sklearn import tree
from pm4py.objects.conversion.log import converter as log_converter
from pm4py.algo.transformation.log_to_features import algorithm as log_to_features
from pm4py.objects.log.util import get_class_representation
from pm4py.visualization.decisiontree import visualizer as dectree_visualizer
from pm4py.objects.log.importer.xes import importer as xes_importer

MAX_TRAM_LINE_NUMBER = 12

def didHappenDuringIssue(timestamp, line, issuesData):
    #timestampFormatted = datetime.datetime.fromisoformat(timestamp)
    timestampFormatted = timestamp.to_pydatetime().replace(tzinfo=None)
    for issue in issuesData[int(line)]:
        if datetime.datetime.fromisoformat(issue[0]) < timestampFormatted < datetime.datetime.fromisoformat(issue[1]):
            return True
    return False


def import_csv(file_path, activityKey):
    dataFrameCsv = pandas.read_csv(file_path, sep=',')
    uniqueStopIdsList = dataFrameCsv.stopId.unique()
    dataFrame = pm4py.format_dataframe(dataFrameCsv, case_id='trip', activity_key=activityKey, timestamp_key='timestamp', timest_format='%Y-%m-%d %H:%M:%S')
    dataFrame.rename(columns={'trip': 'case:trip'}, inplace=True)
    dataFrame.rename(columns={'variant': 'case:variant'}, inplace=True)
    parameters = {log_converter.Variants.TO_EVENT_LOG.value.Parameters.CASE_ID_KEY: 'case:trip', log_converter.Variants.TO_EVENT_LOG.value.Parameters.CASE_ATTRIBUTE_PREFIX : 'case:'}
    evLog = log_converter.apply(dataFrame, parameters=parameters, variant=log_converter.Variants.TO_EVENT_LOG)
    return evLog, uniqueStopIdsList

def loadIssuesFromAnnouncements():
    result = [[] for _ in range(MAX_TRAM_LINE_NUMBER + 1)]
    issuesFile = open("D:/Informatyka/MAGISTERKA/process_mining_main/announcements_till15.05.csv", 'r')
    dictReader = csv.DictReader(issuesFile)
    for line in dictReader:
        result[int(line['tram_line'])].append((line['start_date'], line['end_date']))
    issuesFile.close()

    return result

def setIssuesInEventStream(evStream):
    print("Start setting issues")
    issuesData = loadIssuesFromAnnouncements()
    for event in evStream._list:
        event["stopName"] = removeAccents(event["stopName"])
        if isinstance(event["concept:name"], str):
            event["concept:name"] = removeAccents(event["concept:name"])
        if event["status"] == "REALTIME":
            event["delay"] = int(event["delay"])
            precisionFixWhenNegative = 0
            if event["delay"] < 0:
                precisionFixWhenNegative = 1
            event["timestampExpected"] = event["timestamp"] - pandas.Timedelta(seconds=event["delay"] - precisionFixWhenNegative)
        else:
            del event["delay"]
        if didHappenDuringIssue(event["timestamp"], getLineFromVariant(event["case:variant"]), issuesData):
            #event["departureDuringIssues"] = True - na potrzeby reworka, tam str/num attributes sie podaje
            event["departureDuringIssues"] = "true"
        else:
            #event["departureDuringIssues"] = False- na potrzeby reworka, tam str/num attributes sie podaje
            event["departureDuringIssues"] = "false"

def setTripDetailsInEventLog(evLog):
    vehiclesFile = open("D:/Informatyka/MAGISTERKA/process_mining_main/vehicles_all.csv", 'r')
    dictReader = csv.DictReader(vehiclesFile)
    counterS = counterF = 0
    index = 0
    tracesToDelete = []
    for trace in evLog:
        tripFound = False
        for line in dictReader:
            if line['usedInTrip'] == str(trace._attributes['trip']):
                counterS += 1
                trace._attributes['vehicleId'] = line['id']
                trace._attributes['vehicleCode'] = line['code']
                trace._attributes['service'] = line['service']
                trace._attributes['vehicleBrand'] = line['brand']
                trace._attributes['vehicleModel'] = line['brand'] + " Model:" + line['model']
                trace._attributes['vehicleProductionYear'] = int(line['productionYear'])
                trace._attributes['vehiclefloorHeight'] = line['floorHeight']
                trace._attributes['vehiclePassengerDoors'] = int(line['passengersDoors'])
                tripFound = True
                break
        if not tripFound:
            print ("NOT FOUND FOR TRIP" + str(trace._attributes['trip']))
            tracesToDelete.append(trace)
            counterF += 1
        index += 1
        vehiclesFile.seek(0)
    print("Successfully matched trips to vehicle data: " + str(counterS))
    print("Failed matching trips to vehicle data: " + str(counterF) + ". Trips removed")
    for trace in tracesToDelete:
        evLog._list.remove(trace)
    print("Length:" + str(len(evLog)))
    vehiclesFile.close()

def createEventLog(activityKey):
    #evLog, uniqueStopIdsList = import_csv("D:/Informatyka/MAGISTERKA/process_mining_main/departures_20-24.04+26-29.04+05-11.05-NonesFixed.csv", activityKey)
    evLog, uniqueStopIdsList = import_csv("D:/Informatyka/MAGISTERKA/process_mining_main/departures_22_23.csv", activityKey)
    parameters = {}
    evStream = log_converter.apply(evLog, parameters=parameters, variant=log_converter.Variants.TO_EVENT_STREAM)
    setIssuesInEventStream(evStream)
    parameters = {log_converter.Variants.TO_EVENT_LOG.value.Parameters.CASE_ID_KEY: 'case:trip'}
    evLog = log_converter.apply(evStream, parameters=parameters, variant=log_converter.Variants.TO_EVENT_LOG)
    setTripDetailsInEventLog(evLog)
    print ("CREATED FINAL EVENT LOG.")

    checkReworkFilter(evLog, uniqueStopIdsList)

    return evLog

def getTripsWithRepeatingStopMessage(evLog):
    result = ""
    for trace in evLog:
        result += str(trace._attributes["trip"]) + ", "
    
    return result[:-2]

def checkReworkFilter(evLog, uniqueStopIdsList):
    for stopId in uniqueStopIdsList:
        filteredLog = pm4py.filter_activities_rework(evLog, str(stopId), 2) # minimum 2 times
        if len(filteredLog) > 0:
            print("WARNING: Repeat of " + str(stopId) + " count=" + str(len(filteredLog)) + " in trips: " + getTripsWithRepeatingStopMessage(filteredLog))

######HELPERS###########################
def getLineFromVariant(variant):
    return variant.rsplit('R', 1)[1]

def removeAccents(input_text):
    strange='ŮôῡΒძěἊἦëĐᾇόἶἧзвŅῑἼźἓŉἐÿἈΌἢὶЁϋυŕŽŎŃğûλВὦėἜŤŨîᾪĝžἙâᾣÚκὔჯᾏᾢĠфĞὝŲŊŁČῐЙῤŌὭŏყἀхῦЧĎὍОуνἱῺèᾒῘᾘὨШūლἚύсÁóĒἍŷöὄЗὤἥბĔõὅῥŋБщἝξĢюᾫაπჟῸდΓÕűřἅгἰშΨńģὌΥÒᾬÏἴქὀῖὣᾙῶŠὟὁἵÖἕΕῨčᾈķЭτἻůᾕἫжΩᾶŇᾁἣჩαἄἹΖеУŹἃἠᾞåᾄГΠКíōĪὮϊὂᾱიżŦИὙἮὖÛĮἳφᾖἋΎΰῩŚἷРῈĲἁéὃσňİΙῠΚĸὛΪᾝᾯψÄᾭêὠÀღЫĩĈμΆᾌἨÑἑïოĵÃŒŸζჭᾼőΣŻçųøΤΑËņĭῙŘАдὗპŰἤცᾓήἯΐÎეὊὼΘЖᾜὢĚἩħĂыῳὧďТΗἺĬὰὡὬὫÇЩᾧñῢĻᾅÆßшδòÂчῌᾃΉᾑΦÍīМƒÜἒĴἿťᾴĶÊΊȘῃΟúχΔὋŴćŔῴῆЦЮΝΛῪŢὯнῬũãáἽĕᾗნᾳἆᾥйᾡὒსᾎĆрĀüСὕÅýფᾺῲšŵкἎἇὑЛვёἂΏθĘэᾋΧĉᾐĤὐὴιăąäὺÈФĺῇἘſგŜæῼῄĊἏØÉПяწДĿᾮἭĜХῂᾦωთĦлðὩზკίᾂᾆἪпἸиᾠώᾀŪāоÙἉἾρаđἌΞļÔβĖÝᾔĨНŀęᾤÓцЕĽŞὈÞუтΈέıàᾍἛśìŶŬȚĳῧῊᾟάεŖᾨᾉςΡმᾊᾸįᾚὥηᾛġÐὓłγľмþᾹἲἔбċῗჰხοἬŗŐἡὲῷῚΫŭᾩὸùᾷĹēრЯĄὉὪῒᾲΜᾰÌœĥტ'
    ascii_replacements='UoyBdeAieDaoiiZVNiIzeneyAOiiEyyrZONgulVoeETUiOgzEaoUkyjAoGFGYUNLCiIrOOoqaKyCDOOUniOeiIIOSulEySAoEAyooZoibEoornBSEkGYOapzOdGOuraGisPngOYOOIikoioIoSYoiOeEYcAkEtIuiIZOaNaicaaIZEUZaiIaaGPKioIOioaizTIYIyUIifiAYyYSiREIaeosnIIyKkYIIOpAOeoAgYiCmAAINeiojAOYzcAoSZcuoTAEniIRADypUitiiIiIeOoTZIoEIhAYoodTIIIaoOOCSonyKaAsSdoACIaIiFIiMfUeJItaKEISiOuxDOWcRoiTYNLYTONRuaaIeinaaoIoysACRAuSyAypAoswKAayLvEaOtEEAXciHyiiaaayEFliEsgSaOiCAOEPYtDKOIGKiootHLdOzkiaaIPIIooaUaOUAIrAdAKlObEYiINleoOTEKSOTuTEeiaAEsiYUTiyIIaeROAsRmAAiIoiIgDylglMtAieBcihkoIrOieoIYuOouaKerYAOOiaMaIoht'
    translator=str.maketrans(strange,ascii_replacements)
    
    return input_text.translate(translator)

def isTraceOnlyRealtime(trace):
    for event in trace._list:
        if event['status'] == "SCHEDULED":
            return False
    return True

def isTraceContainingGivenStopsInOrder(trace, stopNames):
    index = 0
    for event in trace._list:
        if event['stopName'] == stopNames[index]:
            index += 1
        if index == len(stopNames):
            return True
    return False

def isInRushHour(timestamp):
    startMorningRushHour = datetime.time(7, 0, 0)
    endMorningRushHour = datetime.time(9, 0, 0)
    startEveningRushHour = datetime.time(15, 0, 0)
    endEveningRushHour = datetime.time(17, 0, 0)

    return startMorningRushHour <= timestamp.time() <= endMorningRushHour or startEveningRushHour <= timestamp.time() <= endEveningRushHour

def isOnTheWeekend(timestamp):
    return timestamp.isoweekday() in [6,7]

def isTraceInGivenDay(trace, dayString):
    for event in trace._list:
        if event['timestamp'].isoformat()[:10] == dayString:
            return True
    return False

######FILTERS###########################
def filterByEventAttribute(evLog, eventAttributeName, eventAttributeValue, positive):
    from pm4py.algo.filtering.log.attributes import attributes_filter
    evLogFiltered = attributes_filter.apply(evLog, [eventAttributeValue],
                                          parameters={attributes_filter.Parameters.ATTRIBUTE_KEY: eventAttributeName, attributes_filter.Parameters.POSITIVE: positive})
    return evLogFiltered

def filterByTraceAttribute(evLog, traceAttributeName, traceAttributeValue):
    return pm4py.filter_log(lambda x: x._attributes[traceAttributeName] == traceAttributeValue, evLog)

def filterByNotTraceAttribute(evLog, traceAttributeName, traceAttributeValue):
    return pm4py.filter_log(lambda x: x._attributes[traceAttributeName] != traceAttributeValue, evLog)

def filterTracesWithOnlyRealtime(evLog):
    return pm4py.filter_log(lambda x: isTraceOnlyRealtime(x), evLog)

def filterByLine(evLog, line):
    return pm4py.filter_log(lambda x: getLineFromVariant(x._attributes["variant"]) == line, evLog)

def filterVehiclesOlderEqualTo2000(evLog):
    return pm4py.filter_log(lambda x: x._attributes["vehicleProductionYear"] <= 2000, evLog)

def filterVehiclesYoungerThan2000(evLog):
    return pm4py.filter_log(lambda x: x._attributes["vehicleProductionYear"] > 2000, evLog)

def filterVehiclesTwoWayDoorsLessEvenTo8(evLog):
    return pm4py.filter_log(lambda x: x._attributes["vehiclePassengerDoors"] <= 8, evLog)

def filterVehiclesTwoWayDoorsMoreThan8(evLog):
    return pm4py.filter_log(lambda x: x._attributes["vehiclePassengerDoors"] > 8, evLog)

def filterTracesContainingGivenStopsInOrder(evLog, stopNames):
    return pm4py.filter_log(lambda x: isTraceContainingGivenStopsInOrder(x, stopNames), evLog)

def filterTracesByGivenDay(evLog, dayString):
    return pm4py.filter_log(lambda x: isTraceInGivenDay(x, dayString), evLog)

def filterTracesRushHour(evLog):
        return pm4py.filter_log(lambda x: True in (isInRushHour(t["timestamp"]) for t in x._list), evLog)

def filterTracesLightTraffic(evLog):
        return pm4py.filter_log(lambda x: all(isInRushHour(t["timestamp"]) == False for t in x._list), evLog)
    
def filterTracesWeekday(evLog):
        return pm4py.filter_log(lambda x: False in (isOnTheWeekend(t["timestamp"]) for t in x._list), evLog)

def filterTracesWeekend(evLog):
        return pm4py.filter_log(lambda x: True in (isOnTheWeekend(t["timestamp"]) for t in x._list), evLog)
######DATA ANALYSIS#####################
def getDecisionTreeForEventAttributeValue(evLog):
    data, feature_names = log_to_features.apply(evLog, parameters={"str_tr_attr": ["vehicleId","service", "variant"], "str_ev_attr": ["concept:name", "departureDuringIssues"], "num_tr_attr": ["trip","vehicleProductionYear"], "num_ev_attr": []})
    target, classes = get_class_representation.get_class_representation_by_str_ev_attr_value_value(evLog, 3600)
    clf = tree.DecisionTreeClassifier()
    clf.fit(data, target)

    gviz = dectree_visualizer.apply(clf, feature_names, classes)
    dectree_visualizer.view(gviz)

def getDecisionTreesForTraceDuration(evLog, parameters, traceDuration):
    
    data, feature_names = log_to_features.apply(evLog, parameters=parameters)
    target, classes = get_class_representation.get_class_representation_by_trace_duration(evLog, traceDuration)
    
    tmpSum = 0
    for t in target:
        tmpSum += t

    clf = tree.DecisionTreeClassifier()
    clf.fit(data, target)

    gviz = dectree_visualizer.apply(clf, feature_names, classes)
    dectree_visualizer.view(gviz)

def getHeuristicMinerHeuristicsNet(evLog, minOccurencesForEdge):
    from pm4py.algo.discovery.heuristics import algorithm as heuristics_miner
    from pm4py.visualization.heuristics_net import visualizer as hn_visualizer
    parameters = {heuristics_miner.Variants.CLASSIC.value.Parameters.DEPENDENCY_THRESH: -1,
               heuristics_miner.Variants.CLASSIC.value.Parameters.MIN_DFG_OCCURRENCES: minOccurencesForEdge
              }

    heu_net = heuristics_miner.apply_heu(evLog, parameters)
    act_occur = heu_net.activities_occurrences
    dfg_matrix = heu_net.dfg_matrix

    gviz = hn_visualizer.apply(heu_net)
    hn_visualizer.view(gviz)

def getHeuristicMinerPetriNet(evLog, minOccurencesForEdge):
    from pm4py.algo.discovery.heuristics import algorithm as heuristics_miner
    net, im, fm = heuristics_miner.apply(evLog, parameters={heuristics_miner.Variants.CLASSIC.value.Parameters.DEPENDENCY_THRESH: 0,
    heuristics_miner.Variants.CLASSIC.value.Parameters.MIN_DFG_OCCURRENCES: minOccurencesForEdge})

    from pm4py.visualization.petri_net import visualizer as pn_visualizer
    gviz = pn_visualizer.apply(net, im, fm)
    pn_visualizer.view(gviz)

def getDirectlyFollowsGraphFrequency(evLog):
    from pm4py.algo.discovery.dfg import algorithm as dfg_discovery
    from pm4py.visualization.dfg import visualizer as dfg_visualization
    
    dfg = dfg_discovery.apply(evLog)
    gviz = dfg_visualization.apply(dfg, log=evLog, variant=dfg_visualization.Variants.FREQUENCY)
    dfg_visualization.view(gviz)

def getDirectlyFollowsGraphPerformanceMin(evLog):
    from pm4py.algo.discovery.dfg import algorithm as dfg_discovery
    from pm4py.visualization.dfg import visualizer as dfg_visualization

    parameters = {pm4py.algo.discovery.dfg.variants.performance.Parameters.AGGREGATION_MEASURE: "min"}

    dfg = dfg_discovery.apply(evLog, parameters=parameters, variant=dfg_discovery.Variants.PERFORMANCE)
    gviz = dfg_visualization.apply(dfg, log=evLog, parameters=parameters, variant=dfg_visualization.Variants.PERFORMANCE)
    dfg_visualization.view(gviz)

def getDirectlyFollowsGraphPerformanceMedian(evLog):
    from pm4py.algo.discovery.dfg import algorithm as dfg_discovery
    from pm4py.visualization.dfg import visualizer as dfg_visualization

    parameters = {pm4py.algo.discovery.dfg.variants.performance.Parameters.AGGREGATION_MEASURE: "median"}

    dfg = dfg_discovery.apply(evLog, parameters=parameters, variant=dfg_discovery.Variants.PERFORMANCE)
    gviz = dfg_visualization.apply(dfg, log=evLog, parameters=parameters, variant=dfg_visualization.Variants.PERFORMANCE)
    dfg_visualization.view(gviz)
 
def getPerformanceSpectrum(evLog, activitiesList):
    pm4py.view_performance_spectrum(evLog, activitiesList, format="png")

def getDistributionOfCaseDurationGraph(evLog, title):
    from pm4py.util import constants
    from pm4py.statistics.traces.generic.log import case_statistics
    from pm4py.visualization.graphs import visualizer as graphs_visualizer

    x, y = case_statistics.get_kde_caseduration(evLog, parameters={constants.PARAMETER_CONSTANT_TIMESTAMP_KEY: "time:timestamp"})

    gviz = graphs_visualizer.apply_plot(x, y, parameters={pm4py.visualization.graphs.variants.attributes.Parameters.TITLE: title}, variant=graphs_visualizer.Variants.CASES)
    graphs_visualizer.view(gviz)

def getDistributionOfNumericAttribute(evLog, attributeName, title):

    from pm4py.algo.filtering.log.attributes import attributes_filter
    from pm4py.visualization.graphs import visualizer as graphs_visualizer
    from pm4py.visualization.graphs import visualizer as graphs_visualizer

    x, y = attributes_filter.get_kde_numeric_attribute(evLog, attributeName)

    gviz = graphs_visualizer.apply_plot(x, y, parameters={pm4py.visualization.graphs.variants.attributes.Parameters.TITLE: title}, variant=graphs_visualizer.Variants.ATTRIBUTES)
    graphs_visualizer.view(gviz)

def getDottedChart(evLog, attributesXYZ):
    pm4py.view_dotted_chart(evLog, attributes=attributesXYZ, format="png")

def getMeanDelayForAttr(dataFrame, evStream, attrName):
    attrNameNoCase = attrName
    if ':' in attrName:
        attrNameNoCase = attrName.rsplit(':', 1)[1]
    
    fileToSave = open("delaysMeanForAttr_" + attrNameNoCase + ".csv", "w")
    fileToSave.write(attrNameNoCase + ",meanDelayAll,meanDelayRushHour,meanDelayLightTraffic,meanDelayWeekend,meanDelayWeekday\n")
    uniqueEventAttributesList = dataFrame[attrName].unique()
    delaysDict = {}
    for attrValue in uniqueEventAttributesList:
        delaysDict[str(attrValue)] = [(0,0),(0,0),(0,0),(0,0),(0,0)]

    for event in evStream._list:
        delaysDict[str(event[attrName])][0] = (delaysDict[str(event[attrName])][0][0] + event["delay"], delaysDict[str(event[attrName])][0][1] + 1)
        if isInRushHour(event["timestampExpected"]):
            delaysDict[str(event[attrName])][1] = (delaysDict[str(event[attrName])][1][0] + event["delay"], delaysDict[str(event[attrName])][1][1] + 1)
        else:
            delaysDict[str(event[attrName])][2] = (delaysDict[str(event[attrName])][2][0] + event["delay"], delaysDict[str(event[attrName])][2][1] + 1)
        if isOnTheWeekend(event["timestampExpected"]):
            delaysDict[str(event[attrName])][3] = (delaysDict[str(event[attrName])][3][0] + event["delay"], delaysDict[str(event[attrName])][3][1] + 1)
        else:
            delaysDict[str(event[attrName])][4] = (delaysDict[str(event[attrName])][4][0] + event["delay"], delaysDict[str(event[attrName])][4][1] + 1)
    for key in delaysDict:
        meanValAll = f'{delaysDict[key][0][0] / delaysDict[key][0][1]:.2f}'
        if delaysDict[key][1][1] == 0:
            meanValRushHours = "-"
        else:
            meanValRushHours = f'{delaysDict[key][1][0] / delaysDict[key][1][1]:.2f}'  
        if delaysDict[key][2][1] == 0:
            meanValLightTraffic = "-"
        else:
            meanValLightTraffic = f'{delaysDict[key][2][0] / delaysDict[key][2][1]:.2f}'
        if delaysDict[key][3][1] == 0:
            meanValWeekend = "-"
        else:
            meanValWeekend = f'{delaysDict[key][3][0] / delaysDict[key][3][1]:.2f}' 
        if delaysDict[key][4][1] == 0:
            meanValWeekday = "-"
        else:
            meanValWeekday = f'{delaysDict[key][4][0] / delaysDict[key][4][1]:.2f}' 
        fileToSave.write(key + "," + meanValAll + "," + meanValRushHours + "," + meanValLightTraffic + "," + meanValWeekend + "," + meanValWeekday + "\n")
    fileToSave.truncate()
    fileToSave.close()

def getMedianDelayForAttr(dataFrame, evStream, attrName):
    import statistics
    attrNameNoCase = attrName
    if ':' in attrName:
        attrNameNoCase = attrName.rsplit(':', 1)[1]
    
    fileToSave = open("delaysMedianForAttr_" + attrNameNoCase + ".csv", "w")
    fileToSave.write(attrNameNoCase + ",medianDelayAll,medianDelayRushHour,medianDelayLightTraffic,medianDelayWeekend,medianDelayWeekday\n")
    uniqueEventAttributesList = dataFrame[attrName].unique()
    delaysDict = {}
    for attrValue in uniqueEventAttributesList:
        delaysDict[str(attrValue)] = [[] for _ in range(5)]

    for event in evStream._list:
        delaysDict[str(event[attrName])][0].append(event["delay"])
        if isInRushHour(event["timestampExpected"]):
            delaysDict[str(event[attrName])][1].append(event["delay"])
        else:
            delaysDict[str(event[attrName])][2].append(event["delay"])
        if isOnTheWeekend(event["timestampExpected"]):
            delaysDict[str(event[attrName])][3].append(event["delay"])
        else:
            delaysDict[str(event[attrName])][4].append(event["delay"])
    for key in delaysDict:
        medianValAll = str(statistics.median(delaysDict[key][0]))
        if len(delaysDict[key][1]) == 0:
            medianValRushHours = "-"
        else:
            medianValRushHours = str(statistics.median(delaysDict[key][1]))
        if len(delaysDict[key][2]) == 0:
            medianValLightTraffic = "-"
        else:
            medianValLightTraffic = str(statistics.median(delaysDict[key][2]))
        if len(delaysDict[key][3]) == 0:
            medianValWeekend = "-"
        else:
            medianValWeekend = str(statistics.median(delaysDict[key][3]))
        if len(delaysDict[key][4]) == 0:
            medianValWeekday = "-"
        else:
            medianValWeekday = str(statistics.median(delaysDict[key][4]))
        fileToSave.write(key + "," + medianValAll + "," + medianValRushHours + "," + medianValLightTraffic + "," + medianValWeekend + "," + medianValWeekday + "\n")
    fileToSave.truncate()
    fileToSave.close()

if __name__ == "__main__":
    from pm4py.objects.log.exporter.xes import exporter as xes_exporter

    #evLog = createEventLog("stopId")
    #evLog = xes_importer.apply('tramDepartures_AllFinal_stopId.xes')
    #evLogRealtime = filterTracesWithOnlyRealtime(evLog)
    #evLog2 = createEventLog("stopName")
    evLog2 = xes_importer.apply('tramDepartures_AllFinal_stopName.xes')
    #xes_exporter.apply(evLog, 'tramDepartures_AllFinal_stopId.xes')
    #xes_exporter.apply(evLog2, 'tramDepartures_AllFinal_stopName.xes')
    
    #getHeuristicMinerHeuristicsNet(evLog,4)
    #getHeuristicMinerPetriNet(evLog,4)
    #getHeuristicMinerHeuristicsNet(evLog2,4)
    #getHeuristicMinerPetriNet(evLog2,4)
    #evLogOneVariant2 = filterByTraceAttribute(evLog2, "variant", "T11R2") # depends if u pref stop id or stop name 
    #getHeuristicMinerHeuristicsNet(evLogOneVariant2,2) # depends if u pref stop id or stop name
    #evLogOneLine2 = filterByLine(evLog2, "12")
    #getHeuristicMinerHeuristicsNet(evLogOneLine2,2)
    #getHeuristicMinerPetriNet(evLogOneLine2,2)
    #evLogOneLine = filterByLine(evLog, "12")
    #getHeuristicMinerPetriNet(evLogOneLine,2)

    #evLogRealtime = filterTracesWithOnlyRealtime(evLog)
    #getDirectlyFollowsGraphFrequency(evLogRealtime) # using filtered because noise in data(sometimes SCHEDULED trips confuse the time resulting in e.g. 2010->2014->2012)
    #evLogRealtime2 = filterTracesWithOnlyRealtime(evLog2)
    #evLogRealtimeOneVariant = filterByTraceAttribute(evLogRealtime, "variant", "T52R6")
    #getDirectlyFollowsGraphFrequency(evLogRealtimeOneVariant)
    #getDirectlyFollowsGraphPerformanceMin(evLogRealtimeOneVariant)
    #getDirectlyFollowsGraphPerformanceMedian(evLogRealtimeOneVariant)
    #evLogRealtimeOneVariant2 = filterByTraceAttribute(evLogRealtime2, "variant", "T52R6") # depends if u pref stop id or stop name
    #getDirectlyFollowsGraphFrequency(evLogRealtimeOneVariant2) # depends if u pref stop id or stop name
    #getHeuristicMinerHeuristicsNet(evLogRealtimeOneVariant2,1) # for comparision with directlyfollowsgraph
    #getDirectlyFollowsGraphPerformanceMin(evLogRealtimeOneVariant2) # depends if u pref stop id or stop name
    #getDirectlyFollowsGraphPerformanceMedian(evLogRealtimeOneVariant2) # depends if u pref stop id or stop name
    #evLogRealtimeOneLine2 = filterByLine(evLogRealtime2, "12")
    #getDirectlyFollowsGraphFrequency(evLogRealtimeOneLine2)
    #getDirectlyFollowsGraphPerformanceMin(evLogRealtimeOneLine2)
    #getDirectlyFollowsGraphPerformanceMedian(evLogRealtimeOneLine2)

    # evLog2SingleDay = filterTracesByGivenDay(evLog2, "2022-04-27")#standard day
    # evLog2SingleDayFromTrauguttaToObroncowWesterplatte= filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Ujescisko", "Dworzec Glowny", "Obroncow Westerplatte"])
    # getPerformanceSpectrum(evLog2SingleDayFromTrauguttaToObroncowWesterplatte, ["Ujescisko", "Dworzec Glowny", "Obroncow Westerplatte"])
    # evLog2SingleDayFromOdrzanskaToDworzec = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Odrzanska", "Srodmiescie SKM", "Dworzec Glowny"])
    # getPerformanceSpectrum(evLog2SingleDayFromOdrzanskaToDworzec, ["Odrzanska", "Srodmiescie SKM", "Dworzec Glowny"])#ODRZANSKA - SRODMIESCIE SKM - DWORZEC GL
    # evLog2SingleDayFromChmielnaToDworzec = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Chmielna", "Okopowa", "Dworzec Glowny"])
    # getPerformanceSpectrum(evLog2SingleDayFromChmielnaToDworzec, ["Chmielna", "Okopowa", "Dworzec Glowny"])#CHMIELNA - OKOPOWA - DWORZEC GL
    # evLog2SingleDayFromCiasnaToDworzec = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Ciasna", "Powstancow Warszawskich", "Dworzec Glowny"])
    # getPerformanceSpectrum(evLog2SingleDayFromCiasnaToDworzec, ["Ciasna", "Powstancow Warszawskich", "Dworzec Glowny"])#CIASNA - POWSTANCOW - DWORZEC GL
    # evLog2SingleDayFromChodowieckiegoToSrodmiescie = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Chodowieckiego", "Dworzec Glowny", "Srodmiescie SKM"])
    # getPerformanceSpectrum(evLog2SingleDayFromChodowieckiegoToSrodmiescie, ["Chodowieckiego", "Dworzec Glowny", "Srodmiescie SKM"])#CHODOWIECKIEGO - DWORZEC GL - SRODMIESCIE SKM
    # evLog2SingleDayFromChodowieckiegoToOkopowa = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Chodowieckiego", "Dworzec Glowny", "Okopowa"])
    # getPerformanceSpectrum(evLog2SingleDayFromChodowieckiegoToOkopowa, ["Chodowieckiego", "Dworzec Glowny", "Okopowa"])#CHODOWIECKIEGO - DWORZEC GL - OKOPOWA
    # evLog2SingleDayFromChodowieckiegoDoPowstancow = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Chodowieckiego", "Dworzec Glowny", "Powstancow Warszawskich"])
    # getPerformanceSpectrum(evLog2SingleDayFromChodowieckiegoDoPowstancow, ["Chodowieckiego", "Dworzec Glowny", "Powstancow Warszawskich"])#CHODOWIECKIEGO - DWORZEC GL  - POWSTANCOW
    # #tramwaj 4 vs 2,6 jak pomaga droga przez pks
    # evLog2SingleDayOneLine = filterByLine(evLog2SingleDay, "4")
    # evLog2SingleDayOneLineFromCebertowiczaToBramaOliwska = filterTracesContainingGivenStopsInOrder(evLog2SingleDayOneLine, ["Cebertowicza", "Pohulanka", "Brama Oliwska"])
    # getPerformanceSpectrum(evLog2SingleDayOneLineFromCebertowiczaToBramaOliwska, ["Cebertowicza", "Pohulanka", "Brama Oliwska"])#CEBERTOWICZA - POHULANKA - BRAMA OLIWSKA 
    # evLog2SingleDayOneLine = filterByLine(evLog2SingleDay, "2")
    # evLog2SingleDayOneLineFromCebertowiczaToBramaOliwska = filterTracesContainingGivenStopsInOrder(evLog2SingleDayOneLine, ["Cebertowicza", "Pohulanka", "Brama Oliwska"])
    # getPerformanceSpectrum(evLog2SingleDayOneLineFromCebertowiczaToBramaOliwska, ["Cebertowicza", "Pohulanka", "Brama Oliwska"])#CEBERTOWICZA - POHULANKA - BRAMA OLIWSKA 

    # evLog2SingleDay = filterTracesByGivenDay(evLog2, "2022-04-23")#weekend (saturday)
    # evLog2SingleDayFromTrauguttaToDworzec = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Ujescisko", "Dworzec Glowny", "Obroncow Westerplatte"])
    # getPerformanceSpectrum(evLog2SingleDayFromTrauguttaToDworzec, ["Ujescisko", "Dworzec Glowny", "Obroncow Westerplatte"])
    # evLog2SingleDayFromOdrzanskaToDworzec = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Odrzanska", "Srodmiescie SKM", "Dworzec Glowny"])
    # getPerformanceSpectrum(evLog2SingleDayFromOdrzanskaToDworzec, ["Odrzanska", "Srodmiescie SKM", "Dworzec Glowny"])#ODRZANSKA - SRODMIESCIE SKM - DWORZEC GL
    # evLog2SingleDayFromChmielnaToDworzec = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Chmielna", "Okopowa", "Dworzec Glowny"])
    # getPerformanceSpectrum(evLog2SingleDayFromChmielnaToDworzec, ["Chmielna", "Okopowa", "Dworzec Glowny"])#CHMIELNA - OKOPOWA - DWORZEC GL
    # evLog2SingleDayFromCiasnaToDworzec = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Ciasna", "Powstancow Warszawskich", "Dworzec Glowny"])
    # getPerformanceSpectrum(evLog2SingleDayFromCiasnaToDworzec, ["Ciasna", "Powstancow Warszawskich", "Dworzec Glowny"])#CIASNA - POWSTANCOW - DWORZEC GL
    # evLog2SingleDayFromChodowieckiegoToSrodmiescie = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Chodowieckiego", "Dworzec Glowny", "Srodmiescie SKM"])
    # getPerformanceSpectrum(evLog2SingleDayFromChodowieckiegoToSrodmiescie, ["Chodowieckiego", "Dworzec Glowny", "Srodmiescie SKM"])#CHODOWIECKIEGO - DWORZEC GL - SRODMIESCIE SKM
    # evLog2SingleDayFromChodowieckiegoToOkopowa = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Chodowieckiego", "Dworzec Glowny", "Okopowa"])
    # getPerformanceSpectrum(evLog2SingleDayFromChodowieckiegoToOkopowa, ["Chodowieckiego", "Dworzec Glowny", "Okopowa"])#CHODOWIECKIEGO - DWORZEC GL - OKOPOWA
    # evLog2SingleDayFromChodowieckiegoDoPowstancow = filterTracesContainingGivenStopsInOrder(evLog2SingleDay, ["Chodowieckiego", "Dworzec Glowny", "Powstancow Warszawskich"])
    # getPerformanceSpectrum(evLog2SingleDayFromChodowieckiegoDoPowstancow, ["Chodowieckiego", "Dworzec Glowny", "Powstancow Warszawskich"])#CHODOWIECKIEGO - DWORZEC GL  - POWSTANCOW
    
    # evLog2SingleDayOneTrace = filterByTraceAttribute(evLog2SingleDay, "variant", "T201R12")
    # fullT201R12Trace = ["Lawendowe Wzgorze", "Ujescisko", "Zabornia", "Stolema", "Labedzia", "Krolewskie Wzgorze", "Migowo", 
    # "Budapesztanska", "Warnenska", "Belgradzka", "Piekarnicza", "Siedlce", "Skrajna", "Zakopianska", "Ciasna", "Paska", 
    # "Powstancow Warszawskich", "Hucisko", "Dworzec Glowny", "Brama Oliwska", "Chodowieckiego", # uniwersytet medyczny - out(renovation)
    # "Traugutta", "Opera Baltycka", "Politechnika", "Miszewskiego", "Jaskowa Dolina", "Klonowa", "Galeria Baltycka", "Wojska Polskiego", 
    # "Zamenhofa", "Zajezdnia", "Strzyza PKM", "Uniwersytet Gdanski", "Bazynskiego", "Tetmajera", "Derdowskiego", "Obroncow Westerplatte", "Oliwa"]
    # evLog2SingleDayOneTraceFullTrace = filterTracesContainingGivenStopsInOrder(evLog2SingleDayOneTrace, fullT201R12Trace)
    # pm4py.view_performance_spectrum(evLog2SingleDayOneTraceFullTrace, fullT201R12Trace, format="png")
   
    evLog2RushHourWeekday = filterTracesWeekday(filterTracesRushHour(evLog2))
    evLog2RushHourWeekdayOneLine = pm4py.filter_log(lambda x: x._attributes["variant"] == "T201R12" or x._attributes["variant"] == "T202R12", evLog2RushHourWeekday)
    evLog2RushHourWeekdayOneLineRealtime = filterTracesWithOnlyRealtime(evLog2RushHourWeekdayOneLine)
    getDecisionTreesForTraceDuration(evLog2RushHourWeekdayOneLineRealtime, {"str_tr_attr": ["vehicleBrand", "variant"], "str_ev_attr": ["departureDuringIssues"], 
                                     "num_tr_attr": ["vehicleProductionYear"], "num_ev_attr": ["delay"]}, 4300)

    # evLog2RushHourWeekdayOneVariant = filterByTraceAttribute(evLog2RushHourWeekday, "variant", "T52R6")
    # evLog2RushHourWeekdayOneVariantRealtime = filterTracesWithOnlyRealtime(evLog2RushHourWeekdayOneVariant)

    # getDecisionTreesForTraceDuration(evLog2RushHourWeekdayOneVariantRealtime, {"str_tr_attr": ["vehicleBrand"], "str_ev_attr": ["departureDuringIssues"], 
    #                                 "num_tr_attr": ["vehicleProductionYear"], "num_ev_attr": ["delay"]}, 4000)


    #evLogRealtime = filterTracesWithOnlyRealtime(evLog)
    # evLogRealtimeOneVariantTwoWay = pm4py.filter_log(lambda x: x._attributes["variant"] == "T201R12" or x._attributes["variant"] == "T202R12", evLogRealtime)# special for case duration graph
    # getDistributionOfCaseDurationGraph(evLogRealtimeOneVariantTwoWay, "")
    # evLogRealtimeOneVariantTwoWayPesa = filterByTraceAttribute(evLogRealtimeOneVariantTwoWay, "vehicleBrand", "Pesa  Bydgoszcz  S.A.")
    # getDistributionOfCaseDurationGraph(evLogRealtimeOneVariantTwoWayPesa, "")
    # evLogRealtimeOneVariantTwoWayNotPesa = filterByNotTraceAttribute(evLogRealtimeOneVariantTwoWay, "vehicleBrand", "Pesa  Bydgoszcz  S.A.")
    # getDistributionOfCaseDurationGraph(evLogRealtimeOneVariantTwoWayNotPesa, "")
    # evLogRealtimeOneVariantTwoWayLowFloor = filterByTraceAttribute(evLogRealtimeOneVariantTwoWay, "vehiclefloorHeight", "Pojazd niskopodĹ‚ogowy")
    # getDistributionOfCaseDurationGraph(evLogRealtimeOneVariantTwoWayLowFloor, "")
    # evLogRealtimeOneVariantTwoWayNotLowFloor = filterByTraceAttribute(evLogRealtimeOneVariantTwoWay, "vehiclefloorHeight", "Pojazd czÄ™Ĺ›ciowo niskopodĹ‚ogowy")
    # getDistributionOfCaseDurationGraph(evLogRealtimeOneVariantTwoWayNotLowFloor, "")
    # evLogRealtimeOneVariantTwoWayWithIssues = filterByEventAttribute(evLogRealtimeOneVariantTwoWay, "departureDuringIssues", "true", True)
    # getDistributionOfCaseDurationGraph(evLogRealtimeOneVariantTwoWayWithIssues, "")
    # evLogRealtimeOneVariantTwoWayWithoutIssues = filterByEventAttribute(evLogRealtimeOneVariantTwoWay, "departureDuringIssues", "true", False)
    # getDistributionOfCaseDurationGraph(evLogRealtimeOneVariantTwoWayWithoutIssues, "")

    # getDistributionOfNumericAttribute(evLogRealtime, "delay", "")
    # evLogRealtimeTwoWayPesa = filterByTraceAttribute(evLogRealtime, "vehicleBrand", "Pesa  Bydgoszcz  S.A.")
    # getDistributionOfNumericAttribute(evLogRealtimeTwoWayPesa, "delay", "")
    # evLogRealtimeTwoWayNotPesa = filterByNotTraceAttribute(evLogRealtime, "vehicleBrand", "Pesa  Bydgoszcz  S.A.")
    # getDistributionOfNumericAttribute(evLogRealtimeTwoWayNotPesa, "delay", "")
    # evLogRealtimeTwoWayDoorsLessEven8 = filterVehiclesTwoWayDoorsLessEvenTo8(evLogRealtime)
    # evLogRealtimeTwoWayWithIssues = filterByEventAttribute(evLogRealtime, "departureDuringIssues", "true", True)
    # getDistributionOfNumericAttribute(evLogRealtimeTwoWayWithIssues, "delay", "")
    # evLogRealtimeTwoWayWithoutIssues = filterByEventAttribute(evLogRealtime, "departureDuringIssues", "true", False)
    # getDistributionOfNumericAttribute(evLogRealtimeTwoWayWithoutIssues, "delay", "")


    # evLogRealtime = filterTracesWithOnlyRealtime(evLog)

    # evLogRealtimeOneVariant = filterByTraceAttribute(evLogRealtime, "variant", "T201R12")
    # getDottedChart(evLogRealtimeOneVariant, ["time:timestamp", "delay", "stopName"])
    # evLogRealtimeOneVariant = filterByTraceAttribute(evLogRealtime, "variant", "T52R6")
    # getDottedChart(evLogRealtimeOneVariant, ["time:timestamp", "delay", "case:trip"])
    # evLogRealtimeOneVariant = filterByTraceAttribute(evLogRealtime, "variant", "T201R12")
    # getDottedChart(evLogRealtimeOneVariant, ["time:timestamp", "delay", "case:trip"])

    # evLogRealtimeOneLine = filterByLine(evLogRealtime, "12")
    # getDottedChart(evLogRealtimeOneVariant, ["time:timestamp", "delay", "stopName"])
    # getDottedChart(evLogRealtime, ["time:timestamp", "delay", "stopName"])
    # evLogRealtimeOneVariant = filterByLine(evLogRealtime, "6")
    # getDottedChart(evLogRealtimeOneVariant, ["time:timestamp", "delay", "case:trip"])
    # evLogRealtimeOneVariant = filterByLine(evLogRealtime, "12")
    # getDottedChart(evLogRealtimeOneVariant, ["time:timestamp", "delay", "case:trip"])

    # evLogRealtime = filterTracesWithOnlyRealtime(evLog)
    # dataFrame = log_converter.apply(evLogRealtime, variant=log_converter.Variants.TO_DATA_FRAME)
    # evStream = log_converter.apply(evLogRealtime, parameters={}, variant=log_converter.Variants.TO_EVENT_STREAM)
    # getMeanDelayForAttr(dataFrame, evStream, "case:variant")
    # getMeanDelayForAttr(dataFrame, evStream, "case:vehicleCode")
    # getMeanDelayForAttr(dataFrame, evStream, "case:service")
    # getMeanDelayForAttr(dataFrame, evStream, "case:vehicleBrand")
    # getMeanDelayForAttr(dataFrame, evStream, "case:vehicleModel")
    # getMeanDelayForAttr(dataFrame, evStream, "case:vehicleProductionYear")
    # getMeanDelayForAttr(dataFrame, evStream, "case:vehiclefloorHeight")
    # getMeanDelayForAttr(dataFrame, evStream, "case:vehiclePassengerDoors")
    # getMeanDelayForAttr(dataFrame, evStream, "departureDuringIssues")
    # getMeanDelayForAttr(dataFrame, evStream, "stopId")
    # getMeanDelayForAttr(dataFrame, evStream, "stopName")

    # getMedianDelayForAttr(dataFrame, evStream, "case:variant")
    # getMedianDelayForAttr(dataFrame, evStream, "case:vehicleCode")
    # getMedianDelayForAttr(dataFrame, evStream, "case:service")
    # getMedianDelayForAttr(dataFrame, evStream, "case:vehicleBrand")
    # getMedianDelayForAttr(dataFrame, evStream, "case:vehicleModel")
    # getMedianDelayForAttr(dataFrame, evStream, "case:vehicleProductionYear")
    # getMedianDelayForAttr(dataFrame, evStream, "case:vehiclefloorHeight")
    # getMedianDelayForAttr(dataFrame, evStream, "case:vehiclePassengerDoors")
    # getMedianDelayForAttr(dataFrame, evStream, "departureDuringIssues")
    # getMedianDelayForAttr(dataFrame, evStream, "stopId")
    # getMedianDelayForAttr(dataFrame, evStream, "stopName")
