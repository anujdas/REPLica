#!/usr/bin/env python

import sys
import getopt, parser_generator, grammar_parser, interpreter
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print "Please give one argument, the input filename."
        sys.exit(1)

    cs164_grammar_file = './cs164b.grm'
    cs164_input_file = sys.argv[1]
    cs164_library_file = './library.164'

    cs164parser = parser_generator.makeParser(grammar_parser.parse(open(cs164_grammar_file).read()))

    # Load library into the cs164interpreter
    library_ast = cs164parser.parse(open(cs164_library_file).read())
    interpreter.ExecGlobal(library_ast)

    # Load program into the cs164interpreter
    input_ast = cs164parser.parse(open(cs164_input_file).read())
    interpreter.ExecGlobal(input_ast)
