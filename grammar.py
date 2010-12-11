##
 # @file grammar.py
 #
 # $Id: grammar.py,v 1.7 2007/04/02 20:46:57 cgjones Exp $
import re, types
from sys import stdout

class Production:
    '''
    LHS is the LHS symbol (redundancy beware: this symbol is also stored in the Rule)

    RHS is an array of symbols; e.g., ["E", "+", "E"].

    ACTIONS is the set of actions associated with this production.  It
    is an array of texts of functions to execute either before
    evaluating a symbol (I-actions) or after evaluating all
    symbols in the RHS (S-action).  Each action corresponds to a
    symbol from RHS, and the final action is the optional
    S-action.  Each action can be None.

    PREC is the precedence of this production among all the ones for
    this rule.

    ASSOC is a terminal symbol whose precedence should be used
    in this rule, overriding that of any other terminals with
    associativity declarations.

    RHSACTIONS is a list of (Symbol, Action) pairs.  Each Action
    will executed before its Symbol is evaluated.  The Actions can
    pass inherited attributes down the tree, allowing the use of
    L-attributed SDTs.

    opPrec:
    opAssoc:
    ''' 
    def __init__ (self, lhs, rhs, actions, prec, assoc):
        '''Create a new production'''
        self.LHS = lhs
        self.RHS = rhs
        self.actions = actions
        self.prec = prec
        self.assoc = assoc

        self.opPrec = None
        self.opAssoc = None
        self.info = None


    def toString (self,invRenamedTerminals):
        '''Print a representation of the production in the form
        LHS -> RHS.  Token regexes are reintroduced using invRenamedTerminals.
        See Earley.preprocess for more information on this map.
        '''
        return self.LHS+" -> "+" ".join([invRenamedTerminals.get(sym,sym) for sym in self.RHS])

class Rule:
    '''A mapping from Symbol -> [RHSs].

    Also keeps track of associativity declarations for each
    production, and the precedences of ambiguous production (if any).
    '''

    def __init__ (self, symbol):
        '''Create a new rule for SYMBOL.'''
        self.lhs = symbol
        self.productions = []

    def __repr__ (self): return str (self)

    def __str__ (self):
        return '<grammar.Rule lhs="%s" ...>' % (self.lhs)


    def dump (self, file=stdout, i=0):
        '''Print a pretty version of this rule to FILE at indent level I'''

        REGEX = re.compile ('a')        # so we simulate isinstance()

        print >>file, (i*' ')+'(Rule %s'% (self.lhs)
        i += 4
        for prod in self.productions:
            print >>file, (i*' ')+'(production [',

            for sym in prod.RHS:
                if sym == Grammar.EPSILON:
                    print >>file, '(epsilon),',
                elif type (sym) == type (REGEX):
                    print >>file, '%s,'% (sym.pattern),
                else:
                    print >>file, '%s,'% (sym),
            print >>file, ']'

            if prod.prec >= 0:
                print >>file, ((i+4)*' ')+'(precedence %d)'% (prod.prec)
            if prod.assoc:
                print >>file, ((i+4)*' ')+'(assoc %s)'% (prod.assoc.pattern)
            if prod.actions:
                print >>file, ((i+4)*' ')+'(action {%s})'% (prod.actions[-1])
            if prod.opPrec >= 0:
                print >>file, ((i+4)*' ')+'(operator precedence %d)'% (prod.opPrec)
            if prod.opAssoc:
                print >>file, ((i+4)*' ')+'(operator assoc %s)'% (prod.opAssoc)
            if prod.info:
                print >>file, ((i+4)*' ')+'(info %s)'% (str(prod.info))
            print >>file, (i*' ')+ ')'

        i -= 4
        print >>file, (i*' ')+')'


    def addProduction (self, rhs, actions=None, prec=-1, assoc=None):
        '''Add a production self.lhs -> RHS, with an optional precedence,
        semantic action, and associativity override.
        '''

        # CYK TODO: make sure changing Production from a dict to an object
        # did not break the cyk parser.

        # (old) CYK code
        # self.productions.append (
        #    { 'rhs': tuple(rhs), 'actions': actions, 'prec': prec,
        #      'assoc': assoc,})

        self.productions.append(Production(
                self.lhs, tuple(rhs),
                actions, prec, assoc))

##-----------------------------------------------------------------------------

class Grammar:
    '''The data structure representing an abstract grammar.'''

    EPSILON = '_',

    LEFT_ASSOCIATIVE = 'left',
    RIGHT_ASSOCIATIVE = 'right',

    def __init__ (self):
		'''Create a new Grammar.'''
		self.rules = []                 # list of Rules
		self.startSymbol = ''           # the start symbol of this grammar
		self.imports = []               # modules to be imported
		self.ignores = []               # terminals to be ignored
		self.optionals = []             # "optional" terminal symbols

		self.__opAssocDecls = []        # operator associativity declarations
		self.__currOpPrec = 0           # the current operator precedence

		self.__symbol2rule = {}		# map symbols to their Rule

    def __repr__ (self): return str (self)

    def __str__ (self):
        return '<grammar.Grammar startSymbol="%s" ...>'% (self.startSymbol)


    def dump (self, file=stdout):
        '''Print a pretty version of this grammar to FILE'''
        print >>file, '(Grammar'

        print >>file, (4*' ')+'(Declarations'
        for mod in self.imports:
            print >>file, (8*' ')+'(import %s)'% (mod)
        for (op, prec, assoc) in self.__opAssocDecls:
            print >>file, (8*' ')+'(assoc %s %d %s)'% (op.pattern, prec, assoc)
        print >>file, (4*' ')+')'

        print >>file, (4*' ')+'(Rules'
        for rule in self.rules:
            rule.dump (file, 8)
        print >>file, (4*' ')+')'

        print >>file, (4*' ')+'(StartSymbol %s)'% (self.startSymbol)

        print >>file, ')'


    def setStartSymbol (self, startSymbol):
        '''Set the start symbol of this grammar.'''
        self.startSymbol = startSymbol


    def declareImport (self, module):
        '''Declare that MODULE should be imported by this grammar.'''
        self.imports.append (module)


    def declareIgnore (self, regex):
        '''Declare that REGEX should be ignored while tokenizing.'''
        self.ignores.append (regex)


    def declareOptional (self, sym, regex):
        '''Declare that if REGEX is matched in the input, it should receive
        a self-edge with symbol SYM.'''
        self.optionals.append ((sym, regex))


    def declareOperatorAssocs (self, operators, assoc):
        '''Declare the associativity of the sequence OPERATORS to be ASSOC.

        Also sets the precedence of these operators; the last set of
        operators passed to declareAssociativities() will have highest
        precedence, and so on.
        '''
        for op in operators:
            self.__opAssocDecls.append ((op, self.__currOpPrec, assoc))
        self.__currOpPrec += 1


    def addRule (self, rule):
        '''Add RULE to the set of rules for this grammar.'''
        self.rules.append (rule)
        self.__symbol2rule[rule.lhs] = rule

    def getAssocDecls (self):
        '''Fetch the operators with associativity declarations.  Returns
        the list [(operator, precedence, associativity)]
        '''
        return self.__opAssocDecls

    def __getitem__(self, symbol):
	'''Return the rule for the nonterminal symbol, or None if symbol is not defined'''
        return self.__symbol2rule[symbol]

    def validate (self):
        '''Run semantic checks against this grammar and its
        constituent rules.  Returns the tuple (valid?, message).

        "valid?" is True if the grammar is valid, False otherwise.

        "message" is a description of the semantic validations, and is
        only interesting when valid? is False.
        '''
        lhss = {}
        # Seed LHSes with optional symbols
        for sym, regex in self.optionals:
            lhss[sym] = True

        # Check property 1: no multiple definitions
        for rule in self.rules:
            if lhss.get (rule.lhs, None):
                return (False, 'nonterminal %s multiply defined'%(rule.lhs))
            else:
                lhss[rule.lhs] = True

        # Check property 2: no undefined symbols
        for rule in self.rules:
            for prod in rule.productions:
                for sym in prod.RHS:
                    if (isinstance (sym, types.StringType)
                        and not lhss.get (sym, None)
                        and (sym is not Grammar.EPSILON)):
                        return (False, 'symbol "%s" not defined'% (sym))

        return (True, 'valid')

##-----------------------------------------------------------------------------

def main ():
    pass

if __name__ == '__main__':
    main ()
