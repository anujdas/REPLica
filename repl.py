#!/usr/bin/env python
import curses, sys, textwrap, re, os
import parser_generator, interpreter, grammar_parser

greetings = ["Welcome to cs164b!","To exit, hit <Ctrl-d>.","Press F2 to see the menu."]
PROMPTSTR =   "cs164b> "
CONTINUESTR = "    ... "

class cs164bRepl:
    def __init__(self):
        #initialize parser
        cs164grammarFile = './cs164b.grm'
        self.cs164bparser = parser_generator.makeParser(grammar_parser.parse(open(cs164grammarFile).read()))

        # vars for file saving
        self.history = []           # history of succesfully executed lines
        self.currLine = ""          # and the current line, which may yet succeed
        self.exec_fail = False      # otherwise, how would we know if it succeeded?

        # collect token information for later
        self.terminals = self.cs164bparser.terminals
        self.id_tkn = self.cs164bparser.tokenize('a')[0]
        self.dot_tkn = self.cs164bparser.tokenize('.')[0]
        self.colon_tkn = self.cs164bparser.tokenize(':')[0]
        self.comma_tkn = self.cs164bparser.tokenize(',')[0]
        self.open_tkn = self.cs164bparser.tokenize('(')[0]
        self.close_tkn = self.cs164bparser.tokenize(')')[0]

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

    # quick macro for loading in a file, based on the line-by-line parser model.
    # TODO: change this to fast-fail; if a file has an error, we want to know immediately
    # and parsing the rest of the file is a waste.
    # I'll change this after the current version is merged into the REPL.
    def loadProgram(self, p_file):
        #message to return
        message = ""

        # save the history
        history = self.history[:]

        # grab the token for a newline so we know how to pad our lines
        newline = self.cs164bparser.tokenize("\n")

        # load in the program file
        try:
            prog = re.findall('[^\r\n;]+', re.sub("#.*\r?\n", "", open(p_file).read()))
        except IOError, e:
            message = "Error opening file!"
            return (False, message)

        # initialize a parser instance, i.e., a coroutine, and prep it
        parser = self.cs164bparser.parse()
        parser.next()

        # no newline insert before the first line of a statement
        first_line = True
        success = True
        for l in prog:
            try:
                tokens = self.cs164bparser.tokenize(l)
                if tokens:                              # no need to consume non-code lines
                    if not first_line:                  # separate lines w/ newline characters
                        tokens = newline + tokens
                    input_ast = parser.send(tokens)     # parse this line
                    first_line = False
                    if type(input_ast) == tuple:        # parsing completed on this line; execute result
                        self.exec_fail = False
                        interpreter.ExecGlobalStmt(input_ast)
                        if self.exec_fail:
                            raise Exception

                        # create and prep a new parser instance
                        parser = self.cs164bparser.parse()
                        parser.next()
                        first_line = True

            # soft failure - if there's an error, print a helpful message and create a new parser
            except SyntaxError, e:
                message = "Error while parsing line: " + l + "\n" + e.msg
                success = False
                break
            except Exception:
                success = False
                break

        # restore history
        self.history = history
        return (success, message)

    def parse_line(self, line):
        complete = False                            # a flag set each time a statement is completed
        try:
            tokens = self.cs164bparser.tokenize(line)
            if tokens:                              # no need to consume non-code lines
                input_ast = self.parser.send(tokens)     # parse this line
                self.currLine = self.currLine + line
                if type(input_ast) == tuple:        # parsing completed on this line; execute result
                    self.exec_fail = False
                    interpreter.ExecGlobalStmt(input_ast,self)
                    if not self.exec_fail:
                        self.history.append(self.currLine + '\n')
                    self.currLine = ""

                    # create and prep a new parser instance
                    self.parser = self.cs164bparser.parse()
                    self.parser.next()

                    complete = True                 # mark the start of a new statement

        # soft failure - if there's an error, print a helpful message and create a new parser
        except NameError, e:
            self.printLine("Error while tokenizing line: " + line, 1, curses.A_BOLD)
            self.printLine(str(e), 1)
            self.parser = self.cs164bparser.parse()
            self.parser.next()
            complete = True                         # mark the start of a new statement
        except SyntaxError, e:
            self.printLine("Error while parsing line: " + line, 1, curses.A_BOLD)
            self.printLine(e.msg)
            self.parser = self.cs164bparser.parse()
            self.parser.next()
            complete = True                         # mark the start of a new statement

        return complete

    def printLine(self,s,code=0, attr = curses.A_NORMAL):
        self.clearBox(self.infoBox)
        self.curLineNumber += 1
        self.screen.addstr(self.curLineNumber, 0, s,curses.color_pair(code) | attr) # print the prompt

    def init_colors(self):
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK) #errors
        curses.init_pair(2, curses.COLOR_MAGENTA, curses.COLOR_BLACK) #keywords
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE) #comments

        operators = ["&&", "||", "<=", ">=", "==", "!=", "=", ",", \
                         ";","+","*","/","-","(",")","[","]","{","}"]
        keywords = ["def", "in", "for", "null", "error","lambda", "print", \
                     "if", "while", "in", "null","len", "native", \
                      "ite", "coroutine", "resume", "yield"]
        quotedStrings = ["\"a string\""]
        number = ["5"]
        categories = [(operators, 2, curses.A_BOLD), (keywords, 3, curses.A_NORMAL), (quotedStrings, 5, curses.A_NORMAL), (number, 4,curses.A_NORMAL)]

        #populate colorMap
        for category, colorNumber, attr in categories:
            for token in category:
                tokenCode = self.cs164bparser.tokenize(token)[0][0]
                self.colorMap[tokenCode] = (colorNumber, attr)

    def updateCurrentLine(self, s, tab=False, stringCompletion=False, interruptFlag=False):

        width = self.screen.getmaxyx()[1] - 6
        padding = width - len(PROMPTSTR)

        # separate out any comments before doing anything else
        comment = ""
        comment_pos = s.find('#')
        if comment_pos >= 0:
            s, comment = s[:comment_pos], s[comment_pos:]

        # disregard tokens, acquire suggestions
        suggestions = {}
        try:
            if interruptFlag:
                raise NameError
            lineTokens = self.cs164bparser.tokenize(s)
            if lineTokens:
                suggestions = self.getSuggestions(lineTokens)
        except NameError, e:
            lineTokens = []

            self.screen.addstr(self.curLineNumber, len(PROMPTSTR), s, curses.color_pair(1))
            self.screen.addstr(self.curLineNumber, len(s)+len(PROMPTSTR), padding * ' ')
            self.clearBox(self.infoBox)
            self.screen.move(self.curLineNumber, len(s)+len(PROMPTSTR))
            return

        if tab:
            if not self.inTab:
                #if we are just entering the autocomplete, save this and the iterator
                self.currentSuggestions = []
                self.suggestionsIndex = -1
                if type(suggestions) == tuple:          # special case for fn. completions
                    suggestions = suggestions[2]
                for k,v in suggestions.iteritems():
                    self.currentSuggestions.append(k)
                self.inTab = True
                #save index into token
                self.fragmentIndex = len(lineTokens[-1][1])

            self.suggestionsIndex = (self.suggestionsIndex+1) % len(self.currentSuggestions) #shift to the next item
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

        # print any comments, if they're there
        self.screen.addstr(self.curLineNumber, x_pos, comment, curses.color_pair(6))
        x_pos += len(comment)

        self.screen.addstr(self.curLineNumber, x_pos, padding * ' ')
        self.showSuggestions(suggestions)
        self.screen.move(self.curLineNumber, x_pos) #move cursor to end of line

    #helper function to clear the info box
    def clearBox(self,box):
        del box
        self.screen.touchwin()
        self.screen.refresh()

    # update the info box.
    #   lineNum: line number that the box should appear on
    #   s: string to display in the box
    #   scr: the current curses window object
    #   box: the box's curses window object
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
            i = 0
            while i < len(tokens) - 1:
                if tokens[i+1][0] in (self.dot_tkn[0], self.colon_tkn[0]):
                    env = interpreter.locateInEnv(tokens[i][1], env)    # go one object in
                    i += 1                                              # and skip over the dot
                    if type(env) != dict:
                        return None                                     # no such variable, or not an object
                elif tokens[i+1][0] == self.open_tkn[0]:                # make sure this is actually a function
                    if isinstance(interpreter.locateInEnv(tokens[i][1], env), interpreter.FunVal):
                        inparens.append((tokens[i][1], env))            # if so, add it to the stack, along with its env
                        env = interpreter.globEnv
                        i += 1
                elif tokens[i][0]  == self.open_tkn[0]:                 # generic parentheses
                    inparens.append('(')
                    env = interpreter.globEnv
                elif tokens[i][0] == self.close_tkn[0] and inparens:    # pop out of the current paren stack, if one exists
                        inparens.pop()
                else:
                    env = interpreter.globEnv                           # out of this object, back to global environment
                i += 1

            if tokens[-1][0] == self.close_tkn[0] and inparens:         # clean up trailing parens
                inparens.pop()
            elif tokens[-1][0] == self.open_tkn[0]:
                inparens.append('(')

            # Now attempt to determine the type of the fragment, and what is needed to get its completions
            if env is interpreter.globEnv:                              # not in an object
                if inparens and type(inparens[-1]) == tuple:            # in a function call
                    return ('fun', inparens[-1][0], fragment, inparens[-1][1])
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
            funVal = interpreter.locateInEnv(fragType[1], fragType[3])
            argList = funVal.fun.argList
            return (fragType[1], argList, dict(interpreter.complete(fragType[2])))  # (function name, arguments, tab completions)

    def showSuggestions(self, suggestions):

        # special print method for dictionaries, since nested dicts (objects) are ugly as hell
        def dictStr(d):
            def getObjAttrs(obj):
                supers = getObjAttrs(obj['__mt']) if '__mt' in obj and obj['__mt'] else []
                return supers + [(k,obj[k]) for k in obj if not k.startswith('__')]

            contents = sorted(["." + str(k) + ": " + ("{...}" if type(v) is dict else str(v)) for k,v in dict(getObjAttrs(d)).iteritems()])
            return "{" + (reduce(lambda x,y: x + ", " + y, contents) if contents else "") + "}"

        output = ""                             # the string that goes in the box
        width = self.screen.getmaxyx()[1] - 6
        sugList = []

        # special case for functions: print the function definition first
        if type(suggestions) == tuple:
            output = suggestions[0] + "(" + (reduce(lambda x,y: x+", "+y, suggestions[1]) if suggestions[1] else "") + ")"
            output += (width - len(output)) * ' '
            suggestions = suggestions[2]

        if suggestions:
            for k,v in suggestions.iteritems():
                # string representation of a single entry
                if suggestions[k]:
                    sugList.append(str(k) + ": " + (dictStr(suggestions[k]) if type(suggestions[k]) is dict else str(suggestions[k])))
                else:
                    sugList.append(str(k))
            output = output + reduce(lambda x,y: x + "\t\t\t" + y, sorted(sugList))
            self.updateBox(self.curLineNumber+1, output, self.screen, self.infoBox)
        elif output == "":
            self.updateBox(self.curLineNumber+1, "", self.screen, self.infoBox)
            self.clearBox(self.infoBox)
        else:
            self.updateBox(self.curLineNumber+1, output, self.screen, self.infoBox)

    def gracefulExit(self, msg=None, ret=0):
        curses.nocbreak() #de-initialize curses
        self.screen.keypad(0)
        curses.echo()
        curses.endwin()
        if msg:
            print msg
        sys.exit(ret)

    def softError(self, s):
        self.printLine("Error: " + s, 1, curses.A_BOLD)
        self.exec_fail = True

    def menu(self):
        y,x = self.screen.getmaxyx()
        menu = curses.newwin(y,x,0,0)
        menu.addstr(1,0,"1 - Load a file")
        menu.addstr(2,0,"2 - Save to a file")
        menu.addstr(3,0,"3 - Exit")
        menu.touchwin()
        menu.refresh()
        c = menu.getch()
        del menu
        curses.echo()

        if (c == ord('1')):
            menu = curses.newwin(y,x,0,0)
            menu.addstr(1,0,"Enter file name to load: ")

            #save for later
            oS = self.screen
            self.screen = menu
            s = [x for x in os.listdir('.') if x.endswith('.164')]
            if s:
                s = "Available files: "+reduce(lambda x,y: x + "\t\t\t" + y, sorted(s))
            else:
                s = "No 164 files here"
            self.updateBox(3, s,self.screen, self.infoBox)

            menu.move(1, len("Enter file name to load: "))
            fileName = menu.getstr()
            #do stuff with fileName
            suc, msg = self.loadProgram(fileName)
            if suc:
                menu.addstr(2,0,"Loaded. Press any key.")
            else:
                menu.addstr(3,0,"Loading %s failed!" % fileName, curses.color_pair(1) | curses.A_BOLD)
                menu.addstr(2,0,msg,curses.color_pair(1) | curses.A_BOLD)
            menu.getch()

            self.screen = oS

        elif(c == ord('2')):
            menu = curses.newwin(y,x,0,0)
            menu.addstr(1,0,"Enter file name to save: ")
            menu.move(1, len("Enter file name to save: "))
            fileName = menu.getstr()
            #do stuff with fileName
            try:
                f = open(fileName, 'w')
                f.writelines(self.history)
                f.close()
                menu.addstr(2,0,"Saved. Press any key.")
            except IOError, e:
                menu.addstr(2,0,"Saving to %s failed!" % fileName)
            menu.getch()

        elif(c == ord('3')):
            self.gracefulExit()

        curses.noecho()
        del menu
        self.screen.touchwin()
        self.screen.refresh()

    def main(self):
        i = 0
        line = ""
        first_line = True

        history = []
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

            history.insert(hist_ptr, line)
            i = 0

            # processes each character on this line
            while i != ord('\n') and i != ord(';'):

                tab = False
                interruptFlag = False
                self.screen.refresh()
                try:
                    i = self.screen.getch() #get next char
                except KeyboardInterrupt:
                    interruptFlag = True
                    i = ord('\n')

                if self.inTab and i != 9:
                    self.inTab = False
                    line = self.suggestedLine

                if i >= 32 and i < 127:                         # printable characters
                    line += chr(i)                              # add to the current buffer
                    hist_ptr = 0
                    history[hist_ptr] = line                    # and save the line so far
                    try:
                        lineTokens = self.cs164bparser.tokenize(line)
                    except NameError, e:
                        lineTokens = []

                elif i == ord('\n') or i == ord(';'):           # EOL characters
                    self.screen.addch(i)
                    line += chr(i)                              #add to the current buffer

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
                    if line == "" or line[-1].isspace():
                        line += '\t'
                    else:
                        suggestions = self.getSuggestions(lineTokens)
                        if (type(suggestions) == dict and suggestions) or (type(suggestions) == tuple and suggestions[2]):
                            tab = True
                        else:
                            line += '\t'

                elif i == curses.KEY_F2: #F2
                    self.menu()

                elif (i == 4):                                  # exit on EOF (ctrl+d)
                    self.gracefulExit()

                # refresh the display
                self.updateCurrentLine(line, tab, interruptFlag=interruptFlag)
            if not interruptFlag and len(lineTokens) > 0 and len(line) > 1:
                if not first_line:
                    to_parse = '\n' + line[:-1]
                else:
                    to_parse = line[:-1]
                    first_line = False
                if self.parse_line(to_parse):                   # do an incremental parse
                    first_line = True                           # check if a statement was completed

            hist_ptr = 0
            history[hist_ptr] =  line[:-1]

if __name__ == "__main__":
    repl = cs164bRepl()

    # load any libraries if specified
    if len(sys.argv) > 1:
        repl.printLine("---------")
        for fileName in sys.argv[1:]:
            (success, msg) = repl.loadProgram(fileName)
            if success:
                repl.printLine("Successfully loaded %s into the global environment." % fileName)
            else:
                repl.printLine("Failed to load %s!" % fileName)
                repl.printLine(msg)
        repl.printLine("---------")

    # and then initialize the main loop
    repl.main()
