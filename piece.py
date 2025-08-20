import hashlib
import math
import random
import re
import sys

class Piece:
    def __init__(self, pieceID, birthday, color, square, configuration, chesstopia):
        self.ID = pieceID
        self.board = chesstopia.board
        self.born = birthday
        self.chesstopia = chesstopia
        self.color = color
        self.configuration = configuration
        self.debug = chesstopia.debug 

        self.square = square
        self.x = square[0]
        self.y = square[1]

        self.age = 0
        self.alive = True
        self.capturer = None
        self.causeOfDeath = None
        self.lastMoved = -1
        self.lastMoveOptimal = True
        self.neighbors = []
        self.piece = None
        self.squaresInRange = []
        self.timestep = birthday

        self.adjacent = [(0,1), (0,-1), (1,0), (-1,0), (1,1), (-1,1), (1,-1), (-1,-1)]
        self.cardinal = [(0,1), (0,2), (0,3), (0,4), (0,5), (0,6), (0,7),
                         (1,0), (2,0), (3,0), (4,0), (5,0), (6,0), (7,0),
                         (0,-1), (0,-2), (0,-3), (0,-4), (0,-5), (0,-6), (0,-7),
                         (-1,0), (-2,0), (-3,0), (-4,0), (-5,0), (-6,0), (-7,0)]
        self.ordinal = [(1,1), (2,2), (3,3), (4,4), (5,5), (6,6), (7,7),
                        (1,-1), (2,-2), (3,-3), (4,-4), (5,-5), (6,-6), (7,-7),
                        (-1,1), (-2,2), (-3,3), (-4,4), (-5,5), (-6,6), (-7,7),
                        (-1,-1), (-2,-2), (-3,-3), (-4,-4), (-5,-5), (-6,-6), (-7,-7)]

    def canReachSquare(self, square):
        if square == self.square or square in self.squaresInRange:
            return True
        return False

    def doAging(self):
        if self.isAlive() == False:
            return
        self.age += 1

    def doDeath(self, capturer=None):
        if capturer != None:
            self.capturer = capturer
        self.alive = False
        self.resetSquare()

    def doTimestep(self, timestep):
        self.timestep = timestep
        # Prevent dead or already moved agent from moving
        if self.isAlive() == True and self.lastMoved != self.timestep:
            # Bookkeeping before performing actions
            self.lastMoved = self.timestep
            # Beginning of timestep actions
            self.moveToBestSquare()
            self.updateNeighbors()
            # Middle of timestep actions
            self.doAging()
            # End of timestep actions
            self.findSquaresInRange()

    def findBestSquare(self):
        bestSquare = None
        potentialSquares = self.rankSquaresInRange()
        greedyBestSquare = potentialSquares[0]["square"]

        #if self.decisionModelFactor > 0:
        #    bestSquare = self.findBestEthicalSquare(potentialSquares, greedyBestSquare)
        if bestSquare == None:
            bestSquare = greedyBestSquare
        return bestSquare

    def findBestEthicalSquare(self, squares, greedyBestSquare=None):
        if len(squares) == 0:
            return None
        bestSquare = None
        squares = self.sortSquaresByValue(squares)
        # If not an ethical agent, return top selfish choice
        if self.decisionModel == "none":
            return greedyBestSquare

        for square in squares:
            square["value"] = self.findEthicalValueOfSquare(square["square"])
        if self.selfishnessFactor >= 0:
            for square in squares:
                if square["value"] > 0:
                    bestSquare = square["square"]
                    break
        else:
            # Negative utilitarian model uses positive and negative utility to find minimum harm
            squares.sort(key = lambda square: (square["value"]["unhappiness"], square["value"]["happiness"]), reverse = True)
            bestSquare = squares[0]["square"]

        # If additional ordering consideration, select new best square
        if "Top" in self.decisionModel:
            squares = self.sortSquaresByValue(squares)
            bestSquare = squares[0]["square"]

        if bestSquare == None:
            if greedyBestSquare == None:
                bestSquare = squares[0]["square"]
            else:
                bestSquare = greedyBestSquare
            if "all" in self.debug or "agent" in self.debug:
                print(f"Agent {self} could not find an ethical square")
        return bestSquare

    def findSquaresInRange(self):
        squaresInRange = []
        for movement in self.movementPattern:
            deltaX = self.x + movement[0]
            deltaY = self.y + movement[1]
            if deltaX < 0 or deltaY < 0 or deltaX >= len(self.board) or deltaY >= len(self.board[0]):
                continue
            squaresInRange.append((deltaX, deltaY))
        self.squaresInRange = squaresInRange
        return squaresInRange

    def findRetaliatorsInVision(self):
        retaliators = {}
        for square in self.squaresInRange.keys():
            agent = square.agent
            if agent != None:
                agentValue = agent.sugar + agent.spice
                if agent.tribe not in retaliators:
                    retaliators[agent.tribe] = agentValue
                elif retaliators[agent.tribe] < agentValue:
                    retaliators[agent.tribe] = agentValue
        return retaliators

    def gotoSquare(self, square):
        x = square[0]
        y = square[1]
        prey = self.board[x][y]
        if prey != None and self.isValidPrey(prey):
            self.lastDoneCombat = self.chesstopia.timestep
            prey.doDeath("combat")
        self.resetSquare()
        self.square = square
        self.x = x
        self.y = y
        self.chesstopia.board[x][y] = self

    def isAlive(self):
        return self.alive

    def isInGroup(self, group, notInGroup=False):
        membership = False
        if group == self.decisionModel:
            membership = True
        elif group == "depressed":
            membership = self.depressed
        elif "disease" in group:
            diseaseID = re.search(r"disease(?P<ID>\d+)", group).group("ID")
            membership = self.isInfectedWithDisease(diseaseID)
        elif group == "female":
            membership = True if self.sex == "female" else False
        elif group == "male":
            membership = True if self.sex == "male" else False
        elif group == "sick":
            membership = self.isSick()

        if notInGroup == True:
            membership = not membership
        return membership

    def isValidPrey(self, prey):
        if prey == None:
            return False
        elif self.color != prey.color:
            return True
        return False

    def isSquareOccupied(self, square):
        if square == None:
            return False
        x = square[0]
        y = square[1]
        if self.board[x][y] != None:
            return True
        return False

    def moveToBestSquare(self):
        bestSquare = self.findBestSquare()
        if "all" in self.debug or "agent" in self.debug:
            print(f"Agent {self} moving to ({bestSquare.x},{bestSquare.y})")
        print(f"Agent {self} moving from {self.square} to {bestSquare}.")
        self.gotoSquare(bestSquare)

    def printSquareScores(self, squares):
        i = 0
        while i < len(squares):
            square = squares[i]
            squareString = f"({square['square'].x},{square['square'].y}) [{square['value']}]"
            print(f"Square {i + 1}/{len(squares)}: {squareString}")
            i += 1

    def printEthicalSquareScores(self, squares):
        i = 0
        while i < len(squares):
            square = squares[i]
            squareString = f"({square['square'].x},{square['square'].y}) [{square['value']}]"
            print(f"Ethical square {i + 1}/{len(squares)}: {squareString}")
            i += 1

    def rankSquaresInRange(self):
        self.findSquaresInRange()
        if len(self.squaresInRange) == 0:
            return [{"square": self.square, "value": 0}]
        squaresInRange = self.squaresInRange
        random.shuffle(squaresInRange)

        bestSquare = None
        bestValue = 0
        potentialSquares = []

        for square in squaresInRange:
            squareValue = 0
            # Avoid attacking agents ineligible to attack
            prey = self.board[square[0]][square[1]]
            if self.isSquareOccupied(square) and self.isValidPrey(prey) == False:
                continue
            preyColor = prey.color if prey != None else None
            preyValue = prey.value if prey != None else 0

            squareValue += preyValue
            # Select closest square with the most resources
            if squareValue > bestValue:
                bestSquare = square

            squareRecord = {"square": square, "value": squareValue}
            potentialSquares.append(squareRecord)

        if len(potentialSquares) == 0:
            potentialSquares.append({"square": self.square, "value": 0})
        rankedSquares = self.sortSquaresByValue(potentialSquares)
        return rankedSquares

    def resetSquare(self):
        self.board[self.x][self.y] = None
        self.square = None

    def sortSquaresByValue(self, squares):
        # Insertion sort of squares by value in descending order
        i = 0
        while i < len(squares):
            j = i
            while j > 0 and (squares[j - 1]["value"] < squares[j]["value"]):
                currSquare = squares[j]
                squares[j] = squares[j - 1]
                squares[j - 1] = currSquare
                j -= 1
            i += 1
        return squares

    def updateNeighbors(self):
        self.neighbors = [self.board[square[0]][square[1]] for square in self.squaresInRange if self.board[square[0]][square[1]] != None]

    def __str__(self):
        return f"{self.piece}"

class Bishop(Piece):
    def __init__(self, pieceID, birthday, color, square, configuration, chesstopia):
        super().__init__(pieceID, birthday, color, square, configuration, chesstopia)
        self.movementPattern = self.ordinal
        self.piece = "\u265D" if color == "black" else "\u2657"
        self.value = 3

class King(Piece):
    def __init__(self, pieceID, birthday, color, square, configuration, chesstopia):
        super().__init__(pieceID, birthday, color, square, configuration, chesstopia)
        self.movementPattern = self.adjacent
        self.piece = "\u265A" if color == "black" else "\u2654"
        self.value = sys.maxsize

class Knight(Piece):
    def __init__(self, pieceID, birthday, color, square, configuration, chesstopia):
        super().__init__(pieceID, birthday, color, square, configuration, chesstopia)
        self.movementPattern = [(1,2), (-1,2), (1,-2), (-1,-2)]
        self.piece = "\u265E" if color == "black" else "\u2658"
        self.value = 3

class Pawn(Piece):
    def __init__(self, pieceID, birthday, color, square, configuration, chesstopia):
        super().__init__(pieceID, birthday, color, square, configuration, chesstopia)
        self.movementPattern = [(0,-1)] if color == "black" else [(0,1)]
        self.piece = "\u265F" if color == "black" else "\u2659"
        self.value = 1

class Rook(Piece):
    def __init__(self, pieceID, birthday, color, square, configuration, chesstopia):
        super().__init__(pieceID, birthday, color, square, configuration, chesstopia)
        self.movementPattern = self.cardinal
        self.piece = "\u265C" if color == "black" else "\u2656"
        self.value = 5

class Queen(Piece):
    def __init__(self, pieceID, birthday, color, square, configuration, chesstopia):
        super().__init__(pieceID, birthday, color, square, configuration, chesstopia)
        self.movementPattern = self.cardinal + self.ordinal
        self.piece = "\u265B" if color == "black" else "\u2655"
        self.value = 9
