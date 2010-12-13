# Bytecode interpreter for lambdas and coroutines
#
# Motivation: stackful interpreter cannot implement coroutines

import sys, getopt, parser_generator, grammar_parser, repl

# global environment.  Persists across invocations of the ExecGlobal function 
globEnv = {'__up__':None}
cs164b_builtins = ["def", "error", "print", "if", "while", "for", "in", "null", "len", "lambda", "type", "native", "ite", "coroutine", "resume", "yield", "&&", "||", "<=", ">=", "==", "!="]
cs164parser = None

def ExecGlobal(ast):
    Resume(bytecode(desugar(ast))[1], globEnv)
def ExecGlobalStmt(ast,repl = None):
    Resume(bytecode(desugar([ast]))[1], globEnv, REPL=repl)

# get tab-completion results for a given string fragment
def complete(fragment, env=globEnv):
    lookups = map(lambda k: (k, env[k]), filter(lambda name: name.startswith(fragment), env))
    builtins = map(lambda k: (k, None), filter(lambda name: name.startswith(fragment), cs164b_builtins))
    return filter(lambda s: not s[0].startswith('__'), lookups + builtins)

# same as above, except for dictionary/object lookups
# go by Lua standard: __mt/__index for lookups
def completeObj(fragment, obj):

    # recursively collect all attributes belonging to this function and its parent classes
    def lookupObjectAttrs(obj):
        attrs = complete(fragment, env=obj)
        if '__mt' in obj:
            attrs = attrs + lookupObjectAttrs(obj['__mt'])
        elif '__index' in obj:
            attrs = attrs + lookupObjectAttrs(obj['__index'])
        return attrs

    return lookupObjectAttrs(obj)

# same as above, again, but for function argument completions
# NOTE: this does not return a list of tuples, but instead a list of arguments. DO NOT SORT!
def completeFunArgs(fragment, fun, env=globEnv):
    argList = env[fun].fun.argList if (fun in env and isinstance(env[fun], FunVal)) else []
    return filter(lambda arg: arg.startswith(fragment), argList)

# check if the variable exists anywhere accessible from this environment
# if so, return its value, else None
def locateInEnv(var, env):
    if not env:
        return None
    elif var in env:
        return env[var]
    elif '__up__' in env:
        return locateInEnv(var, env['__up__'])
    elif '__mt' in env:
        if '__index' in env:
            return locateInEnv(var, env['__mt']) or locateInEnv(var, env['__index'])
        else:
            return locateInEnv(var, env['__mt'])
    else:
        return None


# Abstract syntax of bytecode:
#
# ('=', lhs, rhs)                 --  lhs = rhs
# ('ite', cond, then, else)       --  ite(cond, then, else)
# ('def', var, val)               --  def var = val
# (op, lhs, val1, val2)           --  lhs = val1 op val2  where op = {'+', '==', etc.}
# ('lambda', lhs, params, body)   --  lhs = lambda (params) {body}
# ('call', lhs, fun, args)        --  lhs = fun(args)
# ('coroutine', lhs, fun)         --  lhs = coroutine(fun)
# ('resume', lhs, co, arg)        --  lhs = resume(co, arg)
# ('yield', lhs,  arg)            --  lhs = yield(arg)
# ('print', var)                  --  print var
# ('string-lit', reg, "foo")      --  "foo"
# ('null', reg)                   --  null
# ('return', reg)                 --  ?
# The bytecode array stores instructions of the main scope; bytecode arrays
# for lambda bodies are nested bytecode arrays, stored in the call instruction

cnt = 0
def bytecode(e):
    def newTemp():
        global cnt
        cnt = cnt + 1
        return '$'+str(cnt)
    def bc(e,t):
        t1, t2, t3 = newTemp(), newTemp(), newTemp()
        if type(e) == type([]): # is a list of statements (body of function or outer level code)
            codeList = reduce(lambda code,s: code+bc(s,t), e, [])
            if len(codeList) == 0:
                codeList = [('null', t)]
            codeList.append(('return', t))
            return codeList

        if type(e) == type(()): # e is an expression or a statement
            # expressions
            if e[0] == 'int-lit'     or \
               e[0] == 'var':        return [('def', t, e[1])]
            if e[0] == 'dict-lit':   return [('dict', t)]
            if e[0] == 'string-lit': return [('string', t, e[1])]
            if e[0] == 'null':       return [('null', t)]
            if e[0] == '+' or \
               e[0] == '-' or \
               e[0] == '/' or \
               e[0] == '*' or \
               e[0] == '==' or \
               e[0] == '!=' or \
               e[0] == '<=' or \
               e[0] == '>=' or \
               e[0] == '<' or \
               e[0] == '>':         return bc(e[1],t1) + bc(e[2],t2) + [(e[0], t, t1, t2)]
            if e[0] == 'ite':       return bc(e[1],t1) + bc(e[2],t2) + bc(e[3],t3) + [(e[0], t, t1, t2, t3)]
            if e[0] == 'coroutine': return bc(e[1],t1) + [('coroutine', t, t1)]
            if e[0] == 'yield':     return bc(e[1],t1) + [('yield', t, t1)]
            if e[0] == 'resume':    return bc(e[1],t1) + bc(e[2],t2) + [('resume', t, t1, t2)]
            if e[0] == 'type':      return bc(e[1],t1) + [('type', t, t1)]
            if e[0] == 'len':       return bc(e[1],t1) + [('len', t, t1)]
            if e[0] == 'in':        return bc(e[1],t1) + bc(e[2],t2) + [('in', t, t1,t2)]
            if e[0] == 'put':       return bc(e[1],t) + bc(e[2],t1) + bc(e[3],t2) + [('put', t, t1, t2)]
            if e[0] == 'get':       return bc(e[1],t1) + bc(e[2], t2)+ [('get', t, t1, t2)]
            if e[0] == 'lambda':    return [('lambda', t, e[1], bc(e[2],t1))]
            if e[0] == 'native':
                if len(e[3]) > 0:
                    codeList = bc(e[3][0], t1)
                    codeList = codeList + [('native', t, e[1], e[2], t1)]
                    return codeList
                else:
                    return [('native', t, e[1], e[2], None)]
            if e[0] == 'call':
                if e[1] == ('var', 'type'):
                    if len(e[2]) != 1:      # since 'type' is a hack, we need to validate args
                        REPL.softError("Error")       # explicitly, rather than relying on the interpreter
                        sys.exit(-1)
                    else:
                        return bc(('type', e[2][0]), t)
                args = e[2]
                func = e[1]
                # Implement calls with more than zero argument.
                if len(args) > 0:
                    argRegisters = [newTemp() for arg in args]
                    codeList = bc(func, t1)
                    argDefs = [bc(args[i], argRegisters[i]) for i in range(len(args))]
                    for d in argDefs:
                        codeList.extend(d)
                    codeList = codeList + [('call', t, t1, argRegisters)]
                    return codeList
                return bc(func,t1) + [('call', t, t1, [])]

            # Statements
            if e[0] == 'exp':       return bc(e[1],t)
            if e[0] == 'asgn':      return bc(e[2],t) + [('=',e[1],t)] # '=' always write to user-defined vars
            if e[0] == 'def':       return bc(e[2],t) + [('def',e[1],t)]
            if e[0] == 'print':     return bc(e[1],t) + [('print', t)]
            if e[0] == 'error':     return bc(e[1],t) + [('error', t)]
        raise SyntaxError("Illegal AST node %s " % str(e))
    t = newTemp()
    return t,bc(e,t)

def print_bytecode(p,indent=0):
    for inst in p:
        if inst[0] != 'lambda': print " "*4*indent, inst
        else:
            print " "*4*indent, inst[0:3]
            print_bytecode(inst[3],indent+1)


# The interpreter   
class Fun:     # the function: (ret-var, arg list, body)
    def __init__(self, argList, body):
        self.argList = argList
        self.body = body

class FunVal:  # function value (a closure): (fun, env)
    def __init__(self, fun, env, coroutine=False):
        self.fun = fun
        self.env = env
        self.coroutine = coroutine
        self.corStack = ()      # (stmts, pc, lhsVar, env, callStack)
        self.corArg = None
    def __str__(self):
        return "function(" + (reduce(lambda x,y: x+", "+y, self.fun.argList) if self.fun.argList else "") + ")"
    def __repr__(self):
        return "function(" + (reduce(lambda x,y: x+", "+y, self.fun.argList) if self.fun.argList else "") + ")"

def Exec(stmts):
    """ Execute a sequence of statements at the outermost level"""
    return Resume(stmts)  # return the last statement's value 
def ExecFun(closure, args):
    """ Execute a function with arguments args."""
    env = dict(zip(closure.fun.argList,args))
    env['__up__'] = closure.env
    return Resume(closure.fun.body, env) # return the function's return value
def ExecFunByName(funName, args):
    """ Execute stmts and then call function with name 'funName'
        with arguments args.  The function definition must be among
        the statements. """
    env = globEnv
    return ExecFun(env[funName],args)
def ExecString(code, args):
    """ Execute code snippet with the given arguments """
    global cs164parser
    if not cs164parser:
        cs164grammarFile = './cs164b.grm'
        cs164parser = parser_generator.makeParser(grammar_parser.parse(open(cs164grammarFile).read()))
    env = args
    env['__up__'] = globEnv
    bc = bytecode(desugar(cs164parser.parse(code)))
    Resume(bc[1], env)

# This is the main function of the bytecode interpreter.
# Error handling is missing from the skeleton.
def Resume(stmts, env={'__up__': None}, pc=0, callStack=[], fun=None, REPL=None):
    """ Arguments represent the state of the coroutine (as well as of the main program)
        stmts: array of bytecodes, pc: index into stmts where the execution should (re)start
        callStack: the stack of calling context of calls pending in the coroutine
        env: the current environment. """

    def lookup(name):
        def _lookup(name, env):
            if env.has_key(name):
                return env[name]
            elif env["__up__"]:
                return _lookup(name, env["__up__"])
            else:
                REPL.softError("No such variable: " + name)
                raise NameError
        return _lookup(name, env)

    def lookupObject(obj, var):
        if var in obj:
            return obj[var]
        elif '__mt' not in obj or not obj['__mt']:
            REPL.softError("No such attribute %s in %s." % (var, obj))
            raise NameError
        else:
            return lookupObject(obj['__mt'], var)

    def update(name, val):
        def _update(name, env, val):
            if env.has_key(name):
                env[name] = val
            elif env["__up__"]:
                _update(name, env["__up__"], val)
            else:
                REPL.softError("Can't assign value to uninitialized variable: " + name)
                raise NameError
        _update(name, env, val)
    def define(name,val):
        env[name] = val
    def addScope(parentEnv):
        " create an empty scope and link it to parentEnv "
        return {'__up__': parentEnv}

    # This only gets executed if this is a coroutine
    if fun and fun.coroutine:
        stmts, pc, lhsVar, env, callStack = fun.corStack
        define(lhsVar, fun.corArg)

    if pc == -1:
        REPL.softError("Attempted to resume a terminated coroutine.")       # this is a coroutine that has ended
        return

    while True:

        e = stmts[pc]
        pc = pc + 1
        try:
            if   e[0] == '=':      update(e[1], lookup(e[2]))
            elif e[0] == 'dict':   define(e[1], {})  # we represent 164 dicts with Python dictionaries
            elif e[0] == 'string': define(e[1], e[2])  # we represent 164 strings with Python strings
            elif e[0] == 'def':    define(e[1], e[2] if type(e[2])==type(1) else lookup(e[2]))
            elif e[0] == 'print':
                if lookup(e[1]) != None:
                    REPL.printLine(str(lookup(e[1])))
                else:
                    REPL.printLine("null")
            elif e[0] == 'error':
                if lookup(e[1]) != None:
                    REPL.gracefulExit("Error: " + str(lookup(e[1])), -1)
                else:
                    REPL.gracefulExit("Error", -1)
            elif e[0] == '+':
                if type(lookup(e[2])) == type(lookup(e[3])) == type(0):
                    define(e[1], lookup(e[2]) + lookup(e[3]))
                else:
                    define(e[1], unicode(lookup(e[2])) + unicode(lookup(e[3])))
            elif e[0] == '-':      define(e[1], lookup(e[2]) - lookup(e[3]))
            elif e[0] == '*':      define(e[1], lookup(e[2]) * lookup(e[3]))
            elif e[0] == '/':
                if lookup(e[3]) != 0:
                    define(e[1], lookup(e[2]) / lookup(e[3]))
                else:
                    REPL.softError("Dividing by zero is a no-no")
                    return
            elif e[0] == '==':     define(e[1], 1 if (lookup(e[2]) == lookup(e[3])) else 0)
            elif e[0] == '!=':     define(e[1], 1 if (lookup(e[2]) != lookup(e[3])) else 0)
            elif e[0] == '<=':     define(e[1], 1 if (lookup(e[2]) <= lookup(e[3])) else 0)
            elif e[0] == '>=':     define(e[1], 1 if (lookup(e[2]) >= lookup(e[3])) else 0)
            elif e[0] == '<':      define(e[1], 1 if (lookup(e[2]) < lookup(e[3])) else 0)
            elif e[0] == '>':      define(e[1], 1 if (lookup(e[2]) > lookup(e[3])) else 0)
            elif e[0] == 'ite':    define(e[1], lookup(e[3]) if lookup(e[2]) else lookup(e[4]))
            elif e[0] == 'lambda': define(e[1], FunVal(Fun(e[2],e[3]),env) )
            elif e[0] == 'null':   define(e[1], None) # represent 164 null with Python's None 

            # table operations
            elif e[0] == 'len':
                l = lookup(e[2])
                length = 0
                for i in range(len(l)):
                    if l.has_key(i): length = i + 1
                    else: break
                define(e[1], length)
            elif e[0] == 'in':      define(e[1], 1 if (lookup(e[2]) in lookup(e[3])) else 0)
            elif e[0] == 'get':     define(e[1], lookupObject(lookup(e[2]), lookup(e[3])))
            elif e[0] == 'put':     lookup(e[1])[lookup(e[2])] = lookup(e[3])

            # not a real function
            elif e[0] == 'type':
                toType = e[2] if type(e[2])==type(1) else lookup(e[2])
                define(e[1], str(type(toType)).split("'")[1])

            # support native calls to the Python API
            elif e[0] == 'native':
                args = lookup(e[4]) if e[4] else None
                exec 'import ' + e[2] in locals()     # import the relevant library
                try:
                    ret = eval(e[2] + '.' + e[3])(**args) if args else eval(e[2] + '.' + e[3])()
                except Exception, e:
                    REPL.softError("Native call failed with error: \n    " + str(e))       # Native call failed; exit "gracefully" (aka DIE IN A FIRE)
                    return
                if type(ret) == type(()) or type(ret) == type([]):
                    ret = dict(zip(range(len(ret)), ret))
                define(e[1], ret)

            # calls and returns
            elif e[0] == 'call':

                lhsVar = e[1]
                # decompose the function value
                func    = lookup(e[2])

                if not isinstance(func, FunVal):
                    REPL.softError("Can't call that; not a function.")   # not a function :(
                    return

                fbody   = func.fun.body
                fenv    = func.env

                # look up arguments in the current environment frame; save them for later
                if len(e[3]) != len(func.fun.argList):
                    REPL.softError("Expected %d args, got %d." % (len(func.fun.argList), len(e[3])))   # wrong number of args
                    return

                argList = []
                for i in range(len(func.fun.argList)):
                    argList.append(lookup(e[3][i]))

                # push the calling context onto the call stack; we'll restore to it when the call returns
                callStack.append((stmts,pc,lhsVar,env))
                # prepare the enviroment for the callee function
                env = addScope(fenv)    # create a new scope; connect it to the scope to the env of the

                # copy saved arg values into the current frame
                for i in range(len(func.fun.argList)):
                    env[func.fun.argList[i]] = argList[i]

                # function, and make it the new env
                # jump to body of the callee 
                stmts = fbody  # each function has own list of statements (the body)
                pc = 0         # and its body starts at index 0

            elif e[0] == 'return':
                if len(callStack) == 0:
                    # the interpreter base routine has just terminated.
                    if fun:     # so set pc:impossible.
                        fun.corStack = (fun.corStack[0], -1) + fun.corStack[2:]
                    return lookup(e[1])
                # top of call stack stores the the caller's context that we need to restore
                ret = lookup(e[1])
                stmts,pc,lhsVar,cenv = callStack.pop()
                # restore the environment of the call
                env = cenv
                define(lhsVar, ret)

            elif e[0] == 'coroutine':

                funcdef = lookup(e[2])

                # error check - needs to be a function
                if not isinstance(funcdef, FunVal) or funcdef.coroutine:
                    REPL.softError("Can't wrap non-function %s in a coroutine" % e[2] )   # not a function :(
                    return

                # copy the env, so we don't clobber the lambda
                func = FunVal(funcdef.fun, addScope(funcdef.env), True)

                # (stmts, pc, lhsVar, env, callStack)
                func.corStack = (func.fun.body, 0, func.fun.argList[0], func.env, [])

                # In Soviet Russia, environment saves YOU!
                define(e[1], func)

            elif e[0] == 'resume':
                # The second argument to resume is the argument it passes to the coroutine.
                # You must ensure that you handle the case where you try to resume
                #  a coroutine that has already ended.

                co = lookup(e[2])

                # error check
                if not isinstance(co, FunVal) or not co.coroutine:
                    REPL.softError("Can't resume %s: not a coroutine." % e[2])     # not a coroutine :(
                    return

                # can't resume ourselves. double self, what does it mean?
                if co == fun:
                    REPL.softError("Can't resume ourselves...")         # SO INTENSE
                    return

                co.corArg = lookup(e[3])
                define(e[1], Resume(co.fun.body, co.env, fun=co))

            elif e[0] == 'yield':
                # The one parameter is an argument passed to whomever resumed the coroutine.

                # WE GET COROUTINE
                if fun and fun.coroutine:   # only a coroutine will ever have an #arg

                    # MOVE ALL STATE
                    fun.corStack = (stmts, pc, e[1], env, callStack)

                    # MOVE LHSVAR
                    # FOR GREAT RETURN
                    return lookup(e[2])
                else:
                    REPL.softError("Not in a coroutine, can't yield!")       # don't yield the main! DON'T YIELD THE MAIN!
                    return

            else: raise SyntaxError("Illegal instruction: %s " % str(e))
        except TypeError, e:
            print e
            REPL.softError("Type error: " + str(e))
            return
        except NameError:
            return
    return NeverReached

def desugar(ast):

    def desugarIf(e):
        thenclause = ('lambda', [], [('exp', ('lambda', [], e[2]))])
        elseclause = ('lambda', [], [('exp', ('lambda', [], e[3] if e[3] else [('exp', ('null',))]))])      # allow for missing else case
        return desugar(('call', ('call', ('ite', e[1], thenclause, elseclause), []), []))

    def desugarWhile(e):
        return desugar(('call', ('lambda', [], [('def', '#while', ('lambda', [], [('if', e[1], [('exp', ('call', ('lambda', [], e[2]), [])), ('exp', ('call', ('var', '#while'), []))], None)])), ('exp', ('call', ('var', '#while'), []))]), []))

    def desugarFor(e):
        return desugar(
            ('if',
                ('==', ('call', ('var', 'type'), [e[2]]), ('string-lit', 'dict')),
                [
                    ('def', '#listIter',
                        ('lambda', ['#lst'],
                            [
                                ('def', '#n', ('int-lit', 0)),
                                ('exp',
                                    ('lambda', [],
                                        [
                                            ('if',
                                                ('in', ('var', '#n'), ('var', '#lst')),
                                                [
                                                    ('asgn', '#n', ('+', ('var', '#n'), ('int-lit', 1))),
                                                    ('exp',
                                                        ('get', ('var', '#lst'), ('-', ('var', '#n'), ('int-lit', 1)))
                                                    )
                                                ],
                                                [
                                                    ('exp', ('null',))
                                                ]
                                            )
                                        ]
                                    )
                                )
                            ]
                        )
                    ),
                    ('def', '#iter', ('call', ('var', '#listIter'), [e[2]])),
                    ('def', '#temp', ('call', ('var', '#iter'), [])),
                    ('while',
                        ('!=', ('var', '#temp'), ('null',)),
                        [
                            ('exp', ('call', ('lambda', [e[1]], e[3]), [('var', '#temp')])),
                            ('asgn', '#temp', ('call', ('var', '#iter'), []))
                        ]
                    )
                ],
                [
                    ('def', '#iter', e[2]),
                    ('def', '#temp', ('call', ('var', '#iter'), [])),
                    ('while',
                        ('!=', ('var', '#temp'), ('null',)),
                        [
                            ('exp', ('call', ('lambda', [e[1]], e[3]), [('var', '#temp')])),
                            ('asgn', '#temp', ('call', ('var', '#iter'), []))
                        ]
                    )
                ]
            )
        )

    def desugarAnd(e):
        trueCase = [('exp', ('int-lit', 1))]
        falseCase = [('exp', ('int-lit', 0))]
        return desugar(('call', ('lambda', [], [('if', e[1], [('if', e[2], trueCase, falseCase)], falseCase)]), []))

    def desugarOr(e):
        trueCase = [('exp', ('int-lit', 1))]
        falseCase = [('exp', ('int-lit', 0))]
        return desugar(('call', ('lambda', [], [('if', e[1], trueCase, [('if', e[2], trueCase, falseCase)])]), []))

    def desugarDict(e):
        if e[1] == []:
            return e
        else:
            assgns = [('put', ('var', '#tbl'), ('string-lit', var), val) for var, val in e[1]]
            return  desugar(('call', ('lambda', [], [('def', '#tbl', ('dict-lit', []))] + assgns + [('exp', ('var', '#tbl'))]), []))

    def desugarComp(e):
        expr = e[1]
        var = e[2]
        src = e[3]
        return desugar(
            ('call',
                    ('lambda', [],
                        [
                            ('def', '#tL', ('dict-lit', [])),
                            ('def', '#a', ('int-lit', 0)),
                            ('if',
                                ('==', ('call', ('var', 'type'), [src]), ('string-lit', 'dict')),
                                [
                                    ('for', '#b', src,
                                        [
                                            ('put',
                                                ('var', '#tL'),
                                                ('var', '#a'),
                                                ('call',
                                                    ('lambda',
                                                        [var],
                                                        [('exp', expr)]
                                                    ),
                                                    [('get', src, ('var', '#a'))]
                                                )
                                            ),
                                            ('asgn', '#a',
                                                ('+',
                                                    ('var', '#a'),
                                                    ('int-lit', 1)
                                                )
                                            )
                                        ]
                                    ),
                                    ('exp', ('var', '#tL'))
                                ],
                                [
                                    ('for', '#b', src,
                                        [
                                            ('put',
                                                ('var', '#tL'),
                                                ('var', '#a'),
                                                ('call',
                                                    ('lambda',
                                                        [var],
                                                        [('exp', expr)]
                                                    ),
                                                    [('var', '#b')]
                                                )
                                            ),
                                            ('asgn', '#a',
                                                ('+',
                                                    ('var', '#a'),
                                                    ('int-lit', 1)
                                                )
                                            )
                                        ]
                                    ),
                                    ('exp', ('var', '#tL'))
                                ]
                            )
                        ]
                    ),
                    []
                )
            )

    def desugarObjCall(e):
        obj = e[1]
        func = e[2]
        args = e[3]
        return desugar(
            ('exp',
                ('call',
                    ('lambda',
                        [],
                        [
                            ('def', '#self', obj),
                            ('exp',
                                ('call',
                                    ('get', ('var', '#self'), ('string-lit', func)),
                                    [('var', '#self')] + args
                                )
                            )
                        ]
                    ),
                    []
                )
            )
        )

    if type(ast) == type(()):
        if   ast[0] == 'if':        return desugarIf(ast)
        elif ast[0] == 'while':     return desugarWhile(ast)
        elif ast[0] == 'for':       return desugarFor(ast)
        elif ast[0] == '||':        return desugarOr(ast)
        elif ast[0] == '&&':        return desugarAnd(ast)
        elif ast[0] == 'dict-lit':  return desugarDict(ast)
        elif ast[0] == 'comprehension':  return desugarComp(ast)
        elif ast[0] == 'objcall':   return desugarObjCall(ast)
        else:                       return tuple(map(desugar, ast))
    elif type(ast) == type([]):
        return map(desugar, ast)
    else:
        return ast

# This is the interpreter entry point.
def run(ast):
    #print "AST:"
    #print ast
    sast = desugar(ast)
    #print "SAST:"
    #print sast
    bc = bytecode(sast)[1]
    #print "Bytecode:"
    #print_bytecode(bc)
    Exec(bc)
