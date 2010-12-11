##
 # @file grammar_parser.py
 #
 # $Id: grammar_parser.py,v 1.7 2007/04/16 06:54:11 cgjones Exp $
import grammar, re, sys, types

##-----------------------------------------------------------------------------
## Simple tokenizer
##
class Tokenizer:
    '''A very simple stream tokenizer.'''

    def __init__ (self, input, whitespace='[ ]', comments='#'):
        '''Create a new Tokenizer on INPUT.  Optionally accepts regexes
        for WHITESPACE and COMMENTS to be ignored.'''
        self.input = input
        self.__pos = 0
        self.whitespace = re.compile (whitespace, re.VERBOSE)
        self.comments = re.compile (comments, re.VERBOSE)


    def checkpoint (self):
        '''Make a checkpoint of the current scanning state.'''
        return self.__pos


    def restore (self, checkpoint):
        '''Restore a checkpoint made by the checkpoint() method.'''
        self.__pos = checkpoint


    def token (self, regex):
        '''Try to match REGEX against the input at the current position,
        ignoring whitespace and comments.
        Returns the part of the input that matches, or None if there is
        no match.
        
        REGEX can be either a String or compiled regular expression.
        
        If there is a match, updates the current position within
        the input string.
        '''
        # Skip whitespace and comments
        while (self.__matchToken (self.whitespace)
               or self.__matchToken (self.comments)):
            pass

        # Return the match of REGEX
        if isinstance (regex, types.StringType):
            return self.__matchToken (re.compile (regex, re.VERBOSE))
        else:
            return self.__matchToken (regex)


    def __matchToken (self, regex):
        '''Try to match the compiled regular expression REGEX against
        the input at the current position.  Returns the part of the
        input that matches, or None if there is no match.

        If there is a match, updates the current position within
        the input string.
        '''
        match = regex.match (self.input, self.__pos)
        if not match:  return

        matchedText = match.group ()
        self.__pos += len (matchedText)
        return matchedText


##-----------------------------------------------------------------------------
## The Grammar Parser API
##
def parseFile (filename):
    '''Construct a new Grammar from the specification in FILENAME.'''
    return parse (open (filename).read (), filename)


def parse (spec, filename='stdin'):
    '''Construct a new Grammar from the specification SPEC.'''

    def error (msg):
        '''Prints MSG to stderr and exits with a non-zero error code.'''
        print >>sys.stderr, 'Error: %s'% (msg)
        sys.exit (1)

    def checkpoint ():
        '''Create a parser checkpoint.'''
        return (lexer.checkpoint (), len (stack))

    def restore (checkpoint):
        '''Restore a parser checkpoint.'''
        lexer.restore (checkpoint[0])
        stack.__setslice__(0, len (stack), stack[0:checkpoint[1]])
        return True


    lexer = Tokenizer (spec, r'[ \n\r\t\v\f]+', r'//[^\n\r]*?(?:[\n\r]|$)')
    stack = []                          # semantic stack
    g = grammar.Grammar ()              # the grammar to build

    def G ():
        while Declaration ():
            pass
        
        if not lexer.token ('%%'):
            error ('"%%" must separate declarations from rules')

        if not R ():
            error ('must have at least one rule')
        rule = stack.pop ()
        g.setStartSymbol (rule.lhs)
        g.addRule (rule)
        while R ():
            rule = stack.pop ()
            g.addRule (rule)

        return lexer.token ('$') != None

    def Declaration ():
        if AssocDecl ():     pass
        elif ImportDecl ():  pass
        elif IgnoreDecl ():  pass
        elif OptDecl():      pass
        else:                return False
        return True

    def AssocDecl ():
        if lexer.token ('%right'):   assoc = grammar.Grammar.RIGHT_ASSOCIATIVE
        elif lexer.token ('%left'):  assoc = grammar.Grammar.LEFT_ASSOCIATIVE
        else:                        return False

        if not Terminal ():
            error ('"associativity" decls require at least one operator')

        ops = [stack.pop ()]
        while Terminal ():
            ops.append (stack.pop ())

        g.declareOperatorAssocs (ops, assoc)
        return True

    def ImportDecl ():
        if not lexer.token ('%import'):  return False

        if not PyModuleName ():
            error ('"import" decls require a module name')

        module = stack.pop ()
        g.declareImport (module)
        return True

    def IgnoreDecl ():
        if not lexer.token ('%ignore'): return False

        if not Terminal ():
            error ('"ignore" decls require a terminal symbol')

        term = stack.pop ()
        g.declareIgnore (term)
        return True

    def OptDecl ():
        if not lexer.token ('%optional'): return False

        if not (Nonterminal () and Terminal ()):
            error ('invalid %optional decl')

        regex = stack.pop ()
        lhs = stack.pop ()
        g.declareOptional (lhs, regex)
        return True

    def R ():
        if not Nonterminal ():
            return False

        if not lexer.token (r'\->'):
            error ('rules LHSs must be followed by "->"')

        rule = grammar.Rule (stack.pop ())
        if not Production ():
            error ('rule "{0}" has no productions'.format(rule.lhs))
        (rhs, actions, prec, assoc) = stack.pop ()
        rule.addProduction (rhs=rhs, actions=actions, prec=prec, assoc=assoc)

        while lexer.token (r'\|'):
            if not Production ():
                error ('(%s) "|" must be followed by a production'% (rule.lhs))
            (rhs, actions, prec, assoc) = stack.pop ()
            rule.addProduction (rhs=rhs, actions=actions, prec=prec,
                                assoc=assoc)

        if not lexer.token (';'):
            error ('(%s) rules must be ended by ";"'% (rule.lhs))

        stack.append (rule)
        return True

    def Production ():
        if not (EmptyProd () or NonEmptyProd ()):
            return False
        (rhs, prec, assoc, actions) = stack.pop ()
        
        action = None
        if Action ():
            action = stack.pop ()
        actions.append (action)
        stack.append ((rhs, actions, prec, assoc))
        return True

    def EmptyProd ():
        if not Epsilon ():
            return False
        stack.append (([stack.pop ()], -1, None, [None]))
        return True

    def NonEmptyProd ():
        if not ActionSymbol ():
            return False
        sym, action = stack.pop ()
        rhs = [sym]
        actions = [action]
        prec = -1
        assoc = None
        while ActionSymbol ():
            sym, action = stack.pop ()
            rhs.append (sym)
            actions.append (action)
        if PrecDecl ():
            prec = stack.pop ()
        elif TempAssocDecl ():
            assoc = stack.pop ()
        stack.append ((rhs, prec, assoc, actions))
        return True

    def ActionSymbol ():
        cp = checkpoint ()
        action = None

        if Action ():
            action = stack.pop ()
        if not Symbol ():
            restore (cp)
            return False

        stack.append ((stack.pop (), action))
        return True

    def PrecDecl ():
        if not lexer.token ('%dprec'):
            return False
        if not Number ():
            error ('"dprec" decls require a numeric precedence')
        return True

    def TempAssocDecl ():
        if not lexer.token ('%prec'):
            return False
        if not Terminal ():
            error ('"prec" decls require a nonterminal')
        return True

    def Symbol ():
        return Terminal () or Nonterminal ()

    def Terminal ():
        return String () or Regex ()

    def Nonterminal ():
        match = lexer.token (r'[a-zA-Z][a-zA-Z0-9_]*')
        if not match:
            return False
        stack.append (match)
        return True

    def String ():
        match = lexer.token (r'\'.*?\'')
        if not match:
            return False
        stack.append (re.compile (re.escape (match[1:-1])))
        return True

    def Regex ():
        match = lexer.token (r'/ (?: \\\\ | \\/ | [^/])* /')
        if not match:
            return False
        try:
            stack.append (re.compile (match[1:-1]))
        except:
            error ('invalid regular expression')
        return True

    def Epsilon ():
        if not lexer.token ('_'):
            return False
        stack.append (grammar.Grammar.EPSILON)
        return True

    def PyModuleName ():
        match = lexer.token (
            r'[a-zA-Z_][a-zA-Z0-9_]* (?: \. [a-zA-Z_][a-zA-Z0-9_]*)*')
        if not match:
            return False
        stack.append (match)
        return True

    def Action ():
        match = lexer.token (r'%\{ (?: . | [\n\r])*? %\}')
        if not match:
            return False
        stack.append (match[2:-2])
        return True

    def Number ():
        match = lexer.token (r'[0-9]+')
        if not match:
            return False
        try:
            stack.append (int (match))
        except:
            error ('number too large')
        return True

    # And finally, build and return a Grammar
    if not G ():  error ('invalid grammar')
    return g

##-----------------------------------------------------------------------------

import sys

def main (argv):
    testGrammar = r'''
%%
S -> %{ i-action %} A B %{ s-s-action %} ;
A -> _ ;
B -> _ ;
C -> A ;
D -> %{ d-i-action %} E ;
E -> D %{ e-s-action %} ;
''' 
    G = parse (testGrammar)
    print 'Parsed grammar!'
    G.dump ()
    (valid, msg) = G.validate ()
    if not valid:
        print '... but the grammar is invalid: %s'% (msg)
    else:
        print '... and the grammar is valid!'

if __name__ == '__main__':
    main (sys.argv)
