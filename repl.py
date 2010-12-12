#!/usr/bin/env python
import curses, sys, textwrap
import parser_generator, interpreter, grammar_parser

greetings = ["Welcome to cs164b!","To exit, hit <Ctrl-d>."]
PROMPTSTR =   "cs164b> "
CONTINUESTR = "    ... "

#TODO: ;, #, colors

class cs164bRepl:
    def __init__(self):
        #initialize curses
        self.screen = curses.initscr()
        curses.start_color()
        self.init_colors()
        curses.noecho()
        self.screen.keypad(1)
        curses.curs_set(1)
        curses.cbreak()
        self.screen.clear()
        self.screen.leaveok(False)
        self.infoBox = 0

        #print the greeting and adjust the current line accordingly
        for i in range(len(greetings)):
            self.screen.addstr(i,0, greetings[i])
        self.curLineNumber = len(greetings)-1
        cs164grammarFile = './cs164b.grm'
        self.cs164bparser = parser_generator.makeParser(grammar_parser.parse(open(cs164grammarFile).read()))
        self.terminals = self.cs164bparser.terminals
        self.newline = self.cs164bparser.tokenize("\n")
        #self.color_mapping = {}
        self.parser = self.cs164bparser.parse()
        self.parser.next()

    def init_colors(self):
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_WHITE)

    def tokenize (self,inp):
        tokens = []
        pos = 0
        while True:
            matchLHS = 0
            matchText = None
            matchEnd = -1

            for regex, lhs in self.terminals:
                match = regex.match (inp, pos)
                if match and match.end () > matchEnd:
                    matchLHS = lhs
                    matchText = match.group ()
                    matchEnd = match.end ()

            if pos == len (inp):
                if matchLHS:  tokens.append ((matchLHS, matchText))
                break
            elif pos == matchEnd:       # 0-length match
                raise NameError, str(pos) + ": " + str(inp[max(pos-5,0):min(pos+5,len(inp))])
            elif matchLHS is None:      # 'Ignore' tokens
                pass
            elif matchLHS:              # Valid token
                tokens.append ((matchLHS, matchText))
            else:                       # no match
                raise NameError, str(pos) + ": " + str(inp[max(pos-5,0):min(pos+5,len(inp))])

            pos = matchEnd

        return tokens


    def parse_line(self,line):
        try:
            tokens = self.cs164bparser.tokenize(line)
            if tokens:                              # no need to consume non-code lines
                input_ast = self.parser.send(tokens)     # parse this line
                if type(input_ast) == tuple:        # parsing completed on this line; execute result
                    interpreter.ExecGlobalStmt(input_ast,self)

                    # create and prep a new parser instance
                    self.parser = self.cs164bparser.parse()
                    self.parser.next()

        # soft failure - if there's an error, print a helpful message and create a new parser
        except NameError, e:
            self.printLine("Error while tokenizing line: " + line)
            self.printLine(e.msg)
            self.parser = self.cs164bparser.parse()
            self.parser.next()
        except SyntaxError, e:
            self.printLine("Error while parsing line: " + line)
            self.printLine(e.msg)
            self.parser = self.cs164bparser.parse()
            self.parser.next()

    def printLine(self,s):
        self.clearBox(self.infoBox)
        self.curLineNumber += 1
        self.screen.addstr(self.curLineNumber, 0, s) # print the prompt

    def updateCurrentLine(self, s):
        width = self.screen.getmaxyx()[1] - 6
        padding = width - len(PROMPTSTR)
        self.screen.addstr(self.curLineNumber, len(PROMPTSTR), s + padding * ' ')
        self.screen.move(self.curLineNumber, len(PROMPTSTR) + len(s))

    #helper function to clear the info box
    def clearBox(self,box):
        del box
        self.screen.touchwin()
        self.screen.refresh()

    # update the info box.
    #	lineNum: line number that the box should appear on
    #	s: string to display in the box
    #	scr: the current curses window object
    #	box: the box's curses window object
    def updateBox(self, lineNum, s, scr, box):
        self.clearBox(box)
        width = self.screen.getmaxyx()[1] - 6
        s = textwrap.wrap(s, width - 4)
        height = 2 + len(s)
        box = curses.newwin(height,width,lineNum,5)
        box.border(0)
        for line in xrange(1, len(s)+1):
            box.addstr(line, 1, s[line-1])
        box.touchwin()
        box.refresh()

    def showSuggestions(self, suggestions):
        if suggestions:
            width = self.screen.getmaxyx()[1] - 6
            sugList = []
            for k,v in suggestions.iteritems():
                # pretty representation of functions - add others as needed
                if isinstance(v, interpreter.FunVal):
                    suggestions[k] = "function(" + (reduce(lambda x,y: x+","+y, v.fun.argList) if v.fun.argList else "") + ")"

                # string representation of a single entry
                sugList.append(str(k) + ": " + str(suggestions[k]))
            suggestions = reduce(lambda x,y: x + "\t\t\t" + y, sorted(sugList))
            self.updateBox(self.curLineNumber+1, suggestions, self.screen, self.infoBox)
        else:
            self.updateBox(self.curLineNumber+1, "", self.screen, self.infoBox)
            self.clearBox(self.infoBox)

    def gracefulExit(self):
        curses.nocbreak() #de-initialize curses
        self.screen.keypad(0)
        curses.echo()
        curses.endwin()
        sys.exit(0)

    def softError(self,s):
        self.printLine("Error: " + s)

    def main(self):
        i = 0
        line = ""

        history = [""]
        hist_ptr = 0

        #HERE BEGINS THE REPL
        #processes each line until we see "ctrl-d"
        while line != "exit\n":

            self.curLineNumber += 1
            self.clearBox(self.infoBox)
            if not self.cs164bparser.parsedepth:
                self.screen.addstr(self.curLineNumber, 0, PROMPTSTR) # print the prompt
            else:
                self.screen.addstr(self.curLineNumber, 0, CONTINUESTR) # print the secondary prompt

            # handle indenting appropriately
            line = "" + self.cs164bparser.parsedepth * "   "
            self.updateCurrentLine(line)
            i = 0

            # processes each character on this line
            while i != ord('\n') and i != ord(';'):

                self.screen.refresh()
                i = self.screen.getch() #get next char
                suggestions = {}

                if i >= 32 and i < 127:                         # printable characters
                    self.screen.addch(i)
                    line += chr(i)                              # add to the current buffer
                    hist_ptr = 0
                    history[hist_ptr] = line                    # and save the line so far
                    try:
                        lineTokens = self.cs164bparser.tokenize(line)
                        if lineTokens:
                            suggestions = dict(interpreter.complete(lineTokens[-1]))
                    except NameError, e:
                        lineTokens = []                         #TODO color line red

                elif i == ord('\n') or i == ord(';'):           # EOL characters
                    self.screen.addch(i)
                    line += chr(i) #add to the current buffer

                elif (i == 127 or i == curses.KEY_BACKSPACE):   # handle backspace properly, plus a hack for mac
                    cursory, cursorx = self.screen.getyx()
                    if (cursorx > len(PROMPTSTR)):              # but don't delete the prompt
                        line = line[:-1]
                        try:
                            lineTokens = self.cs164bparser.tokenize(line)
                            if lineTokens:
                                suggestions = dict(interpreter.complete(lineTokens[-1]))
                        except NameError, e:
                            lineTokens = []                     # TODO color line red
                        self.screen.delch(cursory,cursorx-1)

                elif i == curses.KEY_UP:
                    if hist_ptr < len(history) - 1:
                        if hist_ptr == 0:
                            history[hist_ptr] = line            # save the line so far, if it's new
                        hist_ptr = hist_ptr + 1                 # go back in time WHHOOOOOHHHO
                        line = history[hist_ptr]
                        self.updateCurrentLine(line)

                elif i == curses.KEY_DOWN:
                    if hist_ptr > 0:                            # if we can go forward, do so
                        hist_ptr = hist_ptr - 1
                        line = history[hist_ptr]
                        self.updateCurrentLine(line)

                elif i == 9:                                    # horizontal tab
                    1   # do some tab-related stuff here, maybe?

                elif (i == 4):                                  # exit on EOF (ctrl+d)
                    self.gracefulExit()

                self.showSuggestions(suggestions)

            self.parse_line(line[:-1])
            hist_ptr = 0
            history.insert(hist_ptr, line[:-1])


if __name__ == "__main__":
    repl = cs164bRepl()
    repl.main()
