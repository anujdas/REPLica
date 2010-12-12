##
# @file parser_generator.py
#
# $Id: parser_generator.py,v 1.7 2007/04/16 06:54:11 cgjones Exp $
import grammar, grammar_parser, re, sys, types, util, string, pprint, os.path
from collections import defaultdict

##-----------------------------------------------------------------------------
## Module interface
##

def makeRecognizer (gram, type='earley'):
    '''Construct and return a "recognizer" of GRAM.

    A recognizer is an object with a method recognize(inp), returning
    True if INP is a valid string in GRAM, and False otherwise.
    '''
    class Recognizer:
        def __init__ (self, parser):
            self.parser = parser

        def dump (self, f=sys.stdout):
            self.parser.dump (f)

        def recognize (self, inp):
            if self.parser.recognize(inp):
                return True
            return False

    return Recognizer (makeParser (gram, type))


def makeParser (gram, type='earley'):
    '''Construct and return a parser of GRAM.

    A parser is an object with a method parse(inp), returning the AST
    constructed from the parse tree of INP by the semantic actions in GRAM.
    '''
    if type == 'earley':
        return EarleyParser (gram)
    else:
        raise TypeError, 'Unknown parser type specified'

##-----------------------------------------------------------------------------

class saObject(): #synthesized attribute object
    def __init__ (self, action=None, children=None, val=None):
        self.action = action
        self.children = children
        self.val = val
    def act(self):
        if not self.children: #this is a terminal, so it has no children to recurse over
            return self
        return saObject(val = self.action(*tuple([self]+[child.act() for child in self.children])))
## Earley Parser
##
class EarleyParser:
    '''A parser implementing the Earley algorithm.'''

    def __init__ (self, gram):
        '''Create a new Earley parser.'''
        self.grammar = gram
        self.terminals, self.invRenamedTerminals = EarleyParser.preprocess (gram)
        self.ambiguous = False      # status vars for each run of the parser
        self.resolved = True        # more status
        self.subparser = None

        self.debug = False
        self.drawGraph = False

    def parse(self):
        # The graph is partioned by (destination,completenessStatus) of edges.
        # The graph is thus a dictionary with the key (dst,complete).
        # Each key maps to a pair consisting of a list of edges as well as a set of edges.
        # Both the list and the set keep the same set of edges.  We use both so that we can modify
        # the set of edges while iterating over it.  While a list data structure can be modified
        # during iteration, it cannot be tested for membership as fast as the set.
        # Hence we use it together with a set. 
        # See the pattern below for illustration of how we use the set and list in tandem.

        # defaultdict is like a dictionary that provides a default value when key is not present
        graph = defaultdict(lambda: ([],set()))
        childrenOfEdges = {}        # edge -> (child, subEdge())

        # status of edge is either complete or inProgress
        complete = 0
        inProgress = 1

        # edge picked by disambiguation
        NEW = 1
        OLD = 2

        ########################
        ### HELPER FUNCTIONS ###
        ########################

        # return (list,set) of edges 
        def edgesIncomingTo(dst,status):
            key = (dst,status)
            return graph[key]

        # wrap the old children in a lambda to prevent excess copying, then add to children
        def appendChild(newEdge, oldEdge, newChild, status):
            if self.debug:
                if len(newEdge) == 4:
                    if newChild and len(newChild) == 4:
                        print "Appending child to ", (newEdge[0], newEdge[1], newEdge[2].RHS, newEdge[3]), ":", (newChild[0], newChild[1], newChild[2].RHS, newChild[3])
                    else:
                        print "Appending child to ", (newEdge[0], newEdge[1], newEdge[2].RHS, newEdge[3]), ":", newChild
                else:
                    print "Appending child to ", newEdge, ":", newChild
            childrenOfEdges[(newEdge, status)] = (newChild, oldEdge)

        def getChildren(e, status=complete):
            children = []
            moreChildren = childrenOfEdges.get((e, status))
            while moreChildren:
                if moreChildren[0]:
                    children.insert(0, moreChildren[0])
                moreChildren = childrenOfEdges.get((moreChildren[1], inProgress))
            return children

        def addEdge(e, oldEdge=None, childEdge=None):
            """Add edge to graph and worklist if not present in graph already.
            Return True iff the edge was actually inserted
            """
            incr(0)
            # edge to key
            src, dst, P, pos = e
            status = complete if len(P.RHS) == pos else inProgress
            (edgeList,edgeSet) = edgesIncomingTo(dst,status)
            toRemove = None
            changed = True
            if status == complete:      # if this is a completed edge..
                for edge in edgeSet:    # with the same src/dst, and that hasn't been removed before
                    if edge[0] == src and edge[2].LHS == P.LHS:

                        (choice, ambiguous, resolved) = disambiguate(e, edge, oldEdge, childEdge)

                        self.ambiguous = self.ambiguous or ambiguous
                        self.resolved = self.resolved and resolved

                        if choice == OLD:     # keep the old edge
                            e = edge
                            changed = False
                        else:               # use the new edge
                            toRemove = edge

                        if self.debug:
                            print " Resolved." if resolved else " Unresolved!!!", "picked", "new" if choice == 1 else "old", "edge.", "(AMBIGUOUS)" if ambiguous else ""

            if toRemove:
                if self.debug:
                    print "Removing edge:", (toRemove[0], toRemove[1], toRemove[2].LHS, toRemove[2].RHS, toRemove[3])
                edgeList.remove(toRemove)
                edgeSet.remove(toRemove)
            if e not in edgeSet:
                edgeList.append(e)
                edgeSet.add(e)
                if changed:
                    appendChild(e, oldEdge, childEdge, status)
                return True
            return False

        # return (edge, ambiguous?, resolved?), where edge is either e1 or e2, others are boolean
        def disambiguate(e1, e2, oldE1, childE1):

            # parse out any information about operators, etc.
            opPrec1,assoc1,dprec1,subsym1,op1 = e1[2].info
            opPrec2,assoc2,dprec2,subsym2,op2 = e2[2].info
            childrenE1 = getChildren(oldE1, inProgress)
            if childE1:
                childrenE1.append(childE1)
            childrenE2 = getChildren(e2)

            if self.debug:
                print "Ambiguity: ", e1[2].LHS, "->", e1[2].RHS, ", ", e2[2].LHS, "->", e2[2].RHS
                print " from ", e2[0], " to ", e2[1]
                print " ", inp[e2[0]:e2[1]]
                print " (opPrec2, assoc2, dprec2, op2) = ", opPrec2,assoc2,dprec2,op2.RHS
                print "   children of old:", [(c[0], c[1], c[2].RHS, c[3]) if len(c) == 4 else c for c in childrenE2]
                print " (opPrec1, assoc1, dprec1, op1) = ", opPrec1,assoc1,dprec1,op1.RHS
                print "   children of new:", [(c[0], c[1], c[2].RHS, c[3]) if len(c) == 4 else c for c in childrenE1]

            if childrenE1 == childrenE2:
                return (OLD, False, True)    # same children => same edge. no ambiguity here, doc
            elif opPrec1 != None and opPrec2 != None:
                if opPrec1 == opPrec2:              # time for the associativity check OF DOOM
                    if assoc1[0] == 'left' and assoc2[0] == 'left':     # think (l + m + n)
                        # the one with the longer left side
                        if childrenE1[0][1] > childrenE2[0][1]:
                            return (NEW, False, True)
                        elif childrenE1[0][1] < childrenE2[0][1]:
                            return (OLD, False, True)
                        else:
                            return (NEW, True, False)    # the stupid case in which two production cover the *same string*
                    elif assoc1[0] == 'right' and assoc2[0] == 'right': # think (y = x = 1)
                        # the one with the longer right side
                        if childrenE1[-1][0] < childrenE2[-1][0]:
                            return (NEW, False, True)
                        elif childrenE1[-1][0] > childrenE2[-1][0]:
                            return (OLD, False, True)
                        else:
                            return (NEW, True, False)    # the stupid case in which two production cover the *same string*
                    else:       # think (n + ++m or y = 1 + x)
                        # this can NEVER HAPPEN unless the grammar is STUPID and doesn't opPrec things
                        return (OLD, True, False)     # so it's ambiguous, yo
                else:
                    return (NEW, True, True) if opPrec1 < opPrec2 else (OLD, True, True)
            elif dprec1 != None and dprec2 != None:     # explicit override
                if dprec1 != dprec2:            # manual precedence override
                    return (NEW, True, True) if dprec1 > dprec2 else (OLD, True, True)
                else:
                    return (OLD, True, False)    # same dprec; ambiguous
            else:
                return (OLD, True, False)        # FAILURE TO DISAMBIGUATE

        def makeTree(e,i=1):
            n = i
            children = [x for x in getChildren(e) if x]
            lhs = e[2].LHS.replace('"','\\"')
            gviz.write(str(n)+ '[label = "%s"];\n' % (lhs)) #add a node for the current
            if len(children) == 1 and len(children[0])==2: #a terminal
                gviz.write(str(n)+' [label = "%s"];\n' % (lhs))
                gviz.write(str(i+1)+' [label = "%s",shape = plaintext];\n' % (children[0][1].replace('"','\\"')))
                gviz.write('    %s -> %s [label = "%s",width=2];\n' % (str(n), str(i+1), lhs+'->'+str(children[0][1].replace('"','\\"'))))
                return i+1

            elif len(children) == 0:#an epsilon
                gviz.write(str(n)+' [label = "%s"];\n' % (lhs))
                gviz.write(str(i+1)+' [label = "%s",shape = plaintext];\n' % ("epsilon"))
                gviz.write('    %s -> %s [label = "%s",width=2];\n' % (str(n), str(i+1), "_"))
                return i+1
            op = 0
            for child in children:
                if len(child) == 4:
                    gviz.write(str(i+1) + '[label = "%s"];\n' % child[2].LHS.replace('"','\\"'))
                    gviz.write('    %s -> %s [label = "%s",width=2];\n' % (str(n), str(i+1), lhs+'->'+child[2].LHS.replace('"','\\"')))
                    i = makeTree(child,i+1)

                elif len(child) == 2:
                    #operator, don't recurse
                    gviz.write("op"+str(op)+str(n) + ' [label = "%s", shape = plaintext ]' % (child[1].replace('"','\\"')))
                    gviz.write('    %s -> %s [label = "%s",width=2];\n' % (str(n), "op"+str(op)+str(n), ""))
                    op += 1
            return i+1

        def doSDT(edge):
            children = [x for x in getChildren(edge) if x]
            if len(children) == 1 and len(children[0])==2: #terminal
                term = children[0]
                return [saObject(None,[],term[1])]

            elif len(children) == 0:#epsilon
                return [saObject(None,[],None)]

            else:
                toReturn = []
                for child in children:
                    if len(child) == 4: #nonterm
                        toReturn.append(saObject(child[2].actions[-1], doSDT(child)))
                    elif len(child) == 2: #operator
                        toReturn.append(saObject(None,None,child[1]))
                return toReturn

        ######################
        ### FUNCTION START ###
        ######################

        if self.drawGraph: #init
            gviz = null
            for i in xrange(100):   # avoid clobbering existing graphs
                if not os.path.isfile('graph-' + str(i) + '.dot'):
                    gviz = open('graph-' + str(i) + '.dot', 'w')
                    gviz.write('digraph G {\nrankdir="TB";')
                    break
            if gviz is null:
                print "Too many graphs; delete some, try again."
                print "No more graphs will be drawn for this run."
                self.drawGraph = False

        # put this here for the initial next() call required by Python coroutines
        line = (yield "Prepped for parse-off, cap'n!")
        inp = line

        # Add edge (0,0,(S -> . alpha)) to worklist, for all S -> alpha
        for P in self.grammar[self.grammar.startSymbol].productions:
            addEdge((0,0,P,0))

        # for all tokens on the input:
        j = 0

        # keep going until we get a full completion edge
        done = False
        while not done:
            while j <= len(inp):

                # skip in first iteration; we need to complete and predict the
                # start nonterminal S before we start advancing over the input
                if j > 0:
                    # ADVANCE across the next token:
                    # for each edge (i,j-1,N -> alpha . inp[j] beta)
                    #     add edge (i,j,N -> alpha inp[j] . beta)
                    if self.debug:
                        print "*ADVANCE*"
                    for (i,_j,P,pos) in edgesIncomingTo(j-1,inProgress)[0]:
                        assert _j==j-1
                        if pos < len(P.RHS) and P.RHS[pos]==inp[j-1][0]:
                            addEdge((i,j,P,pos+1), (i,_j,P,pos), inp[_j])

                # Repeat COMPLETE and PREDICT until no more edges can be added
                edgeWasInserted = True
                while edgeWasInserted:
                    edgeWasInserted = False
                    # COMPLETE productions
                    # for each edge (i,j,N -> alpha .)
                    #    for each edge (k,i,M -> beta . N gamma)
                    #        add edge (k,j,M -> beta N . gamma)
                    if self.debug:
                        print "*COMPLETE*"
                    for (i,_j,P,pos) in edgesIncomingTo(j,complete)[0]:
                        assert _j==j and pos == len(P.RHS)
                        for (k,_i,Q,pos2) in edgesIncomingTo(i,inProgress)[0]:
                            assert _i==i and pos2 < len(Q.RHS)
                            if Q.RHS[pos2]==P.LHS:
                                edgeWasInserted = addEdge((k,j,Q,pos2+1), (k,i,Q,pos2), (i,j,P,pos)) or edgeWasInserted

                    # PREDICT what the parser is to see on input (move dots in edges that are in progress)
                    # for each edge (i,j,N -> alpha . M beta)
                    #     for each production M -> gamma
                    #          add edge (j,j,M -> . gamma)
                    if self.debug:
                        print "*PREDICT*"
                    for (i,_j,P,pos) in edgesIncomingTo(j,inProgress)[0]:
                        assert _j==j and pos < len(P.RHS)
                        if P.RHS[pos][0] not in ('*','@'):  # non-terminals start with special chars
                            M = P.RHS[pos]
                            # prediction: for all rules D->alpha add edge (j,j,.alpha)
                            for P in self.grammar[M].productions:
                                edgeWasInserted = addEdge((j,j,P,0)) or edgeWasInserted

                # remember to advance in the input
                j = j + 1

            # input has been parsed OK if and only if an edge (0,n,S -> alpha .) exists
            for P in self.grammar[self.grammar.startSymbol].productions:
                if (0,len(inp),P,len(P.RHS)) in edgesIncomingTo(len(inp),complete)[1]:

                    if self.drawGraph:
                        makeTree((0,len(inp),P,len(P.RHS)))
                        gviz.write('}')
                        gviz.close()

                    SDTree = saObject( P.actions[-1], doSDT( (0, len(inp), P, len(P.RHS))) )
                    try:
                        v = SDTree.act().val
                    except Exception, e:
                        if self.debug:
                            print e.message
                        util.error("My code is a snake, your python is invalid.")
                    done = True         # no need to continue iterating
                    yield v             # return the AST of this line, then quit

            # if we're not done yet, check to see if we can still continue
            if len(edgesIncomingTo(len(inp), inProgress)[0]) > 0:
                line = (yield None)                 # if we can, wait for more input
                inp = inp + line                    # and stick it on the end
            else:                                   # if there's no chance of going on, we're stuck.
                for i in xrange(0,len(inp)+1):      # so search for the error position and report it.
                    if len(edgesIncomingTo(i, inProgress)[0]) == 0:
                        raise SyntaxError('Bad syntax at token %d: %s' % (i-1,inp[i-1][1]))
                raise SyntaxError('Bad syntax at token %d: %s' % (j,inp[j][1]))

    def tokenize (self, inp):
        '''Return the tokenized version of INP, a sequence of
        (token, lexeme) pairs.
        '''
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
                raise Exception, str(pos) + ": " + str(inp[max(pos-5,0):min(pos+5,len(inp))])

            pos = matchEnd

        return tokens


    def dump (self, f=sys.stdout):
        self.grammar.dump()

        for regex, lhs in self.terminals:
            if lhs is None:  lhs = '(ignore)'
            print lhs, '->', regex.pattern


    ##---  STATIC  ------------------------------------------------------------

    TERM_PFX = '*'     # prefix of nonterminals replacing terminals
    NONTERM_PFX = '@'  # prefix of nonterminals replacing RHSs with > 2 symbols

    @staticmethod
    def preprocess (gram):
        '''Returns the tuple:

        (
          [ (regex, lhs) ],             # pattern/token list
        )

        WARNING: modifies GRAM argument.
        '''

        REGEX = re.compile ('')

        terminals = []
        renamedTerminals = {}
        epsilons = []

        # Import all the grammar's modules into a new global object
        try:
            glob = util.doImports (gram.imports)
        except Exception, e:
            util.error ('problem importing %s: %s' % (gram.imports, str(e)))
            sys.exit(1)

        # Add 'ignore' patterns to the terminals list
        for regex in gram.ignores:
            terminals.append ((regex, None))

        # Add 'optional' patterns to the terminals list
        for sym, regex in gram.optionals:
            terminals.append ((regex, sym))

        # Build a lookup table for operator associavitiy/precedences
        operators = {}
        for op, prec, assoc in gram.getAssocDecls ():
            operators [op.pattern] = (prec, assoc)

        # First pass -- pull out epsilon productions, add terminal rules
        # and take care of semantic actions
        ruleNum = 0                     # newly-created rules
        for rule in gram.rules:
            lhs = rule.lhs
            for production in rule.productions:
                actions = production.actions
                rhs = list(production.RHS)

                # Create the S-action, if specified
                if actions[len (rhs)]:
                    actions[len (rhs)] = EarleyParser.makeSemantFunc (
                        actions[len (rhs)], len (rhs), glob)
                else:
                    actions[len (rhs)] = EarleyParser.makeSemantFunc (
                        "return n1.val", len (rhs), glob)
                # Pull out epsilons and terminals
                for i, sym in enumerate (rhs):
                    if sym == grammar.Grammar.EPSILON:
                        # Epsilon
                        # 
                        # CYK: info = (None, None, None, production)
                        # CYK: epsilons.append ((lhs, info))
                        assert len (rhs) == 1
                        rhs = [] # in Earley, we model empsilon as an empty rhs
                        production.RHS = []

                    elif type (sym) == type (REGEX):
                        # Terminal symbol
                        if sym.pattern in renamedTerminals:
                            # Terminal was already factored out
                            termSym = renamedTerminals[sym.pattern]
                        else:
                            # Add *N -> sym rule, replace old symbol
                            termSym = '%s%d'% (EarleyParser.TERM_PFX, ruleNum)
                            ruleNum += 1
                            renamedTerminals[sym.pattern] = termSym
                            terminals.append ((sym, termSym))

                        if sym.pattern in operators:
                            # This pattern has a global assoc/prec declaration
                            # (which might be overridden later)
                            prec, assoc = operators[sym.pattern]
                            production.opPrec = prec
                            production.opAssoc = assoc
                        rhs[i] = termSym

                    if actions[i]:
                        # I-action for this symbol
                        actions[i] = EarleyParser.makeSemantFunc (
                            actions[i], len (rhs), glob)

                production.RHS = tuple(rhs)

        # Second pass -- build the symbol mapping and collect parsing info
        ruleNum = 0
        for rule in gram.rules:
            for production in rule.productions:
                lhs = rule.lhs
                rhs = production.RHS

                if len (rhs) == 1 and rhs[0] == grammar.Grammar.EPSILON:
                    # Epsilon production, skip it
                    continue

                # Collect precedence/associativity info
                if production.assoc != None:
                    # This production had a %prec declaration
                    opPrec, assoc = operators[production.assoc.pattern]
                elif production.opPrec != None:
                    # This production had a terminal symbol with an assoc/prec
                    # declaration
                    opPrec = production.opPrec
                    assoc = production.opAssoc
                else:
                    # No declarations ==> undefined prec, assoc
                    opPrec, assoc = None, None

                # Collect dprec info
                if production.prec != -1:
                    # Production had a %dprec declaration
                    dprec = production.prec
                else:
                    # No declaration ==> undefined dprec
                    dprec = None

                if production.subsym != None:
                    # Production had a %subparse declaration
                    subsym = production.subsym
                else:
                    # No subparsing for this production
                    subsym = None


                # Information about this production to be used during parsing
                production.info = (opPrec, assoc, dprec, subsym, production)

        return terminals, dict([(new,orig) for (orig,new) in renamedTerminals.iteritems()])


    @staticmethod
    def makeSemantFunc (code, numArgs, globalObject):
        args = ['n0']
        for i in xrange (numArgs):
            args.append ('n%d'% (i+1))
        try:
            return util.createFunction (util.uniqueIdentifier (),
                                        args, code, globalObject)
        except Exception, e:
            util.error ("""couldn't create semantic function: """ + str(e))
            sys.exit(1)

    @staticmethod
    def __isTermSymbol (sym):
        '''Return TRUE iff SYM is a 'virtual' nonterminal for a
        terminal symbol, created during grammar normalization.
        '''
        return sym[0] == EarleyParser.TERM_PFX


    @staticmethod
    def dumpEdges (edges):
        '''Print a representation of the edge set EDGES to stdout.'''
        for sym, frm, to in edges:
            print '(%d)--%s--(%d)'% (frm, sym, to)


    @staticmethod
    def dumpTree (tree, edges, level=0):
        '''Print a representation of the parse tree TREE to stdout.'''
        sym, frm, to = tree[0:3]
        if len (tree) > 3:
            children = tree[3]
        else:
            children = edges[(sym, frm, to)][3]
        if (isinstance (children, types.StringType) or
            children is grammar.Grammar.EPSILON):
            print '%s%s "%s")'% ('-'*level*2, sym, children)
        else:
            print '%s%s %d-%d'% ('-'*level*2, sym, frm, to)
            for child in children:
                EarleyParser.dumpTree (child, edges, level + 1)

# For instrumentation 
def incr(id):
    pass

if __name__ == '__main__':
    pass
