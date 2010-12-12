import curses

greetings = ["Welcome to cs164b!","To exit, type 'exit' or hit <Ctrl-d>."]
PROMPTSTR = "cs164b>"

#TODO: ;, #

import parser_generator, interpreter, grammar_parser

cs164grammarFile = './cs164b.grm'
cs164parser = parser_generator.makeParser(grammar_parser.parse(open(cs164grammarFile).read()))

terminals = cs164parser.terminals
newline = cs164parser.tokenize("\n")
# initialize a parser instance, i.e., a coroutine, and prep it


color_mapping = {}

def init_colors():
	curses.init_pair(1, curses.COLOR_RED, curses.COLOR_WHITE)

def tokenize (inp):
    '''Return the tokenized version of INP, a sequence of
    (token, lexeme) pairs.
    '''
    tokens = []
    pos = 0

    while True:
        matchLHS = 0
        matchText = None
        matchEnd = -1

        for regex, lhs in terminals:
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


def parse_line(line):
    parser = cs164parser.parse()
    parser.next()
    try:
        tokens = cs164parser.tokenize(line)
        if tokens:                              # no need to consume non-code lines
            input_ast = parser.send(tokens)     # parse this line
            if type(input_ast) == tuple:        # parsing completed on this line; execute result
                interpreter.ExecGlobalStmt(input_ast)

                # create and prep a new parser instance
                parser = cs164parser.parse()
                parser.next()

    # soft failure - if there's an error, print a helpful message and create a new parser
    except SyntaxError, e:
        print "Error while parsing line: " + line
        print e.msg
        parser = cs164parser.parse()
        parser.next()


#initialize curses
screen = curses.initscr()
curses.start_color()
#COLORS = curses.has_colors()
init_colors()
curses.noecho()
screen.keypad(1)
curses.curs_set(1)
curses.cbreak()
screen.clear()
screen.leaveok(False)
infoBox = 0
i = 0
line = ""

#print the greeting and adjust the current line accordingly
for i in range(len(greetings)): 
    screen.addstr(i,0, greetings[i])
curLine = len(greetings)-1

#helper function to clear the info box
def clearBox(box):
    del box
    screen.touchwin()
    screen.refresh()
    
#update the info box.
#	lineNum: line number that the box should appear on
#	s: string to display in the box
#	scr: the current curses window object
#	box: the box's curses window object

def updateBox (lineNum, s, scr,box):
    clearBox(box)
    width = screen.getmaxyx()[1]-6
    height = 3
    box = curses.newwin(height,width,lineNum,5)
    box.border(0)
    box.addstr(1,1,s)
    box.touchwin()
    box.refresh()

#HERE BEGINS THE REPL
#processes each line until we see "exit"
while line != "exit\n": 

    curLine += 1
    line = ""
    i = 0
    clearBox(infoBox)    
    screen.addstr(curLine,0, PROMPTSTR) # print the prompt

	# processes each character on this line
    while i != ord('\n') and i != ord(';'):
      
        screen.refresh()
        i = screen.getch() #get next char
        
        if i>=0 and i < 128:
            if (i == 4): #exit on EOF (ctrl+d)
                line = "exit\n"
                break
            screen.addch(i)
            line += chr(i) #add to the current buffer
            lineTokens = tokenize(line)
            
        else:
            if (i==curses.KEY_BACKSPACE): #handle backspace properly
                cursory, cursorx = screen.getyx()
                if (cursorx > len(PROMPTSTR)): #but don't delete the prompt
                    line = line[:-1]
                    screen.delch(cursory,cursorx-1)
                
        updateBox(curLine+1, str(lineTokens), screen, infoBox)
#        updateBox(curLine+1, line, screen, infoBox)
    
    parse_line(line[:-1])
    
curses.nocbreak() #de-initialize curses
screen.keypad(0)
curses.echo()
curses.endwin()
