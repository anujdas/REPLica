#!/usr/bin/env python

import sys, re
import getopt, parser_generator, grammar_parser, interpreter

# quick macro for loading in a file, based on the line-by-line parser model.
# TODO: change this to fast-fail; if a file has an error, we want to know immediately
# and parsing the rest of the file is a waste.
# I'll change this after the current version is merged into the REPL.
def loadProgram(p_file):
    # initialize an EarleyParser object with the appropriate grammar
    cs164_grammar_file = './cs164b.grm'
    cs164parser = parser_generator.makeParser(grammar_parser.parse(open(cs164_grammar_file).read()))

    # grab the token for a newline so we know how to pad our lines
    newline = cs164parser.tokenize("\n")

    # load in the program file
    prog = re.findall('[^\r\n;]+', re.sub("#.*\r?\n", "", open(p_file).read()))

    # initialize a parser instance, i.e., a coroutine, and prep it
    parser = cs164parser.parse()
    parser.next()

    # no newline insert before the first line of a statement
    first_line = True
    for l in prog:
        try:
            tokens = cs164parser.tokenize(l)
            if tokens:                              # no need to consume non-code lines
                if not first_line:                  # separate lines w/ newline characters
                    tokens = newline + tokens
                input_ast = parser.send(tokens)     # parse this line
                first_line = False
                if type(input_ast) == tuple:        # parsing completed on this line; execute result
                    interpreter.ExecGlobalStmt(input_ast)

                    # create and prep a new parser instance
                    parser = cs164parser.parse()
                    parser.next()
                    first_line = True

        # soft failure - if there's an error, print a helpful message and create a new parser
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
