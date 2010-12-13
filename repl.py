#!/usr/bin/env python
import curses, sys, textwrap
import parser_generator, interpreter, grammar_parser

greetings = ["Welcome to cs164b!","To exit, hit <Ctrl-d>."]
PROMPTSTR =   "cs164b> "
CONTINUESTR = "    ... "

#TODO: ;, #, colors

class cs164bRepl:
    def __init__(self):
        #initialize parser
        cs164grammarFile = './cs164b.grm'
        self.cs164bparser = parser_generator.makeParser(grammar_parser.parse(open(cs164grammarFile).read()))

        # collect token information for later
        self.terminals = self.cs164bparser.terminals
        self.id_tkn = self.cs164bparser.tokenize('a')
        self.dot_tkn = self.cs164bparser.tokenize('.')
        self.comma_tkn = self.cs164bparser.tokenize(',')
        self.open_tkn = self.cs164bparser.tokenize('(')
        self.close_tkn = self.cs164bparser.tokenize(')')

        # initialize a parser for future use
        self.parser = self.cs164bparser.parse()
        self.parser.next()
        self.colorMap = {}

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
        
        #tab-complete specific vars
        self.inTab = False
        self.currentSuggestions = []
        self.suggestionsIndex = 0
        self.suggestedLine = ""
        self.fragmentIndex = 0

        #print the greeting and adjust the current line accordingly
        for i in range(len(greetings)):
            self.screen.addstr(i,0, greetings[i])
        self.curLineNumber = len(greetings)-1


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
            self.printLine("Error while tokenizing line: " + line, 1)
            self.printLine(str(e), 1)
            self.parser = self.cs164bparser.parse()
            self.parser.next()
        except SyntaxError, e:
            self.printLine("Error while parsing line: " + line, 1)
            self.printLine(e.msg)
            self.parser = self.cs164bparser.parse()
            self.parser.next()

    def printLine(self,s,code=0, attr = curses.A_NORMAL):
        self.clearBox(self.infoBox)
        self.curLineNumber += 1
        self.screen.addstr(self.curLineNumber, 0, s,curses.color_pair(code) | attr) # print the prompt

    def init_colors(self):
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK) #errors
        curses.init_pair(2, curses.COLOR_MAGENTA, curses.COLOR_BLACK) #keywords
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_MAGENTA, curses.COLOR_WHITE)
        curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)

        operators = ["&&", "||", "<=", ">=", "==", "!=", "=", ",", \
                         ";","+","*","/","-","(",")","[","]","{","}"]
        keywords = ["def", "in", "for", "null", "error","lambda", "print", \
                     "if", "while", "in", "null","len", "native", \
                      "ite", "coroutine", "resume", "yield"]
        quotedStrings = ["\"a string\""]
        categories = [(operators, 2, curses.A_BOLD), (keywords, 3, curses.A_NORMAL), (quotedStrings, 5, curses.A_NORMAL)]

        #populate colorMap
        for category, colorNumber, attr in categories:
            for token in category:
                tokenCode = self.cs164bparser.tokenize(token)[0][0]
                self.colorMap[tokenCode] = (colorNumber, attr)

    def updateCurrentLine(self, s, tab=False, stringCompletion=False):
    
        width = self.screen.getmaxyx()[1] - 6
        padding = width - len(PROMPTSTR)
        
        
        #acquire suggestions
        suggestions = {}
        try:
            lineTokens = self.cs164bparser.tokenize(s)
            if lineTokens:
                suggestions = dict(interpreter.complete(lineTokens[-1]))
        except NameError, e:
            #if not stringCompletion: #try tacking a quote on there, see if it fixes things
            #    return self.updateCurrentLine(s+"\"",tab,True) #set tab=False?
            lineTokens = []                         #TODO color line red, turn off suggestions
            
            self.screen.addstr(self.curLineNumber, len(PROMPTSTR), s, curses.color_pair(1))
            self.screen.addstr(self.curLineNumber, len(s)+len(PROMPTSTR), padding * ' ')
            self.clearBox(self.infoBox)
            self.screen.move(self.curLineNumber, len(s)+len(PROMPTSTR))
            return
            
            
        if tab: #TODO: optimize and clean up
        #BUG: autocompletes to first fork, stays there! this is a problem
            if not self.inTab:
                #if we are just entering the autocomplete, save this and the iterator
                self.currentSuggestions = []
                self.suggestionsIndex = -1
                for k,v in suggestions.iteritems():
                    self.currentSuggestions.append(k)
                self.inTab = True
                #copy current line
                #self.lineFragment = s
                #save index into token
                self.fragmentIndex = len(lineTokens[-1][1])
            self.suggestionsIndex = (self.suggestionsIndex+1)%len(self.currentSuggestions) #shift to the next item
            selectedSuggestion = self.currentSuggestions[self.suggestionsIndex]
            s = s + selectedSuggestion[self.fragmentIndex:]
            self.suggestedLine = s
            #retokenize to account for the new item
            try:
                lineTokens = self.cs164bparser.tokenize(s)
            except NameError, e:
                lineTokens = []
                self.screen.addstr(self.curLineNumber, len(PROMPTSTR), s, curses.color_pair(1))
                self.screen.addstr(self.curLineNumber, len(s)+len(PROMPTSTR), padding * ' ')
                self.clearBox(self.infoBox)
                self.screen.move(self.curLineNumber, len(s)+len(PROMPTSTR))
                return                         
        
        if (s and s[-1].isspace()):
                suggestions = {}
        
        #generate color/string/attr triples, store into stringColorPairs
        stringColorPairs = []
        for code, string in lineTokens:
            color, attr = self.colorMap.get(code,(0, curses.A_NORMAL))
            stringColorPairs.append((string, color, attr))

        x_pos = len(PROMPTSTR)
        str_index = 0

        #loop that prints each token in different colors
        for string, colorNumber, attr in stringColorPairs:
            #print remaining part of string in neutral color first
            self.screen.addstr(self.curLineNumber, x_pos, s[str_index:s.find(string, str_index)], curses.color_pair(0))
            x_pos += s.find(string, str_index) - str_index
            str_index = s.find(string, str_index)
            self.screen.addstr(self.curLineNumber, x_pos, string, curses.color_pair(colorNumber) | attr) #bold/underline?
            x_pos += len(string)
            str_index += len(string)

        #print rest of string if we're not done
        if (str_index != len(s)):
            self.screen.addstr(self.curLineNumber, x_pos, s[str_index:], curses.color_pair(0))

        x_pos = len(PROMPTSTR) + len(s)
        self.screen.addstr(self.curLineNumber, x_pos, padding * ' ')
        self.showSuggestions(self.getSuggestions(lineTokens))
        self.screen.move(self.curLineNumber, x_pos) #move cursor to end of line

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

    def getSuggestions(self, tokens):

        def findFunctionalUnit(tokens):
            if not tokens:                                              # can't fill the hole in your heart, I mean, code
                return None

            fragment = tokens[-1][1]                                    # the text to complete
            env = interpreter.globEnv                                   # env to look in
            inparens = []                                               # call stack

            # iterate through the line to guess type of fragment
            for i in xrange(len(tokens) - 2):
                if tokens[i+1][0] == self.dot_tkn[0]:
                    env = interpreter.locateInEnv(tokens[i][1], env)    # go one object in
                    if type(env) != dict:
                        return None                                     # no such variable, or not an object
                elif tokens[i+1][0] == self.open_tkn[0]:                # make sure this is actually a function
                    if isinstance(interpreter.locateInEnv(tokens[i], env), interpreter.FunVal):
                        inparens.append(tokens[i][1])                   # if so, add it to the stack
                        env = interpreter.globEnv
                    else:
                        return None                                     # otherwise, fail
                elif tokens[i][0]  == self.open_tkn[0]:                 # generic parentheses
                    inparens.append('(')
                    env = interpreter.globEnv
                elif tokens[i][0] == self.close_tkn[0]:                 # pop out of the current paren stack
                    inparens.pop()
                else:
                    env = interpreter.globEnv                           # out of this object, back to global environment

            # Now attempt to determine the type of the fragment, and what is needed to get its completions
            if env is interpreter.globEnv:                              # not in an object
                if inparens and inparens[-1] != '(':                    # in a function call
                    return ('fun', inparens[-1], fragment, env)
                else:                                                   # just plain parentheses
                    return ('none', fragment)
            else:
                return ('obj', env, fragment)

        fragType = findFunctionalUnit(tokens)
        if not fragType:
            return None
        elif fragType[0] == 'none':
            return dict(interpreter.complete(fragType[1]))
        elif fragType[0] == 'obj':
            return dict(interpreter.completeObj(fragType[2], fragType[1]))
        elif fragType[0] == 'fun':
            funVal = fragType[3][fragType[1]]
            argList = funVal.fun.argList
            return (fragType[1], argList, dict(interpreter.complete(fragType[2])))  # (function name, arguments, tab completions)

    def showSuggestions(self, suggestions):
        if suggestions:
            output = ""                             # the string that goes in the box
            width = self.screen.getmaxyx()[1] - 6
            sugList = []

            # special case for functions: print the function definition first
            if type(suggestions) == tuple:
                output = suggestions[0] + "(" + (reduce(lambda x,y: x+","+y, suggestions[1]) if suggestions[1] else "") + ")\n"
                suggestions = suggestions[2]

            for k,v in suggestions.iteritems():
                # pretty representation of functions - add others as needed
                if isinstance(v, interpreter.FunVal):
                    suggestions[k] = "function(" + (reduce(lambda x,y: x+","+y, v.fun.argList) if v.fun.argList else "") + ")"

                # string representation of a single entry
                if suggestions[k]:
                    sugList.append(str(k) + ": " + str(suggestions[k]))
                else:
                    sugList.append(str(k))

            output = output + reduce(lambda x,y: x + "\t\t\t" + y, sorted(sugList))
            self.updateBox(self.curLineNumber+1, output, self.screen, self.infoBox)
        else:
            self.updateBox(self.curLineNumber+1, "", self.screen, self.infoBox)
            self.clearBox(self.infoBox)

    def gracefulExit(self, msg=None, ret=0):
        curses.nocbreak() #de-initialize curses
        self.screen.keypad(0)
        curses.echo()
        curses.endwin()
        if msg:
            print msg
        sys.exit(ret)

    def softError(self,s):
        self.printLine("Error: " + s,1,curses.A_BOLD)

    def main(self):
        i = 0
        line = ""

        history = [""]
        hist_ptr = 0

        #HERE BEGINS THE REPL
        #processes each line until we see "ctrl-d"
        while True:

            self.curLineNumber += 1
            self.clearBox(self.infoBox)
            if not self.cs164bparser.parsedepth:
                self.screen.addstr(self.curLineNumber, 0, PROMPTSTR) # print the prompt
            else:
                self.screen.addstr(self.curLineNumber, 0, CONTINUESTR) # print the secondary prompt

            # handle indenting appropriately
            line = "" + self.cs164bparser.parsedepth * '\t'
            self.updateCurrentLine(line)
            i = 0

            # processes each character on this line
            while i != ord('\n') and i != ord(';'):

                self.screen.refresh()
                try:
                    i = self.screen.getch() #get next char
                except KeyboardInterrupt:
                    i = ord('\n')
                    
                if self.inTab and i != 9:
                    self.inTab = False
                    line = self.suggestedLine
                suggestions = {}

                if i >= 32 and i < 127:                         # printable characters
                    #self.screen.addch(i)
                    line += chr(i)                              # add to the current buffer
                    hist_ptr = 0
                    history[hist_ptr] = line                    # and save the line so far
                    try:
                        lineTokens = self.cs164bparser.tokenize(line)
                        if lineTokens:
                            suggestions = dict(interpreter.complete(lineTokens[-1]))
                    except NameError, e:
                        lineTokens = [] #TODO: tokenize lines

                elif i == ord('\n') or i == ord(';'):           # EOL characters
                    self.screen.addch(i)
                    line += chr(i) #add to the current buffer

                elif (i == 127 or i == curses.KEY_BACKSPACE):   # handle backspace properly, plus a hack for mac
                    cursory, cursorx = self.screen.getyx()
                    if (cursorx > len(PROMPTSTR)):              # but don't delete the prompt
                        line = line[:-1]

                elif i == curses.KEY_UP:
                    if hist_ptr < len(history) - 1:
                        if hist_ptr == 0:
                            history[hist_ptr] = line            # save the line so far, if it's new
                        hist_ptr = hist_ptr + 1                 # go back in time WHHOOOOOHHHO
                        line = history[hist_ptr]

                elif i == curses.KEY_DOWN:
                    if hist_ptr > 0:                            # if we can go forward, do so
                        hist_ptr = hist_ptr - 1
                        line = history[hist_ptr]

                elif i == 9:                                    # horizontal tab
                    if line[-1].isspace() or line == "":
                        line += '\t'
                    else:
                    1   # do some tab-related stuff here, maybe?

                elif (i == 4):                                  # exit on EOF (ctrl+d)
                    self.gracefulExit()

                self.updateCurrentLine(line, tab)
                
                #uncomment to show tokens instead of suggestions
                #self.updateBox(self.curLineNumber+1, str(lineTokens), self.screen, self.infoBox) 

            self.parse_line(line[:-1])
            hist_ptr = 0
            history.insert(hist_ptr, line[:-1])

if __name__ == "__main__":
    repl = cs164bRepl()
    repl.main()
