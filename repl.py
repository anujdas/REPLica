#!/usr/bin/env python
import curses, sys, textwrap, re, os
import parser_generator, interpreter, grammar_parser

cs164b_builtins = ["def", "error", "print", "if", "while", "for", "in", "null", "len", "lambda", "type", "native", "ite", "coroutine", "resume", "yield", "&&", "||", "<=", ">=", "==", "!="]
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
        self.screen.scrollok(True)
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
        self.cursorx = 0

    # quick macro for loading in a file, based on the line-by-line parser model.
    def loadProgram(self, p_file):
        #message to return
        message = ""

        # save state
        history = self.history[:]
        lineNumber = self.curLineNumber

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
                        interpreter.ExecGlobalStmt(input_ast, self)
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
            except KeyboardInterrupt:
                message = "Execution terminated by user while loading file: " + p_file
                success = False
                break
            except Exception:
                success = False
                break

        # restore history
        self.history = history
        self.curLineNumber = lineNumber
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
                    interpreter.ExecGlobalStmt(input_ast, self)
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
        except KeyboardInterrupt:
            self.printLine("Execution terminated by user while exceuting line: " + line, 1, curses.A_BOLD)
            self.parser = self.cs164bparser.parse()
            self.parser.next()
            complete = True                         # mark the start of a new statement

        return complete

    def printLine(self,s,code=0, attr = curses.A_NORMAL):
        self.clearBox(self.infoBox)
        self.curLineNumber += 1
        if self.curLineNumber > self.screen.getmaxyx()[0] - 5:
            self.screen.scroll(5)
            self.curLineNumber -= 5
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
            # special case for functions: print the function definition
            if type(suggestions) == tuple:
                suggestions = {suggestions[0] + "(" + (reduce(lambda x,y: x+", "+y, suggestions[1]) if suggestions[1] else "") + ")" : None}
            else:
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


    # get tab-completion results for a given string fragment
    def complete(self, fragment, env):
        lookups = map(lambda k: (k, env[k]), filter(lambda name: name.startswith(fragment), env))
        builtins = map(lambda k: (k, None), filter(lambda name: name.startswith(fragment), cs164b_builtins))
        return filter(lambda s: not s[0].startswith('__'), lookups + builtins)

    # same as above, except for dictionary/object lookups
    # go by Lua standard: __mt/__index for lookups
    def completeObj(self, fragment, obj):
        # recursively collect all attributes belonging to this function and its parent classes
        supers = self.completeObj(fragment, obj['__mt']) if '__mt' in obj and obj['__mt'] else []
        return supers + self.complete(fragment, env=obj)

    # check if the variable exists anywhere accessible from this environment
    # if so, return its value, else None
    def locateInEnv(self, var, env):
        if not env:
            return None
        elif var in env:
            return env[var]
        elif '__up__' in env:
            return self.locateInEnv(var, env['__up__'])
        elif '__mt' in env:
            return self.locateInEnv(var, env['__mt'])
        else:
            return None

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
                    env = self.locateInEnv(tokens[i][1], env)           # go one object in
                    i += 1                                              # and skip over the dot
                    if type(env) != dict:
                        return None                                     # no such variable, or not an object
                elif tokens[i+1][0] == self.open_tkn[0]:                # make sure this is actually a function
                    if isinstance(self.locateInEnv(tokens[i][1], env), interpreter.FunVal):
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
            return dict(self.complete(fragType[1], interpreter.globEnv))
        elif fragType[0] == 'obj':
            return dict(self.completeObj(fragType[2], fragType[1]))
        elif fragType[0] == 'fun':
            funVal = self.locateInEnv(fragType[1], fragType[3])
            argList = funVal.fun.argList
            return (fragType[1], argList, dict(self.complete(fragType[2], interpreter.globEnv)))  # (function name, arguments, tab completions)

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
                f.write('\n')
                f.close()
                menu.addstr(2,0,"Saved. Press any key.")
            except IOError, e:
                menu.addstr(2,0,"Saving to %s failed!" % fileName, curses.color_pair(1) | curses.A_BOLD)
            menu.getch()

        elif(c == ord('3')):
            self.gracefulExit()

        else:
            menu = curses.newwin(y,x,0,0)
            menu.addstr(1,0,"Not a valid option. Press any key to continue.")
            menu.getch()

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
            if self.curLineNumber > self.screen.getmaxyx()[0] - 5:
                self.screen.scroll(5)
                self.curLineNumber -= 5
            self.clearBox(self.infoBox)
            if not self.cs164bparser.parsedepth:
                self.screen.addstr(self.curLineNumber, 0, PROMPTSTR) # print the prompt
            else:
                self.screen.addstr(self.curLineNumber, 0, CONTINUESTR) # print the secondary prompt

            # handle indenting appropriately
            line = "" + self.cs164bparser.parsedepth * '\t'
            self.updateCurrentLine(line)
            lineTokens = []

            self.cursorx = len(line)

            history.insert(hist_ptr, line)

            # processes each character on this line
            i = 0
            while i != ord('\n'):

                tab = False
                interruptFlag = False
                self.screen.refresh()
                self.screen.move(self.curLineNumber, self.cursorx + len(PROMPTSTR))
                try:
                    i = self.screen.getch() #get next char
                except KeyboardInterrupt:
                    interruptFlag = True
                    i = ord('\n')

                if self.inTab and i != 9:
                    self.inTab = False
                    line = self.suggestedLine
                    self.cursorx = len(line)

                if i >= 32 and i < 127:                         # printable characters
                    line = strInsert(line, chr(i), self.cursorx)
                    self.cursorx += 1
                    hist_ptr = 0
                    history[hist_ptr] = line                    # and save the line so far
                    try:
                        lineTokens = self.cs164bparser.tokenize(line)
                    except NameError, e:
                        lineTokens = []

                elif i == ord('\n'):                            # EOL characters
                    self.screen.addch(i)
                    line += chr(i)                              # add to the current buffer
                    self.cursorx = 0

                elif (i == 127 or i == curses.KEY_BACKSPACE):   # handle backspace properly, plus a hack for mac
                    if self.cursorx > 0:                        # but don't delete the prompt
                        line = strRemove(line, self.cursorx-1)
                        self.cursorx -= 1

                elif i == curses.KEY_UP:
                    if hist_ptr < len(history) - 1:
                        if hist_ptr == 0:
                            history[hist_ptr] = line            # save the line so far, if it's new
                        hist_ptr = hist_ptr + 1                 # go back in time WHHOOOOOHHHO
                        line = history[hist_ptr]
                        self.cursorx = len(line)

                elif i == curses.KEY_DOWN:
                    if hist_ptr > 0:                            # if we can go forward, do so
                        hist_ptr = hist_ptr - 1
                        line = history[hist_ptr]
                        self.cursorx = len(line)

                elif i == curses.KEY_LEFT:                      # cursor movement: move until start of line
                    if self.cursorx > 0:
                        self.cursorx -= 1

                elif i == curses.KEY_RIGHT:                     # more cursor movement
                    if self.cursorx < len(line):
                        self.cursorx += 1

                elif i == 1:                                    # ^A goes to the start of the line
                    self.cursorx = 0

                elif i == 5:                                    # ^E goes to the end of the line
                    self.cursorx = len(line)

                elif i == 11:                                   # ^K kills the line from here to the end
                    line = line[:self.cursorx]

                elif i == 12:                                   # ^L clears the screen except for the current line
                    self.screen.scroll(self.curLineNumber)
                    self.curLineNumber = 0

                elif i == 21:                                   # ^U kills the line from here to the beginning
                    line = line[self.cursorx:]
                    self.cursorx = 0

                elif i == 23:                                   # ^W removes the previous word, up to a space
                    pos = line.rfind(' ', 0, self.cursorx)      # locate the space position
                    if pos != -1:
                        line = line[:pos] + line[self.cursorx:] # if it's there, strip out the word
                        self.cursorx = pos                      # and update cursor pos
                    else:
                        line = ""                               # otherwise, there's only one word - cut the whole thing
                        self.cursorx = 0

                elif i == 9:                                    # horizontal tab
                    if line == "" or line[-1].isspace() or self.cursorx != len(line):
                        line = strInsert(line, '\t', self.cursorx)
                        self.cursorx += 1
                    else:
                        suggestions = self.getSuggestions(lineTokens)
                        if (type(suggestions) == dict and suggestions) or (type(suggestions) == tuple and suggestions[2]):
                            tab = True
                        else:
                            line = strInsert(line, '\t', self.cursorx)
                            self.cursorx += 1

                elif i == curses.KEY_F2: #F2
                    self.menu()

                elif (i == 4):                                  # exit on EOF (ctrl+d)
                    self.gracefulExit()

                # refresh the display
                self.updateCurrentLine(line, tab, interruptFlag=interruptFlag)

                # the suggestions box is useless if we're not where we're supposed to be
                if self.cursorx != len(line):
                    self.clearBox(self.infoBox)

                # cancel the line-to-be on ^C
                if interruptFlag:
                    break
            if not interruptFlag and len(lineTokens) > 0 and len(line) > 1:
                lines = line.split(';')
                lines = [l + '\n' for l in lines[:-1]] + [lines[len(lines) - 1]]
                for l in lines:
                    if not first_line:
                        to_parse = '\n' + l[:-1]
                    else:
                        to_parse = l[:-1]
                        first_line = False
                    if self.parse_line(to_parse):                   # do an incremental parse
                        first_line = True                           # check if a statement was completed
                    if self.exec_fail:
                        break
                hist_ptr = 0
                history[hist_ptr] =  line[:-1]

            elif interruptFlag:
                self.parser = self.cs164bparser.parse()
                self.parser.next()
                first_line = True
                hist_ptr = 0

# because python strings are annoyingly immutable
def strInsert(original, new, pos):
    # inserts new inside original at pos
    return original[:pos] + new + original[pos:]

# same deal as above, remove char at pos
# no arg validation, let lists take care of that
def strRemove(original, pos):
    return original[:pos] + original[pos+1:]

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
