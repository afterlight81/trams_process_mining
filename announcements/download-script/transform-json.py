#!/usr/bin/python3
import sys
import json
import regex
import os
import time
import datetime

ONGOING_ISSUES_FILEPATH = 'D:/Informatyka/MAGISTERKA/announcements/ongoing_issues.csv'
ONGOING_ISSUES_FILE_HEADER = 'tram_line,start_date,estimated_end_date'
RESULT_FILEPATH = 'D:/Informatyka/MAGISTERKA/prepared_data/tram_issues_from_announcements.csv'
CONSECUTIVELY_OMITTED_EMPTY_FILES_AMOUNT_FILEPATH = 'D:/Informatyka/MAGISTERKA/announcements/consecutively_omitted_empty_files_amount.txt'
EMPTY_FILES_IN_A_ROW_TO_OMIT_AMOUNT = 9 # save every 10th empty file
MAX_LAST_MODIFIED_TIME_BEFORE_FILE_DELETION = 18000 # 5 hours <-> 60 * 60 * 5 = 18000 seconds
ESTIMATED_TIME_OF_ISSUE_LASTING_AFTER_TRACE_LOSE = 300 # 5 minutes <-> 5 * 60 = 300 seconds

def createOmittedEmptyFilesCounterFileIfNotPresent():
    if not os.path.isfile(CONSECUTIVELY_OMITTED_EMPTY_FILES_AMOUNT_FILEPATH) or os.path.getsize(CONSECUTIVELY_OMITTED_EMPTY_FILES_AMOUNT_FILEPATH) == 0:
        with open(CONSECUTIVELY_OMITTED_EMPTY_FILES_AMOUNT_FILEPATH, 'w') as f:
            f.write('0')

def createOngoingIssuesFileIfNotPresent():
    if not os.path.isfile(ONGOING_ISSUES_FILEPATH) or os.path.getsize(ONGOING_ISSUES_FILEPATH) == 0:
        with open(ONGOING_ISSUES_FILEPATH, 'w') as f:
            f.write(ONGOING_ISSUES_FILE_HEADER)

def FindLinesExperiencingIssues(announcementTitle):
    textIndicatingIssue = regex.search(r'(awar|trudn|wypad|p\\u00f3\\u017an|problem|późn).*?lini', announcementTitle, regex.IGNORECASE)

    if not textIndicatingIssue:
        return

    textToFindLinesIn = announcementTitle[textIndicatingIssue.span()[1]:]
    dotPlacementRegex = regex.search(r'\.', textToFindLinesIn)

    if dotPlacementRegex:
        sentenceToFindLinesIn = textToFindLinesIn[:dotPlacementRegex.span()[0]]
    else:
        sentenceToFindLinesIn = textToFindLinesIn

    tuplesWithFoundLines = regex.findall(r'[^0-9N](2|3|4|5|6|7|8|9|10|12)([^0-9]|$)', sentenceToFindLinesIn)
    return set([i[0] for i in tuplesWithFoundLines])

def AddNewIssuesToOngoingIssuesFile(linesWithNewIssues, currentIssuesWithDates, file):
    for line in linesWithNewIssues:
        earliestIssueStartTime = datetime.datetime.max # latest date possible
        latestIssueEndTime = datetime.datetime.min # earliest date possible
        for issue in currentIssuesWithDates:
            if line in issue[0]:
                if datetime.datetime.fromisoformat(issue[1]) < earliestIssueStartTime:
                    earliestIssueStartTime = datetime.datetime.fromisoformat(issue[1])
                if datetime.datetime.fromisoformat(issue[2]) > latestIssueEndTime:
                    latestIssueEndTime = datetime.datetime.fromisoformat(issue[2])
                
        file.write('\n' + line + ',' + str(earliestIssueStartTime) + ',' + str(latestIssueEndTime))

def HandlePreviouslyNotedIssues(previouslyNotedIssues, currentIssuesWithDates, allLinesCurrentlyExperiencingIssues, previousIssuesCsvFile):
    eventLogCsvFile = open(RESULT_FILEPATH, 'a')
    for prevIssue in previouslyNotedIssues[1:]:
        prevIssueSplit = prevIssue.split(',')
        lineWithPreviousIssue = prevIssueSplit[0]
        if lineWithPreviousIssue in allLinesCurrentlyExperiencingIssues: # issue still persists
            estimatedEndDate = datetime.datetime.fromisoformat(prevIssueSplit[2].replace('\n', ''))
            for newIssue in currentIssuesWithDates:
                if lineWithPreviousIssue in newIssue[0]:
                    if estimatedEndDate == datetime.datetime.fromisoformat('9999-12-31 23:59:59') or datetime.datetime.fromisoformat(newIssue[2]) > estimatedEndDate:
                        estimatedEndDate = datetime.datetime.fromisoformat(newIssue[2])
            previousIssuesCsvFile.write('\n' + prevIssueSplit[0] + ',' + prevIssueSplit[1] + ',' + str(estimatedEndDate))
        else: # issue is gone
            endDate = prevIssueSplit[2].replace('\n', '')
            if endDate == '9999-12-31 23:59:59':
                endDate = str(datetime.datetime.fromtimestamp(os.path.getmtime(ONGOING_ISSUES_FILEPATH) + ESTIMATED_TIME_OF_ISSUE_LASTING_AFTER_TRACE_LOSE).replace(microsecond=0))
            eventLogCsvFile.write('\n' + prevIssueSplit[0] + ',' + prevIssueSplit[1] + ',' + endDate)

    eventLogCsvFile.close()

def main():
    previouslyNotedIssues = []

    previousIssuesCsvFile = open(ONGOING_ISSUES_FILEPATH, "r+")

    if time.time() - os.path.getmtime(ONGOING_ISSUES_FILEPATH) > MAX_LAST_MODIFIED_TIME_BEFORE_FILE_DELETION:
        previousIssuesCsvFile.write(ONGOING_ISSUES_FILE_HEADER)
        previousIssuesCsvFile.truncate(0) # too long between updates - data unreliable
    else:
        previouslyNotedIssues = previousIssuesCsvFile.readlines()
        previousIssuesCsvFile.seek(0)
        previousIssuesCsvFile.write(ONGOING_ISSUES_FILE_HEADER)

    announcementsJsonFilePath = sys.argv[1]
    announcementsJsonFile = open(announcementsJsonFilePath,)
    data = json.load(announcementsJsonFile)
    currentIssuesWithDates = []
    allLinesCurrentlyExperiencingIssues = set()

    for i in data['komunikaty']:
        linesExperiencingIssues = FindLinesExperiencingIssues(i['tresc'])
        if linesExperiencingIssues:
            currentIssuesWithDates.append((linesExperiencingIssues, i['data_rozpoczecia'], i['data_zakonczenia']))
            allLinesCurrentlyExperiencingIssues.update(linesExperiencingIssues)

    announcementsJsonFile.close()

    linesWithNewIssues = allLinesCurrentlyExperiencingIssues - set([line.split(',')[0] for line in previouslyNotedIssues[1:]])
    if previouslyNotedIssues[1:]: # check if file constist any data apart from header
        HandlePreviouslyNotedIssues(previouslyNotedIssues, currentIssuesWithDates, allLinesCurrentlyExperiencingIssues, previousIssuesCsvFile)

    AddNewIssuesToOngoingIssuesFile(linesWithNewIssues, currentIssuesWithDates, previousIssuesCsvFile)

    previousIssuesCsvFile.truncate()
    previousIssuesCsvFile.close()

    if not data['komunikaty']:
        createOmittedEmptyFilesCounterFileIfNotPresent()
        with open(CONSECUTIVELY_OMITTED_EMPTY_FILES_AMOUNT_FILEPATH, "r+") as f:
            consecutivelyDeletedEmptyAnnouncementFiles = int(f.readline())
            f.seek(0)
            if consecutivelyDeletedEmptyAnnouncementFiles >= EMPTY_FILES_IN_A_ROW_TO_OMIT_AMOUNT:
                f.write("0")
            else:
                f.write(str(consecutivelyDeletedEmptyAnnouncementFiles + 1))
                os.remove(announcementsJsonFilePath)

if __name__ == "__main__":
    main()
