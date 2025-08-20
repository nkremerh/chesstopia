#! /usr/bin/python

import piece

import getopt
import hashlib
import json
import math
import random
import re
import sys

class Chesstopia:
    def __init__(self, configuration):
        self.board = None
        self.bornPieces = []
        self.black = "\033[7;35m"
        self.blackPieces = []
        self.configuration = configuration
        self.deadPieces = []
        self.pieceConfigHashes = None
        self.pieceEndowmentIndex = 0
        self.pieceEndowments = []
        self.nextPieceID = 0
        self.pieces = []
        self.timestep = 0
        self.white = "\033[7;37m"
        self.whitePieces = []

        self.boardHeight = configuration["boardHeight"]
        self.boardWidth = configuration["boardWidth"]
        self.debug = configuration["debugMode"]
        self.keepAlive = configuration["keepAlivePostExtinction"]
        self.maxTimestep = configuration["timesteps"]
        self.seed = configuration["seed"]

        self.configureBoard(self.boardHeight, self.boardWidth, "classical")
        self.printBoard()
        #self.configurePieces(configuration["startingPieces"])
        self.run = False # Simulation start flag
        self.end = False # Simulation end flag
        self.runtimeStats = {"timestep": 0, "pieces": 0}
        self.log = open(configuration["logfile"], 'a') if configuration["logfile"] != None else None
        self.logFormat = configuration["logfileFormat"]
        self.experimentalGroup = configuration["experimentalGroup"]
        if self.experimentalGroup != None:
            # Convert keys to Pythonic case scheme and initialize values
            groupRuntimeStats = {}
            for key in self.runtimeStats.keys():
                controlGroupKey = "control" + key[0].upper() + key[1:]
                experimentalGroupKey = self.experimentalGroup + key[0].upper() + key[1:]
                groupRuntimeStats[controlGroupKey] = 0
                groupRuntimeStats[experimentalGroupKey] = 0
            self.runtimeStats.update(groupRuntimeStats)

    def addPiece(self, piece):
        self.bornPieces.append(piece)
        self.pieces.append(piece)
        if piece.color == "black":
            self.blackPieces.append(piece)
        else:
            self.whitePieces.append(piece)

    def configureBoard(self, height, width, startingPosition, boardFile=None):
        self.board = [[None for j in range(width)]for i in range(height)]
        kingFile = math.floor(len(self.board[0]) / 2)
        queenFile = kingFile - 1
        leftBishopFile = queenFile - 1
        rightBishopFile = kingFile + 1
        leftKnightFile = leftBishopFile - 1
        rightKnightFile = rightBishopFile + 1
        leftRookFile = leftKnightFile - 1
        rightRookFile = rightKnightFile + 1

        if boardFile == None:
            for i in range(height):
                color = None
                if i < 2:
                    color = "black"
                elif i > 5:
                    color = "white"
                for j in range(width):
                    if color == None:
                        continue
                    configuration = None
                    timestep = 0
                    if height > 3 and (i == 1 or i == height - 2):
                        self.board[i][j] = piece.Pawn(self.nextPieceID, timestep, color, (i, j), configuration, self)
                    elif (i == 0 or i == height - 1) and (j == leftRookFile or j == rightRookFile):
                        self.board[i][j] = piece.Rook(self.nextPieceID, timestep, color, (i, j), configuration, self)
                    elif (i == 0 or i == height - 1) and (j == leftKnightFile or j == rightKnightFile):
                        self.board[i][j] = piece.Knight(self.nextPieceID, timestep, color, (i, j), configuration, self)
                    elif (i == 0 or i == height - 1) and (j == leftBishopFile or j == rightBishopFile):
                        self.board[i][j] = piece.Bishop(self.nextPieceID, timestep, color, (i, j), configuration, self)
                    elif (i == 0 or i == height - 1) and j == queenFile:
                        self.board[i][j] = piece.Queen(self.nextPieceID, timestep, color, (i, j), configuration, self)
                    elif (i == 0 or i == height - 1) and j == kingFile:
                        self.board[i][j] = piece.King(self.nextPieceID, timestep, color, (i, j), configuration, self)
                    self.nextPieceID += 1
                    self.addPiece(self.board[i][j])
        else:
            boardFile = open(boardFile)
            loadBoard = json.loads(boardFile.read())
            boardFile.close()
            height = len(loadBoard)
            width = len(loadBoard[0])
            self.board.height = height
            self.board.width = width
            for i in range(width):
                for j in range(height):
                    loadPiece = loadBoard[i][j]
                    self.board[i][j] = loadPiece

    def doTimestep(self):
        if self.timestep >= self.maxTimestep:
            self.toggleEnd()
            return
        if "all" in self.debug or "chesstopia" in self.debug:
            print(f"Timestep: {self.timestep}\nLiving Pieces: {len(self.pieces)}")
        self.timestep += 1
        if self.end == True or (len(self.pieces) == 0 and self.keepAlive == False):
            self.toggleEnd()
        else:
            random.shuffle(self.blackPieces)
            random.shuffle(self.whitePieces)
            smallerSide = self.blackPieces if len(self.blackPieces) < len(self.whitePieces) else self.whitePieces
            biggerSide = self.blackPieces if len(self.blackPieces) >= len(self.whitePieces) else self.whitePieces
            turnOrder = []
            i = 0
            while i < len(smallerSide):
                turnOrder.append(self.whitePieces[i])
                turnOrder.append(self.blackPieces[i])
                i += 1
            while i < len(biggerSide):
                turnOrder.append(biggerSide[i])
                i += 1
            for piece in turnOrder:
                piece.doTimestep(self.timestep)
            self.removeDeadPieces()
            self.updateRuntimeStats()
            self.printBoard()
            # If final timestep, do not write to log to cleanly close JSON array log structure
            if self.timestep != self.maxTimestep and len(self.pieces) > 0:
                self.writeToLog()

    def endLog(self):
        if self.log == None:
            return
        logString = '\t' + json.dumps(self.runtimeStats) + "\n]"
        if self.logFormat == "csv":
            logString = ""
            # Ensure consistent ordering for CSV format
            for stat in sorted(self.runtimeStats):
                if logString == "":
                    logString += f"{self.runtimeStats[stat]}"
                else:
                    logString += f",{self.runtimeStats[stat]}"
            logString += "\n"
        self.log.write(logString)
        self.log.flush()
        self.log.close()

    def endSimulation(self):
        self.removeDeadPieces()
        self.endLog()
        if "all" in self.debug or "chesstopia" in self.debug:
            print(str(self))
        exit(0)

    def generatePieceID(self):
        pieceID = self.nextPieceID
        self.nextPieceID += 1
        return pieceID

    def pauseSimulation(self):
        while self.run == False:
            if self.end == True:
                self.endSimulation()

    def printBoard(self):
        string = ""
        for i in range(self.boardHeight):
            color = self.black
            if i % 2 == 0:
                color = self.white
            previousColor = None
            for j in range(self.boardWidth):
                if previousColor == self.black:
                    color = self.white
                elif previousColor == self.white:
                    color = self.black
                square = self.board[i][j]
                if square == None:
                    square = color + ' '
                else:
                    square = color + str(square.piece)
                string = string + square
                previousColor = color
            string = string + "\033[0m" + '\n'
        print(string)

    def randomizePieceEndowments(self, numPieces):
        configs = self.configuration
        vision = configs["pieceVision"]

        configurations = {
                          "vision": {"endowments": [], "curr": vision[0], "min": vision[0], "max": vision[1]}
                          }

        if self.pieceConfigHashes == None:
            self.pieceConfigHashes = {}
            # Map configuration to a random number via hash to make random number generation independent of iteration order
            for config in configurations.keys():
                hashed = hashlib.md5(config.encode())
                hashNum = int(hashed.hexdigest(), 16)
                self.pieceConfigHashes[config] = hashNum

        for config in configurations:
            configMin = configurations[config]["min"]
            configMax = configurations[config]["max"]
            configMinDecimals = str(configMin).split('.')
            configMaxDecimals = str(configMax).split('.')
            decimalRange = []
            if len(configMinDecimals) == 2:
                configMinDecimals = len(configMinDecimals[1])
                decimalRange.append(configMinDecimals)
            if len(configMaxDecimals) == 2:
                configMaxDecimals = len(configMaxDecimals[1])
                decimalRange.append(configMaxDecimals)
            # If no fractional component to configuration item, assume increment of 1
            decimals = max(decimalRange) if len(decimalRange) > 0 else 0
            increment = 10 ** (-1 * decimals)
            configurations[config]["inc"] = increment
            configurations[config]["decimals"] = decimals

        decisionModels = []
        endowments = []

        for i in range(numPieces):
            for config in configurations.values():
                config["endowments"].append(config["curr"])
                config["curr"] += config["inc"]
                config["curr"] = round(config["curr"], config["decimals"])
                if config["curr"] > config["max"]:
                    config["curr"] = config["min"]

        # Keep state of random numbers to allow extending piece endowments without altering original random object state
        randomNumberReset = random.getstate()
        for config in configurations:
            random.seed(self.pieceConfigHashes[config] + self.timestep)
            random.shuffle(configurations[config]["endowments"])
        random.setstate(randomNumberReset)
        for i in range(numPieces):
            pieceEndowment = {"seed": self.seed}
            for config in configurations:
                pieceEndowment[config] = configurations[config]["endowments"].pop()
            endowments.append(pieceEndowment)
        return endowments

    def removeDeadPieces(self):
        deadPieces = []
        for piece in self.pieces:
            if piece.isAlive() == False:
                deadPieces.append(piece)
            elif piece.square == None:
                deadPieces.append(piece)
        self.deadPieces += deadPieces
        for piece in deadPieces:
            piece.doDeath()
            self.pieces.remove(piece)

    def runSimulation(self, timesteps=5):
        self.startLog()
        if self.log == None:
            self.updateRuntimeStats()
        t = 1
        timesteps = timesteps - self.timestep
        screenshots = 0
        while t <= timesteps:
            if len(self.pieces) == 0:
                break
            self.doTimestep()
            t += 1
        self.endSimulation()

    def startLog(self):
        if self.log == None:
            return
        if self.logFormat == "csv":
            header = ""
            # Ensure consistent ordering for CSV format
            for stat in sorted(self.runtimeStats):
                if header == "":
                    header += f"{stat}"
                else:
                    header += f",{stat}"
            header += "\n"
            self.log.write(header)
        else:
            self.log.write("[\n")
        self.updateRuntimeStats()
        self.writeToLog()

    def toggleEnd(self):
        self.end = True

    def toggleRun(self):
        self.run = not self.run

    def updateRuntimeStats(self):
        # Log separate stats for experimental and control groups
        if self.experimentalGroup != None:
            self.updateRuntimeStatsPerGroup(self.experimentalGroup)
            self.updateRuntimeStatsPerGroup(self.experimentalGroup, True)
        self.updateRuntimeStatsPerGroup()

    def updateRuntimeStatsPerGroup(self, group=None, notInGroup=False):
        meanAge = 0
        meanMovement = 0
        numPieces = 0

        for piece in self.pieces:
            if group != None and piece.isInGroup(group, notInGroup) == False:
                continue

        numDeadPieces = 0
        meanAgeAtDeath = 0
        for piece in self.deadPieces:
            if group != None and piece.isInGroup(group, notInGroup) == False:
                continue
            numDeadPieces += 1

        # TODO: make clear whether piece or board calculation
        runtimeStats = {"pieces": numPieces}

        if group == None:
            self.runtimeStats["timestep"] = self.timestep
            self.deadPieces = []
        else:
            # Convert keys to Pythonic case scheme
            groupString = group if notInGroup == False else "control"
            groupStats = {}
            for key in runtimeStats.keys():
                groupKey = groupString + key[0].upper() + key[1:]
                groupStats[groupKey] = runtimeStats[key]
            runtimeStats = groupStats
            if notInGroup == True:
                runtimeStats.update(controlInteractionStats)
            else:
                runtimeStats.update(experimentalInteractionStats)

        for key in runtimeStats.keys():
            self.runtimeStats[key] = runtimeStats[key]

    def writeToLog(self):
        if self.log == None:
            return
        logString = '\t' + json.dumps(self.runtimeStats) + ",\n"
        if self.logFormat == "csv":
            logString = ""
            # Ensure consistent ordering for CSV format
            for stat in sorted(self.runtimeStats):
                if logString == "":
                    logString += f"{self.runtimeStats[stat]}"
                else:
                    logString += f",{self.runtimeStats[stat]}"
            logString += "\n"
        self.log.write(logString)

    def __str__(self):
        string = f"{str(self.board)}Seed: {self.seed}\nTimestep: {self.timestep}\nLiving Pieces: {len(self.pieces)}"
        return string

def parseConfiguration(configFile, configuration):
    file = open(configFile)
    options = json.loads(file.read())
    # If using the top-level config file, access correct JSON object
    if "chesstopiaOptions" in options:
        options = options["chesstopiaOptions"]

    for opt in configuration:
        if opt in options:
            configuration[opt] = options[opt]
    return configuration

def parseOptions(configuration):
    commandLineArgs = sys.argv[1:]
    shortOptions = "c:h:"
    longOptions = ["conf=", "help"]
    try:
        args, vals = getopt.getopt(commandLineArgs, shortOptions, longOptions)
    except getopt.GetoptError as err:
        print(err)
        printHelp()
    nextArg = 0
    for currArg, currVal in args:
        nextArg += 1
        if currArg in("-c", "--conf"):
            if currVal == "":
                print("No config file provided.")
                printHelp()
            parseConfiguration(currVal, configuration)
        elif currArg in ("-h", "--help"):
            printHelp()
    return configuration

def printHelp():
    print("Usage:\n\tpython chesstopia.py --conf config.json\n\nOptions:\n\t-c,--conf\tUse specified config file for simulation settings.\n\t-h,--help\tDisplay this message.")
    exit(0)

def sortConfigurationTimeframes(configuration, timeframe):
    config = configuration[timeframe]
    if configuration != [0, 0]:
        start = config[0]
        end = config[1]
        # Ensure start and end are in correct order
        if start > end and end >= 0:
            swap = start
            start = end
            end = swap
            if "all" in configuration["debugMode"] or "chesstopia" in configuration["debugMode"] or "board" in configuration["debugMode"]:
                print(f"Start and end values provided for {timeframe} in incorrect order. Switching values around.")
        # If provided a negative value, assume the start timestep is the very first of the simulation
        if start < 0:
            if "all" in configuration["debugMode"] or "chesstopia" in configuration["debugMode"] or "board" in configuration["debugMode"]:
                print(f"Start timestep {start} for {timeframe} is invalid. Setting {timeframe} start timestep to 0.")
            start = 0
        # If provided a negative value, assume the end timestep is the very end of the simulation
        if end < 0:
            if "all" in configuration["debugMode"] or "chesstopia" in configuration["debugMode"] or "board" in configuration["debugMode"]:
                print(f"End timestep {end} for {timeframe} is invalid. Setting {timeframe} end timestep to {configuration['timesteps']}.")
            end = configuration["timesteps"]
        config = [start, end]
    return config

def verifyConfiguration(configuration):
    negativesAllowed = ["seed"]
    timeframes = []
    negativeFlag = 0
    for configName, configValue in configuration.items():
        if isinstance(configValue, list):
            if len(configValue) == 0:
                continue
            configType = type(configValue[0])
            if configName in timeframes:
                configuration[configName] = sortConfigurationTimeframes(configuration, configName)
            else:
                configValue.sort()
            if configName not in negativesAllowed and (configType == int or configType == float):
                for i in range(len(configValue)):
                    if configValue[i] < 0:
                        configValue[i] = 0
                        negativeFlag += 1
        else:
            configType = type(configValue)
            if configName not in negativesAllowed and (configType == int or configType == float) and configValue < 0:
                configValue = 0
                negativeFlag += 1
    if negativeFlag > 0:
        print(f"Detected negative values provided for {negativeFlag} option(s). Setting these values to zero.")

    if configuration["logfile"] == "":
        configuration["logfile"] = None

    if configuration["seed"] == -1:
        configuration["seed"] = random.randrange(sys.maxsize)

    recognizedDebugModes = ["piece", "all", "board", "chesstopia", "ethics", "none"]
    validModes = True
    for mode in configuration["debugMode"]:
        if mode not in recognizedDebugModes:
            print(f"Debug mode {mode} not recognized")
            validModes = False
    if validModes == False:
        printHelp()

    if "all" in configuration["debugMode"] and "none" in configuration["debugMode"]:
        print("Cannot have \"all\" and \"none\" debug modes enabled at the same time")
        printHelp()
    elif "all" in configuration["debugMode"] and len(configuration["debugMode"]) > 1:
        configuration["debugMode"] = "all"
    elif "none" in configuration["debugMode"] and len(configuration["debugMode"]) > 1:
        configuration["debugMode"] = "none"

    # Ensure experimental group is properly defined or otherwise ignored
    if configuration["experimentalGroup"] == "":
        configuration["experimentalGroup"] = None
    groupList = []
    if configuration["experimentalGroup"] != None and configuration["experimentalGroup"] not in groupList and "disease" not in configuration["experimentalGroup"]:
        if "all" in configuration["debugMode"] or "piece" in configuration["debugMode"]:
            print(f"Cannot provide separate log stats for experimental group {configuration['experimentalGroup']}. Disabling separate log stats.")
        configuration["experimentalGroup"] = None

    widths = [1, 2, 4, 6, 8]
    if configuration["boardWidth"] not in widths:
        minIndex = min(range(len(widths)), key=lambda i: abs(widths[i] - configuration["boardWidth"]))
        configuration["boardWidth"] = widths[minIndex]
    elif configuration["boardWidth"] < 1:
        configuration["boardWidth"] = 1
    if configuration["boardHeight"] > 12:
        configuration["boardHeight"] = 12
    elif configuration["boardHeight"] < 3:
        configuration["boardHeight"] = 3

    return configuration

if __name__ == "__main__":
    # Set default values for simulation configuration
    configuration = {"boardHeight": 8,
                     "boardWidth": 8,
                     "debugMode": ["none"],
                     "experimentalGroup": None,
                     "interfaceHeight": 1000,
                     "interfaceWidth": 900,
                     "keepAlivePostExtinction": False,
                     "keepAliveAtEnd": False,
                     "logfile": None,
                     "logfileFormat": "json",
                     "profileMode": False,
                     "screenshots": False,
                     "seed": -1,
                     "startingPosition": "classical",
                     "timesteps": 2
                     }
    configuration = parseOptions(configuration)
    configuration = verifyConfiguration(configuration)
    random.seed(configuration["seed"])
    C = Chesstopia(configuration)
    if configuration["profileMode"] == True:
        import cProfile
        import tracemalloc
        tracemalloc.start()
        cProfile.run("C.runSimulation(configuration[\"timesteps\"])")
        snapshot = tracemalloc.take_snapshot()
        memoryStats = snapshot.statistics("lineno", True)
        for stat in memoryStats[:100]:
            print(stat)
    else:
        C.runSimulation(configuration["timesteps"])
    exit(0)
