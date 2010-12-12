#!/usr/bin/env python

import sys, re
import getopt, parser_generator, grammar_parser, interpreter

def loadProgram(p_file):
    cs164_grammar_file = './cs164b.grm'
    cs164parser = parser_generator.makeParser(grammar_parser.parse(open(cs164_grammar_file).read()))
    newline = cs164parser.tokenize("\n")
    prog = re.findall('[^\r\n;]+', re.sub("#.*\r?\n", "", open(p_file).read()))
    parser = cs164parser.parse()
    parser.next()
    first_line = True
    for l in prog:
        try:
            tokens = cs164parser.tokenize(l)
            if tokens:
                if not first_line:
                    tokens = newline + tokens
                input_ast = parser.send(tokens)
                first_line = False
                if type(input_ast) == tuple:
                    interpreter.ExecGlobalStmt(input_ast)
                    parser = cs164parser.parse()
                    parser.next()
                    first_line = True
        except SyntaxError, e:
            print "Error while parsing line: " + l
            print e.msg
            parser = cs164parser.parse()
            parser.next()
            first_line = True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print "Please give one argument, the input filename."
        sys.exit(1)

    cs164_grammar_file = './cs164b.grm'
    cs164_input_file = sys.argv[1]
    cs164_library_file = './library.164'

    cs164parser = parser_generator.makeParser(grammar_parser.parse(open(cs164_grammar_file).read()))

    # Load library into the cs164interpreter
    loadProgram(cs164_library_file)

    # Load program into the cs164interpreter
    loadProgram(cs164_input_file)
