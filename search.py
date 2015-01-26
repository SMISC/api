class AndToken:
    def __repr__(self):
        return '+'

class OrToken:
    def __repr__(self):
        return ' '

class OpeningParenthesesToken:
    def __repr__(self):
        return '('

class ClosingParenthesesToken:
    def __repr__(self):
        return ')'

class HashtagToken:
    def __repr__(self):
        return '#'

class MentionToken:
    def __repr__(self):
        return '@'

class ColonToken:
    def __repr__(self):
        return ':'

class StringCharacterToken:
    def __init__(self, value):
        self.value = value

    def __repr(self):
        return self.value

class StringToken:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return self.value

class AndConnexive:
    def __init__(self, left, right):
        self.left = left
        self.right = right
    def __repr__(self):
        return str(self.left) + '+' + str(self.right)

class OrConnexive:
    def __init__(self, left, right):
        self.left = left
        self.right = right
    def __repr__(self):
        return str(self.left) + ' ' + str(self.right)

class EOFError(Exception):
    pass

class Search:
    def __init__(self, data):
        self.position = 0
        self.data = data

    def expect(self, tokens, token_type):
        try:
            token = tokens.pop(0)
            if isinstance(token, token_type):
                return token
            else:
                raise SyntaxError("Unexpected %s. Expecting %s" % (token, str(token_type)))
        except IndexError:
            raise SyntaxError("Unexpected end of string. Expecting %s" % (str(token_type)))

    def advance(self):
        self.position += 1

        if len(self.data) == self.position:
            self.position = 0
            raise EOFError()

    def parse(self, tokens_unmerged):
        tokens = []

        for i in tokens_unmerged:
            if isinstance(tokens_unmerged[i], StringCharacterToken):
                string = ""
                for j in range(i, len(tokens_unmerged)):
                    string += str(tokens_unmerged[j])
                tokens.append(StringToken(string))
                i = j
                continue

        for i in range(tokens):
            token = tokens[i]

            if isinstance(token, ColonToken):
                #operand = self.Expect
                pass

    def lex(self):
        if len(self.data) == 0:
            return []

        tokens = []

        try:
            while True:
                token = self.get_token()
                tokens.append(token)
                self.advance()
        except EOFError:
            pass

        return tokens
            
    def get_token():
        char = self.data[self.position]

        if char == ':':
            return ColonToken()
        elif char == '@':
            return MentionToken()
        elif char == '#':
            return HashtagToken()
        elif char == '(':
            return OpeningParenthesesToken()
        elif char == ')':
            return ClosingParenthesesToken()
        elif char == ' ':
            return OrToken()
        elif char == '+':
            return AndToken()
        else:
            return StringCharacterToken(char)

    def apply_filter(tweet_query):
        tokens = []
