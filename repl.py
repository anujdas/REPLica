import curses

greetings = ["Welcome to cs164b!","To exit, hit <Ctrl-d>."]
PROMPTSTR = "cs164b>"

#TODO: ;, #, colors

import sys, parser_generator, interpreter, grammar_parser

class cs164bRepl:
    def __init__(self):
        cs164grammarFile = './cs164b.grm'
        self.parser = parser_generator.makeParser(grammar_parser.parse(open(cs164grammarFile).read()))
        self.terminals = self.parser.terminals
        self.newline = self.parser.tokenize("\n")
        #self.color_mapping = {}

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
                raise Exception, pos
            elif matchLHS is None:      # 'Ignore' tokens
                pass
            elif matchLHS:              # Valid token
                tokens.append ((matchLHS, matchText))
            else:                       # no match
                raise Exception, str(pos) + ": " + str(inp[max(pos-15,0):min(pos+15,len(inp))])

            pos = matchEnd

        return tokens


    def parse_line(self,line):
        parser = self.parser.parse()
        parser.next()
        try:
            tokens = self.parser.tokenize(line)
            if tokens:                              # no need to consume non-code lines
                input_ast = parser.send(tokens)     # parse this line
                if type(input_ast) == tuple:        # parsing completed on this line; execute result
                    interpreter.ExecGlobalStmt(input_ast)

                    # create and prep a new parser instance
                    parser = self.parser.parse()
                    parser.next()

        # soft failure - if there's an error, print a helpful message and create a new parser
        except SyntaxError, e:
            print "Error while parsing line: " + line
            print e.msg
            parser = self.parser.parse()
            parser.next()




    #helper function to clear the info box
    def clearBox(self,box):
        del box
        self.screen.touchwin()
        self.screen.refresh()

    #update the info box.
    #	lineNum: line number that the box should appear on
    #	s: string to display in the box
    #	scr: the current curses window object
    #	box: the box's curses window object

    def updateBox (self, lineNum, s, scr,box):
        self.clearBox(box)
        width = self.screen.getmaxyx()[1]-6
        height = 3
        box = curses.newwin(height,width,lineNum,5)
        box.border(0)
        box.addstr(1,1,s)
        box.touchwin()
        box.refresh()
        
    def gracefulExit(self):
        curses.nocbreak() #de-initialize curses
        self.screen.keypad(0)
        curses.echo()
        curses.endwin()
        sys.exit(0)

    def main(self):
        #initialize curses
        self.screen = curses.initscr()
        curses.start_color()
        #COLORS = curses.has_colors()
        self.init_colors()
        curses.noecho()
        self.screen.keypad(1)
        curses.curs_set(1)
        curses.cbreak()
        self.screen.clear()
        self.screen.leaveok(False)
        infoBox = 0
        i = 0
        line = ""

        #print the greeting and adjust the current line accordingly
        for i in range(len(greetings)):
            self.screen.addstr(i,0, greetings[i])
        curLine = len(greetings)-1
        #HERE BEGINS THE REPL
        #processes each line until we see "exit"
        while line != "exit\n":

            curLine += 1
            line = ""
            i = 0
            self.clearBox(infoBox)
            self.screen.addstr(curLine,0, PROMPTSTR) # print the prompt

            # processes each character on this line
            while i != ord('\n') and i != ord(';'):

                self.screen.refresh()
                i = self.screen.getch() #get next char

                if i>=0 and i < 128:
                    if (i == 4): #exit on EOF (ctrl+d)
                        self.gracefulExit()
                    self.screen.addch(i)
                    line += chr(i) #add to the current buffer
                    lineTokens = self.tokenize(line)

                else:
                    if (i==curses.KEY_BACKSPACE): #handle backspace properly
                        cursory, cursorx = self.screen.getyx()
                        if (cursorx > len(PROMPTSTR)): #but don't delete the prompt
                            line = line[:-1]
                            self.screen.delch(cursory,cursorx-1)

                self.updateBox(curLine+1, str(lineTokens), self.screen, infoBox)
#               updateBox(curLine+1, line, self.screen, infoBox)

            self.parse_line(line[:-1])


if __name__ == "__main__":
    repl = cs164bRepl()
    repl.main()
