##
 # @file util.py
 #
 # $Id: util.py,v 1.2 2007/04/02 20:46:57 cgjones Exp $
import sys

class Ambiguous(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def doImports (moduleNames):
    '''Imports the modules named in the sequence MODULES into a new global
    object (dictionary).
    Returns the new global object.
    '''
    glob = {}
    for module in moduleNames:
        exec ('import %s'% (module), glob)
    return glob


def createFunction (name, args, code, env):
    '''Create and return the function NAME.
    NAME, ARGS, and CODE represent the function signature and body.  ENV
    is the environment in which to define the function NAME.

    The function will be created as:
      def NAME (arg0, arg1, ...): CODE
    '''
    strArgs = ','.join (args)
    exec ('def %s(%s):%s'% (name, strArgs, code), env)
    return env[name]


_nextNum = 0
def uniqueIdentifier ():
    '''Return an identifier that has never before been returned by
    uniqueIdentifier ().
    '''
    global _nextNum
    _nextNum += 1
    return 'f%d'%(_nextNum)


def error (message):
    '''Print MESSAGE to stderr and raise SyntaxError'''
    print >>sys.stderr, message
    raise SyntaxError('Error')
