import curses

greetings = ["Welcome to cs164b!","Type 'exit' to exit."]
PROMPTSTR = "cs164b>"

import parser_generator


def tokenize (terminals, inp):
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



#initialize curses
screen = curses.initscr()
curses.noecho()
screen.keypad(1)
curses.curs_set(1)
curses.cbreak()
screen.clear()
screen.leaveok(False)
infoBox = 0

for i in range(len(greetings)):
    screen.addstr(i,0, greetings[i])

curLine = -1+len(greetings)
i = 0
line = ""

def clearBox(box):
    del box
    screen.touchwin()
    screen.refresh()

def updateBox (lineNum, s, scr,box):
    clearBox(box)
    width = screen.getmaxyx()[1]-6
    height = 3
    box = curses.newwin(height,width,lineNum,5)
    box.border(0)
    box.addstr(1,1,s)
    box.touchwin()
    box.refresh()

while line != "exit\n": #processes lines


    curLine += 1
    line = ""
    i = 0

    clearBox(infoBox)
    
    screen.addstr(curLine,0, PROMPTSTR) # print the prompt

    while i != ord('\n'):# processes chars
      
        screen.refresh()
        i = screen.getch() #get next char
        
        if i>=0 and i < 128:
            if (i == 4):
                #exit on EOF (ctrl+d)
                line = "exit\n"
                break
            screen.addch(i)
            line += chr(i) #add to the current buffer
            lineTokens = tokenize(terminals, line)
            
        else:
            if (i==curses.KEY_BACKSPACE): #handle backspace properly
                cursory, cursorx = screen.getyx()
                if (cursorx > len(PROMPTSTR)): #but don't delete the prompt
                    line = line[:-1]
                    screen.delch(cursory,cursorx-1)
                
        updateBox(curLine+1, line, screen, infoBox)
    
    #parse line
    

curses.nocbreak() #de-initialize curses
screen.keypad(0)
curses.echo()
curses.endwin()
